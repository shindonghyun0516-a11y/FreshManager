"""Offline-safe one-shot backup worker for completed EG-6B batches.

The worker copies immutable batch evidence to a Google Drive for Desktop
*local sync folder*.  It never calls Google Drive or Seoul APIs and it never
loads the collector's ``.env`` file.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Mapping

from .batch_id import BATCH_ID_PATTERN, BatchIdValidationError, canonical_batch_id


WORKER_VERSION = "backup-worker-v1"
RECEIPT_VERSION = "backup-receipt-v1"
EXPECTED_AREA_COUNT = 13
MAX_CONTROL_FILE_BYTES = 5 * 1024 * 1024
MINIMUM_SPACE_MARGIN_BYTES = 256 * 1024 * 1024

SOURCE_ROOT_ENV = "FRESHMANAGER_EG6B_OUTPUT_ROOT"
SYNC_ROOT_ENV = "FRESHMANAGER_BACKUP_SYNC_ROOT"
STAGE_RELATIVE_PATH = Path("stages/eg6b_single_13")
BATCHES_RELATIVE_PATH = Path("data/processed/batches")
LEDGER_RELATIVE_PATH = Path("backup-ledger/eg6b-single-13")
LOGICAL_DESTINATION = "FreshManager-Data/01_raw-backup/eg6b-single-13"
DESTINATION_RELATIVE_PATH = Path("FreshManager-Data/01_raw-backup/eg6b-single-13")
PROJECT_ROOT = Path(__file__).resolve().parent.parent

ELIGIBLE_SUCCESS = "SUCCESS"
ELIGIBLE_PARTIAL_FAILURE = "PARTIAL_FAILURE"
RESTORE_NOT_RUN = "NOT_RUN"
DIRECTORY_FSYNC_UNSUPPORTED = "DIRECTORY_FSYNC_UNSUPPORTED"
FILE_FSYNC_UNSUPPORTED = "FILE_FSYNC_UNSUPPORTED"
IGNORED_PLATFORM_METADATA_BASENAME = ".DS_Store"
SYMLINK_BATCH_ROOT_REJECTED = "SYMLINK_BATCH_ROOT_REJECTED"
CANONICAL_VERIFIED_WITH_IGNORED_PLATFORM_METADATA = (
    "CANONICAL_BACKUP_VERIFIED_WITH_IGNORED_PLATFORM_METADATA"
)

SUCCESS_STATUSES = {"success"}
AREA_FAILURE_STATUSES = {"api_error", "timeout", "parse_error", "validation_error"}
ARTIFACT_TYPES = {"raw_json", "metadata", "collection_log"}
REFERENCE_PATHS = {
    "official_places": "data/reference/seoul_121_places.csv",
    "area_panel": "data/reference/eg6_area_panel.csv",
    "spot_master": "data/reference/eg6_spot_master.csv",
    "sdot_links": "data/reference/eg6_sdot_links.csv",
}
REFERENCE_TYPES = set(REFERENCE_PATHS)
METADATA_FIELDS = {
    "request_id",
    "area_code",
    "endpoint_name",
    "requested_at",
    "received_at",
    "http_status",
    "collection_status",
    "raw_file_path",
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class BackupStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    LOCAL_SYNC_COPY_VERIFIED = "LOCAL_SYNC_COPY_VERIFIED"
    REMOTE_SYNC_PENDING = "REMOTE_SYNC_PENDING"
    REMOTE_SYNC_CONFIRMED = "REMOTE_SYNC_CONFIRMED"
    FAILED = "FAILED"
    CONFLICT = "CONFLICT"


WORKER_EMITTABLE_STATUSES = frozenset(
    {
        BackupStatus.PENDING,
        BackupStatus.IN_PROGRESS,
        BackupStatus.LOCAL_SYNC_COPY_VERIFIED,
        BackupStatus.FAILED,
        BackupStatus.CONFLICT,
    }
)


class CliInputError(ValueError):
    """Raised for a sanitized CLI contract failure."""


class EligibilityError(ValueError):
    """Raised internally with a non-sensitive eligibility reason code."""

    def __init__(self, reason_code: str, *, retryable: bool = False) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.retryable = retryable


class BackupOperationalError(OSError):
    """Raised internally with a non-sensitive operational reason code."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True)
class BackupArtifact:
    artifact_type: str
    relative_path: str
    byte_size: int
    sha256: str
    area_code: str | None
    request_id: str | None


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    eligible_batch_type: str | None
    reason_code: str
    retryable: bool
    batch_id: str
    source_manifest_sha256: str | None
    source_file_count: int


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    reason_code: str
    batch_id: str
    manifest_sha256: str | None
    expected_file_count: int
    verified_file_count: int
    total_tree_file_count: int = 0
    canonical_backup_file_count: int = 0
    ignored_platform_metadata_count: int = 0
    unknown_additional_file_count: int = 0
    unexpected_directory_count: int = 0

    @property
    def canonical_source_file_count(self) -> int:
        return self.expected_file_count

    @property
    def canonical_count_match(self) -> bool:
        return self.expected_file_count == self.canonical_backup_file_count

    @property
    def ignored_platform_metadata_type(self) -> str | None:
        if self.ignored_platform_metadata_count:
            return IGNORED_PLATFORM_METADATA_BASENAME
        return None


@dataclass(frozen=True)
class BackupResult:
    backup_status: BackupStatus
    reason_code: str
    batch_id: str
    eligible_batch_type: str | None
    source_manifest_sha256: str | None
    source_file_count: int
    copied_file_count: int
    verified_file_count: int
    conflict_detected: bool
    receipt_written: bool
    capability_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _BatchPlan:
    stage_root: Path
    batch_id: str
    manifest_relative_path: str
    manifest_sha256: str
    artifacts: tuple[BackupArtifact, ...]
    eligible_batch_type: str

    @property
    def source_file_count(self) -> int:
        return len(self.artifacts) + 1

    @property
    def source_file_bytes(self) -> int:
        manifest_path = self.stage_root / self.manifest_relative_path
        return sum(item.byte_size for item in self.artifacts) + manifest_path.stat().st_size


@dataclass(frozen=True)
class _LockHandle:
    path: Path
    attempt_id: str


@dataclass(frozen=True)
class _TreeInventory:
    total_file_count: int
    canonical_file_count: int
    ignored_platform_metadata_count: int
    unknown_additional_file_count: int
    unexpected_directory_count: int


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise CliInputError("CLI_INPUT_ERROR")


def _now() -> datetime:
    return datetime.now().astimezone()


