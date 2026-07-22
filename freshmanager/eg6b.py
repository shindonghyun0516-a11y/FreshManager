"""EG-6B approved 13-area single collection with immutable batch evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping

from . import backup as backup_contract
from .batch_id import BatchIdValidationError, canonical_batch_id
from .collector import EXPECTED_HEADERS, Collector, HttpResponse, Place, now_seoul
from .config import load_api_key
from .http_adapter import SeoulPopulationHttpClient, Transport, UrllibTransport
from .storage import BatchStorage, FileStorage


EG6B_AREA_CODES = (
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
PANEL_VERSION = "eg6a-v1"
COLLECTOR_VERSION = "eg6b-collector-v1"
DATA_VERSION = "eg6b-data-v1"
COLLECTION_PURPOSE = "single_collection"
STAGE_NAME = "eg6b_single_13"
STAGE_PATH = Path("stages") / STAGE_NAME
RAW_OUTPUT_PATH = STAGE_PATH / "data/raw/population"
METADATA_OUTPUT_PATH = STAGE_PATH / "data/processed/collection_logs"
BATCH_OUTPUT_PATH = STAGE_PATH / "data/processed/batches"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_TIMEOUT_SECONDS = 60.0
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_CSV_PATH = PROJECT_ROOT / "data/reference/seoul_121_places.csv"
AREA_PANEL_PATH = PROJECT_ROOT / "data/reference/eg6_area_panel.csv"
SPOT_MASTER_PATH = PROJECT_ROOT / "data/reference/eg6_spot_master.csv"
SDOT_LINKS_PATH = PROJECT_ROOT / "data/reference/eg6_sdot_links.csv"
PROBE_FILE_PREFIX = ".eg6b-write-probe-"
PROBE_PAYLOAD = b"eg6b-storage-probe"
PER_PLACE_FAILURE_STATUSES = {"api_error", "timeout", "parse_error", "validation_error"}
COMMON_FAILURE_STATUSES = {"config_error", "storage_error", "security_error", "internal_error"}
PANEL_HEADERS = [
    "panel_version",
    "panel_order",
    "service_area_name",
    "area_code",
    "official_area_name",
    "area_mapping_type",
    "mapping_confidence",
    "sdot_group",
    "approved",
    "active",
    "decision_note",
]
SPOT_HEADERS = [
    "spot_id",
    "service_area_name",
    "spot_name",
    "latitude",
    "longitude",
    "coordinate_source",
    "representative_coordinate_type",
    "connected_area_code",
    "connected_area_name",
    "spot_type",
    "business_reason",
    "selling_suitability_status",
    "field_verified",
    "active",
]
SDOT_HEADERS = [
    "spot_id",
    "nearest_sdot_id",
    "nearest_sdot_distance_m",
    "coverage_class",
    "sensor_recent_active",
    "activity_reference_period",
    "mapping_confidence",
    "source_report",
]


class CliInputError(ValueError):
    """Raised for an unsafe CLI value before any collection side effect."""


class ReferenceValidationError(ValueError):
    """Raised when an approved reference input is absent or inconsistent."""


class BatchIntegrityError(ValueError):
    """Raised when a stored batch artifact does not match its manifest."""


class BatchIdConflictError(ValueError):
    """Raised when an approved Batch ID already has collection or backup state."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise CliInputError("input_error")


@dataclass(frozen=True)
class ReferencePaths:
    root: Path
    official_csv: Path
    area_panel: Path
    spot_master: Path
    sdot_links: Path


DEFAULT_REFERENCE_PATHS = ReferencePaths(
    root=PROJECT_ROOT,
    official_csv=OFFICIAL_CSV_PATH,
    area_panel=AREA_PANEL_PATH,
    spot_master=SPOT_MASTER_PATH,
    sdot_links=SDOT_LINKS_PATH,
)


@dataclass(frozen=True)
class ReferenceSnapshot:
    paths: ReferencePaths
    places: tuple[Place, ...]
    panel_version: str
    digests: Mapping[str, str]


@dataclass(frozen=True)
class AreaOutcome:
    panel_order: int
    area_code: str
    request_id: str | None
    attempted: bool
    collection_status: str
    raw_path: Path | None
    metadata_path: Path | None


