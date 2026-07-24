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

DATASET_READINESS_READY_FOR_PHASE1 = "READY_FOR_EG8B_PHASE1_ANALYSIS"
"""Means only: the dataset directory passed load_dataset_bundle's four
provenance checks (file presence, dataset_id, output-artifact SHA-256,
Manifest row counts) and EG-8B B1's analysis functions can run on it.
Does NOT mean: ML training readiness, Seoul Forecast performance passed,
EG-8B as a whole complete, or Recommendation output possible. This is the
only value build_dataset_profile ever produces -- it is reached only after
load_dataset_bundle already succeeded, so it is an invariant marker, not a
computed judgment."""

RECORD_TYPE_RUN = "RUN"
RECORD_TYPE_HOUR = "HOUR"
RUN_COMPLETENESS_COMPLETE = "COMPLETE"
RUN_COMPLETENESS_PARTIAL = "PARTIAL"
FIVE_MINUTE_CADENCE_MINUTES = 5.0
"""The PM_APPROVED_FIXED long-term cadence (AGENTS.md §18, eg7.CADENCE_MINUTES).
Deviation is a strict inequality against this exact value -- no new tolerance
window is introduced."""

MATCH_STATUS_EXACT_MATCH = "EXACT_MATCH"
MATCH_STATUS_BEFORE_DATASET_START = "BEFORE_DATASET_START"
MATCH_STATUS_AFTER_DATASET_END = "AFTER_DATASET_END"
MATCH_STATUS_CURRENT_TARGET_MISSING = "CURRENT_TARGET_MISSING"
MATCH_STATUS_AREA_NOT_FOUND = "AREA_NOT_FOUND"
MATCH_STATUSES = (
    MATCH_STATUS_EXACT_MATCH,
    MATCH_STATUS_BEFORE_DATASET_START,
    MATCH_STATUS_AFTER_DATASET_END,
    MATCH_STATUS_CURRENT_TARGET_MISSING,
    MATCH_STATUS_AREA_NOT_FOUND,
)

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
    "unique_collection_run_count",
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
    "max_observation_gap_minutes",
    "error_row_count",
    "congestion_level_counts_json",
)
TIME_COVERAGE_FIELDNAMES = (
    "record_type",
    "collection_run_id",
    "run_start_called_at",
    "run_min_observed_at",
    "run_max_observed_at",
    "distinct_observed_at_count_in_run",
    "area_count",
    "run_completeness",
    "gap_from_previous_run_minutes",
    "five_minute_contract_deviation",
    "hour_of_day",
    "hour_date",
    "hour_current_row_count",
    "hour_distinct_observed_at_count",
    "hour_area_coverage_count",
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
    error_rows: tuple[Mapping[str, str], ...]


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
        error_rows=tuple(error_raw_rows),
    )


# ---------------------------------------------------------------------------
# Dataset Profile
# ---------------------------------------------------------------------------


def _official_area_codes(bundle: DatasetBundle) -> list[str]:
    must_produce = bundle.quality_report.get("must_produce", {})
    area_row_counts = must_produce.get("area_row_counts", {}) if isinstance(must_produce, dict) else {}
    codes = area_row_counts.get("official_area_codes", []) if isinstance(area_row_counts, dict) else []
    return list(codes) if isinstance(codes, list) else []


def _quality_report_path(bundle: DatasetBundle, *path_keys: str) -> object:
    """Drill into bundle.quality_report along `path_keys`, returning None if
    any segment is absent or not a mapping -- defensive against an upstream
    schema this module does not fully control."""
    node: object = bundle.quality_report
    for key in path_keys:
        if not isinstance(node, Mapping):
            return None
        node = node.get(key)
    return node


def _collection_lag_seconds_list(
    rows: Sequence[CurrentRow] | Sequence[ForecastRow],
) -> list[float]:
    """Per-row called_at - observed_at, in seconds. Same lag definition as
    eg8a.build_quality_report's own collection_lag_seconds computation."""
    return [
        (datetime.fromisoformat(row.called_at) - datetime.fromisoformat(row.observed_at)).total_seconds()
        for row in rows
    ]