def _canonical_batch_id(value: str) -> str:
    try:
        return canonical_batch_id(value)
    except BatchIdValidationError as error:
        raise CliInputError("CLI_INPUT_ERROR") from error


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(description="완료된 EG-6B Batch의 로컬 동기화 복사본 검증")
    parser.add_argument("--batch-id", required=True, type=_canonical_batch_id)
    return parser


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _paths_overlap(left: Path, right: Path) -> bool:
    return _is_within(left, right) or _is_within(right, left)


def _safe_relative_path(value: object, *, forbidden_check: bool = True) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise EligibilityError("ARTIFACT_PATH_UNSAFE")
    pure = PurePosixPath(value)
    if pure.is_absolute() or value != pure.as_posix() or any(part in {"", ".", ".."} for part in pure.parts):
        raise EligibilityError("ARTIFACT_PATH_UNSAFE")
    if forbidden_check and _forbidden_path(pure):
        raise EligibilityError("FORBIDDEN_ARTIFACT")
    return value


def _forbidden_path(path: PurePosixPath) -> bool:
    for part in path.parts:
        lowered = part.casefold()
        if (
            part == IGNORED_PLATFORM_METADATA_BASENAME
            or lowered == ".env"
            or lowered.startswith(".env.")
            or "probe" in lowered
            or "partial" in lowered
            or "temporary" in lowered
        ):
            return True
    return False


def _regular_file(path: Path, *, missing_reason: str = "ARTIFACT_MISSING") -> os.stat_result:
    try:
        information = path.lstat()
    except FileNotFoundError as error:
        raise EligibilityError(missing_reason, retryable=True) from error
    except OSError as error:
        raise EligibilityError("ARTIFACT_MISSING", retryable=True) from error
    if stat.S_ISLNK(information.st_mode) or not stat.S_ISREG(information.st_mode):
        raise EligibilityError("ARTIFACT_NOT_REGULAR")
    return information


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _resolve_real_batch_root(path: Path) -> Path:
    """Resolve one real directory without losing final-component symlink evidence."""

    try:
        original_information = path.lstat()
    except (FileNotFoundError, NotADirectoryError) as error:
        raise EligibilityError("SOURCE_BATCH_NOT_FOUND", retryable=True) from error
    except OSError as error:
        raise EligibilityError("SOURCE_BATCH_NOT_FOUND", retryable=True) from error
    if stat.S_ISLNK(original_information.st_mode):
        raise EligibilityError(SYMLINK_BATCH_ROOT_REJECTED)
    if not stat.S_ISDIR(original_information.st_mode):
        raise EligibilityError("SOURCE_BATCH_NOT_FOUND", retryable=True)

    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        try:
            current_information = path.lstat()
        except OSError:
            current_information = None
        if current_information is not None and stat.S_ISLNK(current_information.st_mode):
            raise EligibilityError(SYMLINK_BATCH_ROOT_REJECTED) from error
        raise EligibilityError("SOURCE_BATCH_NOT_FOUND", retryable=True) from error

    try:
        opened_information = os.fstat(descriptor)
        current_information = path.lstat()
        if stat.S_ISLNK(current_information.st_mode):
            raise EligibilityError(SYMLINK_BATCH_ROOT_REJECTED)
        if (
            not stat.S_ISDIR(opened_information.st_mode)
            or not stat.S_ISDIR(current_information.st_mode)
            or not _same_file_identity(original_information, opened_information)
            or not _same_file_identity(current_information, opened_information)
        ):
            raise EligibilityError("SOURCE_BATCH_NOT_FOUND", retryable=True)
        try:
            resolved = path.resolve(strict=True)
            resolved_information = resolved.stat()
        except (OSError, RuntimeError) as error:
            raise EligibilityError("SOURCE_BATCH_NOT_FOUND", retryable=True) from error
        if (
            not stat.S_ISDIR(resolved_information.st_mode)
            or not _same_file_identity(opened_information, resolved_information)
        ):
            raise EligibilityError("SOURCE_BATCH_NOT_FOUND", retryable=True)
        return resolved
    except OSError as error:
        raise EligibilityError("SOURCE_BATCH_NOT_FOUND", retryable=True) from error
    finally:
        os.close(descriptor)


def _load_json_object(path: Path, *, missing_reason: str) -> dict[str, object]:
    information = _regular_file(path, missing_reason=missing_reason)
    if information.st_size > MAX_CONTROL_FILE_BYTES:
        raise EligibilityError("CONTROL_FILE_INVALID")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EligibilityError("CONTROL_FILE_INVALID") from error
    if not isinstance(document, dict):
        raise EligibilityError("CONTROL_FILE_INVALID")
    return document


