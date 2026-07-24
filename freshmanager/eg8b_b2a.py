"""EG-8B B2a: B0 Persistence Baseline and a single-day provisional Backtest
against Seoul's official Forecast.

Reads EG-8B B1's output directory (produced by eg8b.run_phase1) and the
underlying EG-8A dataset directory (produced by eg8a.export_dataset), both
read-only, and writes four downstream comparison artifacts to an external
output-root, exclusive-create under the same <dataset_id> parent B1 uses (a
sibling PHASE_B2A_VERSION directory -- B1's own phase1-v1 is never opened
for writing).

This module does not judge official success thresholds or EG-8B Gate
PASS/FAIL. B1 (day-of-week/time-of-day) and B2 (4-week average) Baselines
are not implemented here -- both need more data history than a single day
provides (EG-8B B2b).
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import statistics
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence

from . import eg8a, eg8b

PHASE_B2A_VERSION = "phase-b2a-v1"
BACKTEST_SUMMARY_SCHEMA_VERSION = "eg8b-b2a-backtest-summary-v1"

B0_BASELINE_PAIRS_FILENAME = "b0_baseline_pairs.csv"
AREA_PERFORMANCE_FILENAME = "forecast_vs_b0_area_performance.csv"
HORIZON_PERFORMANCE_FILENAME = "forecast_vs_b0_horizon_performance.csv"
BACKTEST_SUMMARY_FILENAME = "backtest_summary.json"

ERROR_B1_OUTPUT_FILE_MISSING = "B1_OUTPUT_FILE_MISSING"
ERROR_B1_DATASET_ID_MISMATCH = "B1_DATASET_ID_MISMATCH"
ERROR_B1_EXACT_MATCH_COUNT_MISMATCH = "B1_EXACT_MATCH_COUNT_MISMATCH"
ERROR_B1_PAIR_ROW_INVALID = "B1_PAIR_ROW_INVALID"

_B1_REQUIRED_FILES = (
    eg8b.DATASET_PROFILE_FILENAME,
    eg8b.AREA_CURRENT_SUMMARY_FILENAME,
    eg8b.TIME_COVERAGE_FILENAME,
    eg8b.FORECAST_MATCH_SUMMARY_FILENAME,
    eg8b.FORECAST_EVALUATION_PAIRS_FILENAME,
)

B0_BASELINE_PAIRS_FIELDNAMES = (
    "area_code",
    "forecast_collection_run_id",
    "forecast_called_at",
    "forecast_observed_at",
    "forecast_at",
    "horizon_minutes",
    "origin_collection_run_id",
    "origin_called_at",
    "origin_population_min",
    "origin_population_max",
    "origin_population_mid",
    "origin_congestion_level",
    "origin_duplicate_flag",
    "forecast_population_min",
    "forecast_population_max",
    "forecast_population_mid",
    "forecast_congestion_level",
    "forecast_duplicate_flag",
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

_PERFORMANCE_METRIC_FIELDNAMES = (
    "pair_count",
    "forecast_mae",
    "forecast_rmse",
    "forecast_relative_error_sample_count",
    "forecast_mean_relative_error",
    "forecast_interval_inclusion_rate",
    "forecast_congestion_match_rate",
    "b0_mae",
    "b0_rmse",
    "b0_relative_error_sample_count",
    "b0_mean_relative_error",
    "b0_interval_inclusion_rate",
    "b0_congestion_match_rate",
    "forecast_mae_lower_than_b0",
)

AREA_PERFORMANCE_FIELDNAMES = ("area_code",) + _PERFORMANCE_METRIC_FIELDNAMES
HORIZON_PERFORMANCE_FIELDNAMES = ("horizon_minutes",) + _PERFORMANCE_METRIC_FIELDNAMES


class B1OutputValidationError(ValueError):
    """Raised when the EG-8B B1 output directory fails provenance validation."""


class EvidenceWriteError(OSError):
    """Raised when a B2a output file or directory cannot be written safely."""


class OutputRootConfigurationError(EvidenceWriteError):
    """Raised when FRESHMANAGER_EG8B_OUTPUT_ROOT is unset or invalid."""


@dataclass(frozen=True)
class PairRow:
    area_code: str
    forecast_collection_run_id: str
    forecast_called_at: str
    forecast_observed_at: str
    forecast_at: str
    horizon_minutes: int
    forecast_congestion_level: str
    forecast_population_min: int
    forecast_population_max: int
    forecast_population_mid: float
    forecast_duplicate_flag: bool
    actual_collection_run_id: str
    actual_called_at: str
    actual_congestion_level: str
    actual_population_min: int
    actual_population_max: int
    actual_population_mid: float
    actual_duplicate_flag: bool


@dataclass(frozen=True)
class B1OutputBundle:
    dataset_id: str
    dataset_profile: Mapping[str, object]
    forecast_match_summary: Mapping[str, object]
    pairs: tuple[PairRow, ...]


@dataclass(frozen=True)
class BacktestResult:
    dataset_id: str
    phase_dir: Path
    backtest_summary: Mapping[str, object]


# ---------------------------------------------------------------------------
# Input validation and loading of EG-8B B1's own output (never modifies
# phase_dir). The underlying EG-8A dataset itself is validated by reusing
# eg8b.load_dataset_bundle() directly -- see run_backtest() below.
# ---------------------------------------------------------------------------


def _read_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise B1OutputValidationError(
            f"{ERROR_B1_OUTPUT_FILE_MISSING}: {label} is unreadable"
        ) from error
    if not isinstance(document, dict):
        raise B1OutputValidationError(
            f"{ERROR_B1_OUTPUT_FILE_MISSING}: {label} is not a JSON object"
        )
    return document


def _read_csv_rows(path: Path, *, label: str) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as error:
        raise B1OutputValidationError(
            f"{ERROR_B1_OUTPUT_FILE_MISSING}: {label} is unreadable"
        ) from error


def _pair_row_from_dict(raw: Mapping[str, str]) -> PairRow:
    try:
        area_code = raw["area_code"]
        if not area_code:
            raise ValueError("area_code is empty")
        forecast_observed_at = raw["forecast_observed_at"]
        forecast_at = raw["forecast_at"]
        datetime.fromisoformat(forecast_observed_at)
        datetime.fromisoformat(forecast_at)
        return PairRow(
            area_code=area_code,
            forecast_collection_run_id=raw["forecast_collection_run_id"],
            forecast_called_at=raw["forecast_called_at"],
            forecast_observed_at=forecast_observed_at,
            forecast_at=forecast_at,
            horizon_minutes=int(raw["horizon_minutes"]),
            forecast_congestion_level=raw["forecast_congestion_level"],
            forecast_population_min=int(raw["forecast_population_min"]),
            forecast_population_max=int(raw["forecast_population_max"]),
            forecast_population_mid=float(raw["forecast_population_mid"]),
            forecast_duplicate_flag=raw["forecast_duplicate_flag"] == "true",
            actual_collection_run_id=raw["current_collection_run_id"],
            actual_called_at=raw["current_called_at"],
            actual_congestion_level=raw["current_congestion_level"],
            actual_population_min=int(raw["current_population_min"]),
            actual_population_max=int(raw["current_population_max"]),
            actual_population_mid=float(raw["current_population_mid"]),
            actual_duplicate_flag=raw["current_duplicate_flag"] == "true",
        )
    except (KeyError, ValueError) as error:
        raise B1OutputValidationError(f"{ERROR_B1_PAIR_ROW_INVALID}: {error}") from error


def load_b1_output_bundle(
    phase_dir: Path,
    *,
    expected_dataset_id: str | None = None,
) -> B1OutputBundle:
    """Load and validate an EG-8B B1 output directory (phase1-v1) read-only.

    Validation order: file existence -> dataset_id match (against
    dataset_profile.json) -> Exact Match row-count match
    (forecast_match_summary.json's exact_match_rows vs
    forecast_evaluation_pairs.csv's actual row count) -> each pair row
    parses. Raises B1OutputValidationError on any failure and never
    modifies phase_dir.
    """
    if not phase_dir.is_dir():
        raise B1OutputValidationError(
            f"{ERROR_B1_OUTPUT_FILE_MISSING}: B1 output directory does not exist"
        )

    file_paths: dict[str, Path] = {}
    for filename in _B1_REQUIRED_FILES:
        path = phase_dir / filename
        if not path.is_file():
            raise B1OutputValidationError(f"{ERROR_B1_OUTPUT_FILE_MISSING}: {filename}")
        file_paths[filename] = path

    dataset_profile = _read_json_object(
        file_paths[eg8b.DATASET_PROFILE_FILENAME], label=eg8b.DATASET_PROFILE_FILENAME
    )
    forecast_match_summary = _read_json_object(
        file_paths[eg8b.FORECAST_MATCH_SUMMARY_FILENAME],
        label=eg8b.FORECAST_MATCH_SUMMARY_FILENAME,
    )

    dataset_id = dataset_profile.get("dataset_id")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise B1OutputValidationError(
            f"{ERROR_B1_DATASET_ID_MISMATCH}: dataset_profile dataset_id is missing or invalid"
        )
    if expected_dataset_id is not None and dataset_id != expected_dataset_id:
        raise B1OutputValidationError(
            f"{ERROR_B1_DATASET_ID_MISMATCH}: expected {expected_dataset_id!r}, "
            f"dataset_profile has {dataset_id!r}"
        )

    pair_raw_rows = _read_csv_rows(
        file_paths[eg8b.FORECAST_EVALUATION_PAIRS_FILENAME],
        label=eg8b.FORECAST_EVALUATION_PAIRS_FILENAME,
    )
    exact_match_rows = forecast_match_summary.get("exact_match_rows")
    if exact_match_rows != len(pair_raw_rows):
        raise B1OutputValidationError(
            f"{ERROR_B1_EXACT_MATCH_COUNT_MISMATCH}: forecast_match_summary="
            f"{exact_match_rows!r} actual_pair_rows={len(pair_raw_rows)}"
        )

    pairs = tuple(_pair_row_from_dict(row) for row in pair_raw_rows)

    return B1OutputBundle(
        dataset_id=dataset_id,
        dataset_profile=dataset_profile,
        forecast_match_summary=forecast_match_summary,
        pairs=pairs,
    )


# ---------------------------------------------------------------------------
# B0 Persistence Baseline: "the population observed at forecast generation
# time persists unchanged through the forecast target time." Origin rows
# carry their full population_min/max/mid/congestion_level forward (not
# just the midpoint) so B0 can be scored on the same 5 metrics as the
# official Forecast.
# ---------------------------------------------------------------------------


def _index_current_by_area_observed(
    bundle: eg8b.DatasetBundle,
) -> dict[tuple[str, str], eg8b.CurrentRow]:
    """Index EG-8A Current rows by (area_code, observed_at) for B0 Origin
    lookup. Mirrors eg8b._build_current_index's key shape (not imported --
    that helper is private to eg8b.py, only its public CurrentRow/
    DatasetBundle types are reused here)."""
    index: dict[tuple[str, str], eg8b.CurrentRow] = {}
    for row in bundle.current_rows:
        index[(row.area_code, row.observed_at)] = row
    return index


def build_b0_baseline_pairs_rows(
    b1_bundle: B1OutputBundle,
    eg8a_bundle: eg8b.DatasetBundle,
) -> tuple[list[dict[str, object]], int]:
    """Return (rows, origin_lookup_missing_count).

    For each B1 Exact-Match Pair, looks up the Current row observed at
    (area_code, forecast_observed_at) -- the same snapshot the Forecast row
    itself was derived from -- as B0's Origin. A Pair whose own Origin
    Current row failed EG-8A validation (became an error row in a Run
    where a sibling Area's row was still valid) cannot have its Origin
    found here; such Pairs are excluded from the returned rows and counted
    rather than raising, since this is a legitimate (if rare) real-data
    outcome, not a structural bug.
    """
    current_index = _index_current_by_area_observed(eg8a_bundle)

    rows: list[dict[str, object]] = []
    origin_lookup_missing_count = 0

    for pair in b1_bundle.pairs:
        origin = current_index.get((pair.area_code, pair.forecast_observed_at))
        if origin is None:
            origin_lookup_missing_count += 1
            continue

        forecast_abs_error = abs(pair.forecast_population_mid - pair.actual_population_mid)
        forecast_relative_error = (
            forecast_abs_error / pair.actual_population_mid
            if pair.actual_population_mid != 0
            else None
        )
        forecast_interval_included = (
            pair.forecast_population_min <= pair.actual_population_mid <= pair.forecast_population_max
        )
        forecast_congestion_match = pair.forecast_congestion_level == pair.actual_congestion_level

        b0_abs_error = abs(origin.population_mid - pair.actual_population_mid)
        b0_relative_error = (
            b0_abs_error / pair.actual_population_mid if pair.actual_population_mid != 0 else None
        )
        b0_interval_included = origin.population_min <= pair.actual_population_mid <= origin.population_max
        b0_congestion_match = origin.congestion_level == pair.actual_congestion_level

        rows.append(
            {
                "area_code": pair.area_code,
                "forecast_collection_run_id": pair.forecast_collection_run_id,
                "forecast_called_at": pair.forecast_called_at,
                "forecast_observed_at": pair.forecast_observed_at,
                "forecast_at": pair.forecast_at,
                "horizon_minutes": pair.horizon_minutes,
                "origin_collection_run_id": origin.collection_run_id,
                "origin_called_at": origin.called_at,
                "origin_population_min": origin.population_min,
                "origin_population_max": origin.population_max,
                "origin_population_mid": origin.population_mid,
                "origin_congestion_level": origin.congestion_level,
                "origin_duplicate_flag": origin.duplicate_flag,
                "forecast_population_min": pair.forecast_population_min,
                "forecast_population_max": pair.forecast_population_max,
                "forecast_population_mid": pair.forecast_population_mid,
                "forecast_congestion_level": pair.forecast_congestion_level,
                "forecast_duplicate_flag": pair.forecast_duplicate_flag,
                "actual_population_min": pair.actual_population_min,
                "actual_population_max": pair.actual_population_max,
                "actual_population_mid": pair.actual_population_mid,
                "actual_congestion_level": pair.actual_congestion_level,
                "actual_duplicate_flag": pair.actual_duplicate_flag,
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
# Shared metrics: MAE / RMSE / relative error / interval inclusion rate /
# congestion match rate. No formula for these exists in
# docs/analysis/ANALYSIS_PLAN.md sec.20 (prose only) -- these were
# prototyped and run against the real Smoke Dataset in the prior read-only
# "EG-8B Phase 1" analysis and are adopted here as-is.
# ---------------------------------------------------------------------------


def _compute_metrics(
    abs_errors: Sequence[float],
    relative_errors: Sequence[float],
    interval_included_flags: Sequence[bool],
    congestion_match_flags: Sequence[bool],
) -> dict[str, object]:
    """relative_errors is expected pre-filtered by the caller (rows whose
    actual_population_mid == 0 excluded to avoid division by zero); its own
    length is reported as the relative-error sample count."""
    n = len(abs_errors)
    return {
        "pair_count": n,
        "mae": statistics.mean(abs_errors) if n else None,
        "rmse": math.sqrt(statistics.mean(e * e for e in abs_errors)) if n else None,
        "relative_error_sample_count": len(relative_errors),
        "mean_relative_error": statistics.mean(relative_errors) if relative_errors else None,
        "interval_inclusion_rate": (sum(interval_included_flags) / n) if n else None,
        "congestion_match_rate": (sum(congestion_match_flags) / n) if n else None,
    }


def _performance_row(
    key_field: str, key_value: object, rows: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    forecast_metrics = _compute_metrics(
        [row["forecast_abs_error"] for row in rows],
        [row["forecast_relative_error"] for row in rows if row["forecast_relative_error"] is not None],
        [row["forecast_interval_included"] for row in rows],
        [row["forecast_congestion_match"] for row in rows],
    )
    b0_metrics = _compute_metrics(
        [row["b0_abs_error"] for row in rows],
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
        "forecast_rmse": forecast_metrics["rmse"],
        "forecast_relative_error_sample_count": forecast_metrics["relative_error_sample_count"],
        "forecast_mean_relative_error": forecast_metrics["mean_relative_error"],
        "forecast_interval_inclusion_rate": forecast_metrics["interval_inclusion_rate"],
        "forecast_congestion_match_rate": forecast_metrics["congestion_match_rate"],
        "b0_mae": b0_mae,
        "b0_rmse": b0_metrics["rmse"],
        "b0_relative_error_sample_count": b0_metrics["relative_error_sample_count"],
        "b0_mean_relative_error": b0_metrics["mean_relative_error"],
        "b0_interval_inclusion_rate": b0_metrics["interval_inclusion_rate"],
        "b0_congestion_match_rate": b0_metrics["congestion_match_rate"],
        "forecast_mae_lower_than_b0": (
            forecast_mae < b0_mae if forecast_mae is not None and b0_mae is not None else None
        ),
    }


def build_area_performance_rows(
    pairs_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    by_area: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in pairs_rows:
        by_area[row["area_code"]].append(row)
    return [_performance_row("area_code", area, rows) for area, rows in sorted(by_area.items())]


def build_horizon_performance_rows(
    pairs_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    by_horizon: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in pairs_rows:
        by_horizon[row["horizon_minutes"]].append(row)
    return [
        _performance_row("horizon_minutes", horizon, rows) for horizon, rows in sorted(by_horizon.items())
    ]


def build_backtest_summary(
    *,
    generated_at: datetime,
    b1_bundle: B1OutputBundle,
    eg8a_dataset_id: str,
    pairs_rows: Sequence[Mapping[str, object]],
    origin_lookup_missing_count: int,
) -> dict[str, object]:
    """No file path (dataset_dir/phase_dir) is ever written into this
    document -- only dataset_id and other non-path identifiers, per the
    PM's explicit "input path must not be recorded" instruction."""
    overall_forecast = _compute_metrics(
        [row["forecast_abs_error"] for row in pairs_rows],
        [row["forecast_relative_error"] for row in pairs_rows if row["forecast_relative_error"] is not None],
        [row["forecast_interval_included"] for row in pairs_rows],
        [row["forecast_congestion_match"] for row in pairs_rows],
    )
    overall_b0 = _compute_metrics(
        [row["b0_abs_error"] for row in pairs_rows],
        [row["b0_relative_error"] for row in pairs_rows if row["b0_relative_error"] is not None],
        [row["b0_interval_included"] for row in pairs_rows],
        [row["b0_congestion_match"] for row in pairs_rows],
    )
    relative_error_excluded = sum(1 for row in pairs_rows if row["forecast_relative_error"] is None)

    return {
        "schema_version": BACKTEST_SUMMARY_SCHEMA_VERSION,
        "dataset_id": b1_bundle.dataset_id,
        "generated_at": eg8a.to_iso8601(generated_at),
        "input_provenance": {
            "b1_dataset_id": b1_bundle.dataset_id,
            "b1_exact_match_rows": b1_bundle.forecast_match_summary.get("exact_match_rows"),
            "eg8a_dataset_id": eg8a_dataset_id,
            "ids_match": b1_bundle.dataset_id == eg8a_dataset_id,
        },
        "pair_count": len(pairs_rows),
        "origin_lookup_missing_count": origin_lookup_missing_count,
        "relative_error_excluded_zero_actual_count": relative_error_excluded,
        "horizon_minutes_present": sorted({row["horizon_minutes"] for row in pairs_rows}),
        "area_codes_present": sorted({row["area_code"] for row in pairs_rows}),
        "overall_forecast_metrics": overall_forecast,
        "overall_b0_metrics": overall_b0,
        "scope_note": (
            "이 산출물은 단일 일자 잠정 분석 결과이며 공식 성공 임계값이나 "
            "EG-8B Gate PASS/FAIL을 판정하지 않는다. B1(요일·시간)·B2(4주 "
            "평균) Baseline은 포함하지 않는다(추가 데이터 필요, B2b)."
        ),
        "gate_judgment": None,
    }


# ---------------------------------------------------------------------------
# Output Writer -- exclusive create, never overwrites. <dataset_id> may
# already exist (B1's own phase1-v1 already lives there); <PHASE_B2A_VERSION>
# itself must not, and B1's phase1-v1 is never opened for writing.
# ---------------------------------------------------------------------------


def resolve_output_root_from_env(environ: Mapping[str, str]) -> Path:
    """Resolve the external EG-8B output-root from the environment. Reuses
    eg8b.py's own env-var name (FRESHMANAGER_EG8B_OUTPUT_ROOT) since B2a's
    output must coexist under the same <dataset_id> parent B1 uses. Never
    defaults to a path inside the repository; fails closed with a
    non-sensitive error if unset or not an existing directory; never
    returns the raw value in an error message."""
    value = environ.get(eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV)
    if not value:
        raise OutputRootConfigurationError(
            f"eg8b_b2a_output_root_error: {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV} is not set"
        )
    try:
        resolved = Path(value).expanduser().resolve(strict=True)
    except OSError as error:
        raise OutputRootConfigurationError(
            f"eg8b_b2a_output_root_error: {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV} does not exist"
        ) from error
    if not resolved.is_dir():
        raise OutputRootConfigurationError(
            f"eg8b_b2a_output_root_error: {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV} is not a directory"
        )
    return resolved


def _write_exclusive(path: Path, payload: bytes) -> None:
    """Write `payload` to `path`; raise EvidenceWriteError instead of ever
    overwriting an existing file (mkstemp + fsync + os.link, mirroring
    eg8b.py's/eg8a.py's exclusive-write algorithm)."""
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
        raise EvidenceWriteError(f"eg8b_b2a_write_error: {path.name} already exists") from error
    except OSError as error:
        raise EvidenceWriteError(f"eg8b_b2a_write_error: failed to write {path.name}") from error
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


def analyze_backtest(
    b1_bundle: B1OutputBundle,
    eg8a_bundle: eg8b.DatasetBundle,
    *,
    eg8b_output_root: Path,
    generated_at: datetime | None = None,
) -> BacktestResult:
    """Write the four B2a comparison artifacts for one validated pair of
    input bundles.

    `eg8b_output_root` must already exist (never auto-created). The
    `<dataset_id>` directory may already exist (B1's own phase1-v1 already
    lives there); `<PHASE_B2A_VERSION>` beneath it is created exclusively --
    a colliding run raises before any file is touched.
    """
    resolved_root = eg8b_output_root.expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise EvidenceWriteError("eg8b_b2a_write_error: output root is not a directory")

    resolved_generated_at = generated_at if generated_at is not None else datetime.now(eg8a.SEOUL)

    dataset_dir = resolved_root / b1_bundle.dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)
    phase_dir = dataset_dir / PHASE_B2A_VERSION
    try:
        phase_dir.mkdir(exist_ok=False)
    except FileExistsError as error:
        raise EvidenceWriteError(
            f"eg8b_b2a_write_error: {PHASE_B2A_VERSION} already exists for dataset {b1_bundle.dataset_id}"
        ) from error

    pairs_rows, origin_lookup_missing_count = build_b0_baseline_pairs_rows(b1_bundle, eg8a_bundle)
    area_rows = build_area_performance_rows(pairs_rows)
    horizon_rows = build_horizon_performance_rows(pairs_rows)
    summary = build_backtest_summary(
        generated_at=resolved_generated_at,
        b1_bundle=b1_bundle,
        eg8a_dataset_id=eg8a_bundle.dataset_id,
        pairs_rows=pairs_rows,
        origin_lookup_missing_count=origin_lookup_missing_count,
    )

    _write_exclusive(
        phase_dir / B0_BASELINE_PAIRS_FILENAME,
        _write_csv_rows(B0_BASELINE_PAIRS_FIELDNAMES, pairs_rows),
    )
    _write_exclusive(
        phase_dir / AREA_PERFORMANCE_FILENAME,
        _write_csv_rows(AREA_PERFORMANCE_FIELDNAMES, area_rows),
    )
    _write_exclusive(
        phase_dir / HORIZON_PERFORMANCE_FILENAME,
        _write_csv_rows(HORIZON_PERFORMANCE_FIELDNAMES, horizon_rows),
    )
    _write_exclusive(phase_dir / BACKTEST_SUMMARY_FILENAME, _write_json_document(summary))

    return BacktestResult(
        dataset_id=b1_bundle.dataset_id,
        phase_dir=phase_dir,
        backtest_summary=summary,
    )


def run_backtest(
    eg8a_dataset_dir: Path,
    b1_phase_dir: Path,
    *,
    eg8b_output_root: Path,
    expected_dataset_id: str | None = None,
    generated_at: datetime | None = None,
) -> BacktestResult:
    """Validate a B1 output directory and its underlying EG-8A dataset
    directory, then write the four B2a comparison artifacts.

    The EG-8A dataset is validated by calling eg8b.load_dataset_bundle()
    directly (existence/dataset_id/SHA-256/row-count, already implemented
    there) with expected_dataset_id set to B1's own recorded dataset_id --
    this is what enforces "B1 Dataset ID == EG-8A Dataset ID" without
    duplicating that validation logic.

    `generated_at` is normally left unset (defaults to the real current
    time); tests inject a fixed value to make repeated runs byte-comparable.
    """
    b1_bundle = load_b1_output_bundle(b1_phase_dir, expected_dataset_id=expected_dataset_id)
    eg8a_bundle = eg8b.load_dataset_bundle(eg8a_dataset_dir, expected_dataset_id=b1_bundle.dataset_id)
    return analyze_backtest(
        b1_bundle, eg8a_bundle, eg8b_output_root=eg8b_output_root, generated_at=generated_at
    )
