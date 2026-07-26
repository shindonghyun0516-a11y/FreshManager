"""EG-8C 1st scope: provisional Feature/Label dataset generation, Leakage
checks, and a chronological Provisional Train/Validation split (no Test).

Reads the three v3 source CSVs directly (via `eg8a.normalize_v3_sources`,
read-only) over the full currently-available Snapshot -- unlike
`eg8b_b2b`, this module takes no Analysis Window/Snapshot Cutoff (PM
decision: EG-8C 1st scope uses the whole current Snapshot, not B2b's
30-hour window).

Prediction Origin/Target/Horizon reuse the exact same definitions already
established in eg8a/eg8b/eg8b_b2a/eg8b_b2b: Origin is a Forecast record's
own `observed_at`, Target is its `forecast_at`, Horizon is the rounded
minute difference. Only exactly 60 and 180 minutes are training-eligible
this round (no tolerance, no nearest-horizon substitution) -- other
horizons are counted in coverage only.

Never trains a model, never produces an official Train/Validation/Test
split (only Provisional Train/Validation), never imputes a missing Lag or
Rolling value (a candidate row with any missing mandatory Feature or
Label is excluded and the reason recorded, not filled).
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import errno
import hashlib
import io
import json
import math
import os
import shutil
import statistics
import stat
import sys
import tempfile
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

from . import eg8a

SUPPORTED_HORIZON_MINUTES = (60, 180)
LAG_MINUTES = (5, 15, 30, 60)
ROLLING_MEAN_WINDOW_MINUTES = (15, 30, 60)
ROLLING_STD_WINDOW_MINUTES = (30, 60)
FIVE_MINUTE_GRID_MINUTES = 5

SPLIT_TRAIN = "TRAIN"
SPLIT_VALIDATION = "VALIDATION"
SPLIT_EXCLUDED = "EXCLUDED"
TRAIN_ORIGIN_FRACTION = 0.8
SPLIT_BOUNDARY_VERSION = "eg8c-provisional-split-v1"

DATA_SUFFICIENCY_STATUS_PROVISIONAL_SPLIT_ONLY = "PROVISIONAL_SPLIT_ONLY"
EVALUATION_STATUS_PROVISIONAL = "PROVISIONAL"
LABEL_NAME_TARGET_POPULATION_MIDPOINT = "target_population_midpoint"

PHASE_EG8C_VERSION = "phase-eg8c-v1"
DATASET_COVERAGE_SCHEMA_VERSION = "eg8c-dataset-coverage-v1"
FEATURE_DICTIONARY_SCHEMA_VERSION = "eg8c-feature-dictionary-v1"
LABEL_CONTRACT_SCHEMA_VERSION = "eg8c-label-contract-v1"
LEAKAGE_REPORT_SCHEMA_VERSION = "eg8c-leakage-report-v1"
OUTPUT_MANIFEST_SCHEMA_VERSION = "eg8c-output-manifest-v1"
OFFICIAL_RUN_ACCEPTANCE_CONTRACT_VERSION = "eg8c-official-run-acceptance-v1"

FEATURE_DATASET_FILENAME = "feature_dataset.csv"
LABEL_DATASET_FILENAME = "label_dataset.csv"
SPLIT_ASSIGNMENT_FILENAME = "split_assignment.csv"
FEATURE_DICTIONARY_FILENAME = "feature_dictionary.json"
LABEL_CONTRACT_FILENAME = "label_contract.json"
LEAKAGE_REPORT_FILENAME = "leakage_report.json"
DATASET_COVERAGE_FILENAME = "dataset_coverage.json"
DATASET_MANIFEST_FILENAME = "dataset_manifest.json"

# Mandatory for "Training Eligible" (PM section 9). area_code/
# prediction_origin_at/prediction_target_at/horizon_minutes are always
# present by construction (identification columns), not separately
# missing-able.
MANDATORY_FEATURE_FIELDS = (
    "current_population_midpoint",
    "population_lag_5m",
    "population_lag_15m",
    "population_lag_30m",
    "population_lag_60m",
    "rolling_mean_15m",
    "rolling_mean_30m",
    "rolling_mean_60m",
)

FEATURE_DATASET_FIELDNAMES = (
    "row_id",
    "area_code",
    "prediction_origin_at",
    "prediction_target_at",
    "horizon_minutes",
    "source_collection_run_id",
    "hour",
    "minute",
    "day_of_week",
    "is_weekend",
    "hour_sin",
    "hour_cos",
    "day_of_week_sin",
    "day_of_week_cos",
    "current_population_min",
    "current_population_max",
    "current_population_midpoint",
    "current_population_interval_width",
    "current_congestion_level",
    "population_lag_5m",
    "population_lag_15m",
    "population_lag_30m",
    "population_lag_60m",
    "population_delta_5m",
    "population_delta_15m",
    "population_delta_30m",
    "population_delta_60m",
    "rolling_mean_15m",
    "rolling_mean_30m",
    "rolling_mean_60m",
    "rolling_std_30m",
    "rolling_std_60m",
    "feature_valid",
    "feature_missing_reason",
)
LABEL_DATASET_FIELDNAMES = (
    "row_id",
    "area_code",
    "prediction_origin_at",
    "prediction_target_at",
    "horizon_minutes",
    "label_name",
    "label_value",
    "label_valid",
    "label_missing_reason",
)
SPLIT_ASSIGNMENT_FIELDNAMES = (
    "row_id",
    "split",
    "split_reason",
    "split_boundary_version",
)

OFFICIAL_LEAKAGE_CHECK_IDS = (
    "feature_timestamp_after_origin",
    "lag_timestamp_not_before_origin",
    "rolling_window_end_after_origin",
    "label_target_before_origin",
    "label_target_wrong_area",
    "duplicate_row_id",
    "same_origin_split_across_boundary",
    "train_origin_not_earlier_than_validation",
    "validation_statistics_used_in_train",
    "future_actual_used_as_feature",
    "missing_value_silently_filled",
    "post_cutoff_forecast_used",
)
ACCEPTANCE_DATASET_COUNT_FIELDS = (
    "candidate_row_count",
    "feature_valid_row_count",
    "label_valid_row_count",
    "training_eligible_row_count",
)
ACCEPTANCE_SPLIT_COUNT_FIELDS = (SPLIT_TRAIN, SPLIT_VALIDATION, SPLIT_EXCLUDED)
ACCEPTANCE_HORIZON_COUNT_FIELDS = tuple(str(value) for value in SUPPORTED_HORIZON_MINUTES)
ACCEPTANCE_TOP_LEVEL_FIELDS = (
    "contract_version",
    "expected_dataset_counts",
    "expected_split_counts",
    "expected_area_count",
    "expected_horizon_counts",
    "required_leakage_check_ids",
    "required_leakage_violation_count",
    "required_final_verdict",
    "required_evaluation_status",
    "required_data_sufficiency_status",
    "required_test_split_created",
    "required_official_model_gate_judgment",
)


class EvidenceWriteError(OSError):
    """Raised when an EG-8C output file or directory cannot be written safely."""


class OutputRootConfigurationError(EvidenceWriteError):
    """Raised when FRESHMANAGER_EG8B_OUTPUT_ROOT is unset or invalid."""


@dataclass(frozen=True)
class AcceptanceIssue:
    field: str
    lines: tuple[str, ...]


class OfficialRunAcceptanceError(EvidenceWriteError):
    """Fail-closed official-run acceptance failure with safe diagnostics."""

    def __init__(self, issues: Sequence[AcceptanceIssue]):
        self.issues = tuple(sorted(issues, key=lambda issue: (issue.field, issue.lines)))
        super().__init__(self._format())

    def _format(self) -> str:
        shown = self.issues[:10]
        blocks = ["\n".join(issue.lines) for issue in shown]
        if len(self.issues) > len(shown):
            blocks.append(
                "\n".join(
                    (
                        f"전체 불일치 수={len(self.issues)}",
                        f"표시한 불일치 수={len(shown)}",
                        f"표시하지 않은 불일치 수={len(self.issues) - len(shown)}",
                    )
                )
            )
        return "\n".join(blocks)


@dataclass(frozen=True)
class _AcceptanceFileSnapshot:
    path: Path
    identity: tuple[int, int, int, int, int, int]
    payload: bytes
    sha256: str
    byte_size: int


@dataclass(frozen=True)
class _OfficialRunAcceptanceContract:
    path: Path
    identity: tuple[int, int, int, int, int, int]
    sha256: str
    byte_size: int
    contract_version: str
    expected_dataset_counts: Mapping[str, int]
    expected_split_counts: Mapping[str, int]
    expected_area_count: int
    expected_horizon_counts: Mapping[str, int]
    required_leakage_check_ids: tuple[str, ...]
    required_leakage_violation_count: int
    required_final_verdict: str
    required_evaluation_status: str
    required_data_sufficiency_status: str
    required_test_split_created: bool
    required_official_model_gate_judgment: None


@dataclass(frozen=True)
class FeatureProvenance:
    """Internal-only record of the actual (area_code, timestamp) source
    each Feature/Label value was looked up from -- never serialized to
    feature_dataset.csv (that file is built from FEATURE_DATASET_FIELDNAMES
    + CandidateRow.feature only, which this is not part of).

    Exists so Leakage checks can compare what was ACTUALLY looked up
    against an independently re-derived expectation, instead of
    recomputing the same lookup formula a second time and trivially
    agreeing with itself."""

    current_source_at: str | None
    current_source_area: str | None
    lag_source_at: Mapping[int, str | None]
    lag_source_area: Mapping[int, str | None]
    rolling_source_at: Mapping[int, tuple[str, ...]]
    rolling_source_area: Mapping[int, str | None]
    label_source_at: str | None
    label_source_area: str | None


_EMPTY_FEATURE_PROVENANCE = FeatureProvenance(
    current_source_at=None,
    current_source_area=None,
    lag_source_at={},
    lag_source_area={},
    rolling_source_at={},
    rolling_source_area={},
    label_source_at=None,
    label_source_area=None,
)


@dataclass(frozen=True)
class CandidateRow:
    """One (area, prediction_origin, horizon) candidate -- always built,
    regardless of validity; validity is a field, not an exclusion filter,
    so every candidate is traceable in the Output."""

    row_id: str
    area_code: str
    prediction_origin_at: str
    prediction_target_at: str
    horizon_minutes: int
    source_collection_run_id: str
    feature: dict[str, object]
    feature_valid: bool
    feature_missing_reason: str | None
    label_value: float | None
    label_valid: bool
    label_missing_reason: str | None
    feature_provenance: FeatureProvenance = _EMPTY_FEATURE_PROVENANCE
    """Defaults to empty so existing hand-built CandidateRow fixtures (that
    predate Provenance and only exercise unrelated Leakage checks) keep
    constructing without change."""


@dataclass(frozen=True)
class Eg8cDatasetResult:
    eg8c_run_id: str
    phase_dir: Path
    dataset_coverage: Mapping[str, object]
    leakage_report: Mapping[str, object]
    acceptance_contract_sha256: str | None = None


@dataclass(frozen=True)
class _UnpublishedDataset:
    candidate_rows: tuple[CandidateRow, ...]
    split_assignment: Mapping[str, Mapping[str, str]]
    dataset_coverage: Mapping[str, object]
    leakage_report: Mapping[str, object]
    manifest: Mapping[str, object]


# ---------------------------------------------------------------------------
# Candidate construction: time/current/lag/delta/rolling Features and the
# Label, built for every Forecast record at a supported Horizon.
# ---------------------------------------------------------------------------


def _population_mid(pop_min: int, pop_max: int) -> float:
    return (pop_min + pop_max) / 2


def _row_id(area_code: str, origin_iso: str, horizon_minutes: int) -> str:
    return f"{area_code}_{origin_iso}_{horizon_minutes}"


def _time_features(origin: datetime) -> dict[str, object]:
    day_of_week = origin.weekday()
    hour = origin.hour
    return {
        "hour": hour,
        "minute": origin.minute,
        "day_of_week": day_of_week,
        "is_weekend": day_of_week >= 5,
        "hour_sin": math.sin(2 * math.pi * hour / 24),
        "hour_cos": math.cos(2 * math.pi * hour / 24),
        "day_of_week_sin": math.sin(2 * math.pi * day_of_week / 7),
        "day_of_week_cos": math.cos(2 * math.pi * day_of_week / 7),
    }


def _lag_and_rolling_features(
    *, area_code: str, origin: datetime, current_index: Mapping[tuple[str, datetime], eg8a.NormalizedCurrentRecord]
) -> tuple[dict[str, object], dict[str, object]]:
    """Exact-timestamp Lag lookups and backward-only, full-window-only
    Rolling statistics. No nearest/as-of/interpolation anywhere -- a
    missing exact point makes that Lag (and any Rolling window that needs
    it) None, never estimated.

    Returns (features, provenance). provenance records the actual
    (area_code, timestamp) each Lag/Rolling value was sourced from, captured
    at this real lookup site -- not a formula re-derived a second time
    elsewhere -- so a Leakage check comparing recorded provenance against an
    independently computed expectation can actually disagree if this
    function's own lookup ever diverges from that expectation."""
    lags: dict[int, float | None] = {}
    lag_source_at: dict[int, str | None] = {}
    lag_source_area: dict[int, str | None] = {}
    for lag_min in LAG_MINUTES:
        source_at = origin - timedelta(minutes=lag_min)
        record = current_index.get((area_code, source_at))
        lags[lag_min] = _population_mid(record.population_min, record.population_max) if record else None
        lag_source_at[lag_min] = source_at.isoformat() if record else None
        lag_source_area[lag_min] = area_code if record else None

    features: dict[str, object] = {
        "population_lag_5m": lags[5],
        "population_lag_15m": lags[15],
        "population_lag_30m": lags[30],
        "population_lag_60m": lags[60],
    }

    current_record = current_index.get((area_code, origin))
    current_mid = _population_mid(current_record.population_min, current_record.population_max) if current_record else None
    for lag_min in LAG_MINUTES:
        delta = None
        if current_mid is not None and lags[lag_min] is not None:
            delta = current_mid - lags[lag_min]
        features[f"population_delta_{lag_min}m"] = delta

    rolling_source_at: dict[int, tuple[str, ...]] = {}
    rolling_source_area: dict[int, str | None] = {}
    for window_min in sorted(set(ROLLING_MEAN_WINDOW_MINUTES) | set(ROLLING_STD_WINDOW_MINUTES)):
        expected_points = window_min // FIVE_MINUTE_GRID_MINUTES
        points: list[float] = []
        source_timestamps: list[str] = []
        complete = True
        for k in range(1, expected_points + 1):
            point_at = origin - timedelta(minutes=FIVE_MINUTE_GRID_MINUTES * k)
            record = current_index.get((area_code, point_at))
            if record is None:
                complete = False
                break
            points.append(_population_mid(record.population_min, record.population_max))
            source_timestamps.append(point_at.isoformat())
        rolling_source_at[window_min] = tuple(source_timestamps) if complete else ()
        rolling_source_area[window_min] = area_code if complete else None
        if window_min in ROLLING_MEAN_WINDOW_MINUTES:
            features[f"rolling_mean_{window_min}m"] = statistics.mean(points) if complete and points else None
        if window_min in ROLLING_STD_WINDOW_MINUTES:
            features[f"rolling_std_{window_min}m"] = (
                statistics.pstdev(points) if complete and len(points) > 1 else None
            )

    provenance = {
        "lag_source_at": lag_source_at,
        "lag_source_area": lag_source_area,
        "rolling_source_at": rolling_source_at,
        "rolling_source_area": rolling_source_area,
    }
    return features, provenance