def _nonnegative_int(value: object, reason_code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EligibilityError(reason_code)
    return value


def _required_string(value: object, reason_code: str) -> str:
    if not isinstance(value, str) or not value:
        raise EligibilityError(reason_code)
    return value


def _valid_sha256(value: object, reason_code: str) -> str:
    if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
        raise EligibilityError(reason_code)
    return value


def _manifest_artifacts(document: Mapping[str, object]) -> tuple[BackupArtifact, ...]:
    raw_artifacts = document.get("artifacts")
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise EligibilityError("MANIFEST_INVALID")
    artifacts: list[BackupArtifact] = []
    seen: set[str] = set()
    for raw in raw_artifacts:
        if not isinstance(raw, dict):
            raise EligibilityError("MANIFEST_INVALID")
        artifact_type = _required_string(raw.get("artifact_type"), "MANIFEST_INVALID")
        if artifact_type not in ARTIFACT_TYPES:
            raise EligibilityError("FORBIDDEN_ARTIFACT")
        relative_path = _safe_relative_path(raw.get("relative_path"))
        if relative_path in seen:
            raise EligibilityError("FILE_COUNT_MISMATCH")
        seen.add(relative_path)
        byte_size = _nonnegative_int(raw.get("byte_size"), "SIZE_MISMATCH")
        digest = _valid_sha256(raw.get("sha256"), "SHA256_MISMATCH")
        area_code = raw.get("area_code")
        request_id = raw.get("request_id")
        if area_code is not None and not isinstance(area_code, str):
            raise EligibilityError("MANIFEST_INVALID")
        if request_id is not None and not isinstance(request_id, str):
            raise EligibilityError("MANIFEST_INVALID")
        artifacts.append(
            BackupArtifact(
                artifact_type=artifact_type,
                relative_path=relative_path,
                byte_size=byte_size,
                sha256=digest,
                area_code=area_code,
                request_id=request_id,
            )
        )
    return tuple(artifacts)


def _validate_reference_evidence(document: Mapping[str, object]) -> None:
    references = document.get("reference_files")
    if not isinstance(references, list) or len(references) != len(REFERENCE_TYPES):
        raise EligibilityError("MANIFEST_INVALID")
    seen_types: set[str] = set()
    seen_paths: set[str] = set()
    for raw in references:
        if not isinstance(raw, dict):
            raise EligibilityError("MANIFEST_INVALID")
        reference_type = _required_string(raw.get("reference_type"), "MANIFEST_INVALID")
        path = _safe_relative_path(raw.get("path"))
        _nonnegative_int(raw.get("byte_size"), "MANIFEST_INVALID")
        _valid_sha256(raw.get("sha256"), "MANIFEST_INVALID")
        if (
            reference_type not in REFERENCE_TYPES
            or path != REFERENCE_PATHS[reference_type]
            or reference_type in seen_types
            or path in seen_paths
        ):
            raise EligibilityError("MANIFEST_INVALID")
        seen_types.add(reference_type)
        seen_paths.add(path)
    if seen_types != REFERENCE_TYPES:
        raise EligibilityError("MANIFEST_INVALID")


def _validate_source_artifacts(stage_root: Path, artifacts: tuple[BackupArtifact, ...]) -> None:
    resolved_root = stage_root.resolve()
    for artifact in artifacts:
        candidate = stage_root / artifact.relative_path
        _regular_file(candidate)
        path = candidate.resolve()
        if not _is_within(path, resolved_root):
            raise EligibilityError("ARTIFACT_PATH_UNSAFE")
        information = path.stat()
        if information.st_size != artifact.byte_size:
            raise EligibilityError("SIZE_MISMATCH")
        try:
            digest = _sha256_file(path)
        except OSError as error:
            raise EligibilityError("ARTIFACT_MISSING", retryable=True) from error
        if digest != artifact.sha256:
            raise EligibilityError("SHA256_MISMATCH")


def _artifact_by_path(artifacts: tuple[BackupArtifact, ...]) -> dict[str, BackupArtifact]:
    return {item.relative_path: item for item in artifacts}


def _validate_metadata_evidence(
    stage_root: Path,
    artifact: BackupArtifact,
    *,
    area_code: str,
    request_id: str,
    collection_status: str,
    raw_expected: bool,
) -> None:
    document = _load_json_object(
        stage_root / artifact.relative_path,
        missing_reason="ARTIFACT_MISSING",
    )
    raw_file_path = document.get("raw_file_path")
    if (
        set(document) != METADATA_FIELDS
        or document.get("area_code") != area_code
        or document.get("request_id") != request_id
        or document.get("endpoint_name") != "citydata_ppltn"
        or document.get("collection_status") != collection_status
        or not isinstance(document.get("requested_at"), str)
        or not document.get("requested_at")
        or not isinstance(document.get("received_at"), str)
        or not document.get("received_at")
        or (raw_expected and (not isinstance(raw_file_path, str) or not raw_file_path))
        or (not raw_expected and raw_file_path is not None)
    ):
        raise EligibilityError("AREA_EVIDENCE_INCOMPLETE")


def _validate_collection_log(
    stage_root: Path,
    log: Mapping[str, object],
    manifest: Mapping[str, object],
    artifacts: tuple[BackupArtifact, ...],
    batch_id: str,
) -> str:
    if log.get("batch_id") != batch_id or manifest.get("batch_id") != batch_id:
        raise EligibilityError("BATCH_ID_MISMATCH")
    if manifest.get("hash_algorithm") != "sha256" or manifest.get("data_version") != log.get("data_version"):
        raise EligibilityError("MANIFEST_INVALID")
    exit_code = _nonnegative_int(log.get("exit_code"), "LOG_INVALID")
    if exit_code not in {0, 1}:
        raise EligibilityError("EXIT_CODE_INELIGIBLE")
    expected = _nonnegative_int(log.get("expected_area_count"), "LOG_INVALID")
    attempted = _nonnegative_int(log.get("attempted_count"), "LOG_INVALID")
    success_count = _nonnegative_int(log.get("success_count"), "LOG_INVALID")
    failure_count = _nonnegative_int(log.get("failure_count"), "LOG_INVALID")
    retry_count = _nonnegative_int(log.get("retry_count"), "LOG_INVALID")
    raw_file_count = _nonnegative_int(log.get("raw_file_count"), "LOG_INVALID")
    metadata_file_count = _nonnegative_int(log.get("metadata_file_count"), "LOG_INVALID")
    if (
        expected != EXPECTED_AREA_COUNT
        or attempted != EXPECTED_AREA_COUNT
        or success_count + failure_count != EXPECTED_AREA_COUNT
        or retry_count != 0
    ):
        raise EligibilityError("BATCH_AGGREGATE_MISMATCH")
    if exit_code == 0 and (success_count != EXPECTED_AREA_COUNT or failure_count != 0):
        raise EligibilityError("BATCH_AGGREGATE_MISMATCH")
    if exit_code == 1 and failure_count < 1:
        raise EligibilityError("BATCH_AGGREGATE_MISMATCH")

    area_results = log.get("area_results")
    failed_area_codes = log.get("failed_area_codes")
    if not isinstance(area_results, list) or len(area_results) != EXPECTED_AREA_COUNT:
        raise EligibilityError("BATCH_AGGREGATE_MISMATCH")
    if not isinstance(failed_area_codes, list) or not all(isinstance(item, str) for item in failed_area_codes):
        raise EligibilityError("BATCH_AGGREGATE_MISMATCH")

    artifact_map = _artifact_by_path(artifacts)
    seen_codes: set[str] = set()
    actual_failed: list[str] = []
    actual_raw_count = 0
    actual_metadata_count = 0
    for expected_order, raw_result in enumerate(area_results, start=1):
        if not isinstance(raw_result, dict):
            raise EligibilityError("LOG_INVALID")
        panel_order = _nonnegative_int(raw_result.get("panel_order"), "LOG_INVALID")
        area_code = _required_string(raw_result.get("area_code"), "LOG_INVALID")
        request_id = _required_string(raw_result.get("request_id"), "LOG_INVALID")
        status_value = _required_string(raw_result.get("collection_status"), "LOG_INVALID")
        if panel_order != expected_order or area_code in seen_codes or raw_result.get("attempted") is not True:
            raise EligibilityError("BATCH_AGGREGATE_MISMATCH")
        seen_codes.add(area_code)
        if status_value not in SUCCESS_STATUSES | AREA_FAILURE_STATUSES:
            raise EligibilityError("EXIT_CODE_INELIGIBLE")

        metadata_relative = _safe_relative_path(raw_result.get("metadata_file"))
        metadata_artifact = artifact_map.get(metadata_relative)
        if (
            metadata_artifact is None
            or metadata_artifact.artifact_type != "metadata"
            or metadata_artifact.area_code != area_code
            or metadata_artifact.request_id != request_id
        ):
            raise EligibilityError("AREA_EVIDENCE_INCOMPLETE")
        actual_metadata_count += 1

        raw_relative = raw_result.get("raw_file")
        _validate_metadata_evidence(
            stage_root,
            metadata_artifact,
            area_code=area_code,
            request_id=request_id,
            collection_status=status_value,
            raw_expected=raw_relative is not None,
        )
        if status_value == "success":
            raw_path = _safe_relative_path(raw_relative)
            raw_artifact = artifact_map.get(raw_path)
            if (
                raw_artifact is None
                or raw_artifact.artifact_type != "raw_json"
                or raw_artifact.area_code != area_code
                or raw_artifact.request_id != request_id
            ):
                raise EligibilityError("AREA_EVIDENCE_INCOMPLETE")
            actual_raw_count += 1
        else:
            actual_failed.append(area_code)
            if raw_relative is not None:
                raw_path = _safe_relative_path(raw_relative)
                raw_artifact = artifact_map.get(raw_path)
                if (
                    raw_artifact is None
                    or raw_artifact.artifact_type != "raw_json"
                    or raw_artifact.area_code != area_code
                    or raw_artifact.request_id != request_id
                ):
                    raise EligibilityError("AREA_EVIDENCE_INCOMPLETE")
                actual_raw_count += 1

    expected_log_relative = (BATCHES_RELATIVE_PATH / batch_id / "collection_log.json").as_posix()
    log_artifacts = [item for item in artifacts if item.artifact_type == "collection_log"]
    if (
        len(log_artifacts) != 1
        or log_artifacts[0].relative_path != expected_log_relative
        or log_artifacts[0].area_code is not None
        or log_artifacts[0].request_id is not None
    ):
        raise EligibilityError("AREA_EVIDENCE_INCOMPLETE")
    if (
        actual_failed != failed_area_codes
        or len(actual_failed) != failure_count
        or actual_raw_count != raw_file_count
        or actual_metadata_count != metadata_file_count
        or len(artifacts) != actual_raw_count + actual_metadata_count + 1
    ):
        raise EligibilityError("FILE_COUNT_MISMATCH")
    return ELIGIBLE_SUCCESS if exit_code == 0 else ELIGIBLE_PARTIAL_FAILURE


def _is_ignored_platform_metadata(
    path: Path,
    information: os.stat_result | None = None,
) -> bool:
    if path.name != IGNORED_PLATFORM_METADATA_BASENAME:
        return False
    if information is None:
        try:
            information = path.lstat()
        except OSError:
            return False
    return stat.S_ISREG(information.st_mode)


def _inspect_batch(
    stage_root: Path,
    batch_id: str,
    *,
    allow_noncanonical_entries: bool = False,
) -> _BatchPlan:
    try:
        batch_id = _canonical_batch_id(batch_id)
    except CliInputError as error:
        raise EligibilityError("BATCH_ID_INVALID") from error
    stage_root = _resolve_real_batch_root(stage_root)
    batch_relative = BATCHES_RELATIVE_PATH / batch_id
    batch_directory = stage_root / batch_relative
    if not batch_directory.exists():
        raise EligibilityError("SOURCE_BATCH_NOT_FOUND", retryable=True)
    if batch_directory.is_symlink() or not batch_directory.is_dir():
        raise EligibilityError("ARTIFACT_NOT_REGULAR")
    manifest_relative = (batch_relative / "manifest.json").as_posix()
    log_relative = (batch_relative / "collection_log.json").as_posix()
    manifest_path = stage_root / manifest_relative
    log_path = stage_root / log_relative
    manifest = _load_json_object(manifest_path, missing_reason="MANIFEST_MISSING")
    log = _load_json_object(log_path, missing_reason="COLLECTION_LOG_MISSING")

    try:
        batch_entries = tuple(batch_directory.iterdir())
    except OSError as error:
        raise EligibilityError("SOURCE_BATCH_NOT_FOUND", retryable=True) from error
    expected_names = {"manifest.json", "collection_log.json"}
    actual_names = {item.name for item in batch_entries}
    if not expected_names.issubset(actual_names):
        raise EligibilityError("FILE_COUNT_MISMATCH")
    unexpected_entries = [item for item in batch_entries if item.name not in expected_names]
    if not allow_noncanonical_entries:
        unknown_entries = [
            item for item in unexpected_entries if not _is_ignored_platform_metadata(item)
        ]
        if unknown_entries:
            raise EligibilityError("UNEXPECTED_NONCANONICAL_FILE")

    _validate_reference_evidence(manifest)
    artifacts = _manifest_artifacts(manifest)
    eligible_type = _validate_collection_log(stage_root, log, manifest, artifacts, batch_id)
    _validate_source_artifacts(stage_root, artifacts)
    manifest_information = _regular_file(manifest_path, missing_reason="MANIFEST_MISSING")
    if manifest_information.st_size <= 0:
        raise EligibilityError("MANIFEST_INVALID")
    try:
        manifest_sha256 = _sha256_file(manifest_path)
    except OSError as error:
        raise EligibilityError("MANIFEST_INVALID") from error
    return _BatchPlan(
        stage_root=stage_root,
        batch_id=batch_id,
        manifest_relative_path=manifest_relative,
        manifest_sha256=manifest_sha256,
        artifacts=artifacts,
        eligible_batch_type=eligible_type,
    )


def _manifest_verification_plan(stage_root: Path, batch_id: str) -> _BatchPlan:
    """Load the canonical path contract before inspecting copied file contents."""

    try:
        batch_id = _canonical_batch_id(batch_id)
    except CliInputError as error:
        raise EligibilityError("BATCH_ID_INVALID") from error
    stage_root = _resolve_real_batch_root(stage_root)
    manifest_relative = (
        BATCHES_RELATIVE_PATH / batch_id / "manifest.json"
    ).as_posix()
    manifest_path = stage_root / manifest_relative
    manifest = _load_json_object(manifest_path, missing_reason="MANIFEST_MISSING")
    if manifest.get("batch_id") != batch_id or manifest.get("hash_algorithm") != "sha256":
        raise EligibilityError("MANIFEST_INVALID")
    _validate_reference_evidence(manifest)
    artifacts = _manifest_artifacts(manifest)
    manifest_information = _regular_file(manifest_path, missing_reason="MANIFEST_MISSING")
    if manifest_information.st_size <= 0:
        raise EligibilityError("MANIFEST_INVALID")
    try:
        manifest_sha256 = _sha256_file(manifest_path)
    except OSError as error:
        raise EligibilityError("MANIFEST_INVALID") from error
    return _BatchPlan(
        stage_root=stage_root,
        batch_id=batch_id,
        manifest_relative_path=manifest_relative,
        manifest_sha256=manifest_sha256,
        artifacts=artifacts,
        eligible_batch_type=ELIGIBLE_SUCCESS,
    )


def assess_batch(stage_root: Path, batch_id: str) -> EligibilityResult:
    """Return a non-sensitive eligibility decision for one completed batch."""

    try:
        plan = _inspect_batch(stage_root, batch_id)
    except EligibilityError as error:
        return EligibilityResult(
            eligible=False,
            eligible_batch_type=None,
            reason_code=error.reason_code,
            retryable=error.retryable,
            batch_id=batch_id,
            source_manifest_sha256=None,
            source_file_count=0,
        )
    return EligibilityResult(
        eligible=True,
        eligible_batch_type=plan.eligible_batch_type,
        reason_code=("ELIGIBLE_SUCCESS" if plan.eligible_batch_type == ELIGIBLE_SUCCESS else "ELIGIBLE_PARTIAL_FAILURE"),
        retryable=True,
        batch_id=plan.batch_id,
        source_manifest_sha256=plan.manifest_sha256,
        source_file_count=plan.source_file_count,
    )


def _resolve_existing_directory(path: Path, reason_code: str) -> Path:
    try:
        expanded = path.expanduser()
        if expanded.is_symlink():
            raise BackupOperationalError(reason_code)
        resolved = expanded.resolve(strict=True)
        if not resolved.is_dir() or resolved.is_symlink() or resolved == resolved.parent:
            raise BackupOperationalError(reason_code)
        return resolved
    except BackupOperationalError:
        raise
    except (OSError, RuntimeError) as error:
        raise BackupOperationalError(reason_code) from error


def _ensure_safe_directory_tree(root: Path, relative_path: Path) -> Path:
    current = root
    for part in relative_path.parts:
        current = current / part
        try:
            if current.exists():
                information = current.lstat()
                if stat.S_ISLNK(information.st_mode) or not stat.S_ISDIR(information.st_mode):
                    raise BackupOperationalError("DESTINATION_UNSAFE")
            else:
                current.mkdir(mode=0o700)
        except BackupOperationalError:
            raise
        except OSError as error:
            raise BackupOperationalError("DESTINATION_UNSAFE") from error
    return current


def _copy_one_file(source: Path, destination: Path) -> bool:
    try:
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        source_flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            source_flags |= os.O_NOFOLLOW
        source_descriptor = os.open(source, source_flags)
        try:
            information = os.fstat(source_descriptor)
            if not stat.S_ISREG(information.st_mode):
                raise BackupOperationalError("ARTIFACT_NOT_REGULAR")
            destination_descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            try:
                with os.fdopen(source_descriptor, "rb", closefd=False) as source_handle:
                    with os.fdopen(destination_descriptor, "wb", closefd=False) as destination_handle:
                        shutil.copyfileobj(source_handle, destination_handle, length=65536)
                        destination_handle.flush()
                try:
                    os.fsync(destination_descriptor)
                    fsync_supported = True
                except OSError as error:
                    if error.errno in {errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}:
                        fsync_supported = False
                    else:
                        raise BackupOperationalError("FSYNC_FAILED") from error
            finally:
                os.close(destination_descriptor)
        finally:
            os.close(source_descriptor)
        return fsync_supported
    except BackupOperationalError:
        raise
    except OSError as error:
        raise BackupOperationalError("COPY_FAILED") from error


def _fsync_directory(path: Path) -> bool:
    try:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return True
    except OSError as error:
        if error.errno in {errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}:
            return False
        raise BackupOperationalError("FSYNC_FAILED") from error


def _fsync_tree_directories(root: Path) -> tuple[str, ...]:
    warnings: list[str] = []
    directories = [item for item in root.rglob("*") if item.is_dir()]
    directories.sort(key=lambda item: len(item.parts), reverse=True)
    for directory in [*directories, root]:
        if not _fsync_directory(directory) and DIRECTORY_FSYNC_UNSUPPORTED not in warnings:
            warnings.append(DIRECTORY_FSYNC_UNSUPPORTED)
    return tuple(warnings)


def _expected_relative_paths(plan: _BatchPlan) -> tuple[str, ...]:
    return tuple(item.relative_path for item in plan.artifacts) + (plan.manifest_relative_path,)


def _expected_relative_directories(plan: _BatchPlan) -> frozenset[str]:
    expected: set[str] = set()
    for relative in _expected_relative_paths(plan):
        parent = PurePosixPath(relative).parent
        while parent != PurePosixPath("."):
            expected.add(parent.as_posix())
            parent = parent.parent
    return frozenset(expected)


def _tree_inventory(plan: _BatchPlan, root: Path) -> _TreeInventory:
    expected = set(_expected_relative_paths(plan))
    expected_directories = _expected_relative_directories(plan)
    total_count = 0
    canonical_count = 0
    ignored_count = 0
    unknown_count = 0
    unexpected_directory_count = 0
    try:
        pending = [root]
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    item = Path(entry.path)
                    information = entry.stat(follow_symlinks=False)
                    relative = item.relative_to(root).as_posix()
                    if stat.S_ISDIR(information.st_mode):
                        if relative not in expected_directories:
                            unexpected_directory_count += 1
                        pending.append(item)
                    else:
                        total_count += 1
                        if relative in expected and stat.S_ISREG(information.st_mode):
                            canonical_count += 1
                        elif _is_ignored_platform_metadata(item, information):
                            ignored_count += 1
                        else:
                            unknown_count += 1
    except (OSError, ValueError) as error:
        raise BackupOperationalError("VERIFY_FAILED") from error
    return _TreeInventory(
        total_file_count=total_count,
        canonical_file_count=canonical_count,
        ignored_platform_metadata_count=ignored_count,
        unknown_additional_file_count=unknown_count,
        unexpected_directory_count=unexpected_directory_count,
    )


def _verification_result(
    *,
    verified: bool,
    reason_code: str,
    plan: _BatchPlan,
    manifest_sha256: str | None,
    verified_file_count: int,
    inventory: _TreeInventory,
) -> VerificationResult:
    return VerificationResult(
        verified=verified,
        reason_code=reason_code,
        batch_id=plan.batch_id,
        manifest_sha256=manifest_sha256,
        expected_file_count=plan.source_file_count,
        verified_file_count=verified_file_count,
        total_tree_file_count=inventory.total_file_count,
        canonical_backup_file_count=inventory.canonical_file_count,
        ignored_platform_metadata_count=inventory.ignored_platform_metadata_count,
        unknown_additional_file_count=inventory.unknown_additional_file_count,
        unexpected_directory_count=inventory.unexpected_directory_count,
    )


def _verify_tree(plan: _BatchPlan, root: Path) -> VerificationResult:
    try:
        root = _resolve_real_batch_root(root)
    except EligibilityError as error:
        return VerificationResult(
            False,
            error.reason_code,
            plan.batch_id,
            None,
            plan.source_file_count,
            0,
        )
    inventory = _tree_inventory(plan, root)
    if (
        inventory.unknown_additional_file_count
        or inventory.unexpected_directory_count
    ):
        return _verification_result(
            verified=False,
            reason_code="UNEXPECTED_NONCANONICAL_FILE",
            plan=plan,
            manifest_sha256=None,
            verified_file_count=0,
            inventory=inventory,
        )
    if not inventory.canonical_file_count == plan.source_file_count:
        return _verification_result(
            verified=False,
            reason_code="FILE_COUNT_MISMATCH",
            plan=plan,
            manifest_sha256=None,
            verified_file_count=0,
            inventory=inventory,
        )
    try:
        inspected = _inspect_batch(root, plan.batch_id, allow_noncanonical_entries=True)
    except EligibilityError as error:
        return _verification_result(
            verified=False,
            reason_code=error.reason_code,
            plan=plan,
            manifest_sha256=None,
            verified_file_count=0,
            inventory=inventory,
        )
    if inspected.manifest_sha256 != plan.manifest_sha256 or inspected.source_file_count != plan.source_file_count:
        return _verification_result(
            verified=False,
            reason_code="SHA256_MISMATCH",
            plan=plan,
            manifest_sha256=inspected.manifest_sha256,
            verified_file_count=0,
            inventory=inventory,
        )
    reason_code = (
        CANONICAL_VERIFIED_WITH_IGNORED_PLATFORM_METADATA
        if inventory.ignored_platform_metadata_count
        else "VERIFIED"
    )
    return _verification_result(
        verified=True,
        reason_code=reason_code,
        plan=plan,
        manifest_sha256=inspected.manifest_sha256,
        verified_file_count=plan.source_file_count,
        inventory=inventory,
    )


def verify_backup_copy(backup_batch_root: Path) -> VerificationResult:
    """Verify a self-contained backup copy without consulting the source."""

    batch_id = backup_batch_root.name
    try:
        plan = _manifest_verification_plan(backup_batch_root, batch_id)
        return _verify_tree(plan, backup_batch_root)
    except EligibilityError as error:
        return VerificationResult(False, error.reason_code, batch_id, None, 0, 0)
    except BackupOperationalError as error:
        return VerificationResult(False, error.reason_code, batch_id, None, 0, 0)


def _write_exclusive_bytes(path: Path, payload: bytes) -> None:
    partial_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, partial_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".partial",
            dir=path.parent,
        )
        partial_path = Path(partial_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(partial_path, path)
    except OSError as error:
        raise BackupOperationalError("RECEIPT_WRITE_FAILED") from error
    finally:
        if partial_path is not None:
            try:
                partial_path.unlink()
            except OSError:
                pass


def _receipt_document(
    *,
    attempt_id: str,
    event_sequence: int,
    batch_id: str,
    manifest_sha256: str | None,
    status_value: BackupStatus,
    eligible_batch_type: str | None,
    source_count: int,
    copied_count: int,
    verified_count: int,
    started_at: datetime,
    completed_at: datetime | None,
    failure_code: str | None,
    conflict_detected: bool,
    capability_warnings: tuple[str, ...],
) -> dict[str, object]:
    if status_value not in WORKER_EMITTABLE_STATUSES:
        raise BackupOperationalError("RECEIPT_WRITE_FAILED")
    return {
        "receipt_version": RECEIPT_VERSION,
        "backup_attempt_id": attempt_id,
        "worker_version": WORKER_VERSION,
        "event_sequence": event_sequence,
        "batch_id": batch_id,
        "source_manifest_sha256": manifest_sha256,
        "logical_destination": LOGICAL_DESTINATION,
        "backup_status": status_value.value,
        "eligible_batch_type": eligible_batch_type,
        "source_file_count": source_count,
        "copied_file_count": copied_count,
        "verified_file_count": verified_count,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat() if completed_at else None,
        "failure_code": failure_code,
        "conflict_detected": conflict_detected,
        "restore_test_status": RESTORE_NOT_RUN,
        "capability_warnings": list(capability_warnings),
    }


RECEIPT_FIELDS = tuple(
    _receipt_document(
        attempt_id="00000000-0000-4000-8000-000000000000",
        event_sequence=0,
        batch_id="00000000-0000-4000-8000-000000000000",
        manifest_sha256=None,
        status_value=BackupStatus.PENDING,
        eligible_batch_type=None,
        source_count=0,
        copied_count=0,
        verified_count=0,
        started_at=datetime(2000, 1, 1).astimezone(),
        completed_at=None,
        failure_code=None,
        conflict_detected=False,
        capability_warnings=(),
    )
)


def _write_receipt_event(ledger_root: Path, document: Mapping[str, object]) -> None:
    batch_id = _canonical_batch_id(str(document["batch_id"]))
    attempt_id = _canonical_batch_id(str(document["backup_attempt_id"]))
    sequence = _nonnegative_int(document["event_sequence"], "RECEIPT_WRITE_FAILED")
    status_value = str(document["backup_status"]).lower()
    receipt_directory = _ensure_safe_directory_tree(
        ledger_root,
        Path("receipts") / batch_id,
    )
    filename = f"{attempt_id}.{sequence:02d}.{status_value}.receipt.json"
    payload = (json.dumps(dict(document), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write_exclusive_bytes(receipt_directory / filename, payload)


def _acquire_lock(ledger_root: Path, batch_id: str, attempt_id: str, created_at: datetime) -> _LockHandle:
    lock_directory = _ensure_safe_directory_tree(ledger_root, Path("locks"))
    path = lock_directory / f"{batch_id}.lock"
    payload = (
        json.dumps(
            {
                "backup_attempt_id": attempt_id,
                "created_at": created_at.isoformat(),
                "process_id": os.getpid(),
                "worker_version": WORKER_VERSION,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise BackupOperationalError("LOCK_HELD") from error
    except OSError as error:
        raise BackupOperationalError("LOCK_CREATE_FAILED") from error
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as error:
        try:
            path.unlink()
        except OSError:
            pass
        raise BackupOperationalError("LOCK_CREATE_FAILED") from error
    return _LockHandle(path=path, attempt_id=attempt_id)


def _release_lock(handle: _LockHandle) -> bool:
    try:
        document = json.loads(handle.path.read_text(encoding="utf-8"))
        if not isinstance(document, dict) or document.get("backup_attempt_id") != handle.attempt_id:
            return False
        handle.path.unlink()
        return True
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def _safe_cleanup_temp(path: Path | None, parent: Path, batch_id: str) -> bool:
    if path is None or not path.exists():
        return True
    expected_prefix = f".freshmanager-incoming-{batch_id}-"
    try:
        if path.parent.resolve() != parent.resolve() or not path.name.startswith(expected_prefix) or not path.name.endswith(".partial"):
            return False
        shutil.rmtree(path)
        return not path.exists()
    except OSError:
        return False


def _available_bytes(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError as error:
        raise BackupOperationalError("DESTINATION_UNSAFE") from error


def _required_free_bytes(source_bytes: int) -> int:
    ten_percent = (source_bytes + 9) // 10
    return source_bytes + max(MINIMUM_SPACE_MARGIN_BYTES, ten_percent)


def _result(
    plan: _BatchPlan,
    status_value: BackupStatus,
    reason_code: str,
    *,
    copied: int = 0,
    verified: int = 0,
    conflict: bool = False,
    receipt_written: bool = False,
    warnings: tuple[str, ...] = (),
) -> BackupResult:
    return BackupResult(
        backup_status=status_value,
        reason_code=reason_code,
        batch_id=plan.batch_id,
        eligible_batch_type=plan.eligible_batch_type,
        source_manifest_sha256=plan.manifest_sha256,
        source_file_count=plan.source_file_count,
        copied_file_count=copied,
        verified_file_count=verified,
        conflict_detected=conflict,
        receipt_written=receipt_written,
        capability_warnings=warnings,
    )


def backup_batch(
    stage_root: Path,
    sync_root: Path,
    ledger_root: Path,
    batch_id: str,
) -> BackupResult:
    """Copy one eligible batch and return only non-sensitive status evidence."""

    try:
        plan = _inspect_batch(stage_root, batch_id)
    except EligibilityError as error:
        return BackupResult(
            backup_status=BackupStatus.FAILED,
            reason_code=error.reason_code,
            batch_id=batch_id,
            eligible_batch_type=None,
            source_manifest_sha256=None,
            source_file_count=0,
            copied_file_count=0,
            verified_file_count=0,
            conflict_detected=False,
            receipt_written=False,
        )

    try:
        resolved_stage = _resolve_existing_directory(plan.stage_root, "SOURCE_BATCH_NOT_FOUND")
        resolved_sync = _resolve_existing_directory(sync_root, "DESTINATION_UNSAFE")
        if _is_within(resolved_sync, PROJECT_ROOT.resolve()) or _paths_overlap(resolved_stage, resolved_sync):
            raise BackupOperationalError("DESTINATION_UNSAFE")
        if ledger_root.exists() and ledger_root.is_symlink():
            raise BackupOperationalError("LEDGER_UNSAFE")
        resolved_ledger = ledger_root.expanduser().resolve()
        if _is_within(resolved_ledger, PROJECT_ROOT.resolve()) or _paths_overlap(resolved_sync, resolved_ledger) or _paths_overlap(resolved_stage, resolved_ledger):
            raise BackupOperationalError("LEDGER_UNSAFE")
        resolved_ledger.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not resolved_ledger.is_dir() or resolved_ledger.is_symlink():
            raise BackupOperationalError("LEDGER_UNSAFE")
    except BackupOperationalError as error:
        return _result(plan, BackupStatus.FAILED, error.reason_code)
    except OSError:
        return _result(plan, BackupStatus.FAILED, "LEDGER_UNSAFE")

    started_at = _now()
    attempt_id = str(uuid.uuid4())
    base_receipt = {
        "attempt_id": attempt_id,
        "batch_id": plan.batch_id,
        "manifest_sha256": plan.manifest_sha256,
        "eligible_batch_type": plan.eligible_batch_type,
        "source_count": plan.source_file_count,
        "started_at": started_at,
    }

    def record(
        sequence: int,
        status_value: BackupStatus,
        *,
        copied: int = 0,
        verified: int = 0,
        failure_code: str | None = None,
        conflict: bool = False,
        warnings: tuple[str, ...] = (),
    ) -> None:
        _write_receipt_event(
            resolved_ledger,
            _receipt_document(
                **base_receipt,
                event_sequence=sequence,
                status_value=status_value,
                copied_count=copied,
                verified_count=verified,
                completed_at=_now() if status_value not in {BackupStatus.PENDING, BackupStatus.IN_PROGRESS} else None,
                failure_code=failure_code,
                conflict_detected=conflict,
                capability_warnings=warnings,
            ),
        )

    try:
        record(0, BackupStatus.PENDING)
    except (BackupOperationalError, CliInputError, EligibilityError):
        return _result(plan, BackupStatus.FAILED, "RECEIPT_WRITE_FAILED")

    try:
        lock = _acquire_lock(resolved_ledger, plan.batch_id, attempt_id, started_at)
    except BackupOperationalError as error:
        receipt_written = True
        try:
            record(1, BackupStatus.FAILED, failure_code=error.reason_code)
        except (BackupOperationalError, CliInputError, EligibilityError):
            receipt_written = False
        return _result(plan, BackupStatus.FAILED, error.reason_code, receipt_written=receipt_written)

    try:
        record(1, BackupStatus.IN_PROGRESS)
    except (BackupOperationalError, CliInputError, EligibilityError):
        _release_lock(lock)
        return _result(plan, BackupStatus.FAILED, "RECEIPT_WRITE_FAILED")

    copied_count = 0
    verified_count = 0
    warnings: list[str] = []
    temporary: Path | None = None
    reason_code: str | None = None
    final_status = BackupStatus.FAILED
    conflict = False

    try:
        destination_parent = _ensure_safe_directory_tree(resolved_sync, DESTINATION_RELATIVE_PATH)
        destination = destination_parent / plan.batch_id
        if destination.exists() or destination.is_symlink():
            existing = _verify_tree(plan, destination)
            if existing.verified:
                final_status = BackupStatus.LOCAL_SYNC_COPY_VERIFIED
                reason_code = "ALREADY_VERIFIED"
                verified_count = existing.verified_file_count
            else:
                final_status = BackupStatus.CONFLICT
                reason_code = (
                    existing.reason_code
                    if existing.reason_code == SYMLINK_BATCH_ROOT_REJECTED
                    else "CONFLICT"
                )
                conflict = True
        else:
            if _available_bytes(destination_parent) < _required_free_bytes(plan.source_file_bytes):
                raise BackupOperationalError("INSUFFICIENT_SPACE")
            temporary = Path(
                tempfile.mkdtemp(
                    prefix=f".freshmanager-incoming-{plan.batch_id}-",
                    suffix=".partial",
                    dir=destination_parent,
                )
            )
            for relative in _expected_relative_paths(plan):
                source = plan.stage_root / relative
                target = temporary / relative
                fsync_supported = _copy_one_file(source, target)
                copied_count += 1
                if not fsync_supported and FILE_FSYNC_UNSUPPORTED not in warnings:
                    warnings.append(FILE_FSYNC_UNSUPPORTED)
            verification = _verify_tree(plan, temporary)
            if not verification.verified:
                raise BackupOperationalError(verification.reason_code)
            verified_count = verification.verified_file_count
            for warning in _fsync_tree_directories(temporary):
                if warning not in warnings:
                    warnings.append(warning)
            if destination.exists():
                raise BackupOperationalError("CONFLICT")
            try:
                os.rename(temporary, destination)
                temporary = None
            except OSError as error:
                raise BackupOperationalError("PUBLISH_FAILED") from error
            if not _fsync_directory(destination_parent) and DIRECTORY_FSYNC_UNSUPPORTED not in warnings:
                warnings.append(DIRECTORY_FSYNC_UNSUPPORTED)
            published = _verify_tree(plan, destination)
            if not published.verified:
                raise BackupOperationalError(published.reason_code)
            verified_count = published.verified_file_count
            final_status = BackupStatus.LOCAL_SYNC_COPY_VERIFIED
            reason_code = "LOCAL_SYNC_COPY_VERIFIED"
    except BackupOperationalError as error:
        reason_code = error.reason_code
        if error.reason_code == "CONFLICT":
            final_status = BackupStatus.CONFLICT
            conflict = True
        else:
            final_status = BackupStatus.FAILED
    except OSError:
        reason_code = "COPY_FAILED"
        final_status = BackupStatus.FAILED

    if not _safe_cleanup_temp(temporary, destination_parent if "destination_parent" in locals() else resolved_sync, plan.batch_id):
        reason_code = "TEMP_CLEANUP_FAILED"
        final_status = BackupStatus.FAILED

    if not _release_lock(lock):
        reason_code = "LOCK_RELEASE_FAILED"
        final_status = BackupStatus.FAILED

    receipt_written = True
    try:
        record(
            2,
            final_status,
            copied=copied_count,
            verified=verified_count,
            failure_code=None
            if final_status == BackupStatus.LOCAL_SYNC_COPY_VERIFIED
            else reason_code,
            conflict=conflict,
            warnings=tuple(warnings),
        )
    except (BackupOperationalError, CliInputError, EligibilityError):
        receipt_written = False
        final_status = BackupStatus.FAILED
        reason_code = "RECEIPT_WRITE_FAILED"

    return _result(
        plan,
        final_status,
        reason_code or "COPY_FAILED",
        copied=copied_count,
        verified=verified_count,
        conflict=conflict,
        receipt_written=receipt_written,
        warnings=tuple(warnings),
    )


def _exit_code(result: BackupResult) -> int:
    if result.backup_status == BackupStatus.LOCAL_SYNC_COPY_VERIFIED:
        return 0
    if result.backup_status == BackupStatus.CONFLICT:
        return 5
    ineligible = {
        "BATCH_ID_INVALID",
        "SOURCE_BATCH_NOT_FOUND",
        "SOURCE_IN_PROGRESS",
        "MANIFEST_MISSING",
        "COLLECTION_LOG_MISSING",
        "CONTROL_FILE_INVALID",
        "MANIFEST_INVALID",
        "LOG_INVALID",
        "BATCH_ID_MISMATCH",
        "EXIT_CODE_INELIGIBLE",
        "BATCH_AGGREGATE_MISMATCH",
        "AREA_EVIDENCE_INCOMPLETE",
        "ARTIFACT_PATH_UNSAFE",
        "FORBIDDEN_ARTIFACT",
        "ARTIFACT_MISSING",
        "ARTIFACT_NOT_REGULAR",
        SYMLINK_BATCH_ROOT_REJECTED,
        "UNEXPECTED_NONCANONICAL_FILE",
        "FILE_COUNT_MISMATCH",
        "SIZE_MISMATCH",
        "SHA256_MISMATCH",
    }
    return 3 if result.reason_code in ineligible else 4


def _report(result: BackupResult, exit_code: int) -> None:
    print("BACKUP_WORKER_RESULT")
    print(f"batch_id={result.batch_id}")
    print(f"backup_status={result.backup_status.value}")
    print(f"reason_code={result.reason_code}")
    print(f"eligible_batch_type={result.eligible_batch_type or ''}")
    print(f"source_file_count={result.source_file_count}")
    print(f"copied_file_count={result.copied_file_count}")
    print(f"verified_file_count={result.verified_file_count}")
    print(f"conflict_detected={'true' if result.conflict_detected else 'false'}")
    print(f"receipt_written={'true' if result.receipt_written else 'false'}")
    print("remote_sync_confirmed=false")
    print(f"exit_code={exit_code}")


def _configuration_failure(batch_id: str, reason_code: str = "CONFIG_ERROR") -> int:
    result = BackupResult(
        backup_status=BackupStatus.FAILED,
        reason_code=reason_code,
        batch_id=batch_id,
        eligible_batch_type=None,
        source_manifest_sha256=None,
        source_file_count=0,
        copied_file_count=0,
        verified_file_count=0,
        conflict_detected=False,
        receipt_written=False,
    )
    _report(result, 2)
    return 2


def run(argv: list[str] | None = None, *, environ: Mapping[str, str] | None = None) -> int:
    """Run the one-shot CLI without loading ``.env`` or discovering paths."""

    try:
        arguments = build_parser().parse_args(argv)
    except CliInputError:
        return _configuration_failure("")
    environment = os.environ if environ is None else environ
    source_value = environment.get(SOURCE_ROOT_ENV)
    sync_value = environment.get(SYNC_ROOT_ENV)
    if not source_value or not sync_value:
        return _configuration_failure(arguments.batch_id)
    try:
        output_root = Path(source_value).expanduser()
        sync_root = Path(sync_value).expanduser()
        stage_root = output_root / STAGE_RELATIVE_PATH
        ledger_root = output_root / LEDGER_RELATIVE_PATH
        result = backup_batch(stage_root, sync_root, ledger_root, arguments.batch_id)
    except Exception:
        result = BackupResult(
            backup_status=BackupStatus.FAILED,
            reason_code="INTERNAL_ERROR",
            batch_id=arguments.batch_id,
            eligible_batch_type=None,
            source_manifest_sha256=None,
            source_file_count=0,
            copied_file_count=0,
            verified_file_count=0,
            conflict_detected=False,
            receipt_written=False,
        )
    code = _exit_code(result)
    _report(result, code)
    return code


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
