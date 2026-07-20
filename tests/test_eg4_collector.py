from __future__ import annotations

import contextlib
import hashlib
import io
import json
import socket
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from freshmanager.collector import METADATA_FIELDS, Collector, HttpResponse, load_place
from freshmanager.config import ConfigError, load_api_key, mask_secret
from freshmanager.offline import run as run_offline
from freshmanager.storage import FileStorage, StorageError


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data/reference/seoul_121_places.csv"
SAMPLE_PATH = ROOT / "data/samples/population_yeouido_sample.json"
FIXED_TIME = datetime(2026, 7, 20, 9, 10, 11, tzinfo=ZoneInfo("Asia/Seoul"))
FIXED_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")
DUMMY_KEY = "dummy-key-for-offline-test"
ENV_NAME = "SEOUL_OPEN" + "_API_KEY"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def env_line(value: str) -> str:
    return f"{ENV_NAME}={value}\n"


class FakeClient:
    def __init__(self, body: bytes | None = None, status_code: int = 200) -> None:
        self.body = SAMPLE_PATH.read_bytes() if body is None else body
        self.status_code = status_code
        self.calls: list[tuple[str, str, float]] = []

    def fetch_population(self, area_code: str, api_key: str, timeout_seconds: float) -> HttpResponse:
        self.calls.append((area_code, api_key, timeout_seconds))
        return HttpResponse(self.status_code, self.body)


class TimeoutClient:
    def fetch_population(self, area_code: str, api_key: str, timeout_seconds: float) -> HttpResponse:
        del area_code, api_key, timeout_seconds
        raise TimeoutError


class ErrorClient:
    def fetch_population(self, area_code: str, api_key: str, timeout_seconds: float) -> HttpResponse:
        del area_code, api_key, timeout_seconds
        raise OSError("offline HTTP failure")


class FailingRawStorage(FileStorage):
    def save_raw(self, area_code: str, requested_at: datetime, request_id: str, payload: bytes) -> Path:
        del area_code, requested_at, request_id, payload
        raise StorageError("storage_error")


class FailingMetadataStorage(FileStorage):
    def __init__(self, raw_root: Path, metadata_root: Path) -> None:
        super().__init__(raw_root, metadata_root)
        self.metadata_calls = 0

    def save_metadata(self, requested_at: datetime, request_id: str, metadata: dict[str, object]) -> Path:
        self.metadata_calls += 1
        del requested_at, request_id, metadata
        raise StorageError("storage_error")