def build_dataset_profile(
    bundle: DatasetBundle,
    *,
    generated_at: datetime,
) -> dict[str, object]:
    """Build the EG-8B Dataset Profile.

    duplicate_rate and area_code_match_rate are read verbatim from the
    upstream quality_report.json (never recomputed with a different
    formula). collection_lag_seconds reuses quality_report.json's mean/min/
    max verbatim and adds median (absent upstream) computed from the same
    per-row called_at-observed_at definition eg8a itself uses.
    """
    official_area_codes = _official_area_codes(bundle)
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

    data_dates = sorted({datetime.fromisoformat(row.observed_at).date().isoformat() for row in bundle.current_rows})

    current_lag = _collection_lag_seconds_list(bundle.current_rows)
    forecast_lag = _collection_lag_seconds_list(bundle.forecast_rows)

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
        "dataset_readiness": DATASET_READINESS_READY_FOR_PHASE1,
        "row_counts": {
            "current_rows": len(bundle.current_rows),
            "forecast_rows": len(bundle.forecast_rows),
            "error_rows": len(bundle.error_rows),
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
            "data_date_count": len(data_dates),
            "data_dates": data_dates,
        },
        "collection_run_count": len(run_ids),
        "duplicate_rate": {
            "current": _quality_report_path(
                bundle, "recommended", "current_duplicate", "semantic_duplicate_rate"
            ),
            "forecast": _quality_report_path(
                bundle, "recommended", "forecast_target_duplicate", "semantic_duplicate_rate"
            ),
        },
        "area_code_match_rate": {
            "current": _quality_report_path(bundle, "recommended", "area_code_match_rate", "current"),
            "forecast": _quality_report_path(bundle, "recommended", "area_code_match_rate", "forecast"),
        },
        "collection_lag_seconds": {
            "current": {
                "mean": _quality_report_path(bundle, "recommended", "collection_lag_seconds", "current", "mean"),
                "min": _quality_report_path(bundle, "recommended", "collection_lag_seconds", "current", "min"),
                "median": statistics.median(current_lag) if current_lag else None,
                "max": _quality_report_path(bundle, "recommended", "collection_lag_seconds", "current", "max"),
            },
            "forecast": {
                "mean": _quality_report_path(bundle, "recommended", "collection_lag_seconds", "forecast", "mean"),
                "min": _quality_report_path(bundle, "recommended", "collection_lag_seconds", "forecast", "min"),
                "median": statistics.median(forecast_lag) if forecast_lag else None,
                "max": _quality_report_path(bundle, "recommended", "collection_lag_seconds", "forecast", "max"),
            },
        },
    }


# ---------------------------------------------------------------------------
# Current Area Summary
# ---------------------------------------------------------------------------


def _error_row_area_code(raw_error_row: Mapping[str, str]) -> str | None:
    """Attribute an Error Row to an official Area: area_code_requested first,
    area_code_returned as fallback, or unattributed (None) if both are
    absent -- never guessed onto an arbitrary official Area."""
    requested = (raw_error_row.get("area_code_requested") or "").strip()
    if requested:
        return requested
    returned = (raw_error_row.get("area_code_returned") or "").strip()
    if returned:
        return returned
    return None


