"""EG-8B B1: Dataset Profile, Time Coverage, and Forecast-Current Exact Join.

Reads an EG-8A Loader V0 dataset directory (produced by
`eg8a.export_dataset`) read-only, validates its provenance (file presence,
recorded dataset_id, output-artifact SHA-256, and Manifest row counts all
checked against the actual files), and writes five downstream analysis
artifacts to an external output-root with the same exclusive-create,
no-overwrite semantics as eg8a.py's own Output Writer.

B0 Baseline computation and Seoul Forecast error metrics (MAE/RMSE/relative
error/etc.) are EG-8B B2a's responsibility and are not implemented here.
This module produces the exact-matched Forecast<->Current join table
(`forecast_evaluation_pairs.csv`) so B2a can compute error metrics from it
without redoing the join.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import statistics
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from . import eg8a

FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV = "FRESHMANAGER_EG8B_OUTPUT_ROOT"
PHASE1_VERSION = "phase1-v1"
DATASET_PROFILE_SCHEMA_VERSION = "eg8b-dataset-profile-v1"
FORECAST_MATCH_SUMMARY_SCHEMA_VERSION = "eg8b-forecast-match-summary-v1"

DATASET_PROFILE_FILENAME = "dataset_profile.json"
AREA_CURRENT_SUMMARY_FILENAME = "area_current_summary.csv"
TIME_COVERAGE_FILENAME = "time_coverage.csv"
FORECAST_MATCH_SUMMARY_FILENAME = "forecast_match_summary.json"
FORECAST_EVALUATION_PAIRS_FILENAME = "forecast_evaluation_pairs.csv"

ERROR_DATASET_FILE_MISSING = "DATASET_FILE_MISSING"
ERROR_DATASET_ID_MISMATCH = "DATASET_ID_MISMATCH"
ERROR_DATASET_HASH_MISMATCH = "DATASET_HASH_MISMATCH"
ERROR_DATASET_ROW_COUNT_MISMATCH = "DATASET_ROW_COUNT_MISMATCH"

_REQUIRED_FILES = (
    eg8a.CURRENT_OUTPUT_FILENAME,
    eg8a.FORECAST_OUTPUT_FILENAME,
    eg8a.ERROR_ROWS_OUTPUT_FILENAME,
    eg8a.QUALITY_REPORT_OUTPUT_FILENAME,
    eg8a.DATASET_MANIFEST_OUTPUT_FILENAME,
)
_HASHED_ARTIFACT_FILES = (
    eg8a.CURRENT_OUTPUT_FILENAME,
    eg8a.FORECAST_OUTPUT_FILENAME,
    eg8a.ERROR_ROWS_OUTPUT_FILENAME,
    eg8a.QUALITY_REPORT_OUTPUT_FILENAME,
)

AREA_CURRENT_SUMMARY_FIELDNAMES = (
    "area_code",
    "row_count",
    "population_min_min",
    "population_min_median",
    "population_min_max",
    "population_max_min",
    "population_max_median",
    "population_max_max",
    "population_mid_min",
    "population_mid_median",
    "population_mid_max",
    "observed_at_first",
    "observed_at_last",
    "consecutive_pairs_within_6min",
    "consecutive_pairs_total",
    "congestion_level_counts_json",
)
TIME_COVERAGE_FIELDNAMES = (
    "collection_run_id",
    "run_start_called_at",
    "run_min_observed_at",
    "run_max_observed_at",
    "distinct_observed_at_count_in_run",
    "area_count",
    "gap_from_previous_run_minutes",
    "hour_of_day",
)
FORECAST_EVALUATION_PAIRS_FIELDNAMES = (
    "area_code",
    "forecast_collection_run_id",
    "forecast_called_at",
    "forecast_observed_at",
    "forecast_at",
    "horizon_minutes",
    "forecast_congestion_level",
    "forecast_population_min",
    "forecast_population_max",
    "forecast_population_mid",
    "current_collection_run_id",
    "current_called_at",
    "current_congestion_level",
    "current_population_min",
    "current_population_max",
    "current_population_mid",
    "current_duplicate_flag",
    "forecast_duplicate_flag",
)


class DatasetValidationError(ValueError):
    """Raised when the EG-8A dataset directory fails provenance validation."""


class EvidenceWriteError(OSError):
    """Raised when an EG-8B output file or directory cannot be written safely."""


class OutputRootConfigurationError(EvidenceWriteError):
    """Raised when FRESHMANAGER_EG8B_OUTPUT_ROOT is unset or invalid."""


@dataclass(frozen=True)
class CurrentRow:
    collection_run_id: str
    called_at: str
    observed_at: str
    area_code: str
    congestion_level: str
    population_min: int
    population_max: int
    population_mid: float
    duplicate_flag: bool


@dataclass(frozen=True)
class ForecastRow:
    collection_run_id: str
    called_at: str
    observed_at: str
    forecast_at: str
    area_code: str
    forecast_congestion_level: str
    forecast_population_min: int
    forecast_population_max: int
    forecast_population_mid: float
    duplicate_flag: bool


@dataclass(frozen=True)
class DatasetBundle:
    dataset_id: str
    dataset_dir: Path
    manifest: Mapping[str, object]
    quality_report: Mapping[str, object]
    current_rows: tuple[CurrentRow, ...]
    forecast_rows: tuple[ForecastRow, ...]
    error_row_count: int


@dataclass(frozen=True)
class Eg8bAnalysisResult:
    dataset_id: str
    phase_dir: Path
    dataset_profile: Mapping[str, object]
    forecast_match_summary: Mapping[str, object]


# ---------------------------------------------------------------------------
# Input validation and loading (ML_READY_DATASET_SPEC.md-adjacent contract:
# never modifies dataset_dir; fails closed on any provenance mismatch)
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DatasetValidationError(
            f"{ERROR_DATASET_FILE_MISSING}: {label} is unreadable"
        ) from error
    if not isinstance(document, dict):
        raise DatasetValidationError(
            f"{ERROR_DATASET_FILE_MISSING}: {label} is not a JSON object"
        )
    return document


def _read_csv_rows(path: Path, *, label: str) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as error:
        raise DatasetValidationError(
            f"{ERROR_DATASET_FILE_MISSING}: {label} is unreadable"
        ) from error


def _current_row_from_dict(raw: Mapping[str, str]) -> CurrentRow:
    return CurrentRow(
        collection_run_id=raw["collection_run_id"],
        called_at=raw["called_at"],
        observed_at=raw["observed_at"],
        area_code=raw["area_code"],
        congestion_level=raw["congestion_level"],
        population_min=int(raw["population_min"]),
        population_max=int(raw["population_max"]),
        population_mid=float(raw["population_mid"]),
        duplicate_flag=raw["duplicate_flag"] == "true",
    )


def _forecast_row_from_dict(raw: Mapping[str, str]) -> ForecastRow:
    return ForecastRow(
        collection_run_id=raw["collection_run_id"],
        called_at=raw["called_at"],
        observed_at=raw["observed_at"],
        forecast_at=raw["forecast_at"],
        area_code=raw["area_code"],
        forecast_congestion_level=raw["forecast_congestion_level"],
        forecast_population_min=int(raw["forecast_population_min"]),
        forecast_population_max=int(raw["forecast_population_max"]),
        forecast_population_mid=float(raw["forecast_population_mid"]),
        duplicate_flag=raw["duplicate_flag"] == "true",
    )


def load_dataset_bundle(
    dataset_dir: Path,
    *,
    expected_dataset_id: str | None = None,
) -> DatasetBundle:
    """Load and validate an EG-8A Loader V0 dataset directory read-only.

    Validation order: file existence -> dataset_id match -> output artifact
    SHA-256 match -> row count match. Each step's precondition depends on
    the previous ones passing (hashing a file that is not there is
    meaningless; comparing row counts when the hash already disagrees would
    compare against a Manifest that may describe a different file
    version). Raises DatasetValidationError on any failure and never
    modifies dataset_dir.
    """
    if not dataset_dir.is_dir():
        raise DatasetValidationError(
            f"{ERROR_DATASET_FILE_MISSING}: dataset directory does not exist"
        )

    file_paths: dict[str, Path] = {}
    for filename in _REQUIRED_FILES:
        path = dataset_dir / filename
        if not path.is_file():
            raise DatasetValidationError(f"{ERROR_DATASET_FILE_MISSING}: {filename}")
        file_paths[filename] = path

    manifest = _read_json_object(
        file_paths[eg8a.DATASET_MANIFEST_OUTPUT_FILENAME],
        label=eg8a.DATASET_MANIFEST_OUTPUT_FILENAME,
    )

    manifest_dataset_id = manifest.get("dataset_id")
    if not isinstance(manifest_dataset_id, str) or not manifest_dataset_id:
        raise DatasetValidationError(
            f"{ERROR_DATASET_ID_MISMATCH}: manifest dataset_id is missing or invalid"
        )
    if expected_dataset_id is not None and manifest_dataset_id != expected_dataset_id:
        raise DatasetValidationError(
            f"{ERROR_DATASET_ID_MISMATCH}: expected {expected_dataset_id!r}, "
            f"manifest has {manifest_dataset_id!r}"
        )

    output_artifacts = manifest.get("output_artifacts")
    if not isinstance(output_artifacts, list):
        raise DatasetValidationError(
            f"{ERROR_DATASET_HASH_MISMATCH}: manifest output_artifacts is missing"
        )
    artifacts_by_relative_path = {
        artifact.get("relative_path"): artifact
        for artifact in output_artifacts
        if isinstance(artifact, dict)
    }
    for filename in _HASHED_ARTIFACT_FILES:
        artifact = artifacts_by_relative_path.get(filename)
        if not isinstance(artifact, dict) or not isinstance(artifact.get("sha256"), str):
            raise DatasetValidationError(
                f"{ERROR_DATASET_HASH_MISMATCH}: manifest missing artifact entry for {filename}"
            )
        if _sha256_file(file_paths[filename]) != artifact["sha256"]:
            raise DatasetValidationError(f"{ERROR_DATASET_HASH_MISMATCH}: {filename}")

    quality_report = _read_json_object(
        file_paths[eg8a.QUALITY_REPORT_OUTPUT_FILENAME],
        label=eg8a.QUALITY_REPORT_OUTPUT_FILENAME,
    )
    current_raw_rows = _read_csv_rows(
        file_paths[eg8a.CURRENT_OUTPUT_FILENAME], label=eg8a.CURRENT_OUTPUT_FILENAME
    )
    forecast_raw_rows = _read_csv_rows(
        file_paths[eg8a.FORECAST_OUTPUT_FILENAME], label=eg8a.FORECAST_OUTPUT_FILENAME
    )
    error_raw_rows = _read_csv_rows(
        file_paths[eg8a.ERROR_ROWS_OUTPUT_FILENAME], label=eg8a.ERROR_ROWS_OUTPUT_FILENAME
    )

    source_row_counts = manifest.get("source_row_counts")
    if not isinstance(source_row_counts, dict):
        raise DatasetValidationError(
            f"{ERROR_DATASET_ROW_COUNT_MISMATCH}: manifest source_row_counts is missing"
        )
    for key, actual_count in (
        ("current_normal_rows", len(current_raw_rows)),
        ("forecast_normal_rows", len(forecast_raw_rows)),
        ("error_rows_total", len(error_raw_rows)),
    ):
        if source_row_counts.get(key) != actual_count:
            raise DatasetValidationError(
                f"{ERROR_DATASET_ROW_COUNT_MISMATCH}: {key} manifest="
                f"{source_row_counts.get(key)!r} actual={actual_count}"
            )

    return DatasetBundle(
        dataset_id=manifest_dataset_id,
        dataset_dir=dataset_dir,
        manifest=manifest,
        quality_report=quality_report,
        current_rows=tuple(_current_row_from_dict(row) for row in current_raw_rows),
        forecast_rows=tuple(_forecast_row_from_dict(row) for row in forecast_raw_rows),
        error_row_count=len(error_raw_rows),
    )


# ---------------------------------------------------------------------------
# Dataset Profile
# ---------------------------------------------------------------------------


def build_dataset_profile(
    bundle: DatasetBundle,
    *,
    generated_at: datetime,
) -> dict[str, object]:
    """Build the EG-8B Dataset Profile.

    Deliberately does not repeat duplicate-rate/collection-lag/area-match-
    rate numbers already present in the upstream quality_report.json (which
    remains readable inside the same dataset directory) -- only provenance
    validation results and information not already in quality_report.json.
    """
    must_produce = bundle.quality_report.get("must_produce", {})
    area_row_counts = must_produce.get("area_row_counts", {}) if isinstance(must_produce, dict) else {}
    official_area_codes = (
        area_row_counts.get("official_area_codes", []) if isinstance(area_row_counts, dict) else []
    )
    official_area_set = set(official_area_codes)
    current_areas = {row.area_code for row in bundle.current_rows}
    forecast_areas = {row.area_code for row in bundle.forecast_rows}

    called_ats = [datetime.fromisoformat(row.called_at) for row in bundle.current_rows] + [
        datetime.fromisoformat(row.called_at) for row in bundle.forecast_rows
    ]
    current_observed = [datetime.fromisoformat(row.observed_at) for row in bundle.current_rows]
    forecast_observed = [datetime.fromisoformat(row.observed_at) for row in bundle.forecast_rows]
    forecast_targets = [datetime.fromisoformat(row.forecast_at) for row in bundle.forecast_rows]
    run_ids = {row.collection_run_id for row in bundle.current_rows}

    return {
        "schema_version": DATASET_PROFILE_SCHEMA_VERSION,
        "dataset_id": bundle.dataset_id,
        "generated_at": eg8a.to_iso8601(generated_at),
        "source": {
            "loader_version": bundle.manifest.get("loader_version"),
            "dataset_version": bundle.manifest.get("dataset_version"),
            "quality_report_schema_version": bundle.quality_report.get("schema_version"),
        },
        "provenance_validation": {
            "all_files_present": True,
            "all_output_hashes_match": True,
            "row_counts_match_manifest": True,
        },
        "row_counts": {
            "current_rows": len(bundle.current_rows),
            "forecast_rows": len(bundle.forecast_rows),
            "error_rows": bundle.error_row_count,
        },
        "area_coverage": {
            "official_area_count": len(official_area_codes),
            "observed_current_area_count": len(current_areas),
            "observed_forecast_area_count": len(forecast_areas),
            "unexpected_areas": sorted((current_areas | forecast_areas) - official_area_set),
            "missing_areas": sorted(official_area_set - (current_areas | forecast_areas)),
        },
        "time_range": {
            "called_at_min": min(called_ats).isoformat() if called_ats else None,
            "called_at_max": max(called_ats).isoformat() if called_ats else None,
            "current_observed_at_min": min(current_observed).isoformat() if current_observed else None,
            "current_observed_at_max": max(current_observed).isoformat() if current_observed else None,
            "forecast_observed_at_min": min(forecast_observed).isoformat() if forecast_observed else None,
            "forecast_observed_at_max": max(forecast_observed).isoformat() if forecast_observed else None,
            "forecast_at_min": min(forecast_targets).isoformat() if forecast_targets else None,
            "forecast_at_max": max(forecast_targets).isoformat() if forecast_targets else None,
            "total_span_seconds": (
                (max(called_ats) - min(called_ats)).total_seconds() if called_ats else None
            ),
        },
        "collection_run_count": len(run_ids),
    }


# ---------------------------------------------------------------------------
# Current Area Summary
# ---------------------------------------------------------------------------


def build_area_current_summary_rows(bundle: DatasetBundle) -> list[dict[str, object]]:
    by_area: dict[str, list[CurrentRow]] = defaultdict(list)
    for row in bundle.current_rows:
        by_area[row.area_code].append(row)

    rows: list[dict[str, object]] = []
    for area_code in sorted(by_area):
        area_rows = sorted(by_area[area_code], key=lambda r: r.observed_at)
        pop_min = [r.population_min for r in area_rows]
        pop_max = [r.population_max for r in area_rows]
        pop_mid = [r.population_mid for r in area_rows]
        observed_times = [datetime.fromisoformat(r.observed_at) for r in area_rows]
        consecutive_pairs = sum(
            1
            for earlier, later in zip(observed_times, observed_times[1:])
            if (later - earlier).total_seconds() <= 360
        )
        congestion_counts = Counter(r.congestion_level for r in area_rows)
        rows.append(
            {
                "area_code": area_code,
                "row_count": len(area_rows),
                "population_min_min": min(pop_min),
                "population_min_median": statistics.median(pop_min),
                "population_min_max": max(pop_min),
                "population_max_min": min(pop_max),
                "population_max_median": statistics.median(pop_max),
                "population_max_max": max(pop_max),
                "population_mid_min": min(pop_mid),
                "population_mid_median": statistics.median(pop_mid),
                "population_mid_max": max(pop_mid),
                "observed_at_first": area_rows[0].observed_at,
                "observed_at_last": area_rows[-1].observed_at,
                "consecutive_pairs_within_6min": consecutive_pairs,
                "consecutive_pairs_total": max(0, len(area_rows) - 1),
                "congestion_level_counts_json": json.dumps(
                    dict(congestion_counts), ensure_ascii=False, sort_keys=True
                ),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Time Coverage -- one row per collection_run_id. Real EG-8A datasets have
# exactly one distinct observed_at per run (all 13 areas share one instant),
# so this single granularity captures both the run-cadence view and the
# observed_at-level view. distinct_observed_at_count_in_run measures that
# uniformity rather than assuming it, so a future dataset that breaks it is
# still faithfully represented (not silently collapsed).
# ---------------------------------------------------------------------------


def build_time_coverage_rows(bundle: DatasetBundle) -> list[dict[str, object]]:
    by_run: dict[str, list[CurrentRow]] = defaultdict(list)
    for row in bundle.current_rows:
        by_run[row.collection_run_id].append(row)

    run_summaries = []
    for run_id, rows in by_run.items():
        called_ats = [datetime.fromisoformat(r.called_at) for r in rows]
        observed_ats = [datetime.fromisoformat(r.observed_at) for r in rows]
        run_summaries.append(
            {
                "collection_run_id": run_id,
                "run_start_called_at": min(called_ats),
                "run_min_observed_at": min(observed_ats),
                "run_max_observed_at": max(observed_ats),
                "distinct_observed_at_count_in_run": len(set(observed_ats)),
                "area_count": len(rows),
            }
        )
    run_summaries.sort(key=lambda item: item["run_start_called_at"])

    output_rows: list[dict[str, object]] = []
    previous_start: datetime | None = None
    for summary in run_summaries:
        start = summary["run_start_called_at"]
        gap_minutes = (
            (start - previous_start).total_seconds() / 60 if previous_start is not None else None
        )
        output_rows.append(
            {
                "collection_run_id": summary["collection_run_id"],
                "run_start_called_at": start.isoformat(),
                "run_min_observed_at": summary["run_min_observed_at"].isoformat(),
                "run_max_observed_at": summary["run_max_observed_at"].isoformat(),
                "distinct_observed_at_count_in_run": summary["distinct_observed_at_count_in_run"],
                "area_count": summary["area_count"],
                "gap_from_previous_run_minutes": gap_minutes,
                "hour_of_day": summary["run_min_observed_at"].hour,
            }
        )
        previous_start = start
    return output_rows


# ---------------------------------------------------------------------------
# Forecast-Current Exact Join
# ---------------------------------------------------------------------------


def _build_current_index(bundle: DatasetBundle) -> dict[tuple[str, str], CurrentRow]:
    """Index Current rows by (area_code, observed_at).

    This key is guaranteed unique per row by eg8a's own upstream structural
    dedup contract: normalize_v3_sources isolates any row sharing a
    (collection_run_id, area_code_requested) Source Correlation Key as
    CURRENT_KEY_DUPLICATE before a record ever reaches the normal output --
    but that key includes collection_run_id, not observed_at directly. Two
    different runs could in principle report the same (area_code,
    observed_at) pair without tripping that check. In every real dataset
    profiled so far this has not occurred (semantic_duplicate_rate 0.0), but
    if it ever does, this index keeps only the last-seen row for that key
    (a silent, order-dependent pick) -- callers who need to detect this
    should inspect NormalizedCurrentRecord.duplicate_flag in the upstream
    Quality Report rather than relying on this index alone.
    """
    index: dict[tuple[str, str], CurrentRow] = {}
    for row in bundle.current_rows:
        index[(row.area_code, row.observed_at)] = row
    return index


def _forecast_horizon_minutes(row: ForecastRow) -> int:
    return round(
        (datetime.fromisoformat(row.forecast_at) - datetime.fromisoformat(row.observed_at)).total_seconds()
        / 60
    )


def build_forecast_match_summary(bundle: DatasetBundle) -> dict[str, object]:
    current_index = _build_current_index(bundle)
    current_observed_ats = [datetime.fromisoformat(row.observed_at) for row in bundle.current_rows]
    max_current_observed_at = max(current_observed_ats) if current_observed_ats else None

    exact_match = 0
    no_match_boundary = 0
    no_match_other = 0
    match_by_area: Counter = Counter()
    match_total_by_area: Counter = Counter()
    horizon_histogram: Counter = Counter()
    matched_horizon_histogram: Counter = Counter()
    unique_targets: set[tuple[str, str]] = set()

    for row in bundle.forecast_rows:
        key = (row.area_code, row.forecast_at)
        unique_targets.add(key)
        match_total_by_area[row.area_code] += 1
        horizon_minutes = _forecast_horizon_minutes(row)
        horizon_histogram[horizon_minutes] += 1
        if key in current_index:
            exact_match += 1
            match_by_area[row.area_code] += 1
            matched_horizon_histogram[horizon_minutes] += 1
        elif max_current_observed_at is not None and datetime.fromisoformat(row.forecast_at) > max_current_observed_at:
            no_match_boundary += 1
        else:
            no_match_other += 1

    total = len(bundle.forecast_rows)
    return {
        "schema_version": FORECAST_MATCH_SUMMARY_SCHEMA_VERSION,
        "dataset_id": bundle.dataset_id,
        "total_forecast_rows": total,
        "unique_forecast_targets": len(unique_targets),
        "exact_match_rows": exact_match,
        "no_match_dataset_boundary_rows": no_match_boundary,
        "no_match_other_rows": no_match_other,
        "exact_match_rate": (exact_match / total) if total else None,
        "match_by_area": dict(sorted(match_by_area.items())),
        "match_total_by_area": dict(sorted(match_total_by_area.items())),
        "horizon_minutes_present": sorted(horizon_histogram),
        "horizon_minutes_histogram": {str(k): v for k, v in sorted(horizon_histogram.items())},
        "matched_horizon_minutes_histogram": {
            str(k): v for k, v in sorted(matched_horizon_histogram.items())
        },
    }


def build_forecast_evaluation_pairs_rows(bundle: DatasetBundle) -> list[dict[str, object]]:
    """Return the exact-matched Forecast<->Current join table.

    Contains raw fields only -- no computed error metrics (MAE/RMSE/etc.
    are EG-8B B2a's responsibility). Unmatched forecasts are not included:
    an "evaluation pair" requires an observed counterpart to pair with.
    """
    current_index = _build_current_index(bundle)
    rows: list[dict[str, object]] = []
    for row in bundle.forecast_rows:
        matched = current_index.get((row.area_code, row.forecast_at))
        if matched is None:
            continue
        rows.append(
            {
                "area_code": row.area_code,
                "forecast_collection_run_id": row.collection_run_id,
                "forecast_called_at": row.called_at,
                "forecast_observed_at": row.observed_at,
                "forecast_at": row.forecast_at,
                "horizon_minutes": _forecast_horizon_minutes(row),
                "forecast_congestion_level": row.forecast_congestion_level,
                "forecast_population_min": row.forecast_population_min,
                "forecast_population_max": row.forecast_population_max,
                "forecast_population_mid": row.forecast_population_mid,
                "current_collection_run_id": matched.collection_run_id,
                "current_called_at": matched.called_at,
                "current_congestion_level": matched.congestion_level,
                "current_population_min": matched.population_min,
                "current_population_max": matched.population_max,
                "current_population_mid": matched.population_mid,
                "current_duplicate_flag": matched.duplicate_flag,
                "forecast_duplicate_flag": row.duplicate_flag,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Output Writer -- exclusive create, never overwrites. <dataset_id> may
# already exist (a later phase/version can coexist under the same parent);
# <PHASE1_VERSION> itself must not.
# ---------------------------------------------------------------------------


def resolve_output_root_from_env(environ: Mapping[str, str]) -> Path:
    """Resolve the external EG-8B output-root from the environment.

    Never defaults to a path inside the repository; fails closed with a
    non-sensitive error if the variable is unset or does not name an
    existing directory. Never returns the value in an error message.
    """
    value = environ.get(FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV)
    if not value:
        raise OutputRootConfigurationError(
            f"eg8b_output_root_error: {FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV} is not set"
        )
    try:
        resolved = Path(value).expanduser().resolve(strict=True)
    except OSError as error:
        raise OutputRootConfigurationError(
            f"eg8b_output_root_error: {FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV} does not exist"
        ) from error
    if not resolved.is_dir():
        raise OutputRootConfigurationError(
            f"eg8b_output_root_error: {FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV} is not a directory"
        )
    return resolved


def _write_exclusive(path: Path, payload: bytes) -> None:
    """Write `payload` to `path`; raise EvidenceWriteError instead of ever
    overwriting an existing file (mkstemp + fsync + os.link, mirroring
    storage.py's/eg8a.py's exclusive-write algorithm)."""
    partial_path: Path | None = None
    try:
        descriptor, partial_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".partial", dir=path.parent
        )
        partial_path = Path(partial_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(partial_path, path)
    except FileExistsError as error:
        raise EvidenceWriteError(f"eg8b_write_error: {path.name} already exists") from error
    except OSError as error:
        raise EvidenceWriteError(f"eg8b_write_error: failed to write {path.name}") from error
    finally:
        if partial_path is not None:
            try:
                partial_path.unlink()
            except OSError:
                pass


def _bool_str(value: object) -> object:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _write_csv_rows(fieldnames: Sequence[str], rows: Sequence[Mapping[str, object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(fieldnames))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _bool_str(value) for key, value in row.items()})
    return buffer.getvalue().encode("utf-8")


def _write_json_document(document: Mapping[str, object]) -> bytes:
    return (json.dumps(dict(document), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def analyze_dataset(
    bundle: DatasetBundle,
    *,
    eg8b_output_root: Path,
    generated_at: datetime | None = None,
) -> Eg8bAnalysisResult:
    """Write the five B1 analysis artifacts for one validated dataset bundle.

    `eg8b_output_root` must already exist (never auto-created). The
    `<dataset_id>` directory may already exist (so other phases/versions can
    coexist under it); `<PHASE1_VERSION>` beneath it is created exclusively
    -- a colliding run raises before any file is touched.
    """
    resolved_root = eg8b_output_root.expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise EvidenceWriteError("eg8b_write_error: output root is not a directory")

    resolved_generated_at = generated_at if generated_at is not None else datetime.now(eg8a.SEOUL)

    dataset_dir = resolved_root / bundle.dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    phase_dir = dataset_dir / PHASE1_VERSION
    try:
        phase_dir.mkdir(exist_ok=False)
    except FileExistsError as error:
        raise EvidenceWriteError(
            f"eg8b_write_error: {PHASE1_VERSION} already exists for dataset {bundle.dataset_id}"
        ) from error

    profile = build_dataset_profile(bundle, generated_at=resolved_generated_at)
    area_summary_rows = build_area_current_summary_rows(bundle)
    time_coverage_rows = build_time_coverage_rows(bundle)
    match_summary = build_forecast_match_summary(bundle)
    evaluation_pairs_rows = build_forecast_evaluation_pairs_rows(bundle)

    _write_exclusive(phase_dir / DATASET_PROFILE_FILENAME, _write_json_document(profile))
    _write_exclusive(
        phase_dir / AREA_CURRENT_SUMMARY_FILENAME,
        _write_csv_rows(AREA_CURRENT_SUMMARY_FIELDNAMES, area_summary_rows),
    )
    _write_exclusive(
        phase_dir / TIME_COVERAGE_FILENAME,
        _write_csv_rows(TIME_COVERAGE_FIELDNAMES, time_coverage_rows),
    )
    _write_exclusive(phase_dir / FORECAST_MATCH_SUMMARY_FILENAME, _write_json_document(match_summary))
    _write_exclusive(
        phase_dir / FORECAST_EVALUATION_PAIRS_FILENAME,
        _write_csv_rows(FORECAST_EVALUATION_PAIRS_FIELDNAMES, evaluation_pairs_rows),
    )

    return Eg8bAnalysisResult(
        dataset_id=bundle.dataset_id,
        phase_dir=phase_dir,
        dataset_profile=profile,
        forecast_match_summary=match_summary,
    )


def run_phase1(
    dataset_dir: Path,
    *,
    eg8b_output_root: Path,
    expected_dataset_id: str | None = None,
) -> Eg8bAnalysisResult:
    """Validate an EG-8A dataset directory and write the B1 analysis artifacts."""
    bundle = load_dataset_bundle(dataset_dir, expected_dataset_id=expected_dataset_id)
    return analyze_dataset(bundle, eg8b_output_root=eg8b_output_root)