class Eg4CollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="freshmanager-eg4-")
        self.root = Path(self.temporary.name)
        self.raw_root = self.root / "data/raw/population"
        self.metadata_root = self.root / "data/processed/collection_logs"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def storage(self) -> FileStorage:
        return FileStorage(self.raw_root, self.metadata_root)

    def collector(self, client: object, storage: FileStorage | None = None) -> Collector:
        return Collector(
            CSV_PATH,
            client,  # type: ignore[arg-type]
            storage or self.storage(),
            clock=lambda: FIXED_TIME,
            request_id_factory=lambda: FIXED_ID,
        )

    def assert_recorded_error(
        self,
        result: object,
        expected_status: str,
        *,
        raw_expected: bool,
    ) -> None:
        self.assertEqual(result.status, expected_status)  # type: ignore[attr-defined]
        self.assertEqual(tuple(result.metadata), METADATA_FIELDS)  # type: ignore[attr-defined]
        self.assertIsNotNone(result.metadata_path)  # type: ignore[attr-defined]
        stored = json.loads(result.metadata_path.read_text(encoding="utf-8"))  # type: ignore[attr-defined]
        self.assertEqual(stored, result.metadata)  # type: ignore[attr-defined]
        rendered = json.dumps(stored, ensure_ascii=False)
        self.assertNotIn(DUMMY_KEY, rendered)
        self.assertNotIn("http://", rendered)
        self.assertNotIn("https://", rendered)
        raw_value = stored["raw_file_path"]
        if raw_expected:
            self.assertTrue(Path(str(raw_value)).is_file())
        else:
            self.assertIsNone(raw_value)

    @staticmethod
    def changed_sample(mutator: object) -> bytes:
        document = json.loads(SAMPLE_PATH.read_text(encoding="utf-8-sig"))
        mutator(document)  # type: ignore[operator]
        return json.dumps(document, ensure_ascii=False).encode("utf-8")

    def test_normal_fake_response_succeeds(self) -> None:
        client = FakeClient()
        result = self.collector(client).collect(DUMMY_KEY)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][0], "POI072")
        self.assertIsNotNone(result.population)

    def test_normalized_population_has_h701_required_values(self) -> None:
        result = self.collector(FakeClient()).collect(DUMMY_KEY)
        population = result.population
        self.assertIsNotNone(population)
        self.assertEqual(population["area_code"], "POI072")  # type: ignore[index]
        self.assertEqual(population["area_name"], "여의도")  # type: ignore[index]
        self.assertTrue(population["population_reference_time"])  # type: ignore[index]
        self.assertLessEqual(population["population_min"], population["population_max"])  # type: ignore[index]
        self.assertTrue(population["forecast_available"])  # type: ignore[index]
        self.assertTrue(population["forecasts"])  # type: ignore[index]

    def test_official_csv_resolves_poi072(self) -> None:
        place = load_place(CSV_PATH)
        self.assertEqual((place.area_code, place.area_name), ("POI072", "여의도"))

    def test_unknown_area_code_fails_without_client_call(self) -> None:
        client = FakeClient()
        result = self.collector(client).collect(DUMMY_KEY, "POI999")
        self.assertEqual(result.status, "validation_error")
        self.assertEqual(client.calls, [])

    def test_missing_env_file_is_config_error(self) -> None:
        with self.assertRaises(ConfigError):
            load_api_key(self.root / "missing.env")

    def test_missing_or_empty_api_key_is_config_error(self) -> None:
        for contents in ("OTHER=value\n", env_line("   ")):
            env_path = self.root / "dummy.env"
            env_path.write_text(contents, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_api_key(env_path)

    def test_env_loader_ignores_comments_and_splits_first_equals(self) -> None:
        env_path = self.root / "dummy.env"
        env_path.write_text(f"# comment\n\n {ENV_NAME} = dummy=value \n", encoding="utf-8")
        self.assertEqual(load_api_key(env_path), "dummy=value")

    def test_empty_direct_key_stops_before_client(self) -> None:
        client = FakeClient()
        result = self.collector(client).collect("")
        self.assert_recorded_error(result, "config_error", raw_expected=False)
        self.assertIsNone(result.metadata["http_status"])
        self.assertEqual(client.calls, [])

    def test_cli_config_error_writes_safe_error_metadata(self) -> None:
        invalid_env = self.root / "must-not-be-reported.env"
        private_setting = "private-dummy-config-content"
        invalid_env.write_text(f"OTHER_SETTING={private_setting}\n", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = run_offline(
                [
                    "--env-file",
                    str(invalid_env),
                    "--csv",
                    str(CSV_PATH),
                    "--sample",
                    str(SAMPLE_PATH),
                    "--raw-root",
                    str(self.raw_root),
                    "--metadata-root",
                    str(self.metadata_root),
                ]
            )
        self.assertEqual(exit_code, 1)
        metadata_files = list(self.metadata_root.rglob("*.metadata.json"))
        self.assertEqual(len(metadata_files), 1)
        stored = json.loads(metadata_files[0].read_text(encoding="utf-8"))
        self.assertEqual(tuple(stored), METADATA_FIELDS)
        self.assertEqual(stored["collection_status"], "config_error")
        self.assertIsNone(stored["http_status"])
        self.assertIsNone(stored["raw_file_path"])
        rendered = stdout.getvalue() + json.dumps(stored, ensure_ascii=False)
        self.assertNotIn(str(invalid_env), rendered)
        self.assertNotIn(private_setting, rendered)
        self.assertNotIn(DUMMY_KEY, rendered)
        self.assertNotIn("http://", rendered)
        self.assertIn("request_id=", stdout.getvalue())

    def test_dummy_key_is_not_written_or_returned(self) -> None:
        result = self.collector(FakeClient()).collect(DUMMY_KEY)
        rendered = repr(result)
        self.assertNotIn(DUMMY_KEY, rendered)
        for path in self.root.rglob("*"):
            if path.is_file():
                self.assertNotIn(DUMMY_KEY.encode(), path.read_bytes())
        self.assertEqual(mask_secret(f"prefix/{DUMMY_KEY}/suffix", DUMMY_KEY), "prefix/********/suffix")

    def test_http_error_is_recorded_and_raw_body_is_preserved(self) -> None:
        body = b'{"RESULT":{"RESULT.CODE":"ERROR"}}'
        result = self.collector(FakeClient(body, 500)).collect(DUMMY_KEY)
        self.assert_recorded_error(result, "api_error", raw_expected=True)
        self.assertEqual(result.metadata["http_status"], 500)
        self.assertEqual(Path(str(result.metadata["raw_file_path"])).read_bytes(), body)

    def test_json_api_error_result_is_not_treated_as_success(self) -> None:
        body = self.changed_sample(
            lambda document: document["RESULT"].update(
                {"RESULT.CODE": "ERROR-001", "RESULT.MESSAGE": "오류 응답"}
            )
        )
        result = self.collector(FakeClient(body)).collect(DUMMY_KEY)
        self.assertEqual(result.status, "api_error")
        self.assertTrue(Path(str(result.metadata["raw_file_path"])).is_file())

    def test_xml_service_error_is_api_error_and_secret_stays_in_raw(self) -> None:
        secret_marker = "synthetic-xml-message-must-stay-in-raw"
        body = (
            b"<RESULT><CODE>synthetic-code</CODE><MESSAGE>"
            + secret_marker.encode("utf-8")
            + b"</MESSAGE></RESULT>"
        )
        client = FakeClient(body)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = self.collector(client).collect(DUMMY_KEY)

        self.assert_recorded_error(result, "api_error", raw_expected=True)
        self.assertEqual(result.metadata["http_status"], 200)
        self.assertEqual(tuple(result.metadata), METADATA_FIELDS)
        self.assertEqual(len(client.calls), 1)

        raw_path = Path(str(result.metadata["raw_file_path"]))
        self.assertEqual(raw_path.read_bytes(), body)
        self.assertIn(secret_marker.encode("utf-8"), raw_path.read_bytes())

        metadata_bytes = result.metadata_path.read_bytes()  # type: ignore[union-attr]
        rendered = stdout.getvalue() + repr(result)
        self.assertNotIn(secret_marker, rendered)
        self.assertNotIn(secret_marker.encode("utf-8"), metadata_bytes)

    def test_unrecognized_non_json_payloads_remain_parse_error(self) -> None:
        cases = {
            "wrong-root": b"<OTHER><CODE>x</CODE><MESSAGE>y</MESSAGE></OTHER>",
            "missing-code": b"<RESULT><MESSAGE>y</MESSAGE></RESULT>",
            "missing-message": b"<RESULT><CODE>x</CODE></RESULT>",
            "namespace": b'<RESULT xmlns="urn:test"><CODE>x</CODE><MESSAGE>y</MESSAGE></RESULT>',
            "html": b"<html><CODE>x</CODE><MESSAGE>y</MESSAGE></html>",
            "plain-text": b"service error",
            "unsupported-xml-encoding": (
                b'<?xml version="1.0" encoding="unknown-encoding"?>'
                b"<RESULT><CODE>x</CODE><MESSAGE>y</MESSAGE></RESULT>"
            ),
        }
        for label, body in cases.items():
            with self.subTest(label=label):
                client = FakeClient(body)
                storage = FileStorage(self.raw_root / label, self.metadata_root / label)
                result = self.collector(client, storage).collect(DUMMY_KEY)
                self.assert_recorded_error(result, "parse_error", raw_expected=True)
                self.assertEqual(result.metadata["http_status"], 200)
                self.assertEqual(Path(str(result.metadata["raw_file_path"])).read_bytes(), body)
                self.assertEqual(len(client.calls), 1)

    def test_timeout_is_recorded_without_raw_file(self) -> None:
        result = self.collector(TimeoutClient()).collect(DUMMY_KEY)
        self.assert_recorded_error(result, "timeout", raw_expected=False)
        self.assertIsNone(result.metadata["http_status"])
        self.assertIsNone(result.metadata["raw_file_path"])

    def test_client_oserror_is_api_error(self) -> None:
        result = self.collector(ErrorClient()).collect(DUMMY_KEY)
        self.assertEqual(result.status, "api_error")
        self.assertIsNone(result.metadata["raw_file_path"])

    def test_invalid_json_is_parse_error_and_raw_is_preserved(self) -> None:
        body = b'{"broken":'
        result = self.collector(FakeClient(body)).collect(DUMMY_KEY)
        self.assert_recorded_error(result, "parse_error", raw_expected=True)
        self.assertEqual(Path(str(result.metadata["raw_file_path"])).read_bytes(), body)

    def test_response_area_code_mismatch_is_validation_error(self) -> None:
        body = self.changed_sample(lambda document: document["SeoulRtd.citydata_ppltn"][0].update(AREA_CD="POI071"))
        result = self.collector(FakeClient(body)).collect(DUMMY_KEY)
        self.assert_recorded_error(result, "validation_error", raw_expected=True)
        self.assertEqual(Path(str(result.metadata["raw_file_path"])).read_bytes(), body)

    def test_missing_required_population_field_is_validation_error(self) -> None:
        body = self.changed_sample(lambda document: document["SeoulRtd.citydata_ppltn"][0].pop("AREA_PPLTN_MIN"))
        result = self.collector(FakeClient(body)).collect(DUMMY_KEY)
        self.assertEqual(result.status, "validation_error")

    def test_missing_forecast_structure_is_validation_error(self) -> None:
        body = self.changed_sample(lambda document: document["SeoulRtd.citydata_ppltn"][0].pop("FCST_PPLTN"))
        result = self.collector(FakeClient(body)).collect(DUMMY_KEY)
        self.assertEqual(result.status, "validation_error")

    def test_filename_contains_area_time_and_request_id(self) -> None:
        result = self.collector(FakeClient()).collect(DUMMY_KEY)
        raw_path = Path(str(result.metadata["raw_file_path"]))
        self.assertEqual(raw_path.name, f"POI072_20260720_091011_{FIXED_ID}.json")
        self.assertEqual(raw_path.parts[-4:-1], ("2026", "07", "20"))

    def test_filename_collision_does_not_overwrite_existing_raw(self) -> None:
        collector = self.collector(FakeClient())
        first = collector.collect(DUMMY_KEY)
        raw_path = Path(str(first.metadata["raw_file_path"]))
        before = file_hash(raw_path)
        second = collector.collect(DUMMY_KEY)
        self.assertEqual(second.status, "storage_error")
        self.assertEqual(file_hash(raw_path), before)
        self.assertEqual(list(self.raw_root.rglob("*.partial")), [])

    def test_raw_storage_failure_returns_storage_error(self) -> None:
        storage = FailingRawStorage(self.raw_root, self.metadata_root)
        result = self.collector(FakeClient(), storage).collect(DUMMY_KEY)
        self.assert_recorded_error(result, "storage_error", raw_expected=False)

    def test_interrupted_raw_write_removes_partial_file(self) -> None:
        storage = self.storage()
        with mock.patch("freshmanager.storage.os.fsync", side_effect=OSError("write interrupted")):
            with self.assertRaises(StorageError):
                storage.save_raw("POI072", FIXED_TIME, str(FIXED_ID), b"partial")
        self.assertEqual(list(self.raw_root.rglob("*.json")), [])
        self.assertEqual(list(self.raw_root.rglob("*.partial")), [])

    def test_cleanup_failure_never_exposes_partial_as_final_json(self) -> None:
        storage = self.storage()
        with mock.patch("freshmanager.storage.os.fsync", side_effect=OSError("write interrupted")):
            with mock.patch.object(Path, "unlink", side_effect=OSError("cleanup unavailable")):
                with self.assertRaises(StorageError):
                    storage.save_raw("POI072", FIXED_TIME, str(FIXED_ID), b"partial")
        self.assertEqual(list(self.raw_root.rglob("*.json")), [])
        partials = list(self.raw_root.rglob("*.partial"))
        self.assertEqual(len(partials), 1)
        self.assertFalse(partials[0].name.endswith(".json"))

    def test_metadata_storage_failure_keeps_raw_and_returns_storage_error(self) -> None:
        storage = FailingMetadataStorage(self.raw_root, self.metadata_root)
        result = self.collector(FakeClient(), storage).collect(DUMMY_KEY)
        self.assertEqual(result.status, "storage_error")
        self.assertTrue(Path(str(result.metadata["raw_file_path"])).is_file())
        self.assertIsNone(result.metadata_path)
        self.assertEqual(storage.metadata_calls, 1)
        self.assertEqual(list(self.metadata_root.rglob("*.json")), [])
        self.assertEqual(list(self.metadata_root.rglob("*.partial")), [])

    def test_metadata_storage_failure_cli_is_safe_and_nonzero(self) -> None:
        env_path = self.root / "dummy.env"
        env_path.write_text(env_line(DUMMY_KEY), encoding="utf-8")
        storage = FailingMetadataStorage(self.raw_root, self.metadata_root)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = run_offline(
                [
                    "--env-file",
                    str(env_path),
                    "--csv",
                    str(CSV_PATH),
                    "--sample",
                    str(SAMPLE_PATH),
                    "--raw-root",
                    str(self.raw_root),
                    "--metadata-root",
                    str(self.metadata_root),
                ],
                storage_factory=lambda raw_root, metadata_root: storage,
            )
        self.assertEqual(exit_code, 1)
        self.assertEqual(storage.metadata_calls, 1)
        self.assertIn("request_id=", stdout.getvalue())
        self.assertIn("collection_status=storage_error", stdout.getvalue())
        self.assertNotIn("metadata_path=", stdout.getvalue())
        self.assertNotIn(DUMMY_KEY, stdout.getvalue())
        self.assertNotIn("http://", stdout.getvalue())
        self.assertEqual(list(self.metadata_root.rglob("*.json")), [])
        self.assertEqual(list(self.metadata_root.rglob("*.partial")), [])

    def test_network_socket_is_never_called(self) -> None:
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")) as connection:
            result = self.collector(FakeClient()).collect(DUMMY_KEY)
        self.assertEqual(result.status, "success")
        connection.assert_not_called()

    def test_metadata_has_exact_approved_fields_and_links_raw(self) -> None:
        result = self.collector(FakeClient()).collect(DUMMY_KEY)
        self.assertEqual(tuple(result.metadata), METADATA_FIELDS)
        self.assertNotIn("raw_payload", result.metadata)
        self.assertNotIn("parser_version", result.metadata)
        self.assertEqual(result.metadata["area_code"], "POI072")
        metadata_document = json.loads(result.metadata_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
        self.assertEqual(metadata_document, result.metadata)
        self.assertTrue(Path(str(metadata_document["raw_file_path"])).is_file())

    def test_offline_command_uses_explicit_dummy_env_and_temp_outputs(self) -> None:
        env_path = self.root / "dummy.env"
        env_path.write_text(env_line(DUMMY_KEY), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            exit_code = run_offline(
                [
                    "--env-file",
                    str(env_path),
                    "--csv",
                    str(CSV_PATH),
                    "--sample",
                    str(SAMPLE_PATH),
                    "--raw-root",
                    str(self.raw_root),
                    "--metadata-root",
                    str(self.metadata_root),
                ]
            )
        self.assertEqual(exit_code, 0)
        self.assertIn("collection_status=success", stdout.getvalue())
        self.assertNotIn(DUMMY_KEY, stdout.getvalue())

    def test_official_inputs_are_unchanged(self) -> None:
        before = (file_hash(CSV_PATH), file_hash(SAMPLE_PATH))
        self.collector(FakeClient()).collect(DUMMY_KEY)
        after = (file_hash(CSV_PATH), file_hash(SAMPLE_PATH))
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