@dataclass(frozen=True)
class Eg6bSummary:
    batch_id: str
    panel_version: str
    target_count: int
    attempted_count: int
    success_count: int
    failure_count: int
    failed_area_codes: tuple[str, ...]
    retry_count: int
    elapsed_seconds: float
    raw_file_count: int
    metadata_file_count: int
    collection_log_saved: bool
    manifest_saved: bool
    hash_verification_passed: bool
    stage: str
    exit_code: int


class _LazyHttpClient:
    def __init__(self, transport_factory: Callable[[], Transport]) -> None:
        self._transport_factory = transport_factory
        self._client: SeoulPopulationHttpClient | None = None

    def fetch_population(self, area_code: str, api_key: str, timeout_seconds: float) -> HttpResponse:
        if self._client is None:
            self._client = SeoulPopulationHttpClient(self._transport_factory())
        return self._client.fetch_population(area_code, api_key, timeout_seconds)


def _timeout_value(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("invalid timeout") from error
    if not math.isfinite(timeout) or not 0 < timeout <= MAX_TIMEOUT_SECONDS:
        raise argparse.ArgumentTypeError("invalid timeout")
    return timeout


def _batch_id_value(value: str) -> str:
    try:
        return canonical_batch_id(value)
    except BatchIdValidationError as error:
        raise argparse.ArgumentTypeError("invalid batch id") from error


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(description="EG-6B 승인 13개 Area 단일 회차 수집")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--batch-id",
        type=_batch_id_value,
        help="PM이 승인한 canonical Batch ID (--execute-live에서 필수)",
    )
    parser.add_argument("--timeout", type=_timeout_value, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="PM 실제 호출 승인을 대체하지 않는 명시적 실행 의사 확인",
    )
    return parser


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validated_output_paths(value: Path) -> tuple[Path, Path, Path, Path, Path]:
    try:
        output_root = value.expanduser().resolve()
        project_root = PROJECT_ROOT.resolve()
        stage_root = (output_root / STAGE_PATH).resolve()
        raw_root = (output_root / RAW_OUTPUT_PATH).resolve()
        metadata_root = (output_root / METADATA_OUTPUT_PATH).resolve()
        batch_root = (output_root / BATCH_OUTPUT_PATH).resolve()
    except (OSError, RuntimeError) as error:
        raise CliInputError("input_error") from error

    candidates = (stage_root, raw_root, metadata_root, batch_root)
    if (
        output_root == output_root.parent
        or (output_root.exists() and not output_root.is_dir())
        or _is_within(output_root, project_root)
        or not all(_is_within(path, output_root) for path in candidates)
        or any(path.exists() and not path.is_dir() for path in candidates)
    ):
        raise CliInputError("input_error")
    return output_root, stage_root, raw_root, metadata_root, batch_root


def _path_present(path: Path) -> bool:
    try:
        return os.path.lexists(path)
    except (OSError, ValueError):
        return True


def _ensure_batch_id_available(
    *,
    output_root: Path,
    batch_root: Path,
    batch_id: str,
    environ: Mapping[str, str],
) -> None:
    ledger_root = output_root / backup_contract.LEDGER_RELATIVE_PATH
    candidates = [
        batch_root / batch_id,
        ledger_root / "receipts" / batch_id,
        ledger_root / "locks" / f"{batch_id}.lock",
    ]
    sync_value = environ.get(backup_contract.SYNC_ROOT_ENV)
    if sync_value:
        try:
            sync_root = Path(sync_value).expanduser().resolve()
        except (OSError, RuntimeError, ValueError) as error:
            raise BatchIdConflictError("batch_id_conflict") from error
        candidates.append(sync_root / backup_contract.DESTINATION_RELATIVE_PATH / batch_id)
    if any(_path_present(path) for path in candidates):
        raise BatchIdConflictError("batch_id_conflict")


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise ReferenceValidationError("validation_error")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reference_items(paths: ReferencePaths) -> tuple[tuple[str, Path], ...]:
    return (
        ("official_places", paths.official_csv),
        ("area_panel", paths.area_panel),
        ("spot_master", paths.spot_master),
        ("sdot_links", paths.sdot_links),
    )


