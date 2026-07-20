from __future__ import annotations

import hashlib
import io
import json
import shutil
import socket
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Callable
from unittest import mock
from urllib.parse import unquote

from freshmanager import eg5
from freshmanager.collector import CURRENT_POPULATION_FIELDS, METADATA_FIELDS, load_place
from freshmanager.storage import FileStorage, StorageError


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data/reference/seoul_121_places.csv"
DUMMY_KEY = "dummy-eg5-key-for-tests"
ENV_NAME = "SEOUL_OPEN" + "_API_KEY"


def synthetic_population(area_code: str, area_name: str) -> bytes:
    current = {field: "1" for field in CURRENT_POPULATION_FIELDS}
    current.update(
        {
            "AREA_NM": area_name,
            "AREA_CD": area_code,
            "AREA_CONGEST_LVL": "보통",
            "AREA_CONGEST_MSG": "합성 테스트 응답",
            "AREA_PPLTN_MIN": "1000",
            "AREA_PPLTN_MAX": "1200",
            "PPLTN_TIME": "2026-07-21 10:00",
            "FCST_YN": "Y",
            "FCST_PPLTN": [
                {
                    "FCST_TIME": "2026-07-21 11:00",
                    "FCST_CONGEST_LVL": "보통",
                    "FCST_PPLTN_MIN": "1100",
                    "FCST_PPLTN_MAX": "1300",
                }
            ],
        }
    )
    document = {
        "SeoulRtd.citydata_ppltn": [current],
        "RESULT": {
            "RESULT.CODE": "INFO-000",
            "RESULT.MESSAGE": "정상 처리되었습니다",
        },
    }
    return json.dumps(document, ensure_ascii=False).encode("utf-8")


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.body) - self.offset
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    def close(self) -> None:
        return None


class FakeTransport:
    def __init__(
        self,
        failures: set[str] | None = None,
        *,
        failure_statuses: dict[str, str] | None = None,
        after_response: Callable[[str, int], None] | None = None,
    ) -> None:
        self.failures = failures or set()
        self.failure_statuses = failure_statuses or {}
        self.after_response = after_response
        self.calls: list[str] = []
        self.full_urls: list[str] = []

    def open(self, request: object, timeout_seconds: float) -> FakeResponse:
        del timeout_seconds
        selector = str(getattr(request, "selector", ""))
        area_code = unquote(selector.rsplit("/", 1)[-1])
        self.calls.append(area_code)
        self.full_urls.append(str(getattr(request, "full_url", "")))
        failure_status = self.failure_statuses.get(area_code)
        if area_code in self.failures or failure_status == "timeout":
            raise TimeoutError("synthetic timeout detail")
        if failure_status == "api_error":
            response = FakeResponse(b'{"synthetic":"api-error"}', status=500)
        elif failure_status == "parse_error":
            response = FakeResponse(b'{"SeoulRtd.citydata_ppltn": [')
        elif failure_status == "validation_error":
            response = FakeResponse(
                synthetic_population("POI999", eg5.EG5_AREA_NAMES[area_code])
            )
        else:
            response = FakeResponse(
                synthetic_population(area_code, eg5.EG5_AREA_NAMES[area_code])
            )
        if self.after_response is not None:
            self.after_response(area_code, len(self.calls))
        return response


class FaultInjectingProbeFile:
    def __init__(self, delegate: BinaryIO, failure_stage: str, detail: str) -> None:
        self.delegate = delegate
        self.failure_stage = failure_stage
        self.detail = detail

    def __enter__(self) -> FaultInjectingProbeFile:
        self.delegate.__enter__()
        return self

    def __exit__(self, *args: object) -> object:
        return self.delegate.__exit__(*args)  # type: ignore[arg-type]

    def write(self, payload: bytes) -> int:
        if self.failure_stage == "write":
            raise OSError(self.detail)
        return self.delegate.write(payload)

    def flush(self) -> None:
        if self.failure_stage == "flush":
            raise OSError(self.detail)
        self.delegate.flush()


