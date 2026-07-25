"""EG-8B B2b (1st scope): short-window multi-day B0 Persistence Baseline and
Seoul Forecast Backtest, bounded to an explicit Analysis Window and a
called_at-based Snapshot Cutoff.

Reads the three v3 source CSVs directly (via `eg8a.normalize_v3_sources`,
read-only) rather than an already-exported EG-8A dataset directory, because
neither B1 nor B2a's pipeline has any Analysis-Window/Snapshot-Cutoff
filtering built in -- that filtering is this module's own responsibility.

Inclusion contract:

- Current, Forecast Source: `observed_at >= analysis_window_start AND
  called_at <= snapshot_cutoff`.
- Raw Log: `collection_run_id` already included via Current, AND the row's
  own `called_at <= snapshot_cutoff` (never `called_at` alone -- Raw Log
  carries no `observed_at` to bound the Window Start with, so filtering it
  independently could pull in pre-Window runs).
- Forecast Evaluation Pair: Exact Join only (no nearest/as-of/interpolation/
  tolerance match anywhere). A Forecast Source record's own `forecast_at`
  is classified against `[analysis_window_start, snapshot_cutoff]` before
  any Actual lookup is attempted.

Same-weekday (B1 Baseline) and 4-week-average (B2 Baseline) are not
implemented here -- both need repeated weekday occurrences a single short
window does not have (see `docs/analysis/ANALYSIS_PLAN.md` sec.9/sec.9.4).
This module produces only a B0 Persistence Baseline (reusing
`eg8b_b2a`'s verified metric formulas, not re-deriving them, so the two
modules' numbers cannot silently drift apart) against Seoul's official
Forecast, scoped to however many calendar dates the Window/Cutoff actually
cover. Never produces a same-weekday/4-week Baseline, a held-out
evaluation, or an official EG-8B Gate PASS/FAIL judgment.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import statistics
import tempfile
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from . import eg6b, eg8a, eg8b, eg8b_b2a

PHASE_B2B_VERSION = "phase-b2b-v1"
DATASET_COVERAGE_SCHEMA_VERSION = "eg8b-b2b-dataset-coverage-v1"
BACKTEST_SUMMARY_SCHEMA_VERSION = "eg8b-b2b-multiday-backtest-summary-v1"
BASELINE_COMPARISON_SCHEMA_VERSION = "eg8b-b2b-baseline-comparison-v1"
OUTPUT_MANIFEST_SCHEMA_VERSION = "eg8b-b2b-output-manifest-v1"

EVALUATION_STATUS_PROVISIONAL = "PROVISIONAL"
"""The only value this module ever produces -- B2b's short-window backtest
is by definition provisional, never a final evaluation."""
COVERAGE_STATUS_SHORT_WINDOW_MULTI_DAY_PARTIAL = "SHORT_WINDOW_MULTI_DAY_PARTIAL_COVERAGE"
"""The only value this module ever produces. Distinct from B2a's
SINGLE_DAY_PARTIAL_COVERAGE: B2b's window can span multiple calendar dates,
but is still far short of the 4-week baseline + 5th-week holdout that the
official EG-8B Gate requires (B2b 2nd scope)."""

DATASET_COVERAGE_FILENAME = "dataset_coverage.json"
EVALUATION_PAIRS_SCORED_FILENAME = "evaluation_pairs_scored.csv"
METRICS_BY_DATE_FILENAME = "metrics_by_date.csv"
METRICS_BY_AREA_FILENAME = "metrics_by_area.csv"
METRICS_BY_HORIZON_FILENAME = "metrics_by_horizon.csv"
BASELINE_COMPARISON_FILENAME = "baseline_comparison.json"
MULTIDAY_BACKTEST_SUMMARY_FILENAME = "multiday_backtest_summary.json"
OUTPUT_MANIFEST_FILENAME = "output_manifest.json"

MATCH_STATUS_EXACT_MATCH = "EXACT_MATCH"
MATCH_STATUS_BEFORE_ANALYSIS_START = "BEFORE_ANALYSIS_START"
MATCH_STATUS_AFTER_EVALUATION_CUTOFF = "AFTER_EVALUATION_CUTOFF"
MATCH_STATUS_CURRENT_TARGET_MISSING = "CURRENT_TARGET_MISSING"
MATCH_STATUS_AREA_NOT_FOUND = "AREA_NOT_FOUND"
MATCH_STATUSES = (
    MATCH_STATUS_EXACT_MATCH,
    MATCH_STATUS_BEFORE_ANALYSIS_START,
    MATCH_STATUS_AFTER_EVALUATION_CUTOFF,
    MATCH_STATUS_CURRENT_TARGET_MISSING,
    MATCH_STATUS_AREA_NOT_FOUND,
)
"""Deliberately not eg8b.MATCH_STATUSES: BEFORE_ANALYSIS_START/
AFTER_EVALUATION_CUTOFF are bounded by this module's own Window/Cutoff, not
by the dataset's own observed range, and must not be conflated with B1's
BEFORE_DATASET_START/AFTER_DATASET_END (docs instruction: "AFTER_DATASET_END
와 AFTER_EVALUATION_CUTOFF의 의미를 혼용하지 않는다")."""

COMPARISON_FORECAST_WIN = "FORECAST_WIN"
COMPARISON_B0_WIN = "B0_WIN"
COMPARISON_TIE = "TIE"

FIVE_MINUTE_CADENCE_MINUTES = 5.0

_PERFORMANCE_METRIC_FIELDNAMES = (
    "pair_count",
    "forecast_mae",
    "forecast_median_abs_error",
    "forecast_rmse",
    "forecast_relative_error_sample_count",
    "forecast_mean_relative_error",
    "forecast_interval_inclusion_rate",
    "forecast_congestion_match_rate",
    "b0_mae",
    "b0_median_abs_error",
    "b0_rmse",
    "b0_relative_error_sample_count",
    "b0_mean_relative_error",
    "b0_interval_inclusion_rate",
    "b0_congestion_match_rate",
    "comparison",
)
METRICS_BY_DATE_FIELDNAMES = ("calendar_date",) + _PERFORMANCE_METRIC_FIELDNAMES
METRICS_BY_AREA_FIELDNAMES = ("area_code",) + _PERFORMANCE_METRIC_FIELDNAMES
METRICS_BY_HORIZON_FIELDNAMES = ("horizon_minutes",) + _PERFORMANCE_METRIC_FIELDNAMES

EVALUATION_PAIRS_SCORED_FIELDNAMES = (
    "area_code",
    "calendar_date",
    "forecast_collection_run_id",
    "forecast_called_at",
    "forecast_observed_at",
    "forecast_at",
    "horizon_minutes",
    "forecast_congestion_level",
    "forecast_population_min",
    "forecast_population_max",
    "forecast_population_mid",
    "forecast_duplicate_flag",
    "origin_collection_run_id",
    "origin_called_at",
    "origin_population_min",
    "origin_population_max",
    "origin_population_mid",
    "origin_congestion_level",
    "origin_duplicate_flag",
    "actual_collection_run_id",
    "actual_called_at",
    "actual_population_min",
    "actual_population_max",
    "actual_population_mid",
    "actual_congestion_level",
    "actual_duplicate_flag",
    "forecast_abs_error",
    "forecast_relative_error",
    "forecast_interval_included",
    "forecast_congestion_match",
    "b0_abs_error",
    "b0_relative_error",
    "b0_interval_included",
    "b0_congestion_match",
)


class AnalysisWindowError(ValueError):
    """Raised when analysis_window_start/snapshot_cutoff are naive or out of order."""


class EvidenceWriteError(OSError):
    """Raised when a B2b output file or directory cannot be written safely."""


class OutputRootConfigurationError(EvidenceWriteError):
    """Raised when FRESHMANAGER_EG8B_OUTPUT_ROOT is unset or invalid."""


@dataclass(frozen=True)
class IncludedDataset:
    current_records: tuple[eg8a.NormalizedCurrentRecord, ...]
    forecast_records: tuple[eg8a.NormalizedForecastRecord, ...]
    raw_log_included_count: int


@dataclass(frozen=True)
class ShortWindowBacktestResult:
    b2b_run_id: str
    phase_dir: Path
    dataset_coverage: Mapping[str, object]
    backtest_summary: Mapping[str, object]


# ---------------------------------------------------------------------------
# Loading and Analysis Window / Snapshot Cutoff filtering
# ---------------------------------------------------------------------------


def build_included_raw_log_count(
    raw_log_path: Path,
    *,
    included_run_ids: set[str],
    snapshot_cutoff: datetime,
) -> int:
    """Raw Log rows carry no `observed_at`, so `analysis_window_start` cannot
    be applied to them directly -- inclusion is scoped through Current's own
    already-Window-filtered run_ids, with an independent
    `called_at <= snapshot_cutoff` check per row (a Raw Log row can, in
    principle, have its own `called_at` differ slightly from its sibling
    Current rows in the same run)."""
    raw_log_rows, _ragged_errors = eg8a.read_source_csv(
        raw_log_path, eg8a.RAW_LOG_REQUIRED_COLUMNS, "raw_log_v3"
    )
    count = 0
    for row in raw_log_rows:
        run_id = row.raw_row.get("collection_run_id", "").strip()
        if run_id not in included_run_ids:
            continue
        called_raw = (row.raw_row.get("called_at") or "").strip()
        if not called_raw:
            continue
        try:
            called_at = eg8a.parse_kst_datetime(called_raw)
        except ValueError:
            continue
        if called_at <= snapshot_cutoff:
            count += 1
    return count


def load_included_dataset(
    *,
    raw_log_path: Path,
    current_path: Path,
    forecast_path: Path,
    analysis_window_start: datetime,
    snapshot_cutoff: datetime,
) -> IncludedDataset:
    """Read and normalize the three v3 source CSVs (via `eg8a`, read-only),
    then filter Current/Forecast Source to:

        observed_at >= analysis_window_start AND called_at <= snapshot_cutoff

    Both bounds must be timezone-aware. `eg8a.parse_kst_datetime` always
    produces Asia/Seoul-aware values, so callers should pass bounds in the
    same zone (any aware zone compares correctly regardless).
    """
    if analysis_window_start.tzinfo is None or snapshot_cutoff.tzinfo is None:
        raise AnalysisWindowError(
            "analysis_window_start and snapshot_cutoff must be timezone-aware"
        )
    if analysis_window_start >= snapshot_cutoff:
        raise AnalysisWindowError(
            "analysis_window_start must be strictly before snapshot_cutoff"
        )

    result = eg8a.normalize_v3_sources(
        raw_log_path=raw_log_path, current_path=current_path, forecast_path=forecast_path
    )

    included_current = tuple(
        record
        for record in result.current_records
        if datetime.fromisoformat(record.observed_at) >= analysis_window_start
        and datetime.fromisoformat(record.called_at) <= snapshot_cutoff
    )
    included_forecast = tuple(
        record
        for record in result.forecast_records
        if datetime.fromisoformat(record.observed_at) >= analysis_window_start
        and datetime.fromisoformat(record.called_at) <= snapshot_cutoff
    )
    included_run_ids = {record.collection_run_id for record in included_current}
    raw_log_included_count = build_included_raw_log_count(
        raw_log_path, included_run_ids=included_run_ids, snapshot_cutoff=snapshot_cutoff
    )

    return IncludedDataset(
        current_records=included_current,
        forecast_records=included_forecast,
        raw_log_included_count=raw_log_included_count,
    )


# ---------------------------------------------------------------------------
# Match Status classification and Evaluation Pairs (Exact Join only)
# ---------------------------------------------------------------------------


def _forecast_horizon_minutes(observed_at: str, forecast_at: str) -> int:
    return round(
        (datetime.fromisoformat(forecast_at) - datetime.fromisoformat(observed_at)).total_seconds() / 60
    )


def classify_forecast_records(
    included: IncludedDataset,
    *,
    analysis_window_start: datetime,
    snapshot_cutoff: datetime,
) -> dict[str, list[eg8a.NormalizedForecastRecord]]:
    """Classify each included Forecast Source record into exactly one of
    MATCH_STATUSES. Priority order: AREA_NOT_FOUND (no included Current data
    for this Area at all) -> BEFORE_ANALYSIS_START / AFTER_EVALUATION_CUTOFF
    (forecast_at outside [analysis_window_start, snapshot_cutoff]) ->
    EXACT_MATCH / CURRENT_TARGET_MISSING (inside bounds, Actual present or
    not). No nearest-match, rounding, or tolerance anywhere."""
    current_index = {
        (record.area_code, record.observed_at): record for record in included.current_records
    }
    known_areas = {record.area_code for record in included.current_records}

    by_status: dict[str, list[eg8a.NormalizedForecastRecord]] = {
        status: [] for status in MATCH_STATUSES
    }
    for record in included.forecast_records:
        if record.area_code not in known_areas:
            by_status[MATCH_STATUS_AREA_NOT_FOUND].append(record)
            continue
        forecast_at = datetime.fromisoformat(record.forecast_at)
        if forecast_at < analysis_window_start:
            by_status[MATCH_STATUS_BEFORE_ANALYSIS_START].append(record)
            continue
        if forecast_at > snapshot_cutoff:
            by_status[MATCH_STATUS_AFTER_EVALUATION_CUTOFF].append(record)
            continue
        if (record.area_code, record.forecast_at) in current_index:
            by_status[MATCH_STATUS_EXACT_MATCH].append(record)
        else:
            by_status[MATCH_STATUS_CURRENT_TARGET_MISSING].append(record)
    return by_status


def build_evaluation_pairs_rows(
    included: IncludedDataset,
    matched_forecast_records: Sequence[eg8a.NormalizedForecastRecord],
) -> tuple[list[dict[str, object]], int]:
    """Return (rows, origin_lookup_missing_count).

    Scores each EXACT_MATCH Forecast record against its Actual (the Current
    record at the same (area_code, forecast_at)) and its B0 Origin (the
    Current record at (area_code, forecast_observed_at) -- the same
    snapshot the Forecast itself was derived from). A matched record whose
    own Origin snapshot did not survive Window/Cutoff filtering is excluded
    and counted rather than raising -- a legitimate boundary outcome, not a
    structural bug.
    """
    current_index = {
        (record.area_code, record.observed_at): record for record in included.current_records
    }

    rows: list[dict[str, object]] = []
    origin_lookup_missing_count = 0

    for record in matched_forecast_records:
        actual = current_index[(record.area_code, record.forecast_at)]
        origin = current_index.get((record.area_code, record.observed_at))
        if origin is None:
            origin_lookup_missing_count += 1
            continue

        actual_mid = actual.population_mid
        forecast_mid = record.forecast_population_mid
        origin_mid = origin.population_mid

        forecast_abs_error = abs(forecast_mid - actual_mid)
        forecast_relative_error = forecast_abs_error / actual_mid if actual_mid != 0 else None
        forecast_interval_included = (
            record.forecast_population_min <= actual_mid <= record.forecast_population_max
        )
        forecast_congestion_match = record.forecast_congestion_level == actual.congestion_level

        b0_abs_error = abs(origin_mid - actual_mid)
        b0_relative_error = b0_abs_error / actual_mid if actual_mid != 0 else None
        b0_interval_included = origin.population_min <= actual_mid <= origin.population_max
        b0_congestion_match = origin.congestion_level == actual.congestion_level

        forecast_at_dt = datetime.fromisoformat(record.forecast_at)

        rows.append(
            {
                "area_code": record.area_code,
                "calendar_date": forecast_at_dt.date().isoformat(),
                "forecast_collection_run_id": record.collection_run_id,
                "forecast_called_at": record.called_at,
                "forecast_observed_at": record.observed_at,
                "forecast_at": record.forecast_at,
                "horizon_minutes": _forecast_horizon_minutes(record.observed_at, record.forecast_at),
                "forecast_congestion_level": record.forecast_congestion_level,
                "forecast_population_min": record.forecast_population_min,
                "forecast_population_max": record.forecast_population_max,
                "forecast_population_mid": forecast_mid,
                "forecast_duplicate_flag": record.duplicate_flag,
                "origin_collection_run_id": origin.collection_run_id,
                "origin_called_at": origin.called_at,
                "origin_population_min": origin.population_min,
                "origin_population_max": origin.population_max,
                "origin_population_mid": origin_mid,
                "origin_congestion_level": origin.congestion_level,
                "origin_duplicate_flag": origin.duplicate_flag,
                "actual_collection_run_id": actual.collection_run_id,
                "actual_called_at": actual.called_at,
                "actual_population_min": actual.population_min,
                "actual_population_max": actual.population_max,
                "actual_population_mid": actual_mid,
                "actual_congestion_level": actual.congestion_level,
                "actual_duplicate_flag": actual.duplicate_flag,
                "forecast_abs_error": forecast_abs_error,
                "forecast_relative_error": forecast_relative_error,
                "forecast_interval_included": forecast_interval_included,
                "forecast_congestion_match": forecast_congestion_match,
                "b0_abs_error": b0_abs_error,
                "b0_relative_error": b0_relative_error,
                "b0_interval_included": b0_interval_included,
                "b0_congestion_match": b0_congestion_match,
            }
        )

    return rows, origin_lookup_missing_count


# ---------------------------------------------------------------------------
# Metrics by date/area/horizon and Forecast-vs-B0 comparison.
#
# eg8b_b2a._compute_metrics is imported and reused verbatim (PM-authorized
# cross-module reuse of B2a's verified formula) rather than re-derived, so
# B2a and B2b can never silently disagree on what "abs error" or "interval
# included" means. Only Median Absolute Error is computed locally -- B2a's
# shared helper does not produce it.
# ---------------------------------------------------------------------------


def _classify_comparison(forecast_mae: float | None, b0_mae: float | None) -> str | None:
    if forecast_mae is None or b0_mae is None:
        return None
    if forecast_mae < b0_mae:
        return COMPARISON_FORECAST_WIN
    if forecast_mae > b0_mae:
        return COMPARISON_B0_WIN
    return COMPARISON_TIE


def _performance_row(
    key_field: str, key_value: object, rows: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    forecast_abs_errors = [row["forecast_abs_error"] for row in rows]
    b0_abs_errors = [row["b0_abs_error"] for row in rows]
    forecast_metrics = eg8b_b2a._compute_metrics(
        forecast_abs_errors,
        [row["forecast_relative_error"] for row in rows if row["forecast_relative_error"] is not None],
        [row["forecast_interval_included"] for row in rows],
        [row["forecast_congestion_match"] for row in rows],
    )
    b0_metrics = eg8b_b2a._compute_metrics(
        b0_abs_errors,
        [row["b0_relative_error"] for row in rows if row["b0_relative_error"] is not None],
        [row["b0_interval_included"] for row in rows],
        [row["b0_congestion_match"] for row in rows],
    )
    forecast_mae = forecast_metrics["mae"]
    b0_mae = b0_metrics["mae"]
    return {
        key_field: key_value,
        "pair_count": len(rows),
        "forecast_mae": forecast_mae,
        "forecast_median_abs_error": statistics.median(forecast_abs_errors) if forecast_abs_errors else None,
        "forecast_rmse": forecast_metrics["rmse"],
        "forecast_relative_error_sample_count": forecast_metrics["relative_error_sample_count"],
        "forecast_mean_relative_error": forecast_metrics["mean_relative_error"],
        "forecast_interval_inclusion_rate": forecast_metrics["interval_inclusion_rate"],
        "forecast_congestion_match_rate": forecast_metrics["congestion_match_rate"],
        "b0_mae": b0_mae,
        "b0_median_abs_error": statistics.median(b0_abs_errors) if b0_abs_errors else None,
        "b0_rmse": b0_metrics["rmse"],
        "b0_relative_error_sample_count": b0_metrics["relative_error_sample_count"],
        "b0_mean_relative_error": b0_metrics["mean_relative_error"],
        "b0_interval_inclusion_rate": b0_metrics["interval_inclusion_rate"],
        "b0_congestion_match_rate": b0_metrics["congestion_match_rate"],
        "comparison": _classify_comparison(forecast_mae, b0_mae),
    }


def build_metrics_by_date_rows(pairs_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    by_date: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in pairs_rows:
        by_date[row["calendar_date"]].append(row)
    return [_performance_row("calendar_date", date, rows) for date, rows in sorted(by_date.items())]


def build_metrics_by_area_rows(pairs_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    by_area: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in pairs_rows:
        by_area[row["area_code"]].append(row)
    return [_performance_row("area_code", area, rows) for area, rows in sorted(by_area.items())]


def build_metrics_by_horizon_rows(pairs_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    by_horizon: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in pairs_rows:
        by_horizon[row["horizon_minutes"]].append(row)
    return [
        _performance_row("horizon_minutes", horizon, rows) for horizon, rows in sorted(by_horizon.items())
    ]


def build_baseline_comparison(
    *,
    overall_row: Mapping[str, object],
    by_date_rows: Sequence[Mapping[str, object]],
    by_area_rows: Sequence[Mapping[str, object]],
    by_horizon_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    def _tally(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
        counts = {COMPARISON_FORECAST_WIN: 0, COMPARISON_B0_WIN: 0, COMPARISON_TIE: 0}
        for row in rows:
            comparison = row.get("comparison")
            if comparison in counts:
                counts[comparison] += 1
        return counts

    return {
        "schema_version": BASELINE_COMPARISON_SCHEMA_VERSION,
        "overall": {
            "comparison": overall_row["comparison"],
            "forecast_mae": overall_row["forecast_mae"],
            "b0_mae": overall_row["b0_mae"],
        },
        "by_date": [
            {
                "calendar_date": row["calendar_date"],
                "comparison": row["comparison"],
                "forecast_mae": row["forecast_mae"],
                "b0_mae": row["b0_mae"],
            }
            for row in by_date_rows
        ],
        "by_area": [
            {
                "area_code": row["area_code"],
                "comparison": row["comparison"],
                "forecast_mae": row["forecast_mae"],
                "b0_mae": row["b0_mae"],
            }
            for row in by_area_rows
        ],
        "by_horizon": [
            {
                "horizon_minutes": row["horizon_minutes"],
                "comparison": row["comparison"],
                "forecast_mae": row["forecast_mae"],
                "b0_mae": row["b0_mae"],
            }
            for row in by_horizon_rows
        ],
        "win_tally": {
            "by_date": _tally(by_date_rows),
            "by_area": _tally(by_area_rows),
            "by_horizon": _tally(by_horizon_rows),
        },
    }


# ---------------------------------------------------------------------------
# Dataset Coverage -- Window/Cutoff-scoped counterpart to B1's dataset_profile
# ---------------------------------------------------------------------------


def build_dataset_coverage(
    included: IncludedDataset,
    *,
    b2b_run_id: str,
    generated_at: datetime,
    analysis_window_start: datetime,
    snapshot_cutoff: datetime,
    match_status_counts: Mapping[str, int],
) -> dict[str, object]:
    official_area_codes = list(eg6b.EG6B_AREA_CODES)
    official_area_set = set(official_area_codes)
    current_areas = {record.area_code for record in included.current_records}

    observed_ats = [datetime.fromisoformat(record.observed_at) for record in included.current_records]
    calendar_dates = sorted({dt.date().isoformat() for dt in observed_ats})

    by_run: dict[str, list[eg8a.NormalizedCurrentRecord]] = defaultdict(list)
    for record in included.current_records:
        by_run[record.collection_run_id].append(record)

    complete_run_count = 0
    run_starts: list[datetime] = []
    for records in by_run.values():
        areas_in_run = {record.area_code for record in records}
        if areas_in_run == official_area_set:
            complete_run_count += 1
        run_starts.append(min(datetime.fromisoformat(record.called_at) for record in records))
    run_starts.sort()

    gaps_minutes = [
        (later - earlier).total_seconds() / 60 for earlier, later in zip(run_starts, run_starts[1:])
    ]
    deviation_count = sum(1 for gap in gaps_minutes if gap != FIVE_MINUTE_CADENCE_MINUTES)

    duplicate_current = sum(1 for record in included.current_records if record.duplicate_flag)
    duplicate_forecast = sum(1 for record in included.forecast_records if record.duplicate_flag)

    return {
        "schema_version": DATASET_COVERAGE_SCHEMA_VERSION,
        "b2b_run_id": b2b_run_id,
        "generated_at": eg8a.to_iso8601(generated_at),
        "analysis_window_start_at": eg8a.to_iso8601(analysis_window_start),
        "snapshot_cutoff_at": eg8a.to_iso8601(snapshot_cutoff),
        "latest_available_observed_at": (
            eg8a.to_iso8601(max(observed_ats)) if observed_ats else None
        ),
        "calendar_date_count": len(calendar_dates),
        "calendar_dates": calendar_dates,
        "row_counts": {
            "current": len(included.current_records),
            "forecast_source": len(included.forecast_records),
            "raw_log": included.raw_log_included_count,
        },
        "area_coverage": {
            "official_area_count": len(official_area_codes),
            "observed_area_count": len(current_areas),
            "unexpected_areas": sorted(current_areas - official_area_set),
            "missing_areas": sorted(official_area_set - current_areas),
        },
        "run_coverage": {
            "included_run_count": len(by_run),
            "complete_run_count": complete_run_count,
            "partial_run_count": len(by_run) - complete_run_count,
        },
        "five_minute_cadence": {
            "deviation_count": deviation_count,
            "on_cadence_count": len(gaps_minutes) - deviation_count,
            "max_gap_minutes": max(gaps_minutes) if gaps_minutes else None,
            "mean_gap_minutes": statistics.mean(gaps_minutes) if gaps_minutes else None,
        },
        "duplicate_counts": {
            "current": duplicate_current,
            "forecast": duplicate_forecast,
        },
        "duplicate_rate": {
            "current": (duplicate_current / len(included.current_records)) if included.current_records else None,
            "forecast": (duplicate_forecast / len(included.forecast_records)) if included.forecast_records else None,
        },
        "match_status_counts": dict(match_status_counts),
    }


def build_multiday_backtest_summary(
    *,
    b2b_run_id: str,
    generated_at: datetime,
    analysis_window_start: datetime,
    snapshot_cutoff: datetime,
    dataset_coverage: Mapping[str, object],
    overall_row: Mapping[str, object],
    origin_lookup_missing_count: int,
) -> dict[str, object]:
    """No file path is ever written into this document -- only b2b_run_id
    and other non-path identifiers."""
    return {
        "schema_version": BACKTEST_SUMMARY_SCHEMA_VERSION,
        "b2b_run_id": b2b_run_id,
        "generated_at": eg8a.to_iso8601(generated_at),
        "analysis_window_start_at": eg8a.to_iso8601(analysis_window_start),
        "snapshot_cutoff_at": eg8a.to_iso8601(snapshot_cutoff),
        "latest_available_observed_at": dataset_coverage["latest_available_observed_at"],
        "calendar_date_count": dataset_coverage["calendar_date_count"],
        "pair_count": overall_row["pair_count"],
        "origin_lookup_missing_count": origin_lookup_missing_count,
        "overall_forecast_metrics": {
            "mae": overall_row["forecast_mae"],
            "median_abs_error": overall_row["forecast_median_abs_error"],
            "rmse": overall_row["forecast_rmse"],
            "relative_error_sample_count": overall_row["forecast_relative_error_sample_count"],
            "mean_relative_error": overall_row["forecast_mean_relative_error"],
            "interval_inclusion_rate": overall_row["forecast_interval_inclusion_rate"],
            "congestion_match_rate": overall_row["forecast_congestion_match_rate"],
        },
        "overall_b0_metrics": {
            "mae": overall_row["b0_mae"],
            "median_abs_error": overall_row["b0_median_abs_error"],
            "rmse": overall_row["b0_rmse"],
            "relative_error_sample_count": overall_row["b0_relative_error_sample_count"],
            "mean_relative_error": overall_row["b0_mean_relative_error"],
            "interval_inclusion_rate": overall_row["b0_interval_inclusion_rate"],
            "congestion_match_rate": overall_row["b0_congestion_match_rate"],
        },
        "overall_comparison": overall_row["comparison"],
        "scope_note": (
            f"이 산출물은 {eg8a.to_iso8601(analysis_window_start)}~"
            f"{eg8a.to_iso8601(snapshot_cutoff)} 단기 다일자 잠정 Backtest 결과이며 "
            "공식 성공 임계값이나 EG-8B Gate PASS/FAIL을 판정하지 않는다. 같은 "
            "요일·시간 Baseline(B1)과 4주 평균 Baseline(B2)은 포함하지 않는다"
            "(반복되는 같은 요일 데이터 필요, B2b 2차 범위)."
        ),
        "evaluation_status": EVALUATION_STATUS_PROVISIONAL,
        "coverage_status": COVERAGE_STATUS_SHORT_WINDOW_MULTI_DAY_PARTIAL,
        "gate_judgment": None,
    }


# ---------------------------------------------------------------------------
# Output Writer -- exclusive create, never overwrites. B2b mints its own
# `b2b_run_id` (not an eg8a dataset_id: B2b reads raw v3 CSVs directly with
# its own Window/Cutoff filter, not an already-exported eg8a dataset
# directory, so there is no upstream dataset_id to inherit) and writes to a
# fresh <b2b_run_id>/phase-b2b-v1/ directory under the shared EG-8B output
# root -- this can never collide with any existing B1 <dataset_id>/phase1-v1
# or B2a <dataset_id>/phase-b2a-v1 directory.
# ---------------------------------------------------------------------------


def resolve_output_root_from_env(environ: Mapping[str, str]) -> Path:
    """Resolve the external EG-8B output-root from the environment. Reuses
    eg8b.py's own env-var name so all EG-8B-family outputs (B1/B2a/B2b)
    share one root. Never defaults to a path inside the repository; fails
    closed with a non-sensitive error if unset or not an existing
    directory; never returns the raw value in an error message."""
    value = environ.get(eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV)
    if not value:
        raise OutputRootConfigurationError(
            f"eg8b_b2b_output_root_error: {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV} is not set"
        )
    try:
        resolved = Path(value).expanduser().resolve(strict=True)
    except OSError as error:
        raise OutputRootConfigurationError(
            f"eg8b_b2b_output_root_error: {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV} does not exist"
        ) from error
    if not resolved.is_dir():
        raise OutputRootConfigurationError(
            f"eg8b_b2b_output_root_error: {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV} is not a directory"
        )
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_exclusive(path: Path, payload: bytes) -> None:
    """Write `payload` to `path`; raise EvidenceWriteError instead of ever
    overwriting an existing file (mkstemp + fsync + os.link, mirroring
    eg8a.py's/eg8b.py's/eg8b_b2a.py's own exclusive-write algorithm)."""
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
        raise EvidenceWriteError(f"eg8b_b2b_write_error: {path.name} already exists") from error
    except OSError as error:
        raise EvidenceWriteError(f"eg8b_b2b_write_error: failed to write {path.name}") from error
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


def analyze_short_window_backtest(
    included: IncludedDataset,
    *,
    b2b_run_id: str,
    analysis_window_start: datetime,
    snapshot_cutoff: datetime,
    eg8b_output_root: Path,
    raw_log_path: Path,
    current_path: Path,
    forecast_path: Path,
    generated_at: datetime | None = None,
) -> ShortWindowBacktestResult:
    """Write the eight B2b output artifacts for one already-filtered
    IncludedDataset. `eg8b_output_root` must already exist (never
    auto-created). `<b2b_run_id>/phase-b2b-v1/` is created exclusively -- a
    colliding run_id raises before any file is touched."""
    resolved_root = eg8b_output_root.expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise EvidenceWriteError("eg8b_b2b_write_error: output root is not a directory")

    resolved_generated_at = generated_at if generated_at is not None else datetime.now(eg8a.SEOUL)

    dataset_dir = resolved_root / b2b_run_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    phase_dir = dataset_dir / PHASE_B2B_VERSION
    try:
        phase_dir.mkdir(exist_ok=False)
    except FileExistsError as error:
        raise EvidenceWriteError(
            f"eg8b_b2b_write_error: {PHASE_B2B_VERSION} already exists for run {b2b_run_id}"
        ) from error

    by_status = classify_forecast_records(
        included, analysis_window_start=analysis_window_start, snapshot_cutoff=snapshot_cutoff
    )
    match_status_counts = {status: len(records) for status, records in by_status.items()}
    pairs_rows, origin_lookup_missing_count = build_evaluation_pairs_rows(
        included, by_status[MATCH_STATUS_EXACT_MATCH]
    )

    by_date_rows = build_metrics_by_date_rows(pairs_rows)
    by_area_rows = build_metrics_by_area_rows(pairs_rows)
    by_horizon_rows = build_metrics_by_horizon_rows(pairs_rows)
    overall_row = _performance_row("scope", "overall", pairs_rows)

    dataset_coverage = build_dataset_coverage(
        included,
        b2b_run_id=b2b_run_id,
        generated_at=resolved_generated_at,
        analysis_window_start=analysis_window_start,
        snapshot_cutoff=snapshot_cutoff,
        match_status_counts=match_status_counts,
    )
    backtest_summary = build_multiday_backtest_summary(
        b2b_run_id=b2b_run_id,
        generated_at=resolved_generated_at,
        analysis_window_start=analysis_window_start,
        snapshot_cutoff=snapshot_cutoff,
        dataset_coverage=dataset_coverage,
        overall_row=overall_row,
        origin_lookup_missing_count=origin_lookup_missing_count,
    )
    baseline_comparison = build_baseline_comparison(
        overall_row=overall_row,
        by_date_rows=by_date_rows,
        by_area_rows=by_area_rows,
        by_horizon_rows=by_horizon_rows,
    )

    payloads: list[tuple[str, bytes]] = [
        (DATASET_COVERAGE_FILENAME, _write_json_document(dataset_coverage)),
        (
            EVALUATION_PAIRS_SCORED_FILENAME,
            _write_csv_rows(EVALUATION_PAIRS_SCORED_FIELDNAMES, pairs_rows),
        ),
        (METRICS_BY_DATE_FILENAME, _write_csv_rows(METRICS_BY_DATE_FIELDNAMES, by_date_rows)),
        (METRICS_BY_AREA_FILENAME, _write_csv_rows(METRICS_BY_AREA_FIELDNAMES, by_area_rows)),
        (
            METRICS_BY_HORIZON_FILENAME,
            _write_csv_rows(METRICS_BY_HORIZON_FIELDNAMES, by_horizon_rows),
        ),
        (BASELINE_COMPARISON_FILENAME, _write_json_document(baseline_comparison)),
        (MULTIDAY_BACKTEST_SUMMARY_FILENAME, _write_json_document(backtest_summary)),
    ]
    for filename, payload in payloads:
        _write_exclusive(phase_dir / filename, payload)

    input_artifacts = [
        {"logical_name": name, "sha256": _sha256_file(path), "byte_size": path.stat().st_size}
        for name, path in (
            ("raw_log_v3", raw_log_path),
            ("population_current_v3", current_path),
            ("population_forecast_v3", forecast_path),
        )
    ]
    output_artifacts = [
        {"relative_path": filename, "sha256": _sha256_bytes(payload), "byte_size": len(payload)}
        for filename, payload in payloads
    ]
    output_manifest = {
        "schema_version": OUTPUT_MANIFEST_SCHEMA_VERSION,
        "b2b_run_id": b2b_run_id,
        "generated_at": eg8a.to_iso8601(resolved_generated_at),
        "hash_algorithm": "sha256",
        "input_artifacts": input_artifacts,
        "output_artifacts": output_artifacts,
    }
    _write_exclusive(phase_dir / OUTPUT_MANIFEST_FILENAME, _write_json_document(output_manifest))

    return ShortWindowBacktestResult(
        b2b_run_id=b2b_run_id,
        phase_dir=phase_dir,
        dataset_coverage=dataset_coverage,
        backtest_summary=backtest_summary,
    )


def run_short_window_backtest(
    *,
    raw_log_path: Path,
    current_path: Path,
    forecast_path: Path,
    analysis_window_start: datetime,
    snapshot_cutoff: datetime,
    eg8b_output_root: Path,
    b2b_run_id: str | None = None,
    generated_at: datetime | None = None,
) -> ShortWindowBacktestResult:
    """Load, filter, backtest, and persist one B2b short-window run.

    `b2b_run_id` is normally left unset (a fresh uuid4 is minted); tests
    inject an explicit value for deterministic output-path assertions.
    `generated_at` is normally left unset (defaults to the real current
    time); tests inject a fixed value to make repeated runs byte-comparable.
    """
    included = load_included_dataset(
        raw_log_path=raw_log_path,
        current_path=current_path,
        forecast_path=forecast_path,
        analysis_window_start=analysis_window_start,
        snapshot_cutoff=snapshot_cutoff,
    )
    resolved_run_id = b2b_run_id if b2b_run_id is not None else str(uuid.uuid4())
    return analyze_short_window_backtest(
        included,
        b2b_run_id=resolved_run_id,
        analysis_window_start=analysis_window_start,
        snapshot_cutoff=snapshot_cutoff,
        eg8b_output_root=eg8b_output_root,
        raw_log_path=raw_log_path,
        current_path=current_path,
        forecast_path=forecast_path,
        generated_at=generated_at,
    )