def _reference_digests(paths: ReferencePaths) -> dict[str, str]:
    return {name: _sha256_file(path) for name, path in _reference_items(paths)}


def _read_csv(path: Path, headers: list[str], *, encoding: str) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding=encoding, newline="") as source:
            reader = csv.DictReader(source, strict=True)
            if list(reader.fieldnames or ()) != headers:
                raise ReferenceValidationError("validation_error")
            rows = list(reader)
            if any(None in row or any(value is None for value in row.values()) for row in rows):
                raise ReferenceValidationError("validation_error")
            return [
                {str(key): str(value).strip() for key, value in row.items()}
                for row in rows
            ]
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise ReferenceValidationError("validation_error") from error


def _load_official_places(path: Path) -> dict[str, Place]:
    rows = _read_csv(path, EXPECTED_HEADERS, encoding="utf-8-sig")
    codes = [row["AREA_CD"] for row in rows]
    if (
        len(rows) != 121
        or any(not code for code in codes)
        or len(codes) != len(set(codes))
        or any(not row["AREA_NM"] for row in rows)
    ):
        raise ReferenceValidationError("validation_error")
    return {
        row["AREA_CD"]: Place(
            category=row["CATEGORY"],
            number=row["NO"],
            area_code=row["AREA_CD"],
            area_name=row["AREA_NM"],
            english_name=row["ENG_NM"],
        )
        for row in rows
    }


def _validate_auxiliary_references(
    paths: ReferencePaths,
    panel_rows: list[dict[str, str]],
) -> None:
    spots = _read_csv(paths.spot_master, SPOT_HEADERS, encoding="utf-8")
    links = _read_csv(paths.sdot_links, SDOT_HEADERS, encoding="utf-8")
    spot_ids = [row["spot_id"] for row in spots]
    link_ids = [row["spot_id"] for row in links]
    approved_codes = {row["area_code"] for row in panel_rows}
    if (
        len(spots) != len(EG6B_AREA_CODES)
        or len(set(spot_ids)) != len(EG6B_AREA_CODES)
        or set(row["connected_area_code"] for row in spots) != approved_codes
        or any(row["active"] != "true" for row in spots)
        or any(row["representative_coordinate_type"] != "STATION_CENTER_PROXY" for row in spots)
        or len(links) != len(EG6B_AREA_CODES)
        or len(set(link_ids)) != len(EG6B_AREA_CODES)
        or set(link_ids) != set(spot_ids)
        or any(row["sensor_recent_active"] != "true" for row in links)
    ):
        raise ReferenceValidationError("validation_error")


def _validate_references(paths: ReferencePaths) -> ReferenceSnapshot:
    before = _reference_digests(paths)
    official = _load_official_places(paths.official_csv)
    panel_rows = _read_csv(paths.area_panel, PANEL_HEADERS, encoding="utf-8")
    try:
        panel_orders = [int(row["panel_order"]) for row in panel_rows]
    except ValueError as error:
        raise ReferenceValidationError("validation_error") from error
    panel_codes = tuple(row["area_code"] for row in panel_rows)
    if (
        len(panel_rows) != len(EG6B_AREA_CODES)
        or panel_orders != list(range(1, len(EG6B_AREA_CODES) + 1))
        or panel_codes != EG6B_AREA_CODES
        or len(set(panel_codes)) != len(EG6B_AREA_CODES)
        or {row["panel_version"] for row in panel_rows} != {PANEL_VERSION}
        or any(row["approved"] != "true" or row["active"] != "true" for row in panel_rows)
    ):
        raise ReferenceValidationError("validation_error")

    places: list[Place] = []
    for row in panel_rows:
        place = official.get(row["area_code"])
        if place is None or place.area_name != row["official_area_name"]:
            raise ReferenceValidationError("validation_error")
        places.append(place)
    _validate_auxiliary_references(paths, panel_rows)
    after = _reference_digests(paths)
    if before != after:
        raise ReferenceValidationError("validation_error")
    return ReferenceSnapshot(paths, tuple(places), PANEL_VERSION, before)