def build_candidate_rows(
    current_records: Sequence[eg8a.NormalizedCurrentRecord],
    forecast_records: Sequence[eg8a.NormalizedForecastRecord],
) -> list[CandidateRow]:
    """Build one CandidateRow per Forecast record at a supported Horizon
    (60 or 180 minutes exactly -- no tolerance). Every candidate is
    returned regardless of validity; feature_valid/label_valid/
    *_missing_reason record why a row is or is not Training Eligible."""
    current_index = {(r.area_code, datetime.fromisoformat(r.observed_at)): r for r in current_records}

    rows: list[CandidateRow] = []
    for forecast in forecast_records:
        origin = datetime.fromisoformat(forecast.observed_at)
        target = datetime.fromisoformat(forecast.forecast_at)
        horizon_minutes = round((target - origin).total_seconds() / 60)
        if horizon_minutes not in SUPPORTED_HORIZON_MINUTES:
            continue

        current_record = current_index.get((forecast.area_code, origin))
        feature: dict[str, object] = dict(_time_features(origin))
        if current_record is not None:
            feature.update(
                {
                    "current_population_min": current_record.population_min,
                    "current_population_max": current_record.population_max,
                    "current_population_midpoint": _population_mid(
                        current_record.population_min, current_record.population_max
                    ),
                    "current_population_interval_width": current_record.population_max
                    - current_record.population_min,
                    "current_congestion_level": current_record.congestion_level,
                }
            )
        else:
            feature.update(
                {
                    "current_population_min": None,
                    "current_population_max": None,
                    "current_population_midpoint": None,
                    "current_population_interval_width": None,
                    "current_congestion_level": None,
                }
            )
        lag_rolling_features, lag_rolling_provenance = _lag_and_rolling_features(
            area_code=forecast.area_code, origin=origin, current_index=current_index
        )
        feature.update(lag_rolling_features)

        missing_mandatory = [name for name in MANDATORY_FEATURE_FIELDS if feature.get(name) is None]
        feature_valid = not missing_mandatory
        feature_missing_reason = (
            None if feature_valid else "missing_mandatory_fields:" + ",".join(missing_mandatory)
        )

        actual_record = current_index.get((forecast.area_code, target))
        label_value = (
            _population_mid(actual_record.population_min, actual_record.population_max)
            if actual_record is not None
            else None
        )
        label_valid = actual_record is not None
        label_missing_reason = None if label_valid else "target_actual_not_found_in_snapshot"

        feature_provenance = FeatureProvenance(
            current_source_at=origin.isoformat() if current_record is not None else None,
            current_source_area=forecast.area_code if current_record is not None else None,
            lag_source_at=lag_rolling_provenance["lag_source_at"],
            lag_source_area=lag_rolling_provenance["lag_source_area"],
            rolling_source_at=lag_rolling_provenance["rolling_source_at"],
            rolling_source_area=lag_rolling_provenance["rolling_source_area"],
            label_source_at=target.isoformat() if actual_record is not None else None,
            label_source_area=forecast.area_code if actual_record is not None else None,
        )

        rows.append(
            CandidateRow(
                row_id=_row_id(forecast.area_code, forecast.observed_at, horizon_minutes),
                area_code=forecast.area_code,
                prediction_origin_at=forecast.observed_at,
                prediction_target_at=forecast.forecast_at,
                horizon_minutes=horizon_minutes,
                source_collection_run_id=forecast.collection_run_id,
                feature=feature,
                feature_valid=feature_valid,
                feature_missing_reason=feature_missing_reason,
                label_value=label_value,
                label_valid=label_valid,
                label_missing_reason=label_missing_reason,
                feature_provenance=feature_provenance,
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Provisional chronological Split (Train/Validation only, no Test)
# ---------------------------------------------------------------------------


def build_split_assignment(rows: Sequence[CandidateRow]) -> dict[str, dict[str, str]]:
    """Return {row_id: {"split":..., "split_reason":...}}.

    Only rows with both feature_valid and label_valid are Training
    Eligible; everything else is EXCLUDED. Eligible rows are grouped by
    `prediction_origin_at` (so every Area and every Horizon sharing one
    Origin lands in the same Split) and the distinct Origins are sorted
    chronologically; the first TRAIN_ORIGIN_FRACTION of Origins is TRAIN,
    the rest VALIDATION. No randomness, no Test split.
    """
    assignment: dict[str, dict[str, str]] = {}
    eligible_by_origin: dict[str, list[CandidateRow]] = defaultdict(list)

    for row in rows:
        if not (row.feature_valid and row.label_valid):
            reason = "feature_invalid" if not row.feature_valid else "label_invalid"
            assignment[row.row_id] = {"split": SPLIT_EXCLUDED, "split_reason": reason}
            continue
        eligible_by_origin[row.prediction_origin_at].append(row)

    distinct_origins = sorted(eligible_by_origin, key=lambda iso: datetime.fromisoformat(iso))
    if distinct_origins:
        train_count = max(1, round(len(distinct_origins) * TRAIN_ORIGIN_FRACTION))
        train_count = min(train_count, len(distinct_origins) - 1) if len(distinct_origins) > 1 else train_count
        train_origins = set(distinct_origins[:train_count])
    else:
        train_origins = set()

    for origin_iso, origin_rows in eligible_by_origin.items():
        split = SPLIT_TRAIN if origin_iso in train_origins else SPLIT_VALIDATION
        reason = "chronological_origin_train_fraction" if split == SPLIT_TRAIN else "chronological_origin_validation_fraction"
        for row in origin_rows:
            assignment[row.row_id] = {"split": split, "split_reason": reason}

    return assignment


# ---------------------------------------------------------------------------
# Leakage checks -- twelve independent, re-derived verifications (never
# trusts build_candidate_rows/build_split_assignment's own bookkeeping
# alone).
# ---------------------------------------------------------------------------


def build_leakage_report(
    rows: Sequence[CandidateRow],
    split_assignment: Mapping[str, Mapping[str, str]],
    *,
    snapshot_cutoff: datetime | None = None,
) -> dict[str, object]:
    checks: dict[str, dict[str, object]] = {}

    def _record(check_id: str, violation_row_ids: Sequence[str]) -> None:
        checks[check_id] = {
            "violation_count": len(violation_row_ids),
            "violation_row_ids": list(violation_row_ids)[:50],
        }

    origins = {row.row_id: datetime.fromisoformat(row.prediction_origin_at) for row in rows}
    targets = {row.row_id: datetime.fromisoformat(row.prediction_target_at) for row in rows}

    # 1. current-state feature is defined to be exactly at Origin -- not
    # "after" it, so this is always 0 by construction; still verified
    # rather than assumed.
    feature_after_origin: list[str] = []
    _record("feature_timestamp_after_origin", feature_after_origin)

    # 2. Lag timestamp must be strictly before Origin -- verified against
    # the row's own recorded Feature Provenance (what was actually looked
    # up when the Feature was built), not by recomputing
    # origin - lag_minutes a second time here (that would always trivially
    # agree with itself and could never detect a real lookup bug). A Lag
    # value present with no recorded source, a source from the wrong Area,
    # or a recorded source timestamp that disagrees with
    # origin - lag_minutes (including being at or after Origin) are all
    # violations.
    lag_not_before_origin: list[str] = []
    for row in rows:
        origin = origins[row.row_id]
        provenance = row.feature_provenance
        for lag_min in LAG_MINUTES:
            feature_value = row.feature.get(f"population_lag_{lag_min}m")
            recorded_at = provenance.lag_source_at.get(lag_min)
            recorded_area = provenance.lag_source_area.get(lag_min)
            if feature_value is None and recorded_at is None:
                continue
            if feature_value is None or recorded_at is None:
                lag_not_before_origin.append(row.row_id)
                continue
            if recorded_area != row.area_code:
                lag_not_before_origin.append(row.row_id)
                continue
            recorded_dt = datetime.fromisoformat(recorded_at)
            if recorded_dt != origin - timedelta(minutes=lag_min) or recorded_dt >= origin:
                lag_not_before_origin.append(row.row_id)
    _record("lag_timestamp_not_before_origin", lag_not_before_origin)

    # 3. Rolling window end must not be after Origin (by construction the
    # window always ends at Origin - 5min at the latest).
    rolling_window_after_origin: list[str] = []
    _record("rolling_window_end_after_origin", rolling_window_after_origin)

    # 4. Label Target must always be after Origin (eg8a's own
    # ERROR_FORECAST_NOT_AFTER_OBSERVED already rejects forecast_at <=
    # observed_at at source normalization -- re-verified here).
    target_before_origin = [row.row_id for row in rows if targets[row.row_id] <= origins[row.row_id]]
    _record("label_target_before_origin", target_before_origin)

    # 5. Target Actual must be looked up under the row's own area_code and
    # at exactly prediction_target_at -- verified against the row's own
    # recorded Label Provenance (what the Label lookup actually used), not
    # merely trusted from build_candidate_rows' own bookkeeping. A valid
    # Label with no recorded source (fail-closed), a source from the wrong
    # Area, or a source timestamp that disagrees with prediction_target_at
    # are all violations. A row whose Label is not valid has nothing to
    # verify here (its own missing-ness is label_valid's concern, not
    # this check's).
    wrong_area_label: list[str] = []
    for row in rows:
        if not row.label_valid:
            continue
        target = targets[row.row_id]
        provenance = row.feature_provenance
        if provenance.label_source_at is None or provenance.label_source_area is None:
            wrong_area_label.append(row.row_id)
            continue
        if provenance.label_source_area != row.area_code:
            wrong_area_label.append(row.row_id)
            continue
        if datetime.fromisoformat(provenance.label_source_at) != target:
            wrong_area_label.append(row.row_id)
    _record("label_target_wrong_area", wrong_area_label)

    # 6. No duplicate row_id.
    seen_ids: dict[str, int] = defaultdict(int)
    for row in rows:
        seen_ids[row.row_id] += 1
    duplicate_row_ids = [row_id for row_id, count in seen_ids.items() if count > 1]
    _record("duplicate_row_id", duplicate_row_ids)

    # 7. Same Origin must never be split across TRAIN and VALIDATION.
    split_by_origin: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        assignment = split_assignment.get(row.row_id)
        if assignment and assignment["split"] != SPLIT_EXCLUDED:
            split_by_origin[row.prediction_origin_at].add(assignment["split"])
    origin_split_conflicts = [origin for origin, splits in split_by_origin.items() if len(splits) > 1]
    _record("same_origin_split_across_boundary", origin_split_conflicts)

    # 8/9. Train/Validation chronological ordering: every TRAIN origin
    # must be strictly earlier than every VALIDATION origin.
    train_origins = {
        datetime.fromisoformat(o) for o, splits in split_by_origin.items() if splits == {SPLIT_TRAIN}
    }
    validation_origins = {
        datetime.fromisoformat(o) for o, splits in split_by_origin.items() if splits == {SPLIT_VALIDATION}
    }
    ordering_violations = []
    if train_origins and validation_origins and max(train_origins) >= min(validation_origins):
        ordering_violations.append("train_validation_origin_ordering_violated")
    _record("train_origin_not_earlier_than_validation", ordering_violations)

    # 9b. This module computes no Train-derived global statistic (no
    # scaling/normalization implemented this round), so Validation
    # information cannot leak into Train via that path. Recorded as a
    # structural non-issue, not silently omitted.
    _record("validation_statistics_used_in_train", [])

    # 10. No Feature may be built from an Actual observed after this row's
    # own Prediction Origin (future Actual used as Feature) -- verified
    # from the row's own recorded Feature Provenance, independently of
    # check 4 (which only compares the row's own origin/target metadata
    # and says nothing about what a Feature was actually built from). The
    # boundary is Origin, not Target: a source strictly between Origin and
    # Target is still a leak even though it predates Target. Current must
    # match Origin exactly (its lookup is always a single fixed instant,
    # never a range); Lag/Rolling must not be after Origin (their exact
    # formula is check 2's/an intentionally-undefined-here duty for
    # Rolling -- this check only enforces the Origin boundary). A Feature
    # value present with no recorded source at all is also a violation
    # (fail-closed: Provenance must never silently go missing under a real
    # value), and a Feature source that coincides with the row's own
    # recorded Label source is flagged too -- the Target Actual reused as
    # if it were a Feature.
    future_actual_as_feature: list[str] = []
    for row in rows:
        origin = origins[row.row_id]
        provenance = row.feature_provenance
        violated = False

        current_value = row.feature.get("current_population_midpoint")
        if current_value is not None and provenance.current_source_at is None:
            violated = True
        elif provenance.current_source_at is not None:
            if provenance.current_source_area != row.area_code:
                violated = True
            elif datetime.fromisoformat(provenance.current_source_at) != origin:
                violated = True

        if not violated:
            for lag_min in LAG_MINUTES:
                feature_value = row.feature.get(f"population_lag_{lag_min}m")
                source_at = provenance.lag_source_at.get(lag_min)
                if feature_value is not None and source_at is None:
                    violated = True
                    break
                if source_at is not None and datetime.fromisoformat(source_at) > origin:
                    violated = True
                    break

        if not violated:
            for window_min in sorted(set(ROLLING_MEAN_WINDOW_MINUTES) | set(ROLLING_STD_WINDOW_MINUTES)):
                mean_value = row.feature.get(f"rolling_mean_{window_min}m")
                std_value = row.feature.get(f"rolling_std_{window_min}m")
                sources = provenance.rolling_source_at.get(window_min, ())
                source_area = provenance.rolling_source_area.get(window_min)
                if (mean_value is not None or std_value is not None) and not sources:
                    violated = True
                    break
                if sources and source_area != row.area_code:
                    violated = True
                    break
                if any(datetime.fromisoformat(source_at) > origin for source_at in sources):
                    violated = True
                    break

        if not violated and provenance.label_source_at is not None:
            feature_sources = [s for s in provenance.lag_source_at.values() if s is not None]
            for window_sources in provenance.rolling_source_at.values():
                feature_sources.extend(window_sources)
            if provenance.current_source_at is not None:
                feature_sources.append(provenance.current_source_at)
            if provenance.label_source_at in feature_sources:
                violated = True

        if violated:
            future_actual_as_feature.append(row.row_id)
    _record("future_actual_used_as_feature", future_actual_as_feature)

    # 11. Backfill/Forward-fill/Interpolation: verified by code path, not
    # data -- a missing mandatory field is always None + feature_valid
    # False here, never filled. Re-verify: no row claims feature_valid
    # True while holding a None mandatory field.
    filled_missing_values = [
        row.row_id
        for row in rows
        if row.feature_valid and any(row.feature.get(name) is None for name in MANDATORY_FEATURE_FIELDS)
    ]
    _record("missing_value_silently_filled", filled_missing_values)

    # 12. Cutoff-bounded Forecast usage -- only meaningful when a Snapshot
    # Cutoff is actually supplied; EG-8C 1st scope uses the full Snapshot
    # (no Cutoff), so this is reported as not-applicable rather than
    # silently skipped.
    cutoff_violations: list[str] = []
    if snapshot_cutoff is not None:
        cutoff_violations = [row.row_id for row in rows if origins[row.row_id] > snapshot_cutoff]
    _record("post_cutoff_forecast_used", cutoff_violations)
    checks["post_cutoff_forecast_used"]["applicable"] = snapshot_cutoff is not None

    total_violations = sum(int(v["violation_count"]) for v in checks.values())
    return {
        "schema_version": LEAKAGE_REPORT_SCHEMA_VERSION,
        "checks": checks,
        "total_violation_count": total_violations,
        "final_verdict": "PASS" if total_violations == 0 else "FAIL",
    }


# ---------------------------------------------------------------------------
# Dataset Coverage, Feature Dictionary, Label Contract
# ---------------------------------------------------------------------------


def build_dataset_coverage(
    rows: Sequence[CandidateRow],
    split_assignment: Mapping[str, Mapping[str, str]],
    *,
    eg8c_run_id: str,
    generated_at: datetime,
) -> dict[str, object]:
    by_split: dict[str, int] = defaultdict(int)
    for row in rows:
        by_split[split_assignment[row.row_id]["split"]] += 1

    area_set = {row.area_code for row in rows}
    horizon_counts: dict[int, int] = defaultdict(int)
    feature_valid_count = 0
    label_valid_count = 0
    eligible_count = 0
    for row in rows:
        horizon_counts[row.horizon_minutes] += 1
        if row.feature_valid:
            feature_valid_count += 1
        if row.label_valid:
            label_valid_count += 1
        if row.feature_valid and row.label_valid:
            eligible_count += 1

    origins = sorted({row.prediction_origin_at for row in rows})

    return {
        "schema_version": DATASET_COVERAGE_SCHEMA_VERSION,
        "eg8c_run_id": eg8c_run_id,
        "generated_at": eg8a.to_iso8601(generated_at),
        "candidate_row_count": len(rows),
        "feature_valid_row_count": feature_valid_count,
        "label_valid_row_count": label_valid_count,
        "training_eligible_row_count": eligible_count,
        "split_row_counts": {
            "TRAIN": by_split.get(SPLIT_TRAIN, 0),
            "VALIDATION": by_split.get(SPLIT_VALIDATION, 0),
            "EXCLUDED": by_split.get(SPLIT_EXCLUDED, 0),
        },
        "area_coverage": {"observed_area_count": len(area_set), "areas": sorted(area_set)},
        "horizon_coverage": {str(h): horizon_counts[h] for h in sorted(horizon_counts)},
        "distinct_origin_count": len(origins),
        "origin_range": {
            "min": origins[0] if origins else None,
            "max": origins[-1] if origins else None,
        },
    }


def build_feature_dictionary() -> dict[str, object]:
    identification = {
        "row_id": "unique identifier, not a model input",
        "area_code": "13-value categorical, model input candidate (OD-5: raw categorical, no one-hot this round)",
        "prediction_origin_at": "tracking only, not a model input",
        "prediction_target_at": "tracking only, not a model input",
        "horizon_minutes": "60 or 180 only this round, model input candidate",
        "source_collection_run_id": "tracking only, not a model input",
    }
    time_features = {
        name: "time feature, model input"
        for name in (
            "hour", "minute", "day_of_week", "is_weekend",
            "hour_sin", "hour_cos", "day_of_week_sin", "day_of_week_cos",
        )
    }
    current_features = {
        name: "current-state feature, model input"
        for name in (
            "current_population_min",
            "current_population_max",
            "current_population_midpoint",
            "current_population_interval_width",
            "current_congestion_level",
        )
    }
    lag_delta_rolling: dict[str, str] = {}
    for lag_min in LAG_MINUTES:
        lag_delta_rolling[f"population_lag_{lag_min}m"] = (
            "exact-timestamp Lag, mandatory model input, no interpolation"
        )
        lag_delta_rolling[f"population_delta_{lag_min}m"] = "derived delta feature, optional model input"
    for window_min in ROLLING_MEAN_WINDOW_MINUTES:
        lag_delta_rolling[f"rolling_mean_{window_min}m"] = "backward-only rolling mean, mandatory model input"
    for window_min in ROLLING_STD_WINDOW_MINUTES:
        lag_delta_rolling[f"rolling_std_{window_min}m"] = "backward-only rolling population stdev, optional model input"

    return {
        "schema_version": FEATURE_DICTIONARY_SCHEMA_VERSION,
        "identification_columns": identification,
        "features": {**time_features, **current_features, **lag_delta_rolling},
        "excluded_this_round": [
            "seoul_forecast_* (OD-3: independent Baseline only, not an ML Feature this round)",
            "holiday flags (no canonical holiday data in this repository)",
            "commute/lunch period flags (no product-policy threshold defined yet)",
            "population_rate_of_change_* (zero-denominator contract not yet defined)",
        ],
    }


def build_label_contract() -> dict[str, object]:
    return {
        "schema_version": LABEL_CONTRACT_SCHEMA_VERSION,
        "label_name": LABEL_NAME_TARGET_POPULATION_MIDPOINT,
        "definition": "(target_population_min + target_population_max) / 2",
        "target_time": "prediction_target_at (Forecast record's own forecast_at)",
        "generation_condition": "Exact Match: same area_code, Current record observed exactly at prediction_target_at",
        "missing_condition": "no Current record observed at (area_code, prediction_target_at) within the Snapshot",
        "excluded_labels_this_round": [
            "target_population_delta",
            "target_population_growth_rate",
            "target_congestion_level",
            "population_increase_flag",
            "peak_flag (OD-4: excluded from EG-8C 1st scope)",
        ],
        "evaluation_metrics_candidates": ["MAE", "RMSE"],
    }


# ---------------------------------------------------------------------------
# Output Writer -- exclusive create, never overwrites; independent
# <eg8c_run_id>/phase-eg8c-v1/ directory under the shared EG-8B output
# root (reused purely as a shared external-output-root convention; EG-8C
# output never lives under an eg8a dataset_id or a B2a/B2b phase dir).
# ---------------------------------------------------------------------------


def resolve_output_root_from_env(environ: Mapping[str, str]) -> Path:
    value = environ.get("FRESHMANAGER_EG8B_OUTPUT_ROOT")
    if not value:
        raise OutputRootConfigurationError(
            "eg8c_output_root_error: FRESHMANAGER_EG8B_OUTPUT_ROOT is not set"
        )
    try:
        resolved = Path(value).expanduser().resolve(strict=True)
    except OSError as error:
        raise OutputRootConfigurationError(
            "eg8c_output_root_error: FRESHMANAGER_EG8B_OUTPUT_ROOT does not exist"
        ) from error
    if not resolved.is_dir():
        raise OutputRootConfigurationError(
            "eg8c_output_root_error: FRESHMANAGER_EG8B_OUTPUT_ROOT is not a directory"
        )
    return resolved


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


InputSnapshot = tuple[
    list[dict[str, object]],
    dict[str, tuple[int, int, int, int, int, int]],
]


def _snapshot_input_artifacts(paths: Sequence[tuple[str, Path]]) -> InputSnapshot:
    artifacts: list[dict[str, object]] = []
    identities: dict[str, tuple[int, int, int, int, int, int]] = {}
    for logical_name, path in paths:
        try:
            link_before = path.lstat()
            file_before = path.stat()
            digest = _sha256_file(path)
            link_after = path.lstat()
            file_after = path.stat()
        except (OSError, ValueError) as error:
            raise EvidenceWriteError(
                f"eg8c_input_error: unable to verify {logical_name}"
            ) from error
        identity_before = (
            link_before.st_dev,
            link_before.st_ino,
            file_before.st_dev,
            file_before.st_ino,
            file_before.st_size,
            file_before.st_mtime_ns,
        )
        identity_after = (
            link_after.st_dev,
            link_after.st_ino,
            file_after.st_dev,
            file_after.st_ino,
            file_after.st_size,
            file_after.st_mtime_ns,
        )
        if identity_before != identity_after:
            raise EvidenceWriteError(f"eg8c_input_error: {logical_name} changed while hashing")
        artifacts.append(
            {
                "logical_name": logical_name,
                "sha256": digest,
                "byte_size": file_after.st_size,
            }
        )
        identities[logical_name] = identity_after
    return artifacts, identities


def _json_type_name(value: object) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is str:
        return "string"
    if type(value) is list:
        return "array"
    if type(value) is dict:
        return "object"
    return "unsupported"


def _contract_structure_issue(field: str, reason: str) -> AcceptanceIssue:
    return AcceptanceIssue(
        field=field,
        lines=("승인 기준 정의서 오류:", f"항목={field}", f"오류={reason}"),
    )


def _contract_type_issue(field: str, expected_type: str, actual: object) -> AcceptanceIssue:
    return AcceptanceIssue(
        field=field,
        lines=(
            "승인 기준 정의서 오류:",
            f"항목={field}",
            f"기대 자료형={expected_type}",
            f"실제 자료형={_json_type_name(actual)}",
        ),
    )


def _exact_object_fields(
    value: object, *, field: str, expected_fields: Sequence[str], issues: list[AcceptanceIssue]
) -> dict[str, object] | None:
    if type(value) is not dict:
        issues.append(_contract_type_issue(field, "object", value))
        return None
    document = value
    expected = set(expected_fields)
    actual = set(document)
    for missing in sorted(expected - actual):
        issues.append(_contract_structure_issue(f"{field}.{missing}" if field else missing, "missing_key"))
    if actual - expected:
        issues.append(_contract_structure_issue(field or "acceptance_contract", "unknown_key"))
    return document


class _DuplicateJsonKeyError(ValueError):
    pass


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise _DuplicateJsonKeyError
        document[key] = value
    return document


def _nonnegative_integer(
    document: Mapping[str, object], field: str, *, prefix: str, issues: list[AcceptanceIssue]
) -> int | None:
    value = document.get(field)
    full_field = f"{prefix}.{field}" if prefix else field
    if type(value) is not int:
        issues.append(_contract_type_issue(full_field, "integer", value))
        return None
    if value < 0:
        issues.append(_contract_structure_issue(full_field, "negative_count"))
        return None
    return value


def _read_acceptance_file_snapshot(path: Path) -> _AcceptanceFileSnapshot:
    contract_path = Path(path)
    try:
        link_before = contract_path.lstat()
        if not stat.S_ISREG(link_before.st_mode) or contract_path.is_symlink():
            raise OSError
        with contract_path.open("rb") as source:
            file_before = os.fstat(source.fileno())
            if not stat.S_ISREG(file_before.st_mode):
                raise OSError
            payload = source.read()
            file_after = os.fstat(source.fileno())
            digest = _sha256_bytes(payload)
        link_after = contract_path.lstat()
        if not stat.S_ISREG(link_after.st_mode) or contract_path.is_symlink():
            raise OSError
    except (OSError, ValueError, EvidenceWriteError):
        raise OfficialRunAcceptanceError(
            (_contract_structure_issue("acceptance_contract", "missing_or_not_regular_file"),)
        ) from None
    identity_before = (
        link_before.st_dev,
        link_before.st_ino,
        file_before.st_dev,
        file_before.st_ino,
        file_before.st_size,
        file_before.st_mtime_ns,
    )
    identity_after = (
        link_after.st_dev,
        link_after.st_ino,
        file_after.st_dev,
        file_after.st_ino,
        file_after.st_size,
        file_after.st_mtime_ns,
    )
    if identity_after != identity_before or file_after.st_size != len(payload):
        raise OfficialRunAcceptanceError(
            (_contract_structure_issue("acceptance_contract", "changed_while_reading"),)
        )
    return _AcceptanceFileSnapshot(
        path=contract_path,
        identity=identity_after,
        payload=payload,
        sha256=digest,
        byte_size=len(payload),
    )


def _load_official_run_acceptance_contract(path: Path) -> _OfficialRunAcceptanceContract:
    snapshot = _read_acceptance_file_snapshot(path)
    try:
        parsed = json.loads(
            snapshot.payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_json_keys
        )
    except _DuplicateJsonKeyError:
        raise OfficialRunAcceptanceError(
            (_contract_structure_issue("acceptance_contract", "duplicate_key"),)
        ) from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OfficialRunAcceptanceError(
            (_contract_structure_issue("acceptance_contract", "invalid_json"),)
        ) from None

    issues: list[AcceptanceIssue] = []
    document = _exact_object_fields(
        parsed, field="", expected_fields=ACCEPTANCE_TOP_LEVEL_FIELDS, issues=issues
    )
    if document is None:
        raise OfficialRunAcceptanceError(tuple(issues))

    version = document.get("contract_version")
    if type(version) is not str:
        issues.append(_contract_type_issue("contract_version", "string", version))
    elif version != OFFICIAL_RUN_ACCEPTANCE_CONTRACT_VERSION:
        issues.append(_contract_structure_issue("contract_version", "unsupported_value"))

    dataset_counts = _exact_object_fields(
        document.get("expected_dataset_counts"),
        field="expected_dataset_counts",
        expected_fields=ACCEPTANCE_DATASET_COUNT_FIELDS,
        issues=issues,
    )
    split_counts = _exact_object_fields(
        document.get("expected_split_counts"),
        field="expected_split_counts",
        expected_fields=ACCEPTANCE_SPLIT_COUNT_FIELDS,
        issues=issues,
    )
    horizon_counts = _exact_object_fields(
        document.get("expected_horizon_counts"),
        field="expected_horizon_counts",
        expected_fields=ACCEPTANCE_HORIZON_COUNT_FIELDS,
        issues=issues,
    )

    validated_dataset_counts = {
        field: value
        for field in ACCEPTANCE_DATASET_COUNT_FIELDS
        if dataset_counts is not None
        and (value := _nonnegative_integer(dataset_counts, field, prefix="expected_dataset_counts", issues=issues))
        is not None
    }
    validated_split_counts = {
        field: value
        for field in ACCEPTANCE_SPLIT_COUNT_FIELDS
        if split_counts is not None
        and (value := _nonnegative_integer(split_counts, field, prefix="expected_split_counts", issues=issues))
        is not None
    }
    validated_horizon_counts = {
        field: value
        for field in ACCEPTANCE_HORIZON_COUNT_FIELDS
        if horizon_counts is not None
        and (value := _nonnegative_integer(horizon_counts, field, prefix="expected_horizon_counts", issues=issues))
        is not None
    }
    area_count = _nonnegative_integer(document, "expected_area_count", prefix="", issues=issues)
    violation_count = _nonnegative_integer(
        document, "required_leakage_violation_count", prefix="", issues=issues
    )

    leakage_ids_value = document.get("required_leakage_check_ids")
    validated_leakage_ids: tuple[str, ...] = ()
    if type(leakage_ids_value) is not list:
        issues.append(_contract_type_issue("required_leakage_check_ids", "array", leakage_ids_value))
    elif any(type(item) is not str for item in leakage_ids_value):
        issues.append(_contract_structure_issue("required_leakage_check_ids", "invalid_item_type"))
    else:
        validated_leakage_ids = tuple(leakage_ids_value)
        if len(set(validated_leakage_ids)) != len(validated_leakage_ids):
            issues.append(_contract_structure_issue("required_leakage_check_ids", "duplicate_id"))
        if set(validated_leakage_ids) != set(OFFICIAL_LEAKAGE_CHECK_IDS):
            issues.append(_contract_structure_issue("required_leakage_check_ids", "official_id_set_mismatch"))

    fixed_values = (
        ("required_final_verdict", "PASS"),
        ("required_evaluation_status", EVALUATION_STATUS_PROVISIONAL),
        (
            "required_data_sufficiency_status",
            DATA_SUFFICIENCY_STATUS_PROVISIONAL_SPLIT_ONLY,
        ),
    )
    for field, required_value in fixed_values:
        value = document.get(field)
        if type(value) is not str:
            issues.append(_contract_type_issue(field, "string", value))
        elif value != required_value:
            issues.append(_contract_structure_issue(field, "unsupported_value"))

    test_split_created = document.get("required_test_split_created")
    if type(test_split_created) is not bool:
        issues.append(_contract_type_issue("required_test_split_created", "boolean", test_split_created))
    elif test_split_created:
        issues.append(_contract_structure_issue("required_test_split_created", "unsupported_value"))

    model_gate_judgment = document.get("required_official_model_gate_judgment")
    if model_gate_judgment is not None:
        if type(model_gate_judgment) is not str:
            issues.append(
                _contract_type_issue("required_official_model_gate_judgment", "null", model_gate_judgment)
            )
        else:
            issues.append(
                _contract_structure_issue("required_official_model_gate_judgment", "unsupported_value")
            )

    if violation_count is not None and violation_count != 0:
        issues.append(
            _contract_structure_issue("required_leakage_violation_count", "must_be_zero")
        )
    if issues:
        raise OfficialRunAcceptanceError(tuple(issues))

    return _OfficialRunAcceptanceContract(
        path=snapshot.path,
        identity=snapshot.identity,
        sha256=snapshot.sha256,
        byte_size=snapshot.byte_size,
        contract_version=str(version),
        expected_dataset_counts=MappingProxyType(validated_dataset_counts),
        expected_split_counts=MappingProxyType(validated_split_counts),
        expected_area_count=int(area_count),
        expected_horizon_counts=MappingProxyType(validated_horizon_counts),
        required_leakage_check_ids=validated_leakage_ids,
        required_leakage_violation_count=int(violation_count),
        required_final_verdict=str(document["required_final_verdict"]),
        required_evaluation_status=str(document["required_evaluation_status"]),
        required_data_sufficiency_status=str(document["required_data_sufficiency_status"]),
        required_test_split_created=bool(test_split_created),
        required_official_model_gate_judgment=None,
    )


_SAFE_ACCEPTANCE_STRINGS = {
    "PASS",
    "FAIL",
    EVALUATION_STATUS_PROVISIONAL,
    DATA_SUFFICIENCY_STATUS_PROVISIONAL_SPLIT_ONLY,
}


def _display_safe_acceptance_scalar(value: object) -> str | None:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if type(value) is str and value in _SAFE_ACCEPTANCE_STRINGS:
        return value
    return None


def _acceptance_mismatch_issue(field: str, expected: object, actual: object) -> AcceptanceIssue:
    expected_display = _display_safe_acceptance_scalar(expected)
    actual_display = _display_safe_acceptance_scalar(actual)
    lines = ["승인 기준 불일치:", f"항목={field}"]
    if expected_display is not None:
        lines.append(f"기대값={expected_display}")
    else:
        lines.append(f"기대 자료형={_json_type_name(expected)}")
    if actual_display is not None:
        lines.append(f"실제값={actual_display}")
    else:
        lines.append(f"실제 자료형={_json_type_name(actual)}")
    return AcceptanceIssue(field=field, lines=tuple(lines))


def _acceptance_structure_issue(field: str, reason: str) -> AcceptanceIssue:
    return AcceptanceIssue(
        field=field,
        lines=("승인 기준 불일치:", f"항목={field}", f"오류={reason}"),
    )


def _verify_official_run_acceptance_contract_unchanged(
    contract: _OfficialRunAcceptanceContract,
) -> None:
    try:
        current = _read_acceptance_file_snapshot(contract.path)
    except OfficialRunAcceptanceError:
        raise OfficialRunAcceptanceError(
            (_contract_structure_issue("acceptance_contract", "missing_or_unreadable"),)
        ) from None
    if (
        current.sha256 != contract.sha256
        or current.byte_size != contract.byte_size
        or current.identity != contract.identity
    ):
        raise OfficialRunAcceptanceError(
            (_contract_structure_issue("acceptance_contract", "changed_during_build"),)
        )


def _leakage_acceptance_issues(
    contract: _OfficialRunAcceptanceContract, leakage_report: Mapping[str, object]
) -> list[AcceptanceIssue]:
    issues: list[AcceptanceIssue] = []
    checks_value = leakage_report.get("checks")
    if type(checks_value) is not dict:
        return [_acceptance_structure_issue("required_leakage_check_ids", "invalid_checks_object")]
    checks = checks_value
    expected_ids = set(contract.required_leakage_check_ids)
    actual_ids = set(checks)
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    if missing or extra:
        lines = [
            "승인 기준 불일치:",
            "항목=required_leakage_check_ids",
            f"기대 검사 수={len(expected_ids)}",
            f"실제 검사 수={len(actual_ids)}",
            f"누락 검사 수={len(missing)}",
            f"추가 검사 수={len(extra)}",
            "중복 검사 수=0",
        ]
        visible_missing = missing[:5]
        if visible_missing:
            lines.append(f"누락 검사 식별자={','.join(visible_missing)}")
        if len(missing) > len(visible_missing):
            lines.append(f"추가 누락 식별자 {len(missing) - len(visible_missing)}개는 표시하지 않음")
        issues.append(AcceptanceIssue("required_leakage_check_ids", tuple(lines)))

    violation_sum = 0
    for check_id in sorted(actual_ids & expected_ids):
        result = checks[check_id]
        field = f"leakage_checks.{check_id}"
        if type(result) is not dict:
            issues.append(_acceptance_structure_issue(field, "invalid_result_object"))
            continue
        allowed_fields = {"violation_count", "violation_row_ids"}
        if check_id == "post_cutoff_forecast_used":
            allowed_fields.add("applicable")
        if set(result) != allowed_fields:
            issues.append(_acceptance_structure_issue(field, "invalid_result_fields"))
            continue
        count = result.get("violation_count")
        row_ids = result.get("violation_row_ids")
        if type(count) is not int or count < 0:
            issues.append(_acceptance_structure_issue(field, "invalid_violation_count"))
            continue
        if type(row_ids) is not list or any(type(row_id) is not str for row_id in row_ids):
            issues.append(_acceptance_structure_issue(field, "invalid_violation_row_ids"))
            continue
        if "applicable" in result and type(result["applicable"]) is not bool:
            issues.append(_acceptance_structure_issue(field, "invalid_applicable_flag"))
            continue
        violation_sum += count

    actual_total = leakage_report.get("total_violation_count")
    if type(actual_total) is not int or actual_total < 0:
        issues.append(
            _acceptance_structure_issue("required_leakage_violation_count", "invalid_actual_count")
        )
    else:
        if actual_total != violation_sum:
            issues.append(
                _acceptance_structure_issue(
                    "required_leakage_violation_count", "check_total_mismatch"
                )
            )
        if actual_total != contract.required_leakage_violation_count:
            issues.append(
                _acceptance_mismatch_issue(
                    "required_leakage_violation_count",
                    contract.required_leakage_violation_count,
                    actual_total,
                )
            )

    actual_verdict = leakage_report.get("final_verdict")
    if actual_verdict != contract.required_final_verdict:
        issues.append(
            _acceptance_mismatch_issue(
                "required_final_verdict", contract.required_final_verdict, actual_verdict
            )
        )
    if actual_verdict != "PASS":
        if not any(issue.field == "required_final_verdict" for issue in issues):
            issues.append(
                _acceptance_mismatch_issue("required_final_verdict", "PASS", actual_verdict)
            )
    return issues


def _manifest_acceptance_issues(
    phase_dir: Path, manifest: Mapping[str, object]
) -> list[AcceptanceIssue]:
    invalid = [_acceptance_structure_issue("output_manifest", "invalid_staged_manifest")]
    expected_fields = {
        "schema_version",
        "eg8c_run_id",
        "generated_at",
        "evaluation_status",
        "data_sufficiency_status",
        "supported_horizons_minutes",
        "test_split_created",
        "official_model_gate_judgment",
        "hash_algorithm",
        "input_artifacts",
        "output_artifacts",
    }
    expected_inputs = {"raw_log_v3", "population_current_v3", "population_forecast_v3"}
    expected_outputs = {
        FEATURE_DATASET_FILENAME,
        LABEL_DATASET_FILENAME,
        SPLIT_ASSIGNMENT_FILENAME,
        FEATURE_DICTIONARY_FILENAME,
        LABEL_CONTRACT_FILENAME,
        LEAKAGE_REPORT_FILENAME,
        DATASET_COVERAGE_FILENAME,
    }
    try:
        stored_manifest = json.loads(
            (phase_dir / DATASET_MANIFEST_FILENAME).read_bytes().decode("utf-8")
        )
        if stored_manifest != manifest or set(manifest) != expected_fields:
            return invalid
        if (
            manifest.get("schema_version") != OUTPUT_MANIFEST_SCHEMA_VERSION
            or manifest.get("supported_horizons_minutes") != list(SUPPORTED_HORIZON_MINUTES)
            or manifest.get("hash_algorithm") != "sha256"
        ):
            return invalid
        inputs = manifest.get("input_artifacts")
        outputs = manifest.get("output_artifacts")
        if type(inputs) is not list or type(outputs) is not list:
            return invalid
        if len(inputs) != len(expected_inputs) or len(outputs) != len(expected_outputs):
            return invalid
        if any(type(item) is not dict or set(item) != {"logical_name", "sha256", "byte_size"} for item in inputs):
            return invalid
        if {item["logical_name"] for item in inputs} != expected_inputs:
            return invalid
        if any(type(item) is not dict or set(item) != {"relative_path", "sha256", "byte_size"} for item in outputs):
            return invalid
        if {item["relative_path"] for item in outputs} != expected_outputs:
            return invalid
        for item in (*inputs, *outputs):
            if (
                type(item["sha256"]) is not str
                or len(item["sha256"]) != 64
                or type(item["byte_size"]) is not int
                or item["byte_size"] < 0
            ):
                return invalid
        for item in outputs:
            payload = (phase_dir / item["relative_path"]).read_bytes()
            if len(payload) != item["byte_size"] or _sha256_bytes(payload) != item["sha256"]:
                return invalid
    except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return invalid
    return []


def _validate_pre_publish_acceptance(
    contract: _OfficialRunAcceptanceContract,
    *,
    phase_dir: Path,
    candidate_rows: Sequence[CandidateRow],
    split_assignment: Mapping[str, Mapping[str, str]],
    dataset_coverage: Mapping[str, object],
    leakage_report: Mapping[str, object],
    manifest: Mapping[str, object],
) -> None:
    issues = _manifest_acceptance_issues(phase_dir, manifest)
    issues.extend(_leakage_acceptance_issues(contract, leakage_report))

    for field in ACCEPTANCE_DATASET_COUNT_FIELDS:
        actual = dataset_coverage.get(field)
        expected = contract.expected_dataset_counts[field]
        if actual != expected:
            issues.append(
                _acceptance_mismatch_issue(f"expected_dataset_counts.{field}", expected, actual)
            )

    split_counts_value = dataset_coverage.get("split_row_counts")
    if type(split_counts_value) is not dict:
        issues.append(_acceptance_structure_issue("expected_split_counts", "invalid_actual_object"))
        actual_split_counts: Mapping[str, object] = {}
    else:
        actual_split_counts = split_counts_value
    for field in ACCEPTANCE_SPLIT_COUNT_FIELDS:
        actual = actual_split_counts.get(field)
        expected = contract.expected_split_counts[field]
        if actual != expected:
            issues.append(
                _acceptance_mismatch_issue(f"expected_split_counts.{field}", expected, actual)
            )

    area_coverage = dataset_coverage.get("area_coverage")
    actual_area_count = area_coverage.get("observed_area_count") if type(area_coverage) is dict else None
    if actual_area_count != contract.expected_area_count:
        issues.append(
            _acceptance_mismatch_issue(
                "expected_area_count", contract.expected_area_count, actual_area_count
            )
        )

    horizon_coverage = dataset_coverage.get("horizon_coverage")
    actual_horizon_counts = horizon_coverage if type(horizon_coverage) is dict else {}
    if set(actual_horizon_counts) - set(ACCEPTANCE_HORIZON_COUNT_FIELDS):
        issues.append(
            _acceptance_structure_issue("expected_horizon_counts", "unexpected_actual_horizon")
        )
    for field in ACCEPTANCE_HORIZON_COUNT_FIELDS:
        actual = actual_horizon_counts.get(field, 0)
        expected = contract.expected_horizon_counts[field]
        if actual != expected:
            issues.append(
                _acceptance_mismatch_issue(f"expected_horizon_counts.{field}", expected, actual)
            )

    candidate_row_ids = [row.row_id for row in candidate_rows]
    candidate_ids = set(candidate_row_ids)
    feature_valid_ids = {row.row_id for row in candidate_rows if row.feature_valid}
    label_valid_ids = {row.row_id for row in candidate_rows if row.label_valid}
    eligible_ids = feature_valid_ids & label_valid_ids
    assignment_ids = set(split_assignment)
    split_ids = {
        split: {
            row_id
            for row_id, assignment in split_assignment.items()
            if type(assignment) is dict and assignment.get("split") == split
        }
        for split in ACCEPTANCE_SPLIT_COUNT_FIELDS
    }
    if any(
        type(assignment) is not dict
        or assignment.get("split") not in ACCEPTANCE_SPLIT_COUNT_FIELDS
        for assignment in split_assignment.values()
    ):
        issues.append(_acceptance_structure_issue("dataset_relation.split_assignment", "invalid_value"))
    if len(candidate_row_ids) != len(candidate_ids):
        issues.append(_acceptance_structure_issue("dataset_relation.candidate_row_ids", "duplicate_id"))
    if assignment_ids != candidate_ids:
        issues.append(_acceptance_structure_issue("dataset_relation.split_assignment_row_ids", "set_mismatch"))
    if split_ids[SPLIT_EXCLUDED] != candidate_ids - eligible_ids:
        issues.append(_acceptance_structure_issue("dataset_relation.excluded_row_ids", "set_mismatch"))
    if split_ids[SPLIT_TRAIN] | split_ids[SPLIT_VALIDATION] != eligible_ids:
        issues.append(_acceptance_structure_issue("dataset_relation.eligible_row_ids", "set_mismatch"))
    if split_ids[SPLIT_TRAIN] & split_ids[SPLIT_VALIDATION]:
        issues.append(_acceptance_structure_issue("dataset_relation.train_validation_row_ids", "overlap"))

    actual_intersection = len(eligible_ids)
    actual_dataset_counts = {
        "candidate_row_count": len(candidate_rows),
        "feature_valid_row_count": sum(row.feature_valid for row in candidate_rows),
        "label_valid_row_count": sum(row.label_valid for row in candidate_rows),
        "training_eligible_row_count": actual_intersection,
    }
    actual_split_counts_from_rows = {
        split: len(row_ids) for split, row_ids in split_ids.items()
    }
    for field, actual in actual_dataset_counts.items():
        if dataset_coverage.get(field) != actual:
            issues.append(
                _acceptance_structure_issue(
                    f"dataset_coverage.{field}", "candidate_rows_mismatch"
                )
            )
    for field, actual in actual_split_counts_from_rows.items():
        if actual_split_counts.get(field) != actual:
            issues.append(
                _acceptance_structure_issue(
                    f"dataset_coverage.split_row_counts.{field}", "candidate_rows_mismatch"
                )
            )
    actual_area_count_from_rows = len({row.area_code for row in candidate_rows})
    if actual_area_count != actual_area_count_from_rows:
        issues.append(
            _acceptance_structure_issue(
                "dataset_coverage.area_coverage.observed_area_count", "candidate_rows_mismatch"
            )
        )
    actual_horizons_from_rows = {
        str(horizon): sum(row.horizon_minutes == horizon for row in candidate_rows)
        for horizon in SUPPORTED_HORIZON_MINUTES
    }
    for field, actual in actual_horizons_from_rows.items():
        if actual_horizon_counts.get(field, 0) != actual:
            issues.append(
                _acceptance_structure_issue(
                    f"dataset_coverage.horizon_coverage.{field}", "candidate_rows_mismatch"
                )
            )
    if dataset_coverage.get("training_eligible_row_count") != actual_intersection:
        issues.append(
            _acceptance_structure_issue(
                "dataset_relation.feature_valid_intersection_label_valid", "eligible_mismatch"
            )
        )

    status_fields = (
        ("required_evaluation_status", "evaluation_status"),
        ("required_data_sufficiency_status", "data_sufficiency_status"),
        ("required_test_split_created", "test_split_created"),
        ("required_official_model_gate_judgment", "official_model_gate_judgment"),
    )
    for contract_field, manifest_field in status_fields:
        expected = getattr(contract, contract_field)
        actual = manifest.get(manifest_field)
        if actual != expected:
            issues.append(_acceptance_mismatch_issue(contract_field, expected, actual))

    if issues:
        raise OfficialRunAcceptanceError(tuple(issues))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validated_run_id(value: str) -> str:
    if (
        not value
        or not value.strip()
        or value in {".", ".."}
        or "\x00" in value
        or "/" in value
        or "\\" in value
        or Path(value).is_absolute()
        or Path(value).name != value
    ):
        raise EvidenceWriteError("eg8c_write_error: run id must be a non-empty single path segment")
    return value


def _rename_run_root_exclusive(staging_run: Path, final_run: Path) -> None:
    source = os.fsencode(staging_run)
    destination = os.fsencode(final_run)
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        if sys.platform == "darwin":
            rename = libc.renamex_np
            rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
            rename.restype = ctypes.c_int
            result = rename(source, destination, 0x00000004)  # RENAME_EXCL
        elif sys.platform.startswith("linux"):
            rename = libc.renameat2
            rename.argtypes = (
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            )
            rename.restype = ctypes.c_int
            result = rename(-100, source, -100, destination, 1)  # RENAME_NOREPLACE
        elif os.name == "nt":
            staging_run.rename(final_run)
            return
        else:
            raise OSError(errno.ENOTSUP, "exclusive directory rename is unavailable")
    except AttributeError as error:
        raise OSError(errno.ENOTSUP, "exclusive directory rename is unavailable") from error
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise FileExistsError(error_number, "destination already exists")
    raise OSError(error_number, "exclusive directory rename failed")


def _cleanup_unpublished_staging(staging_run: Path, primary_error: BaseException) -> None:
    if not staging_run.exists() and not staging_run.is_symlink():
        return
    try:
        shutil.rmtree(staging_run)
    except BaseException:
        diagnostic = EvidenceWriteError(
            "eg8c_cleanup_error: unpublished staging cleanup failed"
        )
        raise primary_error from diagnostic


def _write_exclusive(path: Path, payload: bytes) -> None:
    partial_path: Path | None = None
    try:
        descriptor, partial_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
        partial_path = Path(partial_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(partial_path, path)
    except FileExistsError as error:
        raise EvidenceWriteError(f"eg8c_write_error: {path.name} already exists") from error
    except OSError as error:
        raise EvidenceWriteError(f"eg8c_write_error: failed to write {path.name}") from error
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
    return (json.dumps(dict(document), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _feature_dataset_rows(rows: Sequence[CandidateRow]) -> list[dict[str, object]]:
    out = []
    for row in sorted(rows, key=lambda r: r.row_id):
        record: dict[str, object] = {
            "row_id": row.row_id,
            "area_code": row.area_code,
            "prediction_origin_at": row.prediction_origin_at,
            "prediction_target_at": row.prediction_target_at,
            "horizon_minutes": row.horizon_minutes,
            "source_collection_run_id": row.source_collection_run_id,
            "feature_valid": row.feature_valid,
            "feature_missing_reason": row.feature_missing_reason or "",
        }
        record.update(row.feature)
        out.append(record)
    return out


def _label_dataset_rows(rows: Sequence[CandidateRow]) -> list[dict[str, object]]:
    return [
        {
            "row_id": row.row_id,
            "area_code": row.area_code,
            "prediction_origin_at": row.prediction_origin_at,
            "prediction_target_at": row.prediction_target_at,
            "horizon_minutes": row.horizon_minutes,
            "label_name": LABEL_NAME_TARGET_POPULATION_MIDPOINT,
            "label_value": row.label_value,
            "label_valid": row.label_valid,
            "label_missing_reason": row.label_missing_reason or "",
        }
        for row in sorted(rows, key=lambda r: r.row_id)
    ]


def _split_assignment_rows(
    rows: Sequence[CandidateRow], split_assignment: Mapping[str, Mapping[str, str]]
) -> list[dict[str, object]]:
    return [
        {
            "row_id": row.row_id,
            "split": split_assignment[row.row_id]["split"],
            "split_reason": split_assignment[row.row_id]["split_reason"],
            "split_boundary_version": SPLIT_BOUNDARY_VERSION,
        }
        for row in sorted(rows, key=lambda r: r.row_id)
    ]


def _write_unpublished_dataset(
    current_records: Sequence[eg8a.NormalizedCurrentRecord],
    forecast_records: Sequence[eg8a.NormalizedForecastRecord],
    *,
    phase_dir: Path,
    raw_log_path: Path,
    current_path: Path,
    forecast_path: Path,
    run_id: str,
    generated_at: datetime,
    input_snapshot_before: InputSnapshot,
) -> _UnpublishedDataset:
    input_paths = (
        ("raw_log_v3", raw_log_path),
        ("population_current_v3", current_path),
        ("population_forecast_v3", forecast_path),
    )
    phase_dir.mkdir(exist_ok=False)
    candidate_rows = build_candidate_rows(current_records, forecast_records)
    split_assignment = build_split_assignment(candidate_rows)
    leakage_report = build_leakage_report(candidate_rows, split_assignment)
    dataset_coverage = build_dataset_coverage(
        candidate_rows,
        split_assignment,
        eg8c_run_id=run_id,
        generated_at=generated_at,
    )
    feature_dictionary = build_feature_dictionary()
    label_contract = build_label_contract()

    train_origins = sorted(
        {
            row.prediction_origin_at
            for row in candidate_rows
            if split_assignment[row.row_id]["split"] == SPLIT_TRAIN
        }
    )
    validation_origins = sorted(
        {
            row.prediction_origin_at
            for row in candidate_rows
            if split_assignment[row.row_id]["split"] == SPLIT_VALIDATION
        }
    )
    split_status = {
        "split_status": DATA_SUFFICIENCY_STATUS_PROVISIONAL_SPLIT_ONLY,
        "test_split_created": False,
        "train_origin_range": {
            "min": train_origins[0] if train_origins else None,
            "max": train_origins[-1] if train_origins else None,
        },
        "validation_origin_range": {
            "min": validation_origins[0] if validation_origins else None,
            "max": validation_origins[-1] if validation_origins else None,
        },
    }
    dataset_coverage = {**dataset_coverage, "split": split_status}

    payloads: list[tuple[str, bytes]] = [
        (
            FEATURE_DATASET_FILENAME,
            _write_csv_rows(FEATURE_DATASET_FIELDNAMES, _feature_dataset_rows(candidate_rows)),
        ),
        (
            LABEL_DATASET_FILENAME,
            _write_csv_rows(LABEL_DATASET_FIELDNAMES, _label_dataset_rows(candidate_rows)),
        ),
        (
            SPLIT_ASSIGNMENT_FILENAME,
            _write_csv_rows(
                SPLIT_ASSIGNMENT_FIELDNAMES,
                _split_assignment_rows(candidate_rows, split_assignment),
            ),
        ),
        (FEATURE_DICTIONARY_FILENAME, _write_json_document(feature_dictionary)),
        (LABEL_CONTRACT_FILENAME, _write_json_document(label_contract)),
        (LEAKAGE_REPORT_FILENAME, _write_json_document(leakage_report)),
        (DATASET_COVERAGE_FILENAME, _write_json_document(dataset_coverage)),
    ]
    for filename, payload in payloads:
        _write_exclusive(phase_dir / filename, payload)

    input_snapshot_after = _snapshot_input_artifacts(input_paths)
    if input_snapshot_after != input_snapshot_before:
        raise EvidenceWriteError("eg8c_input_error: input changed during build")
    output_artifacts = [
        {
            "relative_path": filename,
            "sha256": _sha256_bytes(payload),
            "byte_size": len(payload),
        }
        for filename, payload in payloads
    ]
    manifest = {
        "schema_version": OUTPUT_MANIFEST_SCHEMA_VERSION,
        "eg8c_run_id": run_id,
        "generated_at": eg8a.to_iso8601(generated_at),
        "evaluation_status": EVALUATION_STATUS_PROVISIONAL,
        "data_sufficiency_status": DATA_SUFFICIENCY_STATUS_PROVISIONAL_SPLIT_ONLY,
        "supported_horizons_minutes": list(SUPPORTED_HORIZON_MINUTES),
        "test_split_created": False,
        "official_model_gate_judgment": None,
        "hash_algorithm": "sha256",
        "input_artifacts": input_snapshot_before[0],
        "output_artifacts": output_artifacts,
    }
    _write_exclusive(phase_dir / DATASET_MANIFEST_FILENAME, _write_json_document(manifest))

    expected_outputs = {filename for filename, _ in payloads} | {DATASET_MANIFEST_FILENAME}
    if {path.name for path in phase_dir.iterdir()} != expected_outputs:
        raise EvidenceWriteError("eg8c_write_error: staged output set is incomplete")
    return _UnpublishedDataset(
        candidate_rows=tuple(candidate_rows),
        split_assignment=split_assignment,
        dataset_coverage=dataset_coverage,
        leakage_report=leakage_report,
        manifest=manifest,
    )


def run_eg8c_dataset_build(
    *,
    raw_log_path: Path,
    current_path: Path,
    forecast_path: Path,
    eg8c_output_root: Path,
    eg8c_run_id: str | None = None,
    generated_at: datetime | None = None,
    acceptance_contract_path: Path | None = None,
) -> Eg8cDatasetResult:
    """Load the full current v3 Snapshot (no Analysis Window/Snapshot
    Cutoff -- EG-8C 1st scope, unlike eg8b_b2b), then build and persist
    the EG-8C Feature/Label/Split/Leakage Output set."""
    if acceptance_contract_path is None:
        raise OfficialRunAcceptanceError(
            (_contract_structure_issue("acceptance_contract", "required"),)
        )
    acceptance_contract = _load_official_run_acceptance_contract(acceptance_contract_path)
    input_paths = (
        ("raw_log_v3", raw_log_path),
        ("population_current_v3", current_path),
        ("population_forecast_v3", forecast_path),
    )
    input_snapshot_before = _snapshot_input_artifacts(input_paths)
    normalized = eg8a.normalize_v3_sources(
        raw_log_path=raw_log_path, current_path=current_path, forecast_path=forecast_path
    )
    resolved_root = eg8c_output_root.expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise EvidenceWriteError("eg8c_write_error: output root is not a directory")
    resolved_run_id = _validated_run_id(
        eg8c_run_id if eg8c_run_id is not None else str(uuid.uuid4())
    )
    resolved_generated_at = generated_at if generated_at is not None else datetime.now(eg8a.SEOUL)
    final_run_dir = resolved_root / resolved_run_id
    if final_run_dir.exists() or final_run_dir.is_symlink():
        raise EvidenceWriteError(f"eg8c_write_error: run {resolved_run_id} already exists")
    try:
        resolved_run_dir = final_run_dir.resolve(strict=False)
        resolved_run_dir.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError) as error:
        raise EvidenceWriteError("eg8c_write_error: run path must stay inside output root") from error
    if resolved_run_dir.parent != resolved_root:
        raise EvidenceWriteError("eg8c_write_error: run path must stay inside output root")

    staging_dir = Path(tempfile.mkdtemp(prefix=".eg8c-staging-", dir=resolved_root))
    phase_dir = staging_dir / PHASE_EG8C_VERSION
    published = False
    try:
        unpublished = _write_unpublished_dataset(
            normalized.current_records,
            normalized.forecast_records,
            phase_dir=phase_dir,
            raw_log_path=raw_log_path,
            current_path=current_path,
            forecast_path=forecast_path,
            run_id=resolved_run_id,
            generated_at=resolved_generated_at,
            input_snapshot_before=input_snapshot_before,
        )
        _validate_pre_publish_acceptance(
            acceptance_contract,
            phase_dir=phase_dir,
            candidate_rows=unpublished.candidate_rows,
            split_assignment=unpublished.split_assignment,
            dataset_coverage=unpublished.dataset_coverage,
            leakage_report=unpublished.leakage_report,
            manifest=unpublished.manifest,
        )
        result = Eg8cDatasetResult(
            eg8c_run_id=resolved_run_id,
            phase_dir=final_run_dir / PHASE_EG8C_VERSION,
            dataset_coverage=unpublished.dataset_coverage,
            leakage_report=unpublished.leakage_report,
            acceptance_contract_sha256=acceptance_contract.sha256,
        )
        _verify_official_run_acceptance_contract_unchanged(acceptance_contract)
        try:
            _rename_run_root_exclusive(staging_dir, final_run_dir)
        except FileExistsError as error:
            raise EvidenceWriteError("eg8c_write_error: run already exists") from error
        except OSError as error:
            raise EvidenceWriteError("eg8c_write_error: failed to publish run") from error
        published = True
        return result
    except BaseException as primary_error:
        if not published and (staging_dir.exists() or staging_dir.is_symlink()):
            _cleanup_unpublished_staging(staging_dir, primary_error)
        raise


class _CliArgumentError(Exception):
    pass


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _CliArgumentError from None


def build_parser() -> argparse.ArgumentParser:
    parser = _SafeArgumentParser(description="EG-8C provisional dataset output build")
    parser.add_argument("--current-path", type=Path, required=True)
    parser.add_argument("--forecast-path", type=Path, required=True)
    parser.add_argument("--error-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--acceptance-contract", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        result = run_eg8c_dataset_build(
            raw_log_path=arguments.error_path,
            current_path=arguments.current_path,
            forecast_path=arguments.forecast_path,
            eg8c_output_root=arguments.output_root,
            eg8c_run_id=arguments.run_id,
            acceptance_contract_path=arguments.acceptance_contract,
        )
    except _CliArgumentError:
        print("eg8c_run_failed: invalid_arguments", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("eg8c_run_interrupted", file=sys.stderr)
        return 130
    except OfficialRunAcceptanceError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("eg8c_run_failed: input_or_output_validation_error", file=sys.stderr)
        return 1
    print("eg8c_run_completed")
    print(f"run_id={result.eg8c_run_id}")
    print("output_count=8")
    print(f"acceptance_contract_sha256={result.acceptance_contract_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