class FailingMiddleRawStorage(FileStorage):
    def save_raw(
        self,
        area_code: str,
        requested_at: datetime,
        request_id: str,
        payload: bytes,
    ) -> Path:
        if area_code == "POI013":
            raise StorageError("private storage detail")
        return super().save_raw(
            area_code,
            requested_at,
            request_id,
            payload,
        )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_summary(output: str) -> dict[str, str]:
    lines = output.splitlines()
    start = lines.index("EG5_COLLECTION_SUMMARY") + 1
    return dict(line.split("=", 1) for line in lines[start:] if "=" in line)


class Eg5CliTests(unittest.TestCase):
    @staticmethod
    def write_env(root: Path, value: str = DUMMY_KEY) -> Path:
        path = root / "dummy.env"
        path.write_text(f"{ENV_NAME}={value}\n", encoding="utf-8")
        return path

    @staticmethod
    def invoke(argv: list[str], **kwargs: object) -> tuple[int, str]:
        output = io.StringIO()
        errors = io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = eg5.run(argv, **kwargs)  # type: ignore[arg-type]
        return code, output.getvalue() + errors.getvalue()

    def run_fake(
        self,
        root: Path,
        transport: FakeTransport,
        *,
        output_root: Path | None = None,
        official_csv_path: Path | None = None,
    ) -> tuple[int, str, Path]:
        env_path = self.write_env(root)
        selected_output = output_root or root / "output"
        code, output = self.invoke(
            [
                "--env-file",
                str(env_path),
                "--output-root",
                str(selected_output),
                "--execute-live",
            ],
            transport_factory=lambda: transport,
            official_csv_path=official_csv_path,
        )
        return code, output, selected_output

    def assert_success_artifacts_linked(
        self,
        output_root: Path,
        success_codes: set[str],
    ) -> dict[str, tuple[Path, Path]]:
        raw_root = output_root / eg5.RAW_OUTPUT_PATH
        metadata_root = output_root / eg5.METADATA_OUTPUT_PATH
        raw_by_code = {
            code: [path for path in raw_root.rglob(f"{code}_*.json")]
            for code in success_codes
        }
        metadata_entries = [
            (path, json.loads(path.read_text(encoding="utf-8")))
            for path in metadata_root.rglob("*.metadata.json")
        ]
        linked: dict[str, tuple[Path, Path]] = {}
        for code in success_codes:
            metadata_for_code = [
                (path, item)
                for path, item in metadata_entries
                if item.get("area_code") == code and item.get("collection_status") == "success"
            ]
            self.assertEqual(len(raw_by_code[code]), 1)
            self.assertEqual(len(metadata_for_code), 1)
            raw_path = raw_by_code[code][0]
            metadata_path, metadata = metadata_for_code[0]
            self.assertEqual(metadata["area_code"], code)
            self.assertEqual(Path(str(metadata["raw_file_path"])).resolve(), raw_path.resolve())
            self.assertTrue(raw_path.name.endswith(f"_{metadata['request_id']}.json"))
            linked[code] = (raw_path, metadata_path)
        return linked

    def test_fixed_allowlist_has_exactly_three_approved_codes(self) -> None:
        self.assertEqual(eg5.EG5_AREA_CODES, ("POI019", "POI013", "POI014"))
        self.assertEqual(len(set(eg5.EG5_AREA_CODES)), 3)

    def test_official_csv_codes_and_names_match(self) -> None:
        actual = tuple(
            (place.area_code, place.area_name)
            for place in (load_place(CSV_PATH, code) for code in eg5.EG5_AREA_CODES)
        )
        self.assertEqual(
            actual,
            (
                ("POI019", "구로디지털단지역"),
                ("POI013", "가산디지털단지역"),
                ("POI014", "강남역"),
            ),
        )

    def test_three_places_are_processed_in_fixed_order(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            transport = FakeTransport()
            code, _, _ = self.run_fake(Path(temporary), transport)
        self.assertEqual(code, 0)
        self.assertEqual(transport.calls, list(eg5.EG5_AREA_CODES))

    def test_three_successes_return_exit_zero_and_exact_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            code, output, output_root = self.run_fake(Path(temporary), FakeTransport())
        self.assertEqual(code, 0)
        self.assertNotIn(str(output_root.resolve()), output)
        self.assertEqual(
            parse_summary(output),
            {
                "target_count": "3",
                "success_count": "3",
                "failure_count": "0",
                "failed_area_codes": "",
                "retry_count": "0",
                "stage": "eg5_representative_3",
                "exit_code": "0",
            },
        )

    def test_middle_failure_does_not_block_third_place(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            transport = FakeTransport({"POI013"})
            code, _, _ = self.run_fake(Path(temporary), transport)
        self.assertEqual(code, 1)
        self.assertEqual(transport.calls, ["POI019", "POI013", "POI014"])

    def test_partial_failure_returns_exit_one_and_consistent_summary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            code, output, _ = self.run_fake(Path(temporary), FakeTransport({"POI013"}))
        self.assertEqual(code, 1)
        summary = parse_summary(output)
        self.assertEqual(summary["success_count"], "2")
        self.assertEqual(summary["failure_count"], "1")
        self.assertEqual(summary["failed_area_codes"], "POI013")
        self.assertEqual(summary["exit_code"], "1")

    def test_all_per_place_failures_are_each_attempted_once(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            transport = FakeTransport(set(eg5.EG5_AREA_CODES))
            code, output, _ = self.run_fake(Path(temporary), transport)
        self.assertEqual(code, 1)
        self.assertEqual(transport.calls, list(eg5.EG5_AREA_CODES))
        summary = parse_summary(output)
        self.assertEqual(summary["success_count"], "0")
        self.assertEqual(summary["failure_count"], "3")
        self.assertEqual(summary["failed_area_codes"], ",".join(eg5.EG5_AREA_CODES))

    def test_preflight_csv_failure_makes_zero_transport_calls(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            with mock.patch.object(eg5, "OFFICIAL_CSV_PATH", root / "missing.csv"):
                code, output, _ = self.run_fake(root, transport)
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, [])
        self.assertEqual(parse_summary(output)["exit_code"], "2")

    def test_common_configuration_failure_returns_exit_two(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            code, output = self.invoke(
                [
                    "--env-file",
                    str(root / "missing.env"),
                    "--output-root",
                    str(root / "output"),
                    "--execute-live",
                ],
                transport_factory=lambda: transport,
            )
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, [])
        self.assertEqual(parse_summary(output)["exit_code"], "2")

    def test_common_storage_initialization_failure_returns_exit_two(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            env_path = self.write_env(root)
            storage_factory = mock.Mock(side_effect=OSError("private storage detail"))
            code, output = self.invoke(
                [
                    "--env-file",
                    str(env_path),
                    "--output-root",
                    str(root / "output"),
                    "--execute-live",
                ],
                transport_factory=lambda: transport,
                storage_factory=storage_factory,
            )
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, [])
        self.assertNotIn("private storage detail", output)

    def test_storage_root_regular_file_fails_before_transport(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            raw_root = output_root / eg5.RAW_OUTPUT_PATH
            raw_root.parent.mkdir(parents=True)
            raw_root.write_bytes(b"not-a-directory")
            transport = FakeTransport()
            code, output, _ = self.run_fake(root, transport, output_root=output_root)
            probes = list(output_root.rglob(f"{eg5.PROBE_FILE_PREFIX}*"))
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, [])
        self.assertEqual(probes, [])
        self.assertEqual(parse_summary(output)["exit_code"], "2")

    def test_storage_probe_error_fails_before_transport_without_residue(self) -> None:
        private_detail = "private probe write detail"
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            with mock.patch.object(
                eg5,
                "_probe_storage_root",
                side_effect=OSError(private_detail),
            ):
                code, output, output_root = self.run_fake(root, transport)
            probes = list(output_root.rglob(f"{eg5.PROBE_FILE_PREFIX}*"))
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, [])
        self.assertEqual(probes, [])
        self.assertNotIn(private_detail, output)

    def test_probe_write_and_flush_failures_cleanup_both_storage_roots(self) -> None:
        for failing_root_name in ("raw", "metadata"):
            for failure_stage in ("write", "flush"):
                with self.subTest(
                    failing_root=failing_root_name,
                    failure_stage=failure_stage,
                ), tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
                    root = Path(temporary)
                    output_root = root / "output"
                    raw_root = (output_root / eg5.RAW_OUTPUT_PATH).resolve()
                    metadata_root = (output_root / eg5.METADATA_OUTPUT_PATH).resolve()
                    raw_root.mkdir(parents=True)
                    metadata_root.mkdir(parents=True)
                    raw_keep = raw_root / "existing-raw.keep"
                    metadata_keep = metadata_root / "existing-metadata.keep"
                    raw_keep.write_bytes(b"existing raw must remain")
                    metadata_keep.write_bytes(b"existing metadata must remain")
                    keep_hashes = {
                        raw_keep: file_hash(raw_keep),
                        metadata_keep: file_hash(metadata_keep),
                    }
                    failing_root = raw_root if failing_root_name == "raw" else metadata_root
                    private_detail = f"private {failing_root_name} {failure_stage} detail"
                    original_open = Path.open

                    def fault_injecting_open(
                        path: Path,
                        *args: object,
                        **kwargs: object,
                    ) -> object:
                        opened = original_open(path, *args, **kwargs)  # type: ignore[arg-type]
                        if (
                            path.parent == failing_root
                            and path.name.startswith(eg5.PROBE_FILE_PREFIX)
                        ):
                            return FaultInjectingProbeFile(
                                opened,  # type: ignore[arg-type]
                                failure_stage,
                                private_detail,
                            )
                        return opened

                    env_path = self.write_env(root)
                    transport = FakeTransport()
                    transport_factory = mock.Mock(return_value=transport)
                    with mock.patch.object(Path, "open", new=fault_injecting_open):
                        code, output = self.invoke(
                            [
                                "--env-file",
                                str(env_path),
                                "--output-root",
                                str(output_root),
                                "--execute-live",
                            ],
                            transport_factory=transport_factory,
                        )

                    self.assertEqual(code, 2)
                    transport_factory.assert_not_called()
                    self.assertEqual(transport.calls, [])
                    self.assertEqual(
                        list(raw_root.rglob(f"{eg5.PROBE_FILE_PREFIX}*")),
                        [],
                    )
                    self.assertEqual(
                        list(metadata_root.rglob(f"{eg5.PROBE_FILE_PREFIX}*")),
                        [],
                    )
                    self.assertEqual(list(raw_root.rglob("POI*.json")), [])
                    self.assertEqual(list(metadata_root.rglob("*.metadata.json")), [])
                    self.assertTrue(
                        all(
                            path.is_file() and file_hash(path) == digest
                            for path, digest in keep_hashes.items()
                        )
                    )
                    self.assertNotIn(private_detail, output)
                    self.assertNotIn(str(output_root.resolve()), output)
                    self.assertNotIn(DUMMY_KEY, output)
                    self.assertNotIn("openapi.seoul.go.kr", output)

    def test_runtime_storage_failure_stops_with_exit_two_without_retry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            env_path = self.write_env(root)
            code, output = self.invoke(
                [
                    "--env-file",
                    str(env_path),
                    "--output-root",
                    str(root / "output"),
                    "--execute-live",
                ],
                transport_factory=lambda: transport,
                storage_factory=FailingMiddleRawStorage,
            )
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, ["POI019", "POI013"])
        summary = parse_summary(output)
        self.assertEqual(summary["success_count"], "1")
        self.assertEqual(summary["failure_count"], "2")
        self.assertEqual(summary["failed_area_codes"], "POI013,POI014")
        self.assertEqual(summary["retry_count"], "0")

    def test_unexpected_result_access_error_returns_two_and_keeps_saved_raw(self) -> None:
        private_detail = "private result detail"
        collector_class = eg5.Collector

        class BrokenResult:
            @property
            def status(self) -> str:
                raise RuntimeError(private_detail)

        class CollectorProxy:
            def __init__(self, *args: object, **kwargs: object) -> None:
                self.delegate = collector_class(*args, **kwargs)  # type: ignore[arg-type]

            def prepare_request(self, *args: object, **kwargs: object) -> object:
                return self.delegate.prepare_request(*args, **kwargs)  # type: ignore[arg-type]

            def collect(self, api_key: str, area_code: str, **kwargs: object) -> object:
                result = self.delegate.collect(api_key, area_code, **kwargs)  # type: ignore[arg-type]
                return BrokenResult() if area_code == "POI013" else result

        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            with mock.patch.object(eg5, "Collector", side_effect=CollectorProxy):
                code, output, output_root = self.run_fake(root, transport)
            raw_files = list((output_root / eg5.RAW_OUTPUT_PATH).rglob("*.json"))
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, ["POI019", "POI013"])
        self.assertIn("POI019", {path.name.split("_", 1)[0] for path in raw_files})
        self.assertNotIn(private_detail, output)

    def test_place_reporter_error_returns_two_and_keeps_previous_raw(self) -> None:
        private_detail = "private reporter detail"
        original_reporter = eg5._report_place

        def failing_reporter(area_code: str, *args: object, **kwargs: object) -> None:
            if area_code == "POI013":
                raise RuntimeError(private_detail)
            original_reporter(area_code, *args, **kwargs)  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            with mock.patch.object(eg5, "_report_place", side_effect=failing_reporter):
                code, output, output_root = self.run_fake(root, transport)
            raw_files = list((output_root / eg5.RAW_OUTPUT_PATH).rglob("*.json"))
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, ["POI019", "POI013"])
        self.assertIn("POI019", {path.name.split("_", 1)[0] for path in raw_files})
        self.assertNotIn(private_detail, output)

    def test_final_summary_error_returns_two_without_private_detail(self) -> None:
        private_detail = "private summary detail"
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            with mock.patch.object(
                eg5,
                "_make_summary",
                side_effect=RuntimeError(private_detail),
            ):
                code, output, output_root = self.run_fake(root, transport)
            raw_files = list((output_root / eg5.RAW_OUTPUT_PATH).rglob("*.json"))
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, list(eg5.EG5_AREA_CODES))
        self.assertEqual(len(raw_files), 3)
        self.assertNotIn(private_detail, output)

    def test_summary_output_error_returns_two_and_keeps_all_saved_artifacts(self) -> None:
        private_detail = "private summary output detail"
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            with mock.patch.object(
                eg5,
                "_report_summary",
                side_effect=RuntimeError(private_detail),
            ):
                code, output, output_root = self.run_fake(root, transport)
            raw_files = list((output_root / eg5.RAW_OUTPUT_PATH).rglob("*.json"))
            metadata_files = list(
                (output_root / eg5.METADATA_OUTPUT_PATH).rglob("*.metadata.json")
            )
        self.assertEqual(code, 2)
        self.assertNotEqual(code, 1)
        self.assertNotEqual(code, 3)
        self.assertEqual(transport.calls, list(eg5.EG5_AREA_CODES))
        self.assertEqual(len(raw_files), 3)
        self.assertEqual(len(metadata_files), 3)
        self.assertNotIn(private_detail, output)
        self.assertNotIn(DUMMY_KEY, output)
        self.assertNotIn("openapi.seoul.go.kr", output)
        self.assertNotIn(str(output_root.resolve()), output)

    def test_summary_output_does_not_swallow_keyboard_interrupt_or_system_exit(self) -> None:
        for injected_error in (KeyboardInterrupt(), SystemExit(17)):
            with self.subTest(error_type=type(injected_error).__name__), tempfile.TemporaryDirectory(
                prefix="freshmanager-eg5-"
            ) as temporary:
                root = Path(temporary)
                output_root = root / "output"
                transport = FakeTransport()
                with mock.patch.object(eg5, "_report_summary", side_effect=injected_error):
                    with self.assertRaises(type(injected_error)) as raised:
                        self.run_fake(root, transport, output_root=output_root)
                raw_files = list((output_root / eg5.RAW_OUTPUT_PATH).rglob("*.json"))
                metadata_files = list(
                    (output_root / eg5.METADATA_OUTPUT_PATH).rglob("*.metadata.json")
                )
                self.assertEqual(transport.calls, list(eg5.EG5_AREA_CODES))
                self.assertEqual(len(raw_files), 3)
                self.assertEqual(len(metadata_files), 3)
                if isinstance(injected_error, SystemExit):
                    self.assertEqual(raised.exception.code, 17)

    def test_csv_deleted_after_first_place_stops_round_and_keeps_first_raw(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            csv_path = root / "reference.csv"
            shutil.copyfile(CSV_PATH, csv_path)

            def delete_after_first(area_code: str, call_count: int) -> None:
                del area_code
                if call_count == 1:
                    csv_path.unlink()

            transport = FakeTransport(after_response=delete_after_first)
            code, output, output_root = self.run_fake(
                root,
                transport,
                official_csv_path=csv_path,
            )
            raw_files = list((output_root / eg5.RAW_OUTPUT_PATH).rglob("*.json"))
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, ["POI019"])
        self.assertEqual({path.name.split("_", 1)[0] for path in raw_files}, {"POI019"})
        self.assertEqual(parse_summary(output)["success_count"], "1")

    def test_csv_changed_after_first_place_stops_round_and_keeps_first_raw(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            csv_path = root / "reference.csv"
            shutil.copyfile(CSV_PATH, csv_path)
            changed_csv = csv_path.read_bytes() + b"\n"

            def change_after_first(area_code: str, call_count: int) -> None:
                del area_code
                if call_count == 1:
                    csv_path.write_bytes(changed_csv)

            transport = FakeTransport(after_response=change_after_first)
            code, output, output_root = self.run_fake(
                root,
                transport,
                official_csv_path=csv_path,
            )
            raw_files = list((output_root / eg5.RAW_OUTPUT_PATH).rglob("*.json"))
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, ["POI019"])
        self.assertEqual({path.name.split("_", 1)[0] for path in raw_files}, {"POI019"})
        self.assertEqual(parse_summary(output)["success_count"], "1")

    def test_request_ids_are_independent_for_each_place(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            code, _, output_root = self.run_fake(Path(temporary), FakeTransport())
            metadata_files = list((output_root / eg5.METADATA_OUTPUT_PATH).rglob("*.metadata.json"))
            request_ids = {
                json.loads(path.read_text(encoding="utf-8"))["request_id"] for path in metadata_files
            }
        self.assertEqual(code, 0)
        self.assertEqual(len(metadata_files), 3)
        self.assertEqual(len(request_ids), 3)

    def test_raw_and_metadata_are_separate_and_linked_per_place(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            code, _, output_root = self.run_fake(Path(temporary), FakeTransport())
            raw_root = output_root / eg5.RAW_OUTPUT_PATH
            metadata_root = output_root / eg5.METADATA_OUTPUT_PATH
            raw_files = list(raw_root.rglob("*.json"))
            metadata_files = list(metadata_root.rglob("*.metadata.json"))
            metadata = [json.loads(path.read_text(encoding="utf-8")) for path in metadata_files]
            linked_files_exist = all(
                Path(str(item["raw_file_path"])).is_file() for item in metadata
            )
        self.assertEqual(code, 0)
        self.assertEqual({path.name.split("_", 1)[0] for path in raw_files}, set(eg5.EG5_AREA_CODES))
        self.assertEqual({item["area_code"] for item in metadata}, set(eg5.EG5_AREA_CODES))
        self.assertTrue(all(tuple(item) == METADATA_FIELDS for item in metadata))
        self.assertTrue(linked_files_exist)

    def test_files_are_created_only_under_the_fixed_stage_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            code, _, output_root = self.run_fake(Path(temporary), FakeTransport())
            created = [path for path in output_root.rglob("*") if path.is_file()]
        self.assertEqual(code, 0)
        self.assertEqual(len(created), 6)
        self.assertTrue(all(eg5.STAGE_PATH.parts == path.relative_to(output_root).parts[:2] for path in created))
        self.assertFalse((output_root / "data/raw/population").exists())
        self.assertFalse((output_root / "data/processed/collection_logs").exists())

    def test_temporary_eg4_sentinel_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            sentinel = output_root / "data/raw/population/eg4-sentinel.json"
            sentinel.parent.mkdir(parents=True)
            sentinel.write_bytes(b'\x7b"eg4":"unchanged"\x7d')
            before = file_hash(sentinel)
            code, _, _ = self.run_fake(root, FakeTransport(), output_root=output_root)
            after = file_hash(sentinel)
            sentinel_exists = sentinel.is_file()
        self.assertEqual(code, 0)
        self.assertEqual(after, before)
        self.assertTrue(sentinel_exists)

    def test_existing_final_json_files_are_not_automatically_deleted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            first_code, _, output_root = self.run_fake(root, FakeTransport())
            first_raw = list((output_root / eg5.RAW_OUTPUT_PATH).rglob("*.json"))
            before = {path: file_hash(path) for path in first_raw}
            second_code, _, _ = self.run_fake(root, FakeTransport(), output_root=output_root)
            all_raw = list((output_root / eg5.RAW_OUTPUT_PATH).rglob("*.json"))
            preserved = all(
                path.is_file() and file_hash(path) == digest for path, digest in before.items()
            )
        self.assertEqual((first_code, second_code), (0, 0))
        self.assertEqual(len(first_raw), 3)
        self.assertEqual(len(all_raw), 6)
        self.assertTrue(preserved)

    def test_failed_place_is_not_retried(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            transport = FakeTransport({"POI013"})
            code, output, _ = self.run_fake(Path(temporary), transport)
        self.assertEqual(code, 1)
        self.assertEqual(transport.calls.count("POI013"), 1)
        self.assertEqual(parse_summary(output)["retry_count"], "0")

    def test_each_per_place_failure_status_is_isolated_without_retry(self) -> None:
        first_success = "POI019"
        success_codes = {"POI019", "POI014"}
        original_reporter = eg5._report_place
        for failure_status in ("api_error", "parse_error", "validation_error", "timeout"):
            with self.subTest(failure_status=failure_status), tempfile.TemporaryDirectory(
                prefix="freshmanager-eg5-"
            ) as temporary:
                root = Path(temporary)
                transport = FakeTransport(
                    failure_statuses={"POI013": failure_status},
                )
                first_success_snapshot: dict[Path, str] = {}

                def capture_first_success(
                    area_code: str,
                    *args: object,
                    **kwargs: object,
                ) -> None:
                    original_reporter(area_code, *args, **kwargs)  # type: ignore[arg-type]
                    if area_code != first_success:
                        return
                    output_root = root / "output"
                    raw_files = list(
                        (output_root / eg5.RAW_OUTPUT_PATH).rglob(f"{first_success}_*.json")
                    )
                    metadata_files = [
                        path
                        for path in (output_root / eg5.METADATA_OUTPUT_PATH).rglob(
                            "*.metadata.json"
                        )
                        if json.loads(path.read_text(encoding="utf-8")).get("area_code")
                        == first_success
                    ]
                    first_success_snapshot.update(
                        {path: file_hash(path) for path in raw_files + metadata_files}
                    )

                with mock.patch.object(
                    eg5,
                    "_report_place",
                    side_effect=capture_first_success,
                ):
                    code, output, output_root = self.run_fake(root, transport)
                summary = parse_summary(output)
                metadata_statuses = {
                    str(item["area_code"]): str(item["collection_status"])
                    for item in (
                        json.loads(path.read_text(encoding="utf-8"))
                        for path in (output_root / eg5.METADATA_OUTPUT_PATH).rglob(
                            "*.metadata.json"
                        )
                    )
                }
                linked = self.assert_success_artifacts_linked(output_root, success_codes)
                self.assertEqual(code, 1)
                self.assertEqual(transport.calls, list(eg5.EG5_AREA_CODES))
                self.assertEqual(transport.calls.count("POI013"), 1)
                self.assertLessEqual(len(transport.calls), 3)
                self.assertEqual(summary["retry_count"], "0")
                self.assertEqual(summary["failed_area_codes"], "POI013")
                self.assertEqual(metadata_statuses["POI013"], failure_status)
                self.assertEqual(set(linked), success_codes)
                self.assertEqual(len(first_success_snapshot), 2)
                self.assertTrue(
                    all(
                        path.is_file() and file_hash(path) == digest
                        for path, digest in first_success_snapshot.items()
                    )
                )

    def test_total_transport_calls_never_exceed_three(self) -> None:
        for failures in (set(), {"POI013"}, set(eg5.EG5_AREA_CODES)):
            with self.subTest(failures=failures), tempfile.TemporaryDirectory(
                prefix="freshmanager-eg5-"
            ) as temporary:
                transport = FakeTransport(failures)
                self.run_fake(Path(temporary), transport)
                self.assertLessEqual(len(transport.calls), 3)
                self.assertEqual(len(transport.calls), len(set(transport.calls)))

    def test_dummy_key_is_absent_from_output_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            code, output, output_root = self.run_fake(Path(temporary), FakeTransport())
            metadata_text = "".join(
                path.read_text(encoding="utf-8")
                for path in (output_root / eg5.METADATA_OUTPUT_PATH).rglob("*.metadata.json")
            )
        self.assertEqual(code, 0)
        self.assertNotIn(DUMMY_KEY, output)
        self.assertNotIn(DUMMY_KEY, metadata_text)

    def test_completed_authentication_urls_are_not_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            transport = FakeTransport()
            code, output, _ = self.run_fake(Path(temporary), transport)
        self.assertEqual(code, 0)
        self.assertTrue(all(DUMMY_KEY in url for url in transport.full_urls))
        self.assertTrue(all(url not in output for url in transport.full_urls))
        self.assertNotIn("openapi.seoul.go.kr", output)

    def test_fake_execution_uses_no_dns_socket_or_real_http(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg5-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            with (
                mock.patch("socket.create_connection", side_effect=AssertionError("network forbidden")) as create,
                mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")) as connect,
                mock.patch("socket.getaddrinfo", side_effect=AssertionError("network forbidden")) as dns,
                mock.patch(
                    "freshmanager.http_adapter.UrllibTransport.open",
                    side_effect=AssertionError("http forbidden"),
                ) as http_open,
            ):
                code, _, _ = self.run_fake(root, transport)
        self.assertEqual(code, 0)
        create.assert_not_called()
        connect.assert_not_called()
        dns.assert_not_called()
        http_open.assert_not_called()

    def test_arbitrary_area_and_output_path_options_are_rejected(self) -> None:
        for option, value in [
            ("--area-code", "POI072"),
            ("--raw-root", "raw"),
            ("--metadata-root", "metadata"),
            ("--stage", "other"),
        ]:
            with self.subTest(option=option), tempfile.TemporaryDirectory(
                prefix="freshmanager-eg5-"
            ) as temporary:
                root = Path(temporary)
                output_root = root / "output"
                code, output = self.invoke(
                    [
                        "--env-file",
                        str(root / "unused.env"),
                        "--output-root",
                        str(output_root),
                        option,
                        value,
                        "--execute-live",
                    ]
                )
                self.assertEqual(code, 2)
                self.assertEqual(parse_summary(output)["exit_code"], "2")
                self.assertFalse(output_root.exists())


if __name__ == "__main__":
    unittest.main()