def _references_unchanged(snapshot: ReferenceSnapshot) -> bool:
    try:
        return _reference_digests(snapshot.paths) == dict(snapshot.digests)
    except (OSError, ReferenceValidationError):
        return False


def _probe_storage_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    probe_path = root / f"{PROBE_FILE_PREFIX}{uuid.uuid4().hex}.probe"
    try:
        with probe_path.open("xb") as probe:
            probe.write(PROBE_PAYLOAD)
            probe.flush()
    finally:
        if probe_path.exists():
            probe_path.unlink()


def _probe_storage_roots(*roots: Path) -> None:
    for root in roots:
        _probe_storage_root(root)


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, RuntimeError, ValueError) as error:
        raise BatchIntegrityError("integrity_error") from error


def _complete_outcomes(outcomes: list[AreaOutcome]) -> tuple[AreaOutcome, ...]:
    by_code = {item.area_code: item for item in outcomes}
    return tuple(
        by_code.get(
            code,
            AreaOutcome(index, code, None, False, "not_attempted", None, None),
        )
        for index, code in enumerate(EG6B_AREA_CODES, start=1)
    )


def _collection_log(
    *,
    batch_id: str,
    panel_version: str,
    started_at: datetime,
    finished_at: datetime,
    elapsed_seconds: float,
    outcomes: tuple[AreaOutcome, ...],
    stage_root: Path,
    exit_code: int,
) -> dict[str, object]:
    successes = [item for item in outcomes if item.collection_status == "success"]
    failures = [item for item in outcomes if item.collection_status != "success"]
    return {
        "collector_version": COLLECTOR_VERSION,
        "data_version": DATA_VERSION,
        "batch_id": batch_id,
        "panel_version": panel_version,
        "collection_purpose": COLLECTION_PURPOSE,
        "expected_area_count": len(EG6B_AREA_CODES),
        "scheduled_at": None,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_seconds": round(max(0.0, elapsed_seconds), 6),
        "attempted_count": sum(item.attempted for item in outcomes),
        "success_count": len(successes),
        "failure_count": len(failures),
        "failed_area_codes": [item.area_code for item in failures],
        "retry_count": 0,
        "raw_file_count": sum(item.raw_path is not None for item in outcomes),
        "metadata_file_count": sum(item.metadata_path is not None for item in outcomes),
        "exit_code": exit_code,
        "area_results": [
            {
                "panel_order": item.panel_order,
                "area_code": item.area_code,
                "request_id": item.request_id,
                "attempted": item.attempted,
                "collection_status": item.collection_status,
                "raw_file": _relative_path(item.raw_path, stage_root) if item.raw_path else None,
                "metadata_file": _relative_path(item.metadata_path, stage_root) if item.metadata_path else None,
            }
            for item in outcomes
        ],
    }


def _artifact_entry(
    path: Path,
    stage_root: Path,
    artifact_type: str,
    *,
    area_code: str | None = None,
    request_id: str | None = None,
) -> dict[str, object]:
    return {
        "artifact_type": artifact_type,
        "relative_path": _relative_path(path, stage_root),
        "byte_size": path.stat().st_size,
        "sha256": _sha256_file(path),
        "area_code": area_code,
        "request_id": request_id,
    }


def _payload_artifact_entry(
    *,
    path: Path,
    payload: bytes,
    stage_root: Path,
    artifact_type: str,
) -> dict[str, object]:
    return {
        "artifact_type": artifact_type,
        "relative_path": _relative_path(path, stage_root),
        "byte_size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "area_code": None,
        "request_id": None,
    }


