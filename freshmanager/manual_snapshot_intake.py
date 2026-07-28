"""Immutable intake boundary for manually exported v3 source CSV packages."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from . import eg6b, eg8a, eg8c_features
from .batch_id import BatchIdValidationError, canonical_batch_id


SEOUL = ZoneInfo("Asia/Seoul")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANUAL_ROOT_NAME = "manual-snapshots"
SNAPSHOT_MANIFEST_SCHEMA_VERSION = "manual-v3-snapshot-manifest-v1"
VALIDATION_REPORT_SCHEMA_VERSION = "manual-v3-snapshot-validation-v1"
HASH_ALGORITHM = "SHA-256"

PURPOSES = frozenset(
    {
        "DATA_QUALITY_VALIDATION",
        "HISTORICAL_ANALYSIS",
        "UI_PROTOTYPE",
        "MODEL_EVALUATION",
        "PM_APPROVED_LIMITED_SNAPSHOT_REVIEW",
    }
)
MANIFEST_REQUIRED_COLUMNS = (
    "snapshot_intake_purpose",
    "exported_at",
    "source_sheet_contract",
    "source_origin_confirmed_by_pm",
)
MANIFEST_OPTIONAL_COLUMNS = ("note",)
SOURCE_ROLES = (
    "raw_log_v3",
    "population_current_v3",
    "population_forecast_v3",
)
ALL_ROLES = SOURCE_ROLES + ("upload_manifest",)
ROLE_DIRECTORY = {
    "raw_log_v3": "raw",
    "population_current_v3": "current",
    "population_forecast_v3": "forecast",
    "upload_manifest": "intake",
}
SOURCE_FINGERPRINT_LABELS = (
    ("RAW", "raw_log_v3"),
    ("CURRENT", "population_current_v3"),
    ("FORECAST", "population_forecast_v3"),
)
EXPECTED_HEADERS = {
    "raw_log_v3": tuple(eg8a.RAW_LOG_REQUIRED_COLUMNS),
    "population_current_v3": tuple(eg8a.CURRENT_REQUIRED_COLUMNS),
    "population_forecast_v3": tuple(eg8a.FORECAST_REQUIRED_COLUMNS),
}
OPERATIONAL_FALSE_FIELDS = (
    "collection_purpose_inferred",
    "operational_collection_purpose_confirmed",
    "operational_metrics_eligible",
    "dynamic_spot_evidence_eligible",
    "user_publication_allowed",
    "official_recommendation_allowed",
)


class SnapshotIntakeError(RuntimeError):
    """A bounded, non-sensitive Manual Snapshot Intake failure."""

    def __init__(self, code: str, validation_report: Mapping[str, object] | None = None):
        self.code = code
        self.validation_report = validation_report
        super().__init__(code)


@dataclass(frozen=True)
class SnapshotIntakeResult:
    snapshot_id: str
    source_content_fingerprint: str
    intake_metadata_fingerprint: str
    published: bool
    final_path: Path | None
    snapshot_manifest: Mapping[str, object]
    validation_report: Mapping[str, object]


@dataclass(frozen=True)
class Eg8aSnapshotAdapterResult:
    normalization: eg8a.NormalizationResult
    input_paths: Mapping[str, Path]
    input_artifacts: Mapping[str, Mapping[str, object]]


@dataclass(frozen=True)
class _CopiedArtifact:
    logical_name: str
    original_file_name: str
    relative_path: str
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class _UploadManifest:
    snapshot_intake_purpose: str
    exported_at: str
    source_sheet_contract: str
    source_origin_confirmed_by_pm: bool
    note: str


@dataclass(frozen=True)
class _SourceValidation:
    rows: Mapping[str, list[dict[str, str]]]
    row_counts: Mapping[str, int]
    unique_row_counts: Mapping[str, int]
    duplicate_row_counts: Mapping[str, int]
    distinct_collection_run_count: int
    area_count: int
    called_at_min: str
    called_at_max: str
    observed_at_min: str
    observed_at_max: str
    forecast_at_min: str
    forecast_at_max: str


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_output_root(output_root: Path) -> Path:
    path = Path(output_root).expanduser()
    try:
        path_stat = path.lstat()
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise SnapshotIntakeError("OUTPUT_ROOT_INVALID") from error
    if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISDIR(path_stat.st_mode):
        raise SnapshotIntakeError("OUTPUT_ROOT_INVALID")
    if resolved == Path(resolved.anchor) or _is_within(resolved, PROJECT_ROOT.resolve()):
        raise SnapshotIntakeError("OUTPUT_ROOT_INVALID")
    if not os.access(resolved, os.R_OK | os.W_OK | os.X_OK):
        raise SnapshotIntakeError("OUTPUT_ROOT_INVALID")
    return resolved


def _ensure_manual_root(output_root: Path) -> Path:
    manual_root = output_root / MANUAL_ROOT_NAME
    try:
        manual_root.mkdir(mode=0o700)
    except FileExistsError:
        pass
    except OSError as error:
        raise SnapshotIntakeError("OUTPUT_ROOT_INVALID") from error
    try:
        root_stat = manual_root.lstat()
    except OSError as error:
        raise SnapshotIntakeError("OUTPUT_ROOT_INVALID") from error
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise SnapshotIntakeError("OUTPUT_ROOT_INVALID")
    return manual_root


def _copy_inputs_once(
    inputs: Mapping[str, Path], staging_root: Path
) -> tuple[dict[str, _CopiedArtifact], dict[str, Path]]:
    artifacts: dict[str, _CopiedArtifact] = {}
    staged_paths: dict[str, Path] = {}
    seen_paths: set[Path] = set()
    seen_identities: set[tuple[int, int]] = set()

    for role in ALL_ROLES:
        source = Path(inputs[role])
        try:
            before = source.lstat()
            resolved = source.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise SnapshotIntakeError("INPUT_FILE_INVALID") from error
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            raise SnapshotIntakeError("INPUT_FILE_INVALID")
        identity = (before.st_dev, before.st_ino)
        if resolved in seen_paths or identity in seen_identities:
            raise SnapshotIntakeError("INPUT_ROLE_COLLISION")
        seen_paths.add(resolved)
        seen_identities.add(identity)

        destination_dir = staging_root / "source" / ROLE_DIRECTORY[role]
        try:
            destination_dir.mkdir(parents=True)
        except OSError as error:
            raise SnapshotIntakeError("INPUT_FILE_INVALID") from error
        destination = destination_dir / source.name
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(source, flags)
        except OSError as error:
            raise SnapshotIntakeError("INPUT_FILE_INVALID") from error

        digest = hashlib.sha256()
        byte_size = 0
        try:
            with os.fdopen(descriptor, "rb") as source_handle, destination.open("xb") as target:
                opened = os.fstat(source_handle.fileno())
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_size <= 0
                    or (opened.st_dev, opened.st_ino) != identity
                ):
                    raise SnapshotIntakeError("INPUT_FILE_INVALID")
                while True:
                    chunk = source_handle.read(1024 * 1024)
                    if not chunk:
                        break
                    target.write(chunk)
                    digest.update(chunk)
                    byte_size += len(chunk)
                target.flush()
                os.fsync(target.fileno())
                after = os.fstat(source_handle.fileno())
                if (
                    byte_size != opened.st_size
                    or after.st_size != opened.st_size
                    or after.st_mtime_ns != opened.st_mtime_ns
                    or (after.st_dev, after.st_ino) != identity
                ):
                    raise SnapshotIntakeError("INPUT_FILE_CHANGED_DURING_COPY")
        except SnapshotIntakeError:
            raise
        except OSError as error:
            raise SnapshotIntakeError("INPUT_FILE_INVALID") from error

        relative_path = destination.relative_to(staging_root).as_posix()
        artifacts[role] = _CopiedArtifact(
            logical_name=role,
            original_file_name=source.name,
            relative_path=relative_path,
            sha256=digest.hexdigest(),
            byte_size=byte_size,
        )
        staged_paths[role] = destination
    return artifacts, staged_paths


def _read_exact_csv(path: Path, expected_header: Sequence[str], error_code: str) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            if tuple(header) != tuple(expected_header):
                raise SnapshotIntakeError(error_code)
            rows: list[dict[str, str]] = []
            for values in reader:
                if len(values) != len(header):
                    raise SnapshotIntakeError(error_code)
                rows.append(dict(zip(header, values)))
    except StopIteration as error:
        raise SnapshotIntakeError(error_code) from error
    except (UnicodeError, csv.Error, OSError) as error:
        raise SnapshotIntakeError(error_code) from error
    return rows


def _parse_upload_manifest(path: Path) -> _UploadManifest:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = tuple(next(reader))
            allowed_headers = {
                MANIFEST_REQUIRED_COLUMNS,
                MANIFEST_REQUIRED_COLUMNS + MANIFEST_OPTIONAL_COLUMNS,
            }
            if header not in allowed_headers:
                raise SnapshotIntakeError("UPLOAD_MANIFEST_INVALID")
            values = list(reader)
    except StopIteration as error:
        raise SnapshotIntakeError("UPLOAD_MANIFEST_INVALID") from error
    except (UnicodeError, csv.Error, OSError) as error:
        raise SnapshotIntakeError("UPLOAD_MANIFEST_INVALID") from error
    if len(values) != 1 or len(values[0]) != len(header):
        raise SnapshotIntakeError("UPLOAD_MANIFEST_INVALID")
    row = dict(zip(header, values[0]))
    for field in MANIFEST_REQUIRED_COLUMNS:
        value = row.get(field, "")
        if not value or value != value.strip():
            raise SnapshotIntakeError("UPLOAD_MANIFEST_INVALID")

    purpose = row["snapshot_intake_purpose"]
    source_contract = row["source_sheet_contract"]
    confirmed_value = row["source_origin_confirmed_by_pm"]
    exported_at = row["exported_at"]
    if purpose not in PURPOSES or source_contract != "V3" or confirmed_value not in {"true", "false"}:
        raise SnapshotIntakeError("UPLOAD_MANIFEST_INVALID")
    if not exported_at.endswith("+09:00"):
        raise SnapshotIntakeError("UPLOAD_MANIFEST_INVALID")
    try:
        exported = datetime.fromisoformat(exported_at)
    except ValueError as error:
        raise SnapshotIntakeError("UPLOAD_MANIFEST_INVALID") from error
    if exported.tzinfo is None or exported.utcoffset() != timedelta(hours=9):
        raise SnapshotIntakeError("UPLOAD_MANIFEST_INVALID")
    if exported > datetime.now(SEOUL):
        raise SnapshotIntakeError("UPLOAD_MANIFEST_INVALID")
    return _UploadManifest(
        snapshot_intake_purpose=purpose,
        exported_at=exported.isoformat(),
        source_sheet_contract=source_contract,
        source_origin_confirmed_by_pm=confirmed_value == "true",
        note=row.get("note", "").strip(),
    )


def _parse_source_rows(staged_paths: Mapping[str, Path]) -> dict[str, list[dict[str, str]]]:
    rows: dict[str, list[dict[str, str]]] = {}
    for role in SOURCE_ROLES:
        role_rows = _read_exact_csv(staged_paths[role], EXPECTED_HEADERS[role], "V3_HEADER_INVALID")
        if not role_rows:
            raise SnapshotIntakeError("DATA_VALIDATION_FAILED")
        rows[role] = role_rows
    return rows


def _validate_source_rows(rows: Mapping[str, list[dict[str, str]]]) -> _SourceValidation:
    approved_areas = set(eg6b.EG6B_AREA_CODES)
    row_counts: dict[str, int] = {}
    unique_counts: dict[str, int] = {}
    duplicate_counts: dict[str, int] = {}
    unique_keys: dict[str, dict[object, tuple[str, ...]]] = {}
    run_ids: set[str] = set()
    area_codes: set[str] = set()
    called_times: list[datetime] = []
    observed_times: list[datetime] = []
    forecast_times: list[datetime] = []

    for role in SOURCE_ROLES:
        header = EXPECTED_HEADERS[role]
        role_keys: dict[object, tuple[str, ...]] = {}
        duplicates = 0
        for row in rows[role]:
            if any(row.get(field, "").strip() == "" for field in header):
                raise SnapshotIntakeError("DATA_VALIDATION_FAILED")
            run_id = row["collection_run_id"]
            try:
                canonical_batch_id(run_id)
            except BatchIdValidationError as error:
                raise SnapshotIntakeError("DATA_VALIDATION_FAILED") from error
            requested = row["area_code_requested"]
            if requested not in approved_areas:
                raise SnapshotIntakeError("DATA_VALIDATION_FAILED")
            if role != "raw_log_v3" and row["area_code_returned"] != requested:
                raise SnapshotIntakeError("DATA_VALIDATION_FAILED")
            try:
                called_at = eg8a.parse_kst_datetime(row["called_at"])
                observed_at = (
                    eg8a.parse_kst_datetime(row["observed_at"])
                    if role != "raw_log_v3"
                    else None
                )
                forecast_at = (
                    eg8a.parse_kst_datetime(row["forecast_at"])
                    if role == "population_forecast_v3"
                    else None
                )
            except ValueError as error:
                raise SnapshotIntakeError("DATA_VALIDATION_FAILED") from error
            if called_at.tzinfo is None or (observed_at is not None and observed_at.tzinfo is None):
                raise SnapshotIntakeError("DATA_VALIDATION_FAILED")

            if role == "population_current_v3":
                _validate_population_range(row["population_min"], row["population_max"])
            elif role == "population_forecast_v3":
                _validate_population_range(
                    row["forecast_population_min"], row["forecast_population_max"]
                )
                assert observed_at is not None and forecast_at is not None
                if forecast_at <= observed_at:
                    raise SnapshotIntakeError("DATA_VALIDATION_FAILED")

            key: object = (run_id, requested)
            if forecast_at is not None:
                key = (run_id, requested, forecast_at)
            exact_row = tuple(row[field] for field in header)
            previous = role_keys.get(key)
            if previous is not None:
                if previous != exact_row:
                    raise SnapshotIntakeError("CONFLICTING_DUPLICATE_KEY")
                duplicates += 1
            else:
                role_keys[key] = exact_row

            run_ids.add(run_id)
            area_codes.add(requested)
            called_times.append(called_at)
            if observed_at is not None:
                observed_times.append(observed_at)
            if forecast_at is not None:
                forecast_times.append(forecast_at)

        row_counts[role] = len(rows[role])
        unique_counts[role] = len(role_keys)
        duplicate_counts[role] = duplicates
        unique_keys[role] = role_keys

    raw_keys = set(unique_keys["raw_log_v3"])
    current_keys = set(unique_keys["population_current_v3"])
    forecast_base_keys = {
        (run_id, area_code)
        for run_id, area_code, _forecast_at in unique_keys["population_forecast_v3"]
    }
    if raw_keys != current_keys or raw_keys != forecast_base_keys:
        raise SnapshotIntakeError("SOURCE_LINK_MISMATCH")

    return _SourceValidation(
        rows=rows,
        row_counts=row_counts,
        unique_row_counts=unique_counts,
        duplicate_row_counts=duplicate_counts,
        distinct_collection_run_count=len(run_ids),
        area_count=len(area_codes),
        called_at_min=min(called_times).isoformat(),
        called_at_max=max(called_times).isoformat(),
        observed_at_min=min(observed_times).isoformat(),
        observed_at_max=max(observed_times).isoformat(),
        forecast_at_min=min(forecast_times).isoformat(),
        forecast_at_max=max(forecast_times).isoformat(),
    )


def _validate_population_range(minimum: str, maximum: str) -> None:
    try:
        minimum_value = int(minimum)
        maximum_value = int(maximum)
    except ValueError as error:
        raise SnapshotIntakeError("DATA_VALIDATION_FAILED") from error
    if minimum_value < 0 or maximum_value < 0 or minimum_value > maximum_value:
        raise SnapshotIntakeError("DATA_VALIDATION_FAILED")


def _source_content_fingerprint(artifacts: Mapping[str, _CopiedArtifact]) -> str:
    payload = _source_fingerprint_payload(
        {role: artifacts[role].sha256 for role in SOURCE_ROLES}
    )
    return hashlib.sha256(payload).hexdigest()


def _source_fingerprint_payload(hashes: Mapping[str, str]) -> bytes:
    return b"".join(
        label.encode("ascii") + b"\0" + hashes[role].encode("ascii") + b"\n"
        for label, role in SOURCE_FINGERPRINT_LABELS
    )


def _intake_metadata_fingerprint(source_fingerprint: str, manifest: _UploadManifest) -> str:
    document = {
        "exported_at": manifest.exported_at,
        "note": manifest.note,
        "snapshot_intake_purpose": manifest.snapshot_intake_purpose,
        "source_content_fingerprint": source_fingerprint,
        "source_origin_confirmed_by_pm": manifest.source_origin_confirmed_by_pm,
        "source_sheet_contract": manifest.source_sheet_contract,
    }
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def _artifact_documents(
    copied: Mapping[str, _CopiedArtifact], validation: _SourceValidation
) -> dict[str, dict[str, object]]:
    documents: dict[str, dict[str, object]] = {}
    for role in ALL_ROLES:
        artifact = copied[role]
        row_count = validation.row_counts[role] if role in SOURCE_ROLES else 1
        unique_count = validation.unique_row_counts[role] if role in SOURCE_ROLES else 1
        duplicate_count = validation.duplicate_row_counts[role] if role in SOURCE_ROLES else 0
        documents[role] = {
            "sha256": artifact.sha256,
            "byte_size": artifact.byte_size,
            "row_count": row_count,
            "unique_row_count": unique_count,
            "duplicate_row_count": duplicate_count,
        }
    return documents


def _build_documents(
    *,
    snapshot_id: str,
    source_fingerprint: str,
    metadata_fingerprint: str,
    upload: _UploadManifest,
    copied: Mapping[str, _CopiedArtifact],
    validation: _SourceValidation,
) -> tuple[dict[str, object], dict[str, object]]:
    artifacts = _artifact_documents(copied, validation)
    created_at = datetime.now(SEOUL).isoformat()
    manifest: dict[str, object] = {
        "schema_version": SNAPSHOT_MANIFEST_SCHEMA_VERSION,
        "hash_algorithm": HASH_ALGORITHM,
        "snapshot_id": snapshot_id,
        "source_content_fingerprint": source_fingerprint,
        "intake_metadata_fingerprint": metadata_fingerprint,
        "snapshot_intake_purpose": upload.snapshot_intake_purpose,
        "exported_at": upload.exported_at,
        "source_sheet_contract": upload.source_sheet_contract,
        "source_origin_confirmed_by_pm": upload.source_origin_confirmed_by_pm,
        "original_file_names": {
            role: copied[role].original_file_name for role in ALL_ROLES
        },
        "relative_paths": {role: copied[role].relative_path for role in ALL_ROLES},
        "artifacts": artifacts,
        "distinct_collection_run_count": validation.distinct_collection_run_count,
        "called_at_min": validation.called_at_min,
        "called_at_max": validation.called_at_max,
        "observed_at_min": validation.observed_at_min,
        "observed_at_max": validation.observed_at_max,
        "forecast_at_min": validation.forecast_at_min,
        "forecast_at_max": validation.forecast_at_max,
        "validation_status": "PASS",
        "created_at": created_at,
        "source_files_modified": False,
        "collection_purpose_inferred": False,
        "operational_collection_purpose_confirmed": False,
        "operational_metrics_eligible": False,
        "dynamic_spot_evidence_eligible": False,
        "user_publication_allowed": False,
        "official_recommendation_allowed": False,
    }
    blocking_reasons = (
        [] if upload.source_origin_confirmed_by_pm else ["SOURCE_ORIGIN_NOT_CONFIRMED"]
    )
    report: dict[str, object] = {
        "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "file_checks": {role: "PASS" for role in ALL_ROLES},
        "upload_manifest_check": "PASS",
        "header_checks": {role: "PASS" for role in SOURCE_ROLES},
        "row_counts": {role: artifacts[role]["row_count"] for role in ALL_ROLES},
        "unique_row_counts": {
            role: artifacts[role]["unique_row_count"] for role in ALL_ROLES
        },
        "duplicate_row_counts": {
            role: artifacts[role]["duplicate_row_count"] for role in ALL_ROLES
        },
        "conflict_count": 0,
        "distinct_collection_run_count": validation.distinct_collection_run_count,
        "area_count": validation.area_count,
        "called_at_min": validation.called_at_min,
        "called_at_max": validation.called_at_max,
        "observed_at_min": validation.observed_at_min,
        "observed_at_max": validation.observed_at_max,
        "forecast_at_min": validation.forecast_at_min,
        "forecast_at_max": validation.forecast_at_max,
        "source_links": {
            "raw_current": "PASS",
            "raw_forecast": "PASS",
            "current_forecast": "PASS",
        },
        "warnings": [],
        "errors": [],
        "validation_status": "PASS",
        "final_publish_eligible": not blocking_reasons,
        "blocking_reason_codes": blocking_reasons,
    }
    return manifest, report


def _failure_report(code: str) -> dict[str, object]:
    not_evaluated_files = {role: "NOT_EVALUATED" for role in ALL_ROLES}
    not_evaluated_sources = {role: "NOT_EVALUATED" for role in SOURCE_ROLES}
    return {
        "schema_version": VALIDATION_REPORT_SCHEMA_VERSION,
        "file_checks": not_evaluated_files,
        "upload_manifest_check": "NOT_EVALUATED",
        "header_checks": not_evaluated_sources,
        "row_counts": {},
        "unique_row_counts": {},
        "duplicate_row_counts": {},
        "conflict_count": None,
        "distinct_collection_run_count": None,
        "area_count": None,
        "called_at_min": None,
        "called_at_max": None,
        "observed_at_min": None,
        "observed_at_max": None,
        "forecast_at_min": None,
        "forecast_at_max": None,
        "source_links": {
            "raw_current": "NOT_EVALUATED",
            "raw_forecast": "NOT_EVALUATED",
            "current_forecast": "NOT_EVALUATED",
        },
        "validation_status": "FAIL",
        "final_publish_eligible": False,
        "warnings": [],
        "errors": [code],
        "blocking_reason_codes": [code],
    }


def _json_bytes(document: Mapping[str, object]) -> bytes:
    return (json.dumps(dict(document), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _write_exclusive(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as error:
        raise SnapshotIntakeError("STAGING_WRITE_FAILED") from error


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_size = 0
    try:
        path_stat = path.lstat()
        if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
            raise SnapshotIntakeError("STAGING_INTEGRITY_FAILED")
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                byte_size += len(chunk)
    except SnapshotIntakeError:
        raise
    except OSError as error:
        raise SnapshotIntakeError("STAGING_INTEGRITY_FAILED") from error
    return digest.hexdigest(), byte_size


def _verify_staged_artifacts(
    staged_paths: Mapping[str, Path], artifacts: Mapping[str, _CopiedArtifact]
) -> None:
    for role in ALL_ROLES:
        digest, byte_size = _hash_file(staged_paths[role])
        expected = artifacts[role]
        if digest != expected.sha256 or byte_size != expected.byte_size:
            raise SnapshotIntakeError("STAGING_INTEGRITY_FAILED")


def _load_json_object(path: Path) -> dict[str, object]:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        document: dict[str, object] = {}
        for key, value in pairs:
            if key in document:
                raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID")
            document[key] = value
        return document

    try:
        document = json.loads(path.read_bytes(), object_pairs_hook=reject_duplicates)
    except SnapshotIntakeError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID") from error
    if not isinstance(document, dict):
        raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID")
    return document


def _check_existing_snapshot(final_path: Path, source_fingerprint: str, metadata_fingerprint: str) -> None:
    if not final_path.exists() and not final_path.is_symlink():
        return
    if final_path.is_symlink() or not final_path.is_dir():
        raise SnapshotIntakeError("FINAL_SNAPSHOT_CONFLICT")
    try:
        existing = _load_json_object(final_path / "snapshot_manifest.json")
    except SnapshotIntakeError as error:
        raise SnapshotIntakeError("FINAL_SNAPSHOT_CONFLICT") from error
    if existing.get("source_content_fingerprint") != source_fingerprint:
        raise SnapshotIntakeError("FINAL_SNAPSHOT_CONFLICT")
    if existing.get("intake_metadata_fingerprint") == metadata_fingerprint:
        raise SnapshotIntakeError("DUPLICATE_SNAPSHOT_BLOCKED")
    raise SnapshotIntakeError("SOURCE_RECLASSIFICATION_BLOCKED")


def _cleanup_staging(staging_root: Path) -> None:
    if not staging_root.exists() and not staging_root.is_symlink():
        return
    try:
        shutil.rmtree(staging_root)
    except OSError:
        code = "STAGING_CLEANUP_FAILED"
        raise SnapshotIntakeError(code, _failure_report(code)) from None


def run_manual_snapshot_intake(
    *,
    raw_path: Path,
    current_path: Path,
    forecast_path: Path,
    upload_manifest_path: Path,
    output_root: Path,
) -> SnapshotIntakeResult:
    """Return a bounded intake result or a non-sensitive dedicated error."""

    try:
        return _run_manual_snapshot_intake(
            raw_path=Path(raw_path),
            current_path=Path(current_path),
            forecast_path=Path(forecast_path),
            upload_manifest_path=Path(upload_manifest_path),
            output_root=Path(output_root),
        )
    except SnapshotIntakeError as error:
        report = error.validation_report or _failure_report(error.code)
        raise SnapshotIntakeError(error.code, report) from None
    except Exception:
        code = "SNAPSHOT_INTAKE_FAILED"
        raise SnapshotIntakeError(code, _failure_report(code)) from None


def _run_manual_snapshot_intake(
    *,
    raw_path: Path,
    current_path: Path,
    forecast_path: Path,
    upload_manifest_path: Path,
    output_root: Path,
) -> SnapshotIntakeResult:
    """Validate and exclusively publish one explicit Manual V3 Snapshot package."""

    resolved_output = _validate_output_root(output_root)
    manual_root = _ensure_manual_root(resolved_output)
    try:
        staging_root = Path(tempfile.mkdtemp(prefix=".staging-", dir=manual_root))
    except OSError:
        code = "STAGING_CREATE_FAILED"
        raise SnapshotIntakeError(code, _failure_report(code)) from None
    published = False
    try:
        copied, staged_paths = _copy_inputs_once(
            {
                "raw_log_v3": Path(raw_path),
                "population_current_v3": Path(current_path),
                "population_forecast_v3": Path(forecast_path),
                "upload_manifest": Path(upload_manifest_path),
            },
            staging_root,
        )
        upload = _parse_upload_manifest(staged_paths["upload_manifest"])
        validation = _validate_source_rows(_parse_source_rows(staged_paths))
        source_fingerprint = _source_content_fingerprint(copied)
        metadata_fingerprint = _intake_metadata_fingerprint(source_fingerprint, upload)
        snapshot_id = f"snapshot-{source_fingerprint}"
        final_path = manual_root / snapshot_id
        _check_existing_snapshot(final_path, source_fingerprint, metadata_fingerprint)
        snapshot_manifest, validation_report = _build_documents(
            snapshot_id=snapshot_id,
            source_fingerprint=source_fingerprint,
            metadata_fingerprint=metadata_fingerprint,
            upload=upload,
            copied=copied,
            validation=validation,
        )
        if not upload.source_origin_confirmed_by_pm:
            return SnapshotIntakeResult(
                snapshot_id=snapshot_id,
                source_content_fingerprint=source_fingerprint,
                intake_metadata_fingerprint=metadata_fingerprint,
                published=False,
                final_path=None,
                snapshot_manifest=snapshot_manifest,
                validation_report=validation_report,
            )

        _write_exclusive(staging_root / "snapshot_manifest.json", _json_bytes(snapshot_manifest))
        _write_exclusive(staging_root / "validation_report.json", _json_bytes(validation_report))
        _verify_staged_artifacts(staged_paths, copied)
        try:
            eg8c_features._rename_run_root_exclusive(staging_root, final_path)
        except FileExistsError as error:
            raise SnapshotIntakeError("FINAL_PUBLISH_CONFLICT") from error
        except OSError as error:
            raise SnapshotIntakeError("FINAL_PUBLISH_FAILED") from error
        published = True
        return SnapshotIntakeResult(
            snapshot_id=snapshot_id,
            source_content_fingerprint=source_fingerprint,
            intake_metadata_fingerprint=metadata_fingerprint,
            published=True,
            final_path=final_path,
            snapshot_manifest=snapshot_manifest,
            validation_report=validation_report,
        )
    except SnapshotIntakeError as error:
        if error.validation_report is not None:
            raise
        raise SnapshotIntakeError(error.code, _failure_report(error.code)) from None
    finally:
        if not published:
            _cleanup_staging(staging_root)


def normalize_final_snapshot_for_eg8a(snapshot_root: Path) -> Eg8aSnapshotAdapterResult:
    """Return a bounded Adapter result or a non-sensitive dedicated error."""

    try:
        return _normalize_final_snapshot_for_eg8a(Path(snapshot_root))
    except SnapshotIntakeError as error:
        raise SnapshotIntakeError(error.code, error.validation_report) from None
    except Exception:
        raise SnapshotIntakeError("SNAPSHOT_NORMALIZATION_FAILED") from None


def _normalize_final_snapshot_for_eg8a(snapshot_root: Path) -> Eg8aSnapshotAdapterResult:
    """Revalidate a published Snapshot and pass its three sources to EG-8A."""

    root = Path(snapshot_root)
    try:
        root_stat = root.lstat()
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID") from error
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID")
    manifest_path = resolved_root / "snapshot_manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID")
    manifest = _load_json_object(manifest_path)
    if (
        manifest.get("schema_version") != SNAPSHOT_MANIFEST_SCHEMA_VERSION
        or manifest.get("validation_status") != "PASS"
        or manifest.get("source_origin_confirmed_by_pm") is not True
        or manifest.get("source_files_modified") is not False
        or any(manifest.get(field) is not False for field in OPERATIONAL_FALSE_FIELDS)
    ):
        raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID")

    relative_paths = manifest.get("relative_paths")
    artifacts = manifest.get("artifacts")
    if not isinstance(relative_paths, dict) or not isinstance(artifacts, dict):
        raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID")
    verified_paths: dict[str, Path] = {}
    verified_artifacts: dict[str, Mapping[str, object]] = {}
    for role in ALL_ROLES:
        relative = relative_paths.get(role)
        artifact = artifacts.get(role)
        if not isinstance(relative, str) or not isinstance(artifact, dict):
            raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID")
        source_path = resolved_root / relative_path
        try:
            source_stat = source_path.lstat()
            resolved_source = source_path.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise SnapshotIntakeError("SNAPSHOT_SOURCE_INTEGRITY_FAILED") from error
        if (
            stat.S_ISLNK(source_stat.st_mode)
            or not stat.S_ISREG(source_stat.st_mode)
            or not _is_within(resolved_source, resolved_root)
        ):
            raise SnapshotIntakeError("SNAPSHOT_SOURCE_INTEGRITY_FAILED")
        try:
            digest, byte_size = _hash_file(resolved_source)
        except SnapshotIntakeError as error:
            raise SnapshotIntakeError("SNAPSHOT_SOURCE_INTEGRITY_FAILED") from error
        if digest != artifact.get("sha256") or byte_size != artifact.get("byte_size"):
            raise SnapshotIntakeError("SNAPSHOT_SOURCE_INTEGRITY_FAILED")
        verified_paths[role] = resolved_source
        verified_artifacts[role] = {
            "sha256": digest,
            "byte_size": byte_size,
            "relative_path": relative,
        }

    try:
        upload = _parse_upload_manifest(verified_paths["upload_manifest"])
    except SnapshotIntakeError as error:
        raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID") from error
    if (
        manifest.get("snapshot_intake_purpose") != upload.snapshot_intake_purpose
        or manifest.get("exported_at") != upload.exported_at
        or manifest.get("source_sheet_contract") != upload.source_sheet_contract
        or manifest.get("source_origin_confirmed_by_pm")
        is not upload.source_origin_confirmed_by_pm
    ):
        raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID")

    actual_source_fingerprint = hashlib.sha256(
        _source_fingerprint_payload(
            {role: str(verified_artifacts[role]["sha256"]) for role in SOURCE_ROLES}
        )
    ).hexdigest()
    expected_snapshot_id = f"snapshot-{actual_source_fingerprint}"
    actual_metadata_fingerprint = _intake_metadata_fingerprint(
        actual_source_fingerprint, upload
    )
    if (
        manifest.get("source_content_fingerprint") != actual_source_fingerprint
        or manifest.get("intake_metadata_fingerprint") != actual_metadata_fingerprint
        or manifest.get("snapshot_id") != expected_snapshot_id
        or resolved_root.name != expected_snapshot_id
    ):
        raise SnapshotIntakeError("SNAPSHOT_MANIFEST_INVALID")

    input_paths = {role: verified_paths[role] for role in SOURCE_ROLES}
    input_artifacts = {role: verified_artifacts[role] for role in SOURCE_ROLES}

    normalization = eg8a.normalize_v3_sources(
        raw_log_path=input_paths["raw_log_v3"],
        current_path=input_paths["population_current_v3"],
        forecast_path=input_paths["population_forecast_v3"],
    )
    for role in ALL_ROLES:
        try:
            digest, byte_size = _hash_file(verified_paths[role])
        except SnapshotIntakeError as error:
            raise SnapshotIntakeError("SNAPSHOT_SOURCE_INTEGRITY_FAILED") from error
        if (
            digest != verified_artifacts[role]["sha256"]
            or byte_size != verified_artifacts[role]["byte_size"]
        ):
            raise SnapshotIntakeError("SNAPSHOT_SOURCE_INTEGRITY_FAILED")
    return Eg8aSnapshotAdapterResult(
        normalization=normalization,
        input_paths=input_paths,
        input_artifacts=input_artifacts,
    )