def build_area_current_summary_rows(bundle: DatasetBundle) -> list[dict[str, object]]:
    by_area: dict[str, list[CurrentRow]] = defaultdict(list)
    for row in bundle.current_rows:
        by_area[row.area_code].append(row)

    error_counts_by_area: Counter = Counter()
    for raw_error_row in bundle.error_rows:
        attributed_area = _error_row_area_code(raw_error_row)
        if attributed_area is not None:
            error_counts_by_area[attributed_area] += 1

    rows: list[dict[str, object]] = []
    for area_code in sorted(by_area):
        area_rows = sorted(by_area[area_code], key=lambda r: r.observed_at)
        pop_min = [r.population_min for r in area_rows]
        pop_max = [r.population_max for r in area_rows]
        pop_mid = [r.population_mid for r in area_rows]
        observed_times = [datetime.fromisoformat(r.observed_at) for r in area_rows]
        gaps_minutes = [
            (later - earlier).total_seconds() / 60
            for earlier, later in zip(observed_times, observed_times[1:])
        ]
        consecutive_pairs = sum(1 for gap in gaps_minutes if gap <= 6.0)
        congestion_counts = Counter(r.congestion_level for r in area_rows)
        rows.append(
            {
                "area_code": area_code,
                "row_count": len(area_rows),
                "unique_collection_run_count": len({r.collection_run_id for r in area_rows}),
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
                "max_observation_gap_minutes": max(gaps_minutes) if gaps_minutes else None,
                "error_row_count": error_counts_by_area.get(area_code, 0),
                "congestion_level_counts_json": json.dumps(
                    dict(congestion_counts), ensure_ascii=False, sort_keys=True
                ),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Time Coverage -- two record types in one file (record_type column):
# RUN rows (one per collection_run_id, chronological) and HOUR rows (one per
# KST calendar-date+hour bucket of Current rows, date/hour order), so
# Hour-level coverage is directly readable without a second file.
#
# Real EG-8A datasets have exactly one distinct observed_at per run (all 13
# areas share one instant), so RUN rows capture both the run-cadence view
# and the observed_at-level view. distinct_observed_at_count_in_run measures
# that uniformity rather than assuming it, so a future dataset that breaks
# it is still faithfully represented (not silently collapsed).
# ---------------------------------------------------------------------------


def build_time_coverage_rows(bundle: DatasetBundle) -> list[dict[str, object]]:
    official_area_set = set(_official_area_codes(bundle))

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
                "area_codes": {r.area_code for r in rows},
            }
        )
    run_summaries.sort(key=lambda item: item["run_start_called_at"])

    run_rows: list[dict[str, object]] = []
    previous_start: datetime | None = None
    for summary in run_summaries:
        start = summary["run_start_called_at"]
        gap_minutes = (
            (start - previous_start).total_seconds() / 60 if previous_start is not None else None
        )
        deviation = (
            gap_minutes != FIVE_MINUTE_CADENCE_MINUTES if gap_minutes is not None else None
        )
        is_complete = bool(official_area_set) and summary["area_codes"] == official_area_set
        run_rows.append(
            {
                "record_type": RECORD_TYPE_RUN,
                "collection_run_id": summary["collection_run_id"],
                "run_start_called_at": start.isoformat(),
                "run_min_observed_at": summary["run_min_observed_at"].isoformat(),
                "run_max_observed_at": summary["run_max_observed_at"].isoformat(),
                "distinct_observed_at_count_in_run": summary["distinct_observed_at_count_in_run"],
                "area_count": summary["area_count"],
                "run_completeness": (
                    RUN_COMPLETENESS_COMPLETE if is_complete else RUN_COMPLETENESS_PARTIAL
                ),
                "gap_from_previous_run_minutes": gap_minutes,
                "five_minute_contract_deviation": deviation,
                "hour_of_day": summary["run_min_observed_at"].hour,
                "hour_date": None,
                "hour_current_row_count": None,
                "hour_distinct_observed_at_count": None,
                "hour_area_coverage_count": None,
            }
        )
        previous_start = start

    by_hour_bucket: dict[tuple[str, int], list[CurrentRow]] = defaultdict(list)
    for row in bundle.current_rows:
        observed = datetime.fromisoformat(row.observed_at)
        by_hour_bucket[(observed.date().isoformat(), observed.hour)].append(row)

    hour_rows: list[dict[str, object]] = []
    for date_str, hour in sorted(by_hour_bucket):
        bucket_rows = by_hour_bucket[(date_str, hour)]
        distinct_observed = {r.observed_at for r in bucket_rows}
        areas_present = {r.area_code for r in bucket_rows} & official_area_set
        hour_rows.append(
            {
                "record_type": RECORD_TYPE_HOUR,
                "collection_run_id": None,
                "run_start_called_at": None,
                "run_min_observed_at": None,
                "run_max_observed_at": None,
                "distinct_observed_at_count_in_run": None,
                "area_count": None,
                "run_completeness": None,
                "gap_from_previous_run_minutes": None,
                "five_minute_contract_deviation": None,
                "hour_of_day": hour,
                "hour_date": date_str,
                "hour_current_row_count": len(bucket_rows),
                "hour_distinct_observed_at_count": len(distinct_observed),
                "hour_area_coverage_count": len(areas_present),
            }
        )

    return run_rows + hour_rows


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


def _area_observed_range(bundle: DatasetBundle) -> dict[str, tuple[datetime, datetime]]:
    """Per-Area (min, max) Current observed_at. Match classification is
    scoped to each Area's own observation window, not the dataset-wide
    window -- an Area that started or stopped reporting earlier than others
    must not have its misses misclassified against a different Area's range."""
    per_area: dict[str, list[datetime]] = defaultdict(list)
    for row in bundle.current_rows:
        per_area[row.area_code].append(datetime.fromisoformat(row.observed_at))
    return {area_code: (min(times), max(times)) for area_code, times in per_area.items()}