def _manifest(
    *,
    batch_id: str,
    created_at: datetime,
    snapshot: ReferenceSnapshot,
    outcomes: tuple[AreaOutcome, ...],
    collection_log_path: Path,
    collection_log_payload: bytes,
    stage_root: Path,
) -> dict[str, object]:
    references = []
    for name, path in _reference_items(snapshot.paths):
        references.append(
            {
                "reference_type": name,
                "path": _relative_path(path, snapshot.paths.root),
                "byte_size": path.stat().st_size,
                "sha256": snapshot.digests[name],
            }
        )
    artifacts: list[dict[str, object]] = []
    for outcome in outcomes:
        if outcome.raw_path is not None:
            artifacts.append(
                _artifact_entry(
                    outcome.raw_path,
                    stage_root,
                    "raw_json",
                    area_code=outcome.area_code,
                    request_id=outcome.request_id,
                )
            )
        if outcome.metadata_path is not None:
            artifacts.append(
                _artifact_entry(
                    outcome.metadata_path,
                    stage_root,
                    "metadata",
                    area_code=outcome.area_code,
                    request_id=outcome.request_id,
                )
            )
    artifacts.append(
        _payload_artifact_entry(
            path=collection_log_path,
            payload=collection_log_payload,
            stage_root=stage_root,
            artifact_type="collection_log",
        )
    )
    return {
        "data_version": DATA_VERSION,
        "batch_id": batch_id,
        "created_at": created_at.isoformat(),
        "hash_algorithm": "sha256",
        "reference_files": references,
        "artifacts": artifacts,
    }


def _verify_manifest(
    manifest_path: Path,
    stage_root: Path,
    reference_root: Path,
    *,
    pending_artifacts: Mapping[str, bytes] | None = None,
) -> None:
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        references = document["reference_files"]
        artifacts = document["artifacts"]
        if document["hash_algorithm"] != "sha256" or not isinstance(references, list) or not isinstance(artifacts, list):
            raise BatchIntegrityError("integrity_error")
        seen_references: set[str] = set()
        for item in references:
            relative = str(item["path"])
            path = (reference_root / relative).resolve()
            if relative in seen_references or not _is_within(path, reference_root.resolve()):
                raise BatchIntegrityError("integrity_error")
            seen_references.add(relative)
            if path.stat().st_size != int(item["byte_size"]) or _sha256_file(path) != item["sha256"]:
                raise BatchIntegrityError("integrity_error")
        seen_artifacts: set[str] = set()
        for item in artifacts:
            relative = str(item["relative_path"])
            path = (stage_root / relative).resolve()
            if relative in seen_artifacts or not _is_within(path, stage_root.resolve()):
                raise BatchIntegrityError("integrity_error")
            seen_artifacts.add(relative)
            pending_payload = (pending_artifacts or {}).get(relative)
            if pending_payload is not None:
                size = len(pending_payload)
                digest = hashlib.sha256(pending_payload).hexdigest()
            else:
                size = path.stat().st_size
                digest = _sha256_file(path)
            if size != int(item["byte_size"]) or digest != item["sha256"]:
                raise BatchIntegrityError("integrity_error")
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as error:
        if isinstance(error, BatchIntegrityError):
            raise
        raise BatchIntegrityError("integrity_error") from error


def _report_area(outcome: AreaOutcome) -> None:
    print("EG6B_AREA_RESULT")
    print(f"area_code={outcome.area_code}")
    print(f"request_id={outcome.request_id or ''}")
    print(f"collection_status={outcome.collection_status}")
    print(f"raw_saved={'true' if outcome.raw_path else 'false'}")
    print(f"metadata_saved={'true' if outcome.metadata_path else 'false'}")


def _report_summary(summary: Eg6bSummary) -> None:
    print("EG6B_COLLECTION_SUMMARY")
    print(f"batch_id={summary.batch_id}")
    print(f"panel_version={summary.panel_version}")
    print(f"target_count={summary.target_count}")
    print(f"attempted_count={summary.attempted_count}")
    print(f"success_count={summary.success_count}")
    print(f"failure_count={summary.failure_count}")
    print(f"failed_area_codes={','.join(summary.failed_area_codes)}")
    print(f"retry_count={summary.retry_count}")
    print(f"elapsed_seconds={summary.elapsed_seconds:.6f}")
    print(f"raw_file_count={summary.raw_file_count}")
    print(f"metadata_file_count={summary.metadata_file_count}")
    print(f"collection_log_saved={'true' if summary.collection_log_saved else 'false'}")
    print(f"manifest_saved={'true' if summary.manifest_saved else 'false'}")
    print(f"hash_verification_passed={'true' if summary.hash_verification_passed else 'false'}")
    print(f"stage={summary.stage}")
    print(f"exit_code={summary.exit_code}")


