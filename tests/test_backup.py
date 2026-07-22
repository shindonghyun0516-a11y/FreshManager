from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import socket
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest import mock

from freshmanager import backup


BATCH_ID = "11111111-1111-4111-8111-111111111111"
SECOND_BATCH_ID = "22222222-2222-4222-8222-222222222222"
LETTERED_BATCH_ID = "abcdefab-cdef-4abc-8def-abcdefabcdef"
FAKE_PATH_MARKER = "/private/fake-source-root"
TEST_AREA_CODES = (
    "POI019",
    "POI013",
    "POI014",
    "POI072",
    "POI001",
    "POI034",
    "POI042",
    "POI025",
    "POI088",
    "POI003",
    "POI119",
    "POI033",
    "POI032",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_bytes(document: object) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def artifact_entry(
    stage_root: Path,
    relative: str,
    artifact_type: str,
    area_code: str | None,
    request_id: str | None,
) -> dict[str, object]:
    path = stage_root / relative
    return {
        "artifact_type": artifact_type,
        "relative_path": relative,
        "byte_size": path.stat().st_size,
        "sha256": sha256(path),
        "area_code": area_code,
        "request_id": request_id,
    }


def create_fake_batch(
    root: Path,
    *,
    batch_id: str = BATCH_ID,
    partial_failure: bool = False,
    payload_marker: str = "original",
) -> Path:
    stage_root = root / "source" / backup.STAGE_RELATIVE_PATH
    artifacts: list[dict[str, object]] = []
    area_results: list[dict[str, object]] = []
    failed_codes: list[str] = []
    raw_count = 0

    for index, area_code in enumerate(TEST_AREA_CODES, start=1):
        request_id = f"00000000-0000-4000-8000-{index:012d}"
        failed = partial_failure and index == 6
        status_value = "timeout" if failed else "success"
        raw_relative: str | None = None
        if not failed:
            raw_relative = (
                f"data/raw/population/2026/07/22/"
                f"{area_code}_20260722_120000_{request_id}.json"
            )
            write_bytes(
                stage_root / raw_relative,
                json_bytes({"area_code": area_code, "payload_marker": payload_marker}),
            )
            artifacts.append(
                artifact_entry(stage_root, raw_relative, "raw_json", area_code, request_id)
            )
            raw_count += 1
        else:
            failed_codes.append(area_code)

        metadata_relative = (
            f"data/processed/collection_logs/2026/07/22/"
            f"{area_code}_20260722_120000_{request_id}.metadata.json"
        )
        write_bytes(
            stage_root / metadata_relative,
            json_bytes(
                {
                    "request_id": request_id,
                    "area_code": area_code,
                    "endpoint_name": "citydata_ppltn",
                    "requested_at": "2026-07-22T12:00:00+09:00",
                    "received_at": "2026-07-22T12:00:01+09:00",
                    "http_status": None if failed else 200,
                    "collection_status": status_value,
                    "raw_file_path": (
                        f"{FAKE_PATH_MARKER}/{raw_relative}" if raw_relative else None
                    ),
                }
            ),
        )
        artifacts.append(
            artifact_entry(stage_root, metadata_relative, "metadata", area_code, request_id)
        )
        area_results.append(
            {
                "panel_order": index,
                "area_code": area_code,
                "request_id": request_id,
                "attempted": True,
                "collection_status": status_value,
                "raw_file": raw_relative,
                "metadata_file": metadata_relative,
            }
        )

    log_relative = (
        backup.BATCHES_RELATIVE_PATH / batch_id / "collection_log.json"
    ).as_posix()
    log_document = {
        "collector_version": "eg6b-collector-v1",
        "data_version": "eg6b-data-v1",
        "batch_id": batch_id,
        "panel_version": "eg6a-v1",
        "collection_purpose": "single_collection",
        "expected_area_count": backup.EXPECTED_AREA_COUNT,
        "scheduled_at": None,
        "started_at": "2026-07-22T12:00:00+09:00",
        "finished_at": "2026-07-22T12:00:13+09:00",
        "elapsed_seconds": 13.0,
        "attempted_count": backup.EXPECTED_AREA_COUNT,
        "success_count": backup.EXPECTED_AREA_COUNT - len(failed_codes),
        "failure_count": len(failed_codes),
        "failed_area_codes": failed_codes,
        "retry_count": 0,
        "raw_file_count": raw_count,
        "metadata_file_count": backup.EXPECTED_AREA_COUNT,
        "exit_code": 1 if partial_failure else 0,
        "area_results": area_results,
    }
    write_bytes(stage_root / log_relative, json_bytes(log_document))
    artifacts.append(
        artifact_entry(stage_root, log_relative, "collection_log", None, None)
    )

    manifest_relative = (
        backup.BATCHES_RELATIVE_PATH / batch_id / "manifest.json"
    ).as_posix()
    manifest_document = {
        "data_version": "eg6b-data-v1",
        "batch_id": batch_id,
        "created_at": "2026-07-22T12:00:13+09:00",
        "hash_algorithm": "sha256",
        "reference_files": [
            {
                "reference_type": reference_type,
                "path": path,
                "byte_size": 10,
                "sha256": "a" * 64,
            }
            for reference_type, path in (
                ("official_places", "data/reference/seoul_121_places.csv"),
                ("area_panel", "data/reference/eg6_area_panel.csv"),
                ("spot_master", "data/reference/eg6_spot_master.csv"),
                ("sdot_links", "data/reference/eg6_sdot_links.csv"),
            )
        ],
        "artifacts": artifacts,
    }
    write_bytes(stage_root / manifest_relative, json_bytes(manifest_document))
    return stage_root


def manifest_path(stage_root: Path, batch_id: str = BATCH_ID) -> Path:
    return stage_root / backup.BATCHES_RELATIVE_PATH / batch_id / "manifest.json"


def log_path(stage_root: Path, batch_id: str = BATCH_ID) -> Path:
    return stage_root / backup.BATCHES_RELATIVE_PATH / batch_id / "collection_log.json"


def load_document(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def rewrite_document(path: Path, document: dict[str, object]) -> None:
    write_bytes(path, json_bytes(document))


def rewrite_log_and_manifest(
    stage_root: Path,
    mutate: Callable[[dict[str, object]], None],
    batch_id: str = BATCH_ID,
) -> None:
    path = log_path(stage_root, batch_id)
    document = load_document(path)
    mutate(document)
    rewrite_document(path, document)
    manifest = load_document(manifest_path(stage_root, batch_id))
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    for item in artifacts:
        assert isinstance(item, dict)
        if item.get("artifact_type") == "collection_log":
            item["byte_size"] = path.stat().st_size
            item["sha256"] = sha256(path)
    rewrite_document(manifest_path(stage_root, batch_id), manifest)


def refresh_manifest_artifact(stage_root: Path, relative_path: str) -> None:
    manifest = load_document(manifest_path(stage_root))
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, list)
    path = stage_root / relative_path
    for item in artifacts:
        assert isinstance(item, dict)
        if item.get("relative_path") == relative_path:
            item["byte_size"] = path.stat().st_size
            item["sha256"] = sha256(path)
            break
    else:
        raise AssertionError("artifact not found")
    rewrite_document(manifest_path(stage_root), manifest)


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


class BackupWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="freshmanager-backup-test-")
        self.root = Path(self.temporary.name)
        self.sync_root = self.root / "sync"
        self.sync_root.mkdir()
        self.ledger_root = self.root / "source" / backup.LEDGER_RELATIVE_PATH

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def destination(self, batch_id: str = BATCH_ID) -> Path:
        return self.sync_root / backup.DESTINATION_RELATIVE_PATH / batch_id

    def receipts(self, batch_id: str = BATCH_ID) -> list[Path]:
        directory = self.ledger_root / "receipts" / batch_id
        return sorted(directory.glob("*.receipt.json")) if directory.exists() else []

    def test_complete_success_batch_is_eligible(self) -> None:
        stage = create_fake_batch(self.root)
        result = backup.assess_batch(stage, BATCH_ID)
        self.assertTrue(result.eligible)
        self.assertEqual(result.eligible_batch_type, backup.ELIGIBLE_SUCCESS)
        self.assertEqual(result.source_file_count, 28)

    def test_complete_partial_failure_batch_is_eligible(self) -> None:
        stage = create_fake_batch(self.root, partial_failure=True)
        result = backup.assess_batch(stage, BATCH_ID)
        self.assertTrue(result.eligible)
        self.assertEqual(result.eligible_batch_type, backup.ELIGIBLE_PARTIAL_FAILURE)
        self.assertEqual(result.source_file_count, 27)

    def test_complete_success_batch_is_backed_up(self) -> None:
        stage = create_fake_batch(self.root)
        result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        verification = backup.verify_backup_copy(self.destination())
        self.assertEqual(result.backup_status, backup.BackupStatus.LOCAL_SYNC_COPY_VERIFIED)
        self.assertEqual(result.reason_code, "LOCAL_SYNC_COPY_VERIFIED")
        self.assertTrue(result.receipt_written)
        self.assertTrue(verification.verified)
        self.assertEqual(result.verified_file_count, result.source_file_count)

    def test_complete_partial_failure_batch_is_backed_up(self) -> None:
        stage = create_fake_batch(self.root, partial_failure=True)
        result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        self.assertEqual(result.backup_status, backup.BackupStatus.LOCAL_SYNC_COPY_VERIFIED)
        self.assertEqual(result.eligible_batch_type, backup.ELIGIBLE_PARTIAL_FAILURE)
        self.assertTrue(backup.verify_backup_copy(self.destination()).verified)

    def test_exit_code_two_is_excluded(self) -> None:
        stage = create_fake_batch(self.root)
        rewrite_log_and_manifest(stage, lambda document: document.update({"exit_code": 2}))
        result = backup.assess_batch(stage, BATCH_ID)
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason_code, "EXIT_CODE_INELIGIBLE")

    def test_missing_manifest_is_excluded(self) -> None:
        stage = create_fake_batch(self.root)
        manifest_path(stage).unlink()
        result = backup.assess_batch(stage, BATCH_ID)
        self.assertEqual(result.reason_code, "MANIFEST_MISSING")

    def test_missing_collection_log_is_excluded(self) -> None:
        stage = create_fake_batch(self.root)
        log_path(stage).unlink()
        result = backup.assess_batch(stage, BATCH_ID)
        self.assertEqual(result.reason_code, "COLLECTION_LOG_MISSING")
        self.assertTrue(result.retryable)

    def test_not_attempted_area_is_excluded(self) -> None:
        stage = create_fake_batch(self.root)

        def mutate(document: dict[str, object]) -> None:
            results = document["area_results"]
            assert isinstance(results, list) and isinstance(results[-1], dict)
            results[-1]["attempted"] = False
            results[-1]["collection_status"] = "not_attempted"
            document["attempted_count"] = 12
            document["exit_code"] = 2

        rewrite_log_and_manifest(stage, mutate)
        self.assertFalse(backup.assess_batch(stage, BATCH_ID).eligible)

    def test_collection_log_file_count_mismatch_is_excluded(self) -> None:
        stage = create_fake_batch(self.root)
        rewrite_log_and_manifest(stage, lambda document: document.update({"raw_file_count": 12}))
        self.assertEqual(backup.assess_batch(stage, BATCH_ID).reason_code, "FILE_COUNT_MISMATCH")

    def test_metadata_must_match_collection_log_evidence(self) -> None:
        stage = create_fake_batch(self.root)
        log = load_document(log_path(stage))
        area_results = log["area_results"]
        assert isinstance(area_results, list)
        first = area_results[0]
        assert isinstance(first, dict)
        metadata_relative = str(first["metadata_file"])
        metadata = load_document(stage / metadata_relative)
        metadata["collection_status"] = "timeout"
        rewrite_document(stage / metadata_relative, metadata)
        refresh_manifest_artifact(stage, metadata_relative)
        result = backup.assess_batch(stage, BATCH_ID)
        self.assertFalse(result.eligible)
        self.assertEqual(result.reason_code, "AREA_EVIDENCE_INCOMPLETE")

    def test_manifest_size_mismatch_is_excluded(self) -> None:
        stage = create_fake_batch(self.root)
        manifest = load_document(manifest_path(stage))
        artifacts = manifest["artifacts"]
        assert isinstance(artifacts, list) and isinstance(artifacts[0], dict)
        artifacts[0]["byte_size"] = int(artifacts[0]["byte_size"]) + 1
        rewrite_document(manifest_path(stage), manifest)
        self.assertEqual(backup.assess_batch(stage, BATCH_ID).reason_code, "SIZE_MISMATCH")

    def test_manifest_sha256_mismatch_is_excluded(self) -> None:
        stage = create_fake_batch(self.root)
        manifest = load_document(manifest_path(stage))
        artifacts = manifest["artifacts"]
        assert isinstance(artifacts, list) and isinstance(artifacts[0], dict)
        artifacts[0]["sha256"] = "b" * 64
        rewrite_document(manifest_path(stage), manifest)
        self.assertEqual(backup.assess_batch(stage, BATCH_ID).reason_code, "SHA256_MISMATCH")

    def test_root_escape_and_absolute_artifact_paths_are_excluded(self) -> None:
        for bad_path in ("../escape.json", "/absolute/escape.json"):
            with self.subTest(bad_path=bad_path):
                shutil.rmtree(self.root / "source", ignore_errors=True)
                stage = create_fake_batch(self.root)
                manifest = load_document(manifest_path(stage))
                artifacts = manifest["artifacts"]
                assert isinstance(artifacts, list) and isinstance(artifacts[0], dict)
                artifacts[0]["relative_path"] = bad_path
                rewrite_document(manifest_path(stage), manifest)
                self.assertEqual(
                    backup.assess_batch(stage, BATCH_ID).reason_code,
                    "ARTIFACT_PATH_UNSAFE",
                )

    def test_symlink_and_special_file_artifacts_are_excluded(self) -> None:
        for special in ("symlink", "fifo"):
            with self.subTest(special=special):
                shutil.rmtree(self.root / "source", ignore_errors=True)
                stage = create_fake_batch(self.root)
                manifest = load_document(manifest_path(stage))
                artifacts = manifest["artifacts"]
                assert isinstance(artifacts, list) and isinstance(artifacts[0], dict)
                path = stage / str(artifacts[0]["relative_path"])
                path.unlink()
                if special == "symlink":
                    target = self.root / "safe-target"
                    target.write_text("target", encoding="utf-8")
                    path.symlink_to(target)
                else:
                    os.mkfifo(path)
                self.assertEqual(
                    backup.assess_batch(stage, BATCH_ID).reason_code,
                    "ARTIFACT_NOT_REGULAR",
                )

    def test_forbidden_env_probe_partial_and_temporary_artifacts_are_excluded(self) -> None:
        for filename in (".env", "write-probe.json", "copy.partial", "temporary.json"):
            with self.subTest(filename=filename):
                shutil.rmtree(self.root / "source", ignore_errors=True)
                stage = create_fake_batch(self.root)
                relative = f"data/{filename}"
                write_bytes(stage / relative, b"forbidden")
                manifest = load_document(manifest_path(stage))
                artifacts = manifest["artifacts"]
                assert isinstance(artifacts, list)
                artifacts.append(
                    artifact_entry(stage, relative, "metadata", "POI001", "request")
                )
                rewrite_document(manifest_path(stage), manifest)
                self.assertEqual(
                    backup.assess_batch(stage, BATCH_ID).reason_code,
                    "FORBIDDEN_ARTIFACT",
                )

    def test_same_batch_is_idempotent(self) -> None:
        stage = create_fake_batch(self.root)
        first = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        before = tree_hashes(self.destination())
        second = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        self.assertEqual(first.backup_status, backup.BackupStatus.LOCAL_SYNC_COPY_VERIFIED)
        self.assertEqual(second.backup_status, backup.BackupStatus.LOCAL_SYNC_COPY_VERIFIED)
        self.assertEqual(second.reason_code, "ALREADY_VERIFIED")
        self.assertEqual(second.copied_file_count, 0)
        self.assertEqual(before, tree_hashes(self.destination()))

    def test_same_batch_id_with_different_content_is_conflict(self) -> None:
        first_stage = create_fake_batch(self.root, payload_marker="first")
        backup.backup_batch(first_stage, self.sync_root, self.ledger_root, BATCH_ID)
        other_root = self.root / "other"
        second_stage = create_fake_batch(other_root, payload_marker="second")
        result = backup.backup_batch(
            second_stage,
            self.sync_root,
            other_root / "source" / backup.LEDGER_RELATIVE_PATH,
            BATCH_ID,
        )
        self.assertEqual(result.backup_status, backup.BackupStatus.CONFLICT)
        self.assertEqual(result.reason_code, "CONFLICT")
        self.assertTrue(result.conflict_detected)

    def test_destination_is_not_a_directory(self) -> None:
        stage = create_fake_batch(self.root)
        bad_destination = self.root / "not-a-directory"
        bad_destination.write_text("blocked", encoding="utf-8")
        result = backup.backup_batch(stage, bad_destination, self.ledger_root, BATCH_ID)
        self.assertEqual(result.reason_code, "DESTINATION_UNSAFE")

    def test_interrupted_copy_has_no_final_and_cleans_temp(self) -> None:
        stage = create_fake_batch(self.root)
        original = backup._copy_one_file
        calls = 0

        def interrupt(source: Path, destination: Path) -> bool:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise backup.BackupOperationalError("COPY_FAILED")
            return original(source, destination)

        with mock.patch.object(backup, "_copy_one_file", side_effect=interrupt):
            result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        parent = self.sync_root / backup.DESTINATION_RELATIVE_PATH
        leftovers = list(parent.glob(f".freshmanager-incoming-{BATCH_ID}-*.partial"))
        self.assertEqual(result.reason_code, "COPY_FAILED")
        self.assertFalse(self.destination().exists())
        self.assertEqual(leftovers, [])

    def test_destination_write_failure_before_first_file_has_no_final(self) -> None:
        stage = create_fake_batch(self.root)
        with mock.patch.object(
            backup,
            "_copy_one_file",
            side_effect=backup.BackupOperationalError("COPY_FAILED"),
        ):
            result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        self.assertEqual(result.reason_code, "COPY_FAILED")
        self.assertEqual(result.copied_file_count, 0)
        self.assertFalse(self.destination().exists())

    def test_source_is_immutable_after_success_and_failure(self) -> None:
        stage = create_fake_batch(self.root)
        before = tree_hashes(stage)
        backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        self.assertEqual(before, tree_hashes(stage))
        other_root = self.root / "failed"
        failed_stage = create_fake_batch(other_root, batch_id=SECOND_BATCH_ID)
        failed_before = tree_hashes(failed_stage)
        with mock.patch.object(
            backup,
            "_copy_one_file",
            side_effect=backup.BackupOperationalError("COPY_FAILED"),
        ):
            backup.backup_batch(
                failed_stage,
                self.sync_root,
                other_root / "source" / backup.LEDGER_RELATIVE_PATH,
                SECOND_BATCH_ID,
            )
        self.assertEqual(failed_before, tree_hashes(failed_stage))

    def test_receipts_use_exact_allowlist_and_no_sensitive_values(self) -> None:
        stage = create_fake_batch(self.root)
        backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        receipts = self.receipts()
        self.assertEqual(len(receipts), 3)
        for path in receipts:
            document = load_document(path)
            self.assertEqual(tuple(document), backup.RECEIPT_FIELDS)
            rendered = json.dumps(document, ensure_ascii=False)
            self.assertNotIn(str(self.root), rendered)
            self.assertNotIn(FAKE_PATH_MARKER, rendered)
            self.assertNotIn("API_KEY", rendered)
            self.assertNotIn("@", rendered)
        final_receipt = load_document(receipts[-1])
        self.assertEqual(
            final_receipt["backup_status"],
            backup.BackupStatus.LOCAL_SYNC_COPY_VERIFIED.value,
        )
        self.assertIsNone(final_receipt["failure_code"])

    def test_cli_and_receipts_do_not_print_real_paths(self) -> None:
        stage = create_fake_batch(self.root)
        del stage
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = backup.run(
                ["--batch-id", BATCH_ID],
                environ={
                    backup.SOURCE_ROOT_ENV: str(self.root / "source"),
                    backup.SYNC_ROOT_ENV: str(self.sync_root),
                },
            )
        self.assertEqual(code, 0)
        self.assertNotIn(str(self.root), output.getvalue())
        self.assertNotIn(FAKE_PATH_MARKER, output.getvalue())
        for path in self.receipts():
            self.assertNotIn(str(self.root), path.read_text(encoding="utf-8"))

    def test_receipt_failure_preserves_verified_copy(self) -> None:
        stage = create_fake_batch(self.root)
        original = backup._write_receipt_event
        calls = 0

        def fail_final(ledger_root: Path, document: dict[str, object]) -> None:
            nonlocal calls
            calls += 1
            if calls == 3:
                raise backup.BackupOperationalError("RECEIPT_WRITE_FAILED")
            original(ledger_root, document)

        with mock.patch.object(backup, "_write_receipt_event", side_effect=fail_final):
            result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        self.assertEqual(result.reason_code, "RECEIPT_WRITE_FAILED")
        self.assertFalse(result.receipt_written)
        self.assertTrue(backup.verify_backup_copy(self.destination()).verified)

    def test_existing_lock_blocks_worker_and_is_not_deleted(self) -> None:
        stage = create_fake_batch(self.root)
        lock_directory = self.ledger_root / "locks"
        lock_directory.mkdir(parents=True)
        lock_path = lock_directory / f"{BATCH_ID}.lock"
        lock_path.write_text(
            json.dumps(
                {
                    "backup_attempt_id": SECOND_BATCH_ID,
                    "created_at": "2020-01-01T00:00:00+09:00",
                    "process_id": 1,
                    "worker_version": backup.WORKER_VERSION,
                }
            ),
            encoding="utf-8",
        )
        result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        self.assertEqual(result.reason_code, "LOCK_HELD")
        self.assertTrue(lock_path.exists())
        self.assertFalse(self.destination().exists())

    def test_stale_lock_is_never_auto_deleted(self) -> None:
        self.test_existing_lock_blocks_worker_and_is_not_deleted()
        lock_path = self.ledger_root / "locks" / f"{BATCH_ID}.lock"
        self.assertTrue(lock_path.exists())

    def test_worker_never_emits_remote_completion_states(self) -> None:
        stage = create_fake_batch(self.root)
        result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        statuses = {load_document(path)["backup_status"] for path in self.receipts()}
        self.assertEqual(result.backup_status, backup.BackupStatus.LOCAL_SYNC_COPY_VERIFIED)
        self.assertNotIn(backup.BackupStatus.REMOTE_SYNC_PENDING.value, statuses)
        self.assertNotIn(backup.BackupStatus.REMOTE_SYNC_CONFIRMED.value, statuses)

    def test_fake_restore_matches_manifest_and_all_hashes(self) -> None:
        stage = create_fake_batch(self.root)
        backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        restore_root = self.root / "restore" / BATCH_ID
        shutil.copytree(self.destination(), restore_root)
        restored = backup.verify_backup_copy(restore_root)
        self.assertTrue(restored.verified)
        self.assertEqual(
            (self.destination() / backup.BATCHES_RELATIVE_PATH / BATCH_ID / "manifest.json").read_bytes(),
            (restore_root / backup.BATCHES_RELATIVE_PATH / BATCH_ID / "manifest.json").read_bytes(),
        )

    def test_backup_never_calls_collector_transport_or_network(self) -> None:
        stage = create_fake_batch(self.root)
        with mock.patch("socket.socket", side_effect=AssertionError("network forbidden")), mock.patch(
            "socket.create_connection", side_effect=AssertionError("network forbidden")
        ), mock.patch("freshmanager.eg6b.run") as collector_run:
            result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        self.assertEqual(result.backup_status, backup.BackupStatus.LOCAL_SYNC_COPY_VERIFIED)
        collector_run.assert_not_called()

    def test_insufficient_space_fails_without_final_copy(self) -> None:
        stage = create_fake_batch(self.root)
        with mock.patch.object(backup, "_available_bytes", return_value=0):
            result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        self.assertEqual(result.reason_code, "INSUFFICIENT_SPACE")
        self.assertFalse(self.destination().exists())

    def test_directory_fsync_unsupported_is_capability_warning(self) -> None:
        stage = create_fake_batch(self.root)
        with mock.patch.object(backup, "_fsync_directory", return_value=False):
            result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        self.assertEqual(result.backup_status, backup.BackupStatus.LOCAL_SYNC_COPY_VERIFIED)
        self.assertIn(backup.DIRECTORY_FSYNC_UNSUPPORTED, result.capability_warnings)

    def test_file_fsync_unsupported_is_capability_warning(self) -> None:
        stage = create_fake_batch(self.root)
        original = backup._copy_one_file

        def report_unsupported(source: Path, destination: Path) -> bool:
            original(source, destination)
            return False

        with mock.patch.object(backup, "_copy_one_file", side_effect=report_unsupported):
            result = backup.backup_batch(stage, self.sync_root, self.ledger_root, BATCH_ID)
        self.assertEqual(result.backup_status, backup.BackupStatus.LOCAL_SYNC_COPY_VERIFIED)
        self.assertIn(backup.FILE_FSYNC_UNSUPPORTED, result.capability_warnings)

    def test_cli_exit_codes(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.assertEqual(backup.run([], environ={}), 2)
            self.assertEqual(backup.run(["--batch-id", BATCH_ID], environ={}), 2)

            stage = create_fake_batch(self.root)
            log_path(stage).unlink()
            environment = {
                backup.SOURCE_ROOT_ENV: str(self.root / "source"),
                backup.SYNC_ROOT_ENV: str(self.sync_root),
            }
            self.assertEqual(backup.run(["--batch-id", BATCH_ID], environ=environment), 3)

            shutil.rmtree(self.root / "source")
            stage = create_fake_batch(self.root)
            with mock.patch.object(backup, "_available_bytes", return_value=0):
                self.assertEqual(backup.run(["--batch-id", BATCH_ID], environ=environment), 4)

            with mock.patch.object(backup, "_available_bytes", return_value=10**15):
                self.assertEqual(backup.run(["--batch-id", BATCH_ID], environ=environment), 0)
            other_root = self.root / "conflict"
            create_fake_batch(other_root, payload_marker="changed")
            conflict_environment = {
                backup.SOURCE_ROOT_ENV: str(other_root / "source"),
                backup.SYNC_ROOT_ENV: str(self.sync_root),
            }
            self.assertEqual(backup.run(["--batch-id", BATCH_ID], environ=conflict_environment), 5)

    def test_cli_rejects_noncanonical_batch_id_without_normalizing(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.assertEqual(backup.run(["--batch-id", LETTERED_BATCH_ID.upper()], environ={}), 2)
            self.assertEqual(backup.run(["--batch-id", f" {BATCH_ID}"], environ={}), 2)
        self.assertNotIn(BATCH_ID, output.getvalue())
        self.assertNotIn(LETTERED_BATCH_ID, output.getvalue().lower())

    def test_backup_failure_does_not_invoke_collector(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), mock.patch(
            "freshmanager.eg6b.run"
        ) as collector_run:
            code = backup.run(["--batch-id", BATCH_ID], environ={})
        self.assertEqual(code, 2)
        collector_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