def _classify_forecast_row(
    row: ForecastRow,
    *,
    current_index: Mapping[tuple[str, str], CurrentRow],
    area_observed_range: Mapping[str, tuple[datetime, datetime]],
) -> str:
    """Priority order: AREA_NOT_FOUND (no Current data for this Area at
    all) -> EXACT_MATCH -> BEFORE_DATASET_START / AFTER_DATASET_END (target
    outside this Area's own observed range) -> CURRENT_TARGET_MISSING
    (inside the Area's own range but no exact instant). No nearest-match,
    rounding, or tolerance is used anywhere in this classification."""
    if row.area_code not in area_observed_range:
        return MATCH_STATUS_AREA_NOT_FOUND
    if (row.area_code, row.forecast_at) in current_index:
        return MATCH_STATUS_EXACT_MATCH
    forecast_at = datetime.fromisoformat(row.forecast_at)
    area_min, area_max = area_observed_range[row.area_code]
    if forecast_at < area_min:
        return MATCH_STATUS_BEFORE_DATASET_START
    if forecast_at > area_max:
        return MATCH_STATUS_AFTER_DATASET_END
    return MATCH_STATUS_CURRENT_TARGET_MISSING


def build_forecast_match_summary(bundle: DatasetBundle) -> dict[str, object]:
    current_index = _build_current_index(bundle)
    area_observed_range = _area_observed_range(bundle)

    status_counts: Counter = Counter({status: 0 for status in MATCH_STATUSES})
    match_by_area: Counter = Counter()
    match_total_by_area: Counter = Counter()
    horizon_histogram: Counter = Counter()
    matched_horizon_histogram: Counter = Counter()
    unique_targets: set[tuple[str, str]] = set()

    for row in bundle.forecast_rows:
        unique_targets.add((row.area_code, row.forecast_at))
        match_total_by_area[row.area_code] += 1
        horizon_minutes = _forecast_horizon_minutes(row)
        horizon_histogram[horizon_minutes] += 1

        status = _classify_forecast_row(
            row, current_index=current_index, area_observed_range=area_observed_range
        )
        status_counts[status] += 1
        if status == MATCH_STATUS_EXACT_MATCH:
            match_by_area[row.area_code] += 1
            matched_horizon_histogram[horizon_minutes] += 1

    total = len(bundle.forecast_rows)
    exact_match = status_counts[MATCH_STATUS_EXACT_MATCH]
    # Backward-compatible derived fields (kept for existing consumers):
    # Boundary Miss = BEFORE_DATASET_START + AFTER_DATASET_END,
    # Other Miss = CURRENT_TARGET_MISSING + AREA_NOT_FOUND.
    boundary_miss = (
        status_counts[MATCH_STATUS_BEFORE_DATASET_START] + status_counts[MATCH_STATUS_AFTER_DATASET_END]
    )
    other_miss = (
        status_counts[MATCH_STATUS_CURRENT_TARGET_MISSING] + status_counts[MATCH_STATUS_AREA_NOT_FOUND]
    )

    return {
        "schema_version": FORECAST_MATCH_SUMMARY_SCHEMA_VERSION,
        "dataset_id": bundle.dataset_id,
        "total_forecast_rows": total,
        "unique_forecast_targets": len(unique_targets),
        "status_counts": {status: status_counts[status] for status in MATCH_STATUSES},
        "exact_match_rows": exact_match,
        "match_failure_rows": total - exact_match,
        "exact_match_rate": (exact_match / total) if total else None,
        "no_match_dataset_boundary_rows": boundary_miss,
        "no_match_other_rows": other_miss,
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
    generated_at: datetime | None = None,
) -> Eg8bAnalysisResult:
    """Validate an EG-8A dataset directory and write the B1 analysis artifacts.

    `generated_at` is normally left unset (defaults to the real current
    time); tests inject a fixed value to make repeated runs byte-comparable.
    """
    bundle = load_dataset_bundle(dataset_dir, expected_dataset_id=expected_dataset_id)
    return analyze_dataset(bundle, eg8b_output_root=eg8b_output_root, generated_at=generated_at)