def _summary(
    *,
    batch_id: str,
    panel_version: str,
    outcomes: tuple[AreaOutcome, ...],
    elapsed_seconds: float,
    collection_log_saved: bool,
    manifest_saved: bool,
    hash_verification_passed: bool,
    exit_code: int,
) -> Eg6bSummary:
    return Eg6bSummary(
        batch_id=batch_id,
        panel_version=panel_version,
        target_count=len(EG6B_AREA_CODES),
        attempted_count=sum(item.attempted for item in outcomes),
        success_count=sum(item.collection_status == "success" for item in outcomes),
        failure_count=sum(item.collection_status != "success" for item in outcomes),
        failed_area_codes=tuple(item.area_code for item in outcomes if item.collection_status != "success"),
        retry_count=0,
        elapsed_seconds=max(0.0, elapsed_seconds),
        raw_file_count=sum(item.raw_path is not None for item in outcomes),
        metadata_file_count=sum(item.metadata_path is not None for item in outcomes),
        collection_log_saved=collection_log_saved,
        manifest_saved=manifest_saved,
        hash_verification_passed=hash_verification_passed,
        stage=STAGE_NAME,
        exit_code=exit_code,
    )


def _preflight_failure(reason_code: str = "preflight_error") -> int:
    print(f"preflight_status={reason_code}")
    outcomes = _complete_outcomes([])
    summary = _summary(
        batch_id="",
        panel_version=PANEL_VERSION,
        outcomes=outcomes,
        elapsed_seconds=0.0,
        collection_log_saved=False,
        manifest_saved=False,
        hash_verification_passed=False,
        exit_code=2,
    )
    _report_summary(summary)
    return 2


def _execute_batch(
    *,
    snapshot: ReferenceSnapshot,
    api_key: str,
    collector: Collector,
    batch_storage: BatchStorage,
    stage_root: Path,
    batch_id: str,
    clock: Callable[[], datetime],
    monotonic_clock: Callable[[], float],
) -> int:
    started_at = clock()
    started_tick = monotonic_clock()
    outcomes: list[AreaOutcome] = []
    request_ids: set[str] = set()
    common_failure = False

    for panel_order, place in enumerate(snapshot.places, start=1):
        request_id: str | None = None
        try:
            if not _references_unchanged(snapshot):
                common_failure = True
                break
            request = collector.prepare_request(place.area_code)
            request_id = request.request_id
            if request_id in request_ids:
                common_failure = True
                break
            request_ids.add(request_id)
            result = collector.collect(api_key, place.area_code, request=request)
            raw_value = result.metadata.get("raw_file_path")
            outcome = AreaOutcome(
                panel_order=panel_order,
                area_code=place.area_code,
                request_id=request_id,
                attempted=True,
                collection_status=result.status,
                raw_path=Path(str(raw_value)) if raw_value else None,
                metadata_path=result.metadata_path,
            )
        except Exception:
            outcome = AreaOutcome(
                panel_order=panel_order,
                area_code=place.area_code,
                request_id=request_id,
                attempted=request_id is not None,
                collection_status="internal_error",
                raw_path=None,
                metadata_path=None,
            )
            common_failure = True
        outcomes.append(outcome)
        _report_area(outcome)
        if outcome.collection_status in COMMON_FAILURE_STATUSES:
            common_failure = True
        elif outcome.collection_status != "success" and outcome.collection_status not in PER_PLACE_FAILURE_STATUSES:
            common_failure = True
        if not _references_unchanged(snapshot):
            common_failure = True
        if common_failure:
            break

    completed = _complete_outcomes(outcomes)
    finished_at = clock()
    elapsed_seconds = max(0.0, monotonic_clock() - started_tick)
    success_count = sum(item.collection_status == "success" for item in completed)
    exit_code = 2 if common_failure else 0 if success_count == len(EG6B_AREA_CODES) else 1
    collection_log_saved = False
    manifest_saved = False
    hash_verification_passed = False

    try:
        log_document = _collection_log(
            batch_id=batch_id,
            panel_version=snapshot.panel_version,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=elapsed_seconds,
            outcomes=completed,
            stage_root=stage_root,
            exit_code=exit_code,
        )
        collection_log_path = batch_storage.batch_directory / "collection_log.json"
        collection_log_payload = BatchStorage.json_payload(log_document)
        manifest_document = _manifest(
            batch_id=batch_id,
            created_at=finished_at,
            snapshot=snapshot,
            outcomes=completed,
            collection_log_path=collection_log_path,
            collection_log_payload=collection_log_payload,
            stage_root=stage_root,
        )
        manifest_path = batch_storage.save_manifest(manifest_document)
        manifest_saved = True
        log_relative_path = _relative_path(collection_log_path, stage_root)
        _verify_manifest(
            manifest_path,
            stage_root,
            snapshot.paths.root,
            pending_artifacts={log_relative_path: collection_log_payload},
        )
        batch_storage.save_collection_log(log_document)
        collection_log_saved = True
        hash_verification_passed = True
    except Exception:
        exit_code = 2

    summary = _summary(
        batch_id=batch_id,
        panel_version=snapshot.panel_version,
        outcomes=completed,
        elapsed_seconds=elapsed_seconds,
        collection_log_saved=collection_log_saved,
        manifest_saved=manifest_saved,
        hash_verification_passed=hash_verification_passed,
        exit_code=exit_code,
    )
    _report_summary(summary)
    return exit_code


