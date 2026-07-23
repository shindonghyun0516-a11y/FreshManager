from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Callable
from unittest import mock
from urllib.parse import unquote

from freshmanager import backup, eg6b
from freshmanager.collector import CURRENT_POPULATION_FIELDS
from freshmanager.storage import (
    BatchReservationError,
    BatchStorage,
    FileStorage,
    StorageError,
    reserve_batch_directory,
)


ROOT = Path(__file__).resolve().parents[1]
DUMMY_KEY = "dummy-eg6b-key-for-tests"
ENV_NAME = "SEOUL_OPEN" + "_API_KEY"
BATCH_ID = "11111111-1111-4111-8111-111111111111"
LETTERED_BATCH_ID = "abcdefab-cdef-4abc-8def-abcdefabcdef"


def official_names() -> dict[str, str]:
    with (ROOT / "data/reference/seoul_121_places.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as source:
        return {row["AREA_CD"]: row["AREA_NM"] for row in csv.DictReader(source, strict=True)}


AREA_NAMES = official_names()


def synthetic_population(area_code: str) -> bytes:
    current = {field: "1" for field in CURRENT_POPULATION_FIELDS}
    current.update(
        {
            "AREA_NM": AREA_NAMES[area_code],
            "AREA_CD": area_code,
            "AREA_CONGEST_LVL": "보통",
            "AREA_CONGEST_MSG": "합성 테스트 응답",
            "AREA_PPLTN_MIN": "1000",
            "AREA_PPLTN_MAX": "1200",
            "PPLTN_TIME": "2026-07-21 21:00",
            "FCST_YN": "Y",
            "FCST_PPLTN": [
                {
                    "FCST_TIME": "2026-07-21 22:00",
                    "FCST_CONGEST_LVL": "보통",
                    "FCST_PPLTN_MIN": "1100",
                    "FCST_PPLTN_MAX": "1300",
                }
            ],
        }
    )
    return json.dumps(
        {
            "SeoulRtd.citydata_ppltn": [current],
            "RESULT": {
                "RESULT.CODE": "INFO-000",
                "RESULT.MESSAGE": "정상 처리되었습니다",
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")


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
        failure_statuses: dict[str, str] | None = None,
        *,
        after_response: Callable[[str, int], None] | None = None,
    ) -> None:
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
        failure = self.failure_statuses.get(area_code)
        if failure == "timeout":
            raise TimeoutError("synthetic timeout detail")
        if failure == "api_error":
            response = FakeResponse(b'{"synthetic":"api-error"}', status=500)
        elif failure == "parse_error":
            response = FakeResponse(b'{"SeoulRtd.citydata_ppltn": [')
        elif failure == "validation_error":
            document = json.loads(synthetic_population(area_code).decode("utf-8"))
            document["SeoulRtd.citydata_ppltn"][0]["AREA_CD"] = "POI999"
            response = FakeResponse(json.dumps(document, ensure_ascii=False).encode("utf-8"))
        else:
            response = FakeResponse(synthetic_population(area_code))
        if self.after_response is not None:
            self.after_response(area_code, len(self.calls))
        return response


class FailThirdRawStorage(FileStorage):
    def save_raw(
        self,
        area_code: str,
        requested_at: object,
        request_id: str,
        payload: bytes,
    ) -> Path:
        if area_code == eg6b.EG6B_AREA_CODES[2]:
            raise StorageError("private storage detail")
        return super().save_raw(area_code, requested_at, request_id, payload)  # type: ignore[arg-type]


class InterruptAfterFirstRawStorage(FileStorage):
    def save_raw(
        self,
        area_code: str,
        requested_at: object,
        request_id: str,
        payload: bytes,
    ) -> Path:
        super().save_raw(area_code, requested_at, request_id, payload)  # type: ignore[arg-type]
        raise KeyboardInterrupt("synthetic interruption")


class FailingManifestStorage(BatchStorage):
    def save_manifest(self, document: object) -> Path:
        del document
        raise StorageError("private manifest detail")


class FailingCollectionLogStorage(BatchStorage):
    def save_collection_log(self, document: object) -> Path:
        del document
        raise StorageError("private collection log detail")


class TamperingBatchStorage(BatchStorage):
    def save_manifest(self, document: object) -> Path:
        stage_root = self.batch_directory.parents[3]
        raw_path = next((stage_root / "data/raw/population").rglob("*.json"))
        raw_path.write_bytes(raw_path.read_bytes() + b"tampered")
        return super().save_manifest(document)  # type: ignore[arg-type]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_summary(output: str) -> dict[str, str]:
    lines = output.splitlines()
    start = lines.index("EG6B_COLLECTION_SUMMARY") + 1
    return dict(line.split("=", 1) for line in lines[start:] if "=" in line)


class Eg6bTests(unittest.TestCase):
    @staticmethod
    def write_env(root: Path) -> Path:
        path = root / "dummy.env"
        path.write_text(f"{ENV_NAME}={DUMMY_KEY}\n", encoding="utf-8")
        return path

    @staticmethod
    def invoke(argv: list[str], **kwargs: object) -> tuple[int, str]:
        output = io.StringIO()
        errors = io.StringIO()
        kwargs.setdefault("environ", {})
        with redirect_stdout(output), redirect_stderr(errors):
            code = eg6b.run(argv, **kwargs)  # type: ignore[arg-type]
        return code, output.getvalue() + errors.getvalue()

    def run_fake(
        self,
        root: Path,
        transport: FakeTransport,
        batch_id: str = BATCH_ID,
        **kwargs: object,
    ) -> tuple[int, str, Path]:
        output_root = root / "output"
        code, output = self.invoke(
            [
                "--env-file",
                str(self.write_env(root)),
                "--output-root",
                str(output_root),
                "--batch-id",
                batch_id,
                "--execute-live",
            ],
            transport_factory=lambda: transport,
            **kwargs,
        )
        return code, output, output_root

    @staticmethod
    def batch_documents(output_root: Path) -> tuple[Path, dict[str, object], Path, dict[str, object]]:
        batch_root = output_root / eg6b.BATCH_OUTPUT_PATH
        logs = list(batch_root.rglob("collection_log.json"))
        manifests = list(batch_root.rglob("manifest.json"))
        if len(logs) != 1 or len(manifests) != 1:
            raise AssertionError("expected one batch log and manifest")
        return (
            logs[0],
            json.loads(logs[0].read_text(encoding="utf-8")),
            manifests[0],
            json.loads(manifests[0].read_text(encoding="utf-8")),
        )

    def copied_references(self, root: Path) -> eg6b.ReferencePaths:
        reference_root = root / "references"
        paths = eg6b.ReferencePaths(
            root=reference_root,
            official_csv=reference_root / "data/reference/seoul_121_places.csv",
            area_panel=reference_root / "data/reference/eg6_area_panel.csv",
            spot_master=reference_root / "data/reference/eg6_spot_master.csv",
            sdot_links=reference_root / "data/reference/eg6_sdot_links.csv",
        )
        for source, target in (
            (eg6b.OFFICIAL_CSV_PATH, paths.official_csv),
            (eg6b.AREA_PANEL_PATH, paths.area_panel),
            (eg6b.SPOT_MASTER_PATH, paths.spot_master),
            (eg6b.SDOT_LINKS_PATH, paths.sdot_links),
        ):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        return paths

    def test_fixed_panel_order_has_thirteen_approved_codes(self) -> None:
        self.assertEqual(len(eg6b.EG6B_AREA_CODES), 13)
        self.assertEqual(len(set(eg6b.EG6B_AREA_CODES)), 13)
        self.assertEqual(
            eg6b.EG6B_AREA_CODES,
            (
                "POI019", "POI013", "POI014", "POI072", "POI001",
                "POI034", "POI042", "POI025", "POI088", "POI003",
                "POI119", "POI033", "POI032",
            ),
        )

    def test_all_success_creates_complete_batch_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            code, output, output_root = self.run_fake(root, transport)
            log_path, log, manifest_path, manifest = self.batch_documents(output_root)
            raw_paths = list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json"))
            metadata_paths = list((output_root / eg6b.METADATA_OUTPUT_PATH).rglob("*.metadata.json"))

            self.assertEqual(code, 0)
            self.assertEqual(transport.calls, list(eg6b.EG6B_AREA_CODES))
            self.assertEqual(len(raw_paths), 13)
            self.assertEqual(len(metadata_paths), 13)
            self.assertEqual(log["collector_version"], eg6b.COLLECTOR_VERSION)
            self.assertEqual(log["data_version"], eg6b.DATA_VERSION)
            self.assertEqual(log["batch_id"], BATCH_ID)
            self.assertEqual(log["panel_version"], eg6b.PANEL_VERSION)
            self.assertEqual(log["expected_area_count"], 13)
            self.assertEqual(log["attempted_count"], 13)
            self.assertEqual(log["success_count"], 13)
            self.assertEqual(log["failure_count"], 0)
            self.assertEqual(log["retry_count"], 0)
            self.assertEqual(log["exit_code"], 0)
            self.assertGreaterEqual(log["elapsed_seconds"], 0)
            self.assertEqual(len(log["area_results"]), 13)
            self.assertEqual(manifest["hash_algorithm"], "sha256")
            self.assertEqual(manifest["batch_id"], BATCH_ID)
            self.assertEqual(log_path.parent.name, BATCH_ID)
            self.assertEqual(len(manifest["reference_files"]), 4)
            self.assertEqual(len(manifest["artifacts"]), 27)
            self.assertNotIn(manifest_path.name, [item["relative_path"] for item in manifest["artifacts"]])
            self.assertIn(
                log_path.relative_to(output_root / eg6b.STAGE_PATH).as_posix(),
                [item["relative_path"] for item in manifest["artifacts"]],
            )
            summary = parse_summary(output)
            self.assertEqual(summary["target_count"], "13")
            self.assertEqual(summary["batch_id"], BATCH_ID)
            self.assertEqual(summary["attempted_count"], "13")
            self.assertEqual(summary["success_count"], "13")
            self.assertEqual(summary["failure_count"], "0")
            self.assertEqual(summary["retry_count"], "0")
            self.assertEqual(summary["hash_verification_passed"], "true")
            self.assertEqual(summary["exit_code"], "0")

    def test_manifest_hashes_match_every_listed_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            _, _, output_root = self.run_fake(root, FakeTransport())
            _, _, _, manifest = self.batch_documents(output_root)
            stage_root = output_root / eg6b.STAGE_PATH
            for item in manifest["reference_files"]:
                path = ROOT / item["path"]
                self.assertEqual(path.stat().st_size, item["byte_size"])
                self.assertEqual(sha256(path), item["sha256"])
            for item in manifest["artifacts"]:
                path = stage_root / item["relative_path"]
                self.assertEqual(path.stat().st_size, item["byte_size"])
                self.assertEqual(sha256(path), item["sha256"])

    def test_middle_timeout_is_isolated_without_retry(self) -> None:
        failed_code = eg6b.EG6B_AREA_CODES[5]
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            transport = FakeTransport({failed_code: "timeout"})
            code, output, output_root = self.run_fake(root, transport)
            _, log, _, manifest = self.batch_documents(output_root)

        self.assertEqual(code, 1)
        self.assertEqual(transport.calls, list(eg6b.EG6B_AREA_CODES))
        self.assertEqual(transport.calls.count(failed_code), 1)
        self.assertEqual(log["success_count"], 12)
        self.assertEqual(log["failure_count"], 1)
        self.assertEqual(log["failed_area_codes"], [failed_code])
        self.assertEqual(log["retry_count"], 0)
        self.assertEqual(log["batch_id"], BATCH_ID)
        self.assertEqual(manifest["batch_id"], BATCH_ID)
        self.assertEqual(len(manifest["artifacts"]), 26)
        self.assertEqual(parse_summary(output)["exit_code"], "1")

    def test_each_per_place_failure_status_continues(self) -> None:
        statuses = ("api_error", "timeout", "parse_error", "validation_error")
        for status in statuses:
            with self.subTest(status=status), tempfile.TemporaryDirectory(
                prefix="freshmanager-eg6b-"
            ) as temporary:
                failed_code = eg6b.EG6B_AREA_CODES[1]
                transport = FakeTransport({failed_code: status})
                code, _, _ = self.run_fake(Path(temporary), transport)
                self.assertEqual(code, 1)
                self.assertEqual(transport.calls, list(eg6b.EG6B_AREA_CODES))
                self.assertEqual(transport.calls.count(failed_code), 1)

    def test_all_place_timeouts_are_attempted_once(self) -> None:
        failures = {code: "timeout" for code in eg6b.EG6B_AREA_CODES}
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            transport = FakeTransport(failures)
            code, _, output_root = self.run_fake(root, transport)
            _, log, _, _ = self.batch_documents(output_root)
        self.assertEqual(code, 1)
        self.assertEqual(transport.calls, list(eg6b.EG6B_AREA_CODES))
        self.assertEqual(log["attempted_count"], 13)
        self.assertEqual(log["success_count"], 0)
        self.assertEqual(log["failure_count"], 13)
        self.assertEqual(log["metadata_file_count"], 13)
        self.assertEqual(log["raw_file_count"], 0)

    def test_request_ids_are_independent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            _, _, output_root = self.run_fake(root, FakeTransport())
            _, log, _, _ = self.batch_documents(output_root)
        request_ids = [item["request_id"] for item in log["area_results"]]
        self.assertEqual(len(request_ids), 13)
        self.assertEqual(len(set(request_ids)), 13)

    def test_execute_flag_and_arbitrary_area_option_are_rejected_before_transport(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            env_path = self.write_env(root)
            factory = mock.Mock(return_value=FakeTransport())
            without_flag, _ = self.invoke(
                ["--env-file", str(env_path), "--output-root", str(output_root)],
                transport_factory=factory,
            )
            arbitrary_code, _ = self.invoke(
                [
                    "--env-file", str(env_path), "--output-root", str(output_root),
                    "--batch-id", BATCH_ID, "--area-code", "POI999", "--execute-live",
                ],
                transport_factory=factory,
            )
        self.assertEqual(without_flag, 2)
        self.assertEqual(arbitrary_code, 2)
        factory.assert_not_called()
        self.assertFalse(output_root.exists())

    def test_cli_accepts_canonical_batch_id_and_documents_option(self) -> None:
        parser = eg6b.build_parser()
        arguments = parser.parse_args(
            [
                "--env-file", "dummy.env",
                "--output-root", "output",
                "--batch-id", BATCH_ID,
                "--execute-live",
            ]
        )
        self.assertEqual(arguments.batch_id, BATCH_ID)
        self.assertIn("--batch-id", parser.format_help())

    def test_runbook_hands_the_same_batch_id_to_collector_and_backup(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        shared_argument = '--batch-id "$FM_LIVE_BATCH_ID"'
        self.assertGreaterEqual(readme.count(shared_argument), 2)
        self.assertIn("python3 -m freshmanager.eg6b", readme)
        self.assertIn("python3 -m freshmanager.backup", readme)

    def test_live_mode_without_batch_id_fails_before_credential_network_and_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            factory = mock.Mock(return_value=FakeTransport())
            with mock.patch.object(eg6b, "load_api_key") as load_key:
                code, output = self.invoke(
                    [
                        "--env-file", str(root / "missing.env"),
                        "--output-root", str(output_root),
                        "--execute-live",
                    ],
                    transport_factory=factory,
                )
        self.assertEqual(code, 2)
        self.assertIn("preflight_status=batch_id_required", output)
        load_key.assert_not_called()
        factory.assert_not_called()
        self.assertFalse(output_root.exists())

    def test_invalid_batch_ids_fail_before_credential_network_and_writes(self) -> None:
        invalid_values = (
            "",
            "   ",
            f" {BATCH_ID}",
            LETTERED_BATCH_ID.upper(),
            "../11111111-1111-4111-8111-111111111111",
            "not-a-batch-id",
        )
        for value in invalid_values:
            with self.subTest(value=value), tempfile.TemporaryDirectory(
                prefix="freshmanager-eg6b-"
            ) as temporary:
                root = Path(temporary)
                output_root = root / "output"
                factory = mock.Mock(return_value=FakeTransport())
                with mock.patch.object(eg6b, "load_api_key") as load_key:
                    code, output = self.invoke(
                        [
                            "--env-file", str(root / "missing.env"),
                            "--output-root", str(output_root),
                            "--batch-id", value,
                            "--execute-live",
                        ],
                        transport_factory=factory,
                    )
                self.assertEqual(code, 2)
                self.assertIn("preflight_status=input_error", output)
                load_key.assert_not_called()
                factory.assert_not_called()
                self.assertFalse(output_root.exists())

    def test_source_sync_receipt_and_lock_collisions_fail_before_credential_network(self) -> None:
        collision_types = ("source", "sync", "receipt", "lock")
        for collision_type in collision_types:
            with self.subTest(collision_type=collision_type), tempfile.TemporaryDirectory(
                prefix="freshmanager-eg6b-"
            ) as temporary:
                root = Path(temporary)
                output_root = root / "output"
                sync_root = root / "sync"
                if collision_type == "source":
                    collision = output_root / eg6b.BATCH_OUTPUT_PATH / BATCH_ID
                elif collision_type == "sync":
                    collision = sync_root / backup.DESTINATION_RELATIVE_PATH / BATCH_ID
                elif collision_type == "receipt":
                    collision = (
                        output_root / backup.LEDGER_RELATIVE_PATH / "receipts" / BATCH_ID
                    )
                else:
                    collision = (
                        output_root / backup.LEDGER_RELATIVE_PATH / "locks" / f"{BATCH_ID}.lock"
                    )
                if collision_type == "lock":
                    collision.parent.mkdir(parents=True)
                    collision.write_text("synthetic lock", encoding="utf-8")
                else:
                    collision.mkdir(parents=True)
                    (collision / "marker.txt").write_text("immutable", encoding="utf-8")
                before = {
                    item.relative_to(root).as_posix(): sha256(item)
                    for item in root.rglob("*")
                    if item.is_file()
                }
                factory = mock.Mock(return_value=FakeTransport())
                with mock.patch.object(eg6b, "load_api_key") as load_key:
                    code, output = self.invoke(
                        [
                            "--env-file", str(root / "missing.env"),
                            "--output-root", str(output_root),
                            "--batch-id", BATCH_ID,
                            "--execute-live",
                        ],
                        transport_factory=factory,
                        environ={backup.SYNC_ROOT_ENV: str(sync_root)},
                    )
                after = {
                    item.relative_to(root).as_posix(): sha256(item)
                    for item in root.rglob("*")
                    if item.is_file()
                }
                self.assertEqual(code, 2)
                self.assertIn("preflight_status=batch_id_conflict", output)
                self.assertEqual(after, before)
                self.assertFalse((output_root / eg6b.RAW_OUTPUT_PATH).exists())
                self.assertFalse((output_root / eg6b.METADATA_OUTPUT_PATH).exists())
                self.assertEqual(
                    list((output_root / eg6b.BATCH_OUTPUT_PATH).rglob("collection_log.json")),
                    [],
                )
                self.assertEqual(
                    list((output_root / eg6b.BATCH_OUTPUT_PATH).rglob("manifest.json")),
                    [],
                )
                load_key.assert_not_called()
                factory.assert_not_called()

    def test_reservation_precedes_credential_and_transport_access(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            batch_directory = output_root / eg6b.BATCH_OUTPUT_PATH / BATCH_ID
            transport = FakeTransport()
            events: list[str] = []

            def load_key(env_path: Path) -> str:
                del env_path
                self.assertTrue(batch_directory.is_dir())
                events.append("credential")
                return DUMMY_KEY

            def make_transport() -> FakeTransport:
                self.assertTrue(batch_directory.is_dir())
                events.append("transport")
                return transport

            with mock.patch.object(eg6b, "load_api_key", side_effect=load_key):
                code, _ = self.invoke(
                    [
                        "--env-file", str(root / "approved.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=make_transport,
                )

        self.assertEqual(code, 0)
        self.assertEqual(events, ["credential", "transport"])
        self.assertEqual(transport.calls, list(eg6b.EG6B_AREA_CODES))

    def test_concurrent_same_id_has_exactly_one_atomic_transport_winner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            env_path = self.write_env(root)
            argv = [
                "--env-file", str(env_path),
                "--output-root", str(output_root),
                "--batch-id", BATCH_ID,
                "--execute-live",
            ]
            transports = (FakeTransport(), FakeTransport())
            factories = (
                mock.Mock(return_value=transports[0]),
                mock.Mock(return_value=transports[1]),
            )
            reservation_boundary = threading.Barrier(2)
            actual_reserve = eg6b.reserve_batch_directory
            state_lock = threading.Lock()
            reservation_winners: list[int] = []
            reservation_conflicts: list[int] = []
            credential_loads: list[int] = []
            preflight_reasons: list[str] = []

            def synchronized_reserve(path: Path) -> object:
                reservation_boundary.wait(timeout=5)
                try:
                    reservation = actual_reserve(path)
                except eg6b.BatchReservationConflict:
                    with state_lock:
                        reservation_conflicts.append(threading.get_ident())
                    raise
                with state_lock:
                    reservation_winners.append(threading.get_ident())
                return reservation

            def load_key(env_path: Path) -> str:
                del env_path
                with state_lock:
                    credential_loads.append(threading.get_ident())
                return DUMMY_KEY

            actual_preflight_failure = eg6b._preflight_failure

            def record_preflight(reason_code: str = "preflight_error") -> int:
                with state_lock:
                    preflight_reasons.append(reason_code)
                return actual_preflight_failure(reason_code)

            def execute(index: int) -> int:
                return eg6b.run(
                    argv,
                    transport_factory=factories[index],
                    environ={},
                )

            with mock.patch.object(
                eg6b,
                "reserve_batch_directory",
                side_effect=synchronized_reserve,
            ), mock.patch.object(
                eg6b,
                "load_api_key",
                side_effect=load_key,
            ), mock.patch.object(
                eg6b,
                "_preflight_failure",
                side_effect=record_preflight,
            ), mock.patch("builtins.print"):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = tuple(executor.map(execute, (0, 1)))

            raw_files = list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json"))
            metadata_files = list(
                (output_root / eg6b.METADATA_OUTPUT_PATH).rglob("*.metadata.json")
            )
            log_files = list(
                (output_root / eg6b.BATCH_OUTPUT_PATH).rglob("collection_log.json")
            )
            manifest_files = list(
                (output_root / eg6b.BATCH_OUTPUT_PATH).rglob("manifest.json")
            )

        winner_index = results.index(0)
        loser_index = results.index(2)
        self.assertNotEqual(winner_index, loser_index)
        self.assertEqual(len(reservation_winners), 1)
        self.assertEqual(len(reservation_conflicts), 1)
        self.assertEqual(len(credential_loads), 1)
        self.assertEqual(preflight_reasons, ["batch_id_conflict"])
        self.assertEqual(factories[winner_index].call_count, 1)
        self.assertEqual(factories[loser_index].call_count, 0)
        self.assertEqual(len(transports[winner_index].calls), 13)
        self.assertEqual(transports[loser_index].calls, [])
        self.assertEqual(len(raw_files), 13)
        self.assertEqual(len(metadata_files), 13)
        self.assertEqual(len(log_files), 1)
        self.assertEqual(len(manifest_files), 1)

    def test_deleted_reservation_fails_before_credential_and_is_not_recreated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            batch_directory = output_root / eg6b.BATCH_OUTPUT_PATH / BATCH_ID
            existing_raw = output_root / eg6b.RAW_OUTPUT_PATH / "existing-evidence.json"
            existing_raw.parent.mkdir(parents=True)
            existing_raw.write_bytes(b"immutable")
            before_hash = sha256(existing_raw)
            actual_reserve = eg6b.reserve_batch_directory

            def reserve_then_delete(path: Path) -> object:
                reservation = actual_reserve(path)
                path.rmdir()
                return reservation

            factory = mock.Mock(return_value=FakeTransport())
            with mock.patch.object(
                eg6b,
                "reserve_batch_directory",
                side_effect=reserve_then_delete,
            ), mock.patch.object(eg6b, "load_api_key") as load_key:
                code, output = self.invoke(
                    [
                        "--env-file", str(root / "approved.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=factory,
                )

            eligibility = backup.assess_batch(output_root / eg6b.STAGE_PATH, BATCH_ID)
            self.assertEqual(code, 2)
            self.assertIn("preflight_status=reservation_integrity_error", output)
            self.assertFalse(batch_directory.exists())
            self.assertEqual(sha256(existing_raw), before_hash)
            self.assertEqual(
                list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json")),
                [existing_raw],
            )
            self.assertEqual(
                list((output_root / eg6b.METADATA_OUTPUT_PATH).rglob("*.metadata.json")),
                [],
            )
            load_key.assert_not_called()
            factory.assert_not_called()
            self.assertFalse(eligibility.eligible)

    def test_replaced_reservation_directory_is_rejected_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            batch_directory = output_root / eg6b.BATCH_OUTPUT_PATH / BATCH_ID
            original_directory = batch_directory.with_name(f".original-{BATCH_ID}")
            actual_reserve = eg6b.reserve_batch_directory

            def reserve_then_replace(path: Path) -> object:
                reservation = actual_reserve(path)
                path.rename(original_directory)
                path.mkdir(mode=0o700)
                return reservation

            factory = mock.Mock(return_value=FakeTransport())
            with mock.patch.object(
                eg6b,
                "reserve_batch_directory",
                side_effect=reserve_then_replace,
            ), mock.patch.object(eg6b, "load_api_key") as load_key:
                code, output = self.invoke(
                    [
                        "--env-file", str(root / "approved.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=factory,
                )

            eligibility = backup.assess_batch(output_root / eg6b.STAGE_PATH, BATCH_ID)
            self.assertEqual(code, 2)
            self.assertIn("preflight_status=reservation_integrity_error", output)
            self.assertTrue(batch_directory.is_dir())
            self.assertTrue(original_directory.is_dir())
            self.assertEqual(list(batch_directory.iterdir()), [])
            self.assertEqual(list(original_directory.iterdir()), [])
            load_key.assert_not_called()
            factory.assert_not_called()
            self.assertFalse(eligibility.eligible)

    def test_symlink_replacement_is_rejected_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            batch_directory = output_root / eg6b.BATCH_OUTPUT_PATH / BATCH_ID
            original_directory = batch_directory.with_name(f".original-{BATCH_ID}")
            actual_reserve = eg6b.reserve_batch_directory

            def reserve_then_replace_with_symlink(path: Path) -> object:
                reservation = actual_reserve(path)
                path.rename(original_directory)
                try:
                    path.symlink_to(original_directory, target_is_directory=True)
                except OSError as error:
                    reservation.close()
                    self.skipTest(f"symlink unsupported: {type(error).__name__}")
                return reservation

            factory = mock.Mock(return_value=FakeTransport())
            with mock.patch.object(
                eg6b,
                "reserve_batch_directory",
                side_effect=reserve_then_replace_with_symlink,
            ), mock.patch.object(eg6b, "load_api_key") as load_key:
                code, output = self.invoke(
                    [
                        "--env-file", str(root / "approved.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=factory,
                )

            eligibility = backup.assess_batch(output_root / eg6b.STAGE_PATH, BATCH_ID)
            self.assertEqual(code, 2)
            self.assertIn("preflight_status=reservation_integrity_error", output)
            self.assertTrue(batch_directory.is_symlink())
            self.assertEqual(list(original_directory.iterdir()), [])
            load_key.assert_not_called()
            factory.assert_not_called()
            self.assertFalse(eligibility.eligible)

    def test_batch_storage_rejects_directory_replacement_before_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            batch_directory = root / BATCH_ID
            original_directory = root / "original-reservation"
            reservation = reserve_batch_directory(batch_directory)
            try:
                storage = BatchStorage(reservation)
                batch_directory.rename(original_directory)
                batch_directory.mkdir(mode=0o700)
                with self.assertRaises(BatchReservationError):
                    storage.save_manifest({"batch_id": BATCH_ID})
                self.assertEqual(list(batch_directory.iterdir()), [])
                self.assertEqual(list(original_directory.iterdir()), [])
            finally:
                reservation.close()

    def test_interrupted_batch_id_remains_reserved_and_cannot_be_reused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            env_path = self.write_env(root)
            argv = [
                "--env-file", str(env_path),
                "--output-root", str(output_root),
                "--batch-id", BATCH_ID,
                "--execute-live",
            ]
            first_transport = FakeTransport()
            with self.assertRaises(KeyboardInterrupt):
                self.invoke(
                    argv,
                    transport_factory=lambda: first_transport,
                    storage_factory=InterruptAfterFirstRawStorage,
                )

            batch_directory = output_root / eg6b.BATCH_OUTPUT_PATH / BATCH_ID
            raw_files = list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json"))
            metadata_files = list(
                (output_root / eg6b.METADATA_OUTPUT_PATH).rglob("*.metadata.json")
            )
            before = {path.relative_to(output_root).as_posix(): sha256(path) for path in raw_files}
            second_transport = FakeTransport()
            factory = mock.Mock(return_value=second_transport)
            with mock.patch.object(eg6b, "load_api_key") as load_key:
                second_code, output = self.invoke(argv, transport_factory=factory)
            after_files = list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json"))
            after = {
                path.relative_to(output_root).as_posix(): sha256(path)
                for path in after_files
            }
            eligibility = backup.assess_batch(output_root / eg6b.STAGE_PATH, BATCH_ID)

            self.assertEqual(first_transport.calls, [eg6b.EG6B_AREA_CODES[0]])
            self.assertTrue(batch_directory.is_dir())
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(metadata_files, [])
            self.assertEqual(
                list(batch_directory.glob("collection_log.json")),
                [],
            )
            self.assertEqual(list(batch_directory.glob("manifest.json")), [])
            self.assertEqual(second_code, 2)
            self.assertIn("preflight_status=batch_id_conflict", output)
            load_key.assert_not_called()
            factory.assert_not_called()
            self.assertEqual(second_transport.calls, [])
            self.assertEqual(after, before)
            self.assertFalse(eligibility.eligible)

    def test_reservation_survives_credential_failure_without_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            batch_directory = output_root / eg6b.BATCH_OUTPUT_PATH / BATCH_ID
            factory = mock.Mock(return_value=FakeTransport())
            with mock.patch.object(eg6b, "load_api_key", side_effect=RuntimeError("synthetic")):
                code, _ = self.invoke(
                    [
                        "--env-file", str(root / "approved.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=factory,
                )

            self.assertEqual(code, 2)
            self.assertTrue(batch_directory.is_dir())
            self.assertEqual(list(batch_directory.iterdir()), [])
            self.assertEqual(
                list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json")),
                [],
            )
            self.assertEqual(
                list((output_root / eg6b.METADATA_OUTPUT_PATH).rglob("*.metadata.json")),
                [],
            )
            factory.assert_not_called()
            self.assertFalse(
                backup.assess_batch(output_root / eg6b.STAGE_PATH, BATCH_ID).eligible
            )

            second_factory = mock.Mock(return_value=FakeTransport())
            with mock.patch.object(eg6b, "load_api_key") as second_load_key:
                second_code, second_output = self.invoke(
                    [
                        "--env-file", str(root / "approved.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=second_factory,
                )
            self.assertEqual(second_code, 2)
            self.assertIn("preflight_status=batch_id_conflict", second_output)
            second_load_key.assert_not_called()
            second_factory.assert_not_called()
            self.assertTrue(batch_directory.is_dir())
            self.assertEqual(list(batch_directory.iterdir()), [])

    def test_storage_setup_failure_keeps_reservation_and_blocks_reuse(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            batch_directory = output_root / eg6b.BATCH_OUTPUT_PATH / BATCH_ID

            def fail_batch_storage(reservation: object) -> BatchStorage:
                self.assertIsNotNone(reservation)
                raise StorageError("synthetic storage setup failure")

            first_factory = mock.Mock(return_value=FakeTransport())
            with mock.patch.object(eg6b, "load_api_key") as first_load_key:
                first_code, _ = self.invoke(
                    [
                        "--env-file", str(root / "approved.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=first_factory,
                    batch_storage_factory=fail_batch_storage,
                )

            self.assertEqual(first_code, 2)
            self.assertTrue(batch_directory.is_dir())
            self.assertEqual(list(batch_directory.iterdir()), [])
            first_load_key.assert_not_called()
            first_factory.assert_not_called()
            self.assertFalse(
                backup.assess_batch(output_root / eg6b.STAGE_PATH, BATCH_ID).eligible
            )

            second_factory = mock.Mock(return_value=FakeTransport())
            with mock.patch.object(eg6b, "load_api_key") as second_load_key:
                second_code, second_output = self.invoke(
                    [
                        "--env-file", str(root / "approved.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=second_factory,
                )
            self.assertEqual(second_code, 2)
            self.assertIn("preflight_status=batch_id_conflict", second_output)
            second_load_key.assert_not_called()
            second_factory.assert_not_called()
            self.assertEqual(list(batch_directory.iterdir()), [])

    def test_transport_construction_failure_keeps_incomplete_reservation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            output_root = root / "output"
            batch_directory = output_root / eg6b.BATCH_OUTPUT_PATH / BATCH_ID
            first_factory = mock.Mock(side_effect=RuntimeError("synthetic transport failure"))
            with mock.patch.object(
                eg6b,
                "load_api_key",
                return_value=DUMMY_KEY,
            ) as first_load_key:
                first_code, first_output = self.invoke(
                    [
                        "--env-file", str(root / "approved.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=first_factory,
                )

            self.assertEqual(first_code, 2)
            self.assertEqual(first_load_key.call_count, 1)
            self.assertEqual(first_factory.call_count, 1)
            self.assertTrue(batch_directory.is_dir())
            self.assertEqual(list(batch_directory.iterdir()), [])
            self.assertEqual(
                list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json")),
                [],
            )
            self.assertEqual(
                list((output_root / eg6b.METADATA_OUTPUT_PATH).rglob("*.metadata.json")),
                [],
            )
            self.assertEqual(parse_summary(first_output)["collection_log_saved"], "false")
            self.assertEqual(parse_summary(first_output)["manifest_saved"], "false")
            self.assertFalse(
                backup.assess_batch(output_root / eg6b.STAGE_PATH, BATCH_ID).eligible
            )

            second_factory = mock.Mock(return_value=FakeTransport())
            with mock.patch.object(eg6b, "load_api_key") as second_load_key:
                second_code, second_output = self.invoke(
                    [
                        "--env-file", str(root / "approved.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=second_factory,
                )
            self.assertEqual(second_code, 2)
            self.assertIn("preflight_status=batch_id_conflict", second_output)
            second_load_key.assert_not_called()
            second_factory.assert_not_called()
            self.assertEqual(list(batch_directory.iterdir()), [])

    def test_invalid_panel_fails_before_transport_and_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            references = self.copied_references(root)
            text = references.area_panel.read_text(encoding="utf-8")
            references.area_panel.write_text(text.replace("POI019", "POI999", 1), encoding="utf-8")
            factory = mock.Mock(return_value=FakeTransport())
            output_root = root / "output"
            code, _ = self.invoke(
                [
                    "--env-file", str(self.write_env(root)),
                    "--output-root", str(output_root),
                    "--batch-id", BATCH_ID,
                    "--execute-live",
                ],
                transport_factory=factory,
                reference_paths=references,
            )
        self.assertEqual(code, 2)
        factory.assert_not_called()
        self.assertFalse(output_root.exists())

    def test_reference_change_mid_batch_stops_without_retry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            references = self.copied_references(root)

            def mutate_reference(area_code: str, call_count: int) -> None:
                del area_code
                if call_count == 1:
                    references.area_panel.write_bytes(references.area_panel.read_bytes() + b"\n")

            transport = FakeTransport(after_response=mutate_reference)
            code, output, output_root = self.run_fake(
                root,
                transport,
                reference_paths=references,
            )
            raw_paths = list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json"))
        self.assertEqual(code, 2)
        self.assertEqual(transport.calls, [eg6b.EG6B_AREA_CODES[0]])
        self.assertEqual(len(raw_paths), 1)
        self.assertEqual(parse_summary(output)["hash_verification_passed"], "false")

    def test_common_storage_failure_stops_and_preserves_prior_successes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            code, output, output_root = self.run_fake(
                root,
                transport,
                storage_factory=FailThirdRawStorage,
            )
            raw_paths = list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json"))
            _, log, _, _ = self.batch_documents(output_root)
            reservation_exists = (output_root / eg6b.BATCH_OUTPUT_PATH / BATCH_ID).is_dir()
            before = {
                path.relative_to(output_root).as_posix(): sha256(path) for path in raw_paths
            }
            eligibility = backup.assess_batch(output_root / eg6b.STAGE_PATH, BATCH_ID)
            second_transport = FakeTransport()
            second_factory = mock.Mock(return_value=second_transport)
            with mock.patch.object(eg6b, "load_api_key") as second_load_key:
                second_code, second_output = self.invoke(
                    [
                        "--env-file", str(root / "dummy.env"),
                        "--output-root", str(output_root),
                        "--batch-id", BATCH_ID,
                        "--execute-live",
                    ],
                    transport_factory=second_factory,
                )
            after_paths = list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json"))
            after = {
                path.relative_to(output_root).as_posix(): sha256(path) for path in after_paths
            }

            self.assertEqual(code, 2)
            self.assertEqual(transport.calls, list(eg6b.EG6B_AREA_CODES[:3]))
            self.assertEqual(len(raw_paths), 2)
            self.assertEqual(log["attempted_count"], 3)
            self.assertEqual(log["success_count"], 2)
            self.assertEqual(log["failure_count"], 11)
            self.assertEqual(parse_summary(output)["retry_count"], "0")
            self.assertTrue(reservation_exists)
            self.assertFalse(eligibility.eligible)
            self.assertEqual(second_code, 2)
            self.assertIn("preflight_status=batch_id_conflict", second_output)
            second_load_key.assert_not_called()
            second_factory.assert_not_called()
            self.assertEqual(second_transport.calls, [])
            self.assertEqual(after, before)

    def test_manifest_write_failure_does_not_delete_raw_or_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            code, output, output_root = self.run_fake(
                root,
                FakeTransport(),
                batch_storage_factory=FailingManifestStorage,
            )
            raw_paths = list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json"))
            metadata_paths = list((output_root / eg6b.METADATA_OUTPUT_PATH).rglob("*.metadata.json"))
            logs = list((output_root / eg6b.BATCH_OUTPUT_PATH).rglob("collection_log.json"))
            manifests = list((output_root / eg6b.BATCH_OUTPUT_PATH).rglob("manifest.json"))
        self.assertEqual(code, 2)
        self.assertEqual(len(raw_paths), 13)
        self.assertEqual(len(metadata_paths), 13)
        self.assertEqual(logs, [])
        self.assertEqual(manifests, [])
        self.assertEqual(parse_summary(output)["collection_log_saved"], "false")
        self.assertEqual(parse_summary(output)["manifest_saved"], "false")

    def test_hash_verification_detects_tampered_raw(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            code, output, output_root = self.run_fake(
                root,
                FakeTransport(),
                batch_storage_factory=TamperingBatchStorage,
            )
            logs = list((output_root / eg6b.BATCH_OUTPUT_PATH).rglob("collection_log.json"))
        self.assertEqual(code, 2)
        self.assertEqual(logs, [])
        summary = parse_summary(output)
        self.assertEqual(summary["collection_log_saved"], "false")
        self.assertEqual(summary["manifest_saved"], "true")
        self.assertEqual(summary["hash_verification_passed"], "false")

    def test_collection_log_publish_failure_has_no_misleading_final_log(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            code, output, output_root = self.run_fake(
                root,
                FakeTransport(),
                batch_storage_factory=FailingCollectionLogStorage,
            )
            raw_paths = list((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json"))
            metadata_paths = list((output_root / eg6b.METADATA_OUTPUT_PATH).rglob("*.metadata.json"))
            logs = list((output_root / eg6b.BATCH_OUTPUT_PATH).rglob("collection_log.json"))
            manifests = list((output_root / eg6b.BATCH_OUTPUT_PATH).rglob("manifest.json"))
        self.assertEqual(code, 2)
        self.assertEqual(len(raw_paths), 13)
        self.assertEqual(len(metadata_paths), 13)
        self.assertEqual(logs, [])
        self.assertEqual(len(manifests), 1)
        self.assertNotIn("private collection log detail", output)
        summary = parse_summary(output)
        self.assertEqual(summary["collection_log_saved"], "false")
        self.assertEqual(summary["hash_verification_passed"], "false")

    def test_stage_paths_are_automatic_and_separated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            _, _, output_root = self.run_fake(root, FakeTransport())
            raw = next((output_root / eg6b.RAW_OUTPUT_PATH).rglob("*.json"))
            metadata = next((output_root / eg6b.METADATA_OUTPUT_PATH).rglob("*.metadata.json"))
            log, _, manifest, _ = self.batch_documents(output_root)
        self.assertEqual(raw.relative_to(output_root).parts[:2], eg6b.STAGE_PATH.parts)
        self.assertEqual(metadata.relative_to(output_root).parts[:2], eg6b.STAGE_PATH.parts)
        self.assertNotEqual(raw.parent, metadata.parent)
        self.assertEqual(log.parent, manifest.parent)

    def test_console_does_not_expose_key_url_payload_or_absolute_output_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            transport = FakeTransport()
            _, output, output_root = self.run_fake(root, transport)
        self.assertNotIn(DUMMY_KEY, output)
        self.assertNotIn("http://", output)
        self.assertNotIn("https://", output)
        self.assertNotIn(str(output_root.resolve()), output)
        self.assertNotIn("SeoulRtd.citydata_ppltn", output)
        self.assertTrue(all(DUMMY_KEY in url for url in transport.full_urls))

    def test_project_output_path_is_rejected_without_creation(self) -> None:
        output_root = ROOT / "eg6b-forbidden-test-output"
        self.assertFalse(output_root.exists())
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            factory = mock.Mock(return_value=FakeTransport())
            code, _ = self.invoke(
                [
                    "--env-file", str(self.write_env(root)),
                    "--output-root", str(output_root),
                    "--batch-id", BATCH_ID,
                    "--execute-live",
                ],
                transport_factory=factory,
            )
        self.assertEqual(code, 2)
        factory.assert_not_called()
        self.assertFalse(output_root.exists())

    def test_probe_files_are_removed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            _, _, output_root = self.run_fake(root, FakeTransport())
            probes = list(output_root.rglob(f"{eg6b.PROBE_FILE_PREFIX}*"))
            partials = list(output_root.rglob("*.partial"))
        self.assertEqual(probes, [])
        self.assertEqual(partials, [])

    def test_batch_id_collision_never_overwrites_first_batch_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-eg6b-") as temporary:
            root = Path(temporary)
            first_code, _, output_root = self.run_fake(
                root,
                FakeTransport(),
            )
            first_log, _, first_manifest, _ = self.batch_documents(output_root)
            before = (sha256(first_log), sha256(first_manifest))
            second_transport = FakeTransport()
            second_code, _, _ = self.run_fake(
                root,
                second_transport,
            )
            after = (sha256(first_log), sha256(first_manifest))
        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 2)
        self.assertEqual(second_transport.calls, [])
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