def _run(
    argv: list[str] | None,
    *,
    transport_factory: Callable[[], Transport] | None,
    storage_factory: Callable[[Path, Path], FileStorage],
    batch_storage_factory: Callable[[Path], BatchStorage],
    reference_paths: ReferencePaths,
    clock: Callable[[], datetime],
    monotonic_clock: Callable[[], float],
    request_id_factory: Callable[[], uuid.UUID],
    environ: Mapping[str, str],
) -> int:
    try:
        arguments = build_parser().parse_args(argv)
    except CliInputError:
        return _preflight_failure("input_error")
    if not arguments.execute_live:
        return _preflight_failure("execution_not_approved")
    if arguments.batch_id is None:
        return _preflight_failure("batch_id_required")

    try:
        output_root, stage_root, raw_root, metadata_root, batch_root = _validated_output_paths(
            arguments.output_root
        )
        _ensure_batch_id_available(
            output_root=output_root,
            batch_root=batch_root,
            batch_id=arguments.batch_id,
            environ=environ,
        )
        snapshot = _validate_references(reference_paths)
        api_key = load_api_key(arguments.env_file)
        _probe_storage_roots(raw_root, metadata_root, batch_root)
        batch_id = arguments.batch_id
        storage = storage_factory(raw_root, metadata_root)
        batch_storage = batch_storage_factory(batch_root / batch_id)
        client = _LazyHttpClient(transport_factory if transport_factory is not None else UrllibTransport)
        collector = Collector(
            reference_paths.official_csv,
            client,
            storage,
            clock=clock,
            request_id_factory=request_id_factory,
            timeout_seconds=arguments.timeout,
        )
    except BatchIdConflictError:
        return _preflight_failure("batch_id_conflict")
    except Exception:
        return _preflight_failure()

    return _execute_batch(
        snapshot=snapshot,
        api_key=api_key,
        collector=collector,
        batch_storage=batch_storage,
        stage_root=stage_root,
        batch_id=batch_id,
        clock=clock,
        monotonic_clock=monotonic_clock,
    )


def run(
    argv: list[str] | None = None,
    *,
    transport_factory: Callable[[], Transport] | None = None,
    storage_factory: Callable[[Path, Path], FileStorage] = FileStorage,
    batch_storage_factory: Callable[[Path], BatchStorage] = BatchStorage,
    reference_paths: ReferencePaths = DEFAULT_REFERENCE_PATHS,
    clock: Callable[[], datetime] = now_seoul,
    monotonic_clock: Callable[[], float] = time.monotonic,
    request_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    environ: Mapping[str, str] | None = None,
) -> int:
    environment = os.environ if environ is None else environ
    try:
        return _run(
            argv,
            transport_factory=transport_factory,
            storage_factory=storage_factory,
            batch_storage_factory=batch_storage_factory,
            reference_paths=reference_paths,
            clock=clock,
            monotonic_clock=monotonic_clock,
            request_id_factory=request_id_factory,
            environ=environment,
        )
    except Exception:
        return _preflight_failure()


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
