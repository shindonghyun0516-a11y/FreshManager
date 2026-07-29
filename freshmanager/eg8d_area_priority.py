"""EG-8D provisional Area expected-population-change ranking from Seoul Forecast."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping, Sequence

from . import eg6b, eg8a, eg8c_features


LOCKED_DATASET_RUN_ID = "eg8c-20260727T153257-kst"
LOCKED_MANIFEST_SHA256 = "388a5e6649e6e23d05a442ae9b4f8d0857f8ea382011c2ff07c0af64aae42771"
LOCKED_CURRENT_SHA256 = "28521ff8b52ff1697fcf8eb93da4a5faaf2f625a69fdf117e601f8893d84d719"
LOCKED_FORECAST_SHA256 = "a5c4aaa7d711d289ee05d4ed6903b91f4ea725252ff3b6bc8890b62146441649"

HORIZONS = (60, 180)
FORECAST_SOURCE = "SEOUL_FORECAST"
EVALUATION_STATUS = "PROVISIONAL"
TARGET_LEVEL = "AREA"
SELECTION_POLICY = "LATEST_COMPLETE_LOCKED_SNAPSHOT"
CANONICAL_TIMESTAMP_FIELD = "observed_at"
EVALUATION_MODES = {"RUNTIME", "HISTORICAL_AUDIT", "SYNTHETIC_VALIDATION"}
RUNTIME_CONTEXT = "OPERATIONAL_RUNTIME"
HISTORICAL_CONTEXT = "HISTORICAL_AUDIT"
SYNTHETIC_CONTEXT = "SYNTHETIC_CURRENT_ONLY_VALIDATION"
SYSTEM_CLOCK = "SYSTEM_CLOCK_ASIA_SEOUL"
INJECTED_CLOCK = "INJECTED_TEST_CLOCK"
CURRENT_ONLY_CONTRACT = "CURRENT_AREA_STATE_ONLY_V1"
OUTPUT_FILES = {
    "area_priority.csv",
    "area_priority.json",
    "run_metadata.json",
    "area_priority_manifest.json",
}
CONTENT_FILES = OUTPUT_FILES - {"area_priority_manifest.json"}
CURRENT_ONLY_OUTPUT_FILES = {
    "current_area_state.csv",
    "current_area_state.json",
    "run_metadata.json",
    "current_area_state_manifest.json",
}
_RUN_ID_PATTERN = re.compile(r"eg8d-area-priority-\d{8}T\d{6}-kst\Z")

CURRENT_REQUIRED_COLUMNS = {
    "collection_run_id",
    "observed_at",
    "area_code_requested",
    "area_code_returned",
    "area_name",
    "congestion_level",
    "population_min",
    "population_max",
}
FORECAST_REQUIRED_COLUMNS = {
    "collection_run_id",
    "observed_at",
    "forecast_at",
    "area_code_requested",
    "area_code_returned",
    "area_name",
    "forecast_population_min",
    "forecast_population_max",
}
CSV_FIELDS = (
    "generated_at",
    "source_collection_run_id",
    "area_code",
    "area_name",
    "prediction_origin_at",
    "prediction_target_at",
    "horizon_minutes",
    "current_population_midpoint",
    "forecast_population_midpoint",
    "expected_population_change",
    "expected_population_change_rate",
    "opportunity_rank",
    "future_population_rank",
    "rank_difference",
    "change_status",
    "reason_code",
    "input_validity",
    "forecast_source",
    "evaluation_status",
    "target_level",
)
CURRENT_ONLY_CSV_FIELDS = (
    "result_contract",
    "record_role",
    "validation_context",
    "operational_observation",
    "area_code",
    "area_name",
    "current_population_min",
    "current_population_max",
    "current_population_midpoint",
    "current_congestion_level",
    "current_observed_at",
    "evaluation_time",
    "current_age_minutes",
    "freshness_status",
    "current_only_fallback_allowed",
    "area_current_state_display_allowed",
    "area_result_display_allowed",
    "spot_evaluation_allowed",
    "official_recommendation_allowed",
    "reason_codes",
    "warning_message",
    "mode",
)


class AreaPriorityContractError(ValueError):
    """Raised when locked inputs or the exact Forecast join contract fail."""


class AreaPriorityWriteError(OSError):
    """Raised when an isolated result run cannot be published safely."""


@dataclass(frozen=True)
class AreaPriorityRow:
    generated_at: str
    source_collection_run_id: str
    area_code: str
    area_name: str
    prediction_origin_at: str
    prediction_target_at: str
    horizon_minutes: int
    current_population_midpoint: float
    forecast_population_midpoint: float
    expected_population_change: float
    expected_population_change_rate: float | None
    opportunity_rank: int
    future_population_rank: int
    rank_difference: int
    change_status: str
    reason_code: str
    input_validity: str
    forecast_source: str = FORECAST_SOURCE
    evaluation_status: str = EVALUATION_STATUS
    target_level: str = TARGET_LEVEL

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CurrentOnlyRow:
    result_contract: str
    record_role: str
    validation_context: str
    operational_observation: bool
    area_code: str
    area_name: str
    current_population_min: float
    current_population_max: float
    current_population_midpoint: float
    current_congestion_level: str
    current_observed_at: str
    evaluation_time: str
    current_age_minutes: float
    freshness_status: str
    current_only_fallback_allowed: bool
    area_current_state_display_allowed: bool
    area_result_display_allowed: bool
    spot_evaluation_allowed: bool
    official_recommendation_allowed: bool
    reason_codes: tuple[str, ...]
    warning_message: str | None
    mode: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AreaPriorityResult:
    run_id: str
    run_dir: Path
    rows: tuple[AreaPriorityRow | CurrentOnlyRow, ...]
    metadata: Mapping[str, object]
    manifest: Mapping[str, object]


@dataclass(frozen=True)
class HorizonFreshnessResult:
    freshness_status: str
    evaluation_time: str | None
    selected_snapshot_observed_at: str | None
    forecast_target_at: str | None
    snapshot_age_minutes: float | None
    completeness_lag_minutes: float | None
    remaining_lead_minutes: float | None
    area_result_display_allowed: bool
    spot_evaluation_allowed: bool
    official_recommendation_allowed: bool
    current_only_fallback_allowed: bool
    reason_codes: tuple[str, ...]
    warning_message: str | None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class FreshnessGateResult:
    evaluation_mode: str
    evaluation_time: str | None
    latest_available_current_observed_at: str | None
    current_only_data_age_minutes: float | None
    user_display_eligible: bool
    horizons: Mapping[int, HorizonFreshnessResult]

    def as_dict(self) -> dict[str, object]:
        return {
            "evaluation_mode": self.evaluation_mode,
            "evaluation_time": self.evaluation_time,
            "latest_available_current_observed_at": (
                self.latest_available_current_observed_at
            ),
            "current_only_data_age_minutes": self.current_only_data_age_minutes,
            "user_display_eligible": self.user_display_eligible,
            "horizons": {
                str(horizon): result.as_dict()
                for horizon, result in sorted(self.horizons.items())
            },
        }


@dataclass(frozen=True)
class _InMemoryAreaPriorityEvaluation:
    rows: tuple[AreaPriorityRow, ...]
    freshness_gate: FreshnessGateResult
    population_ranges: Mapping[
        tuple[str, int], tuple[float, float, float, float]
    ]


@dataclass(frozen=True)
class _ExecutionContext:
    evaluation_time: datetime
    evaluation_mode: str
    validation_context: str
    operational_observation: bool
    synthetic_validation: bool
    clock_source: str
    operational_publication_allowed: bool


@dataclass(frozen=True)
class _Current:
    area_code: str
    area_name: str
    origin: datetime
    population_min: float
    population_max: float
    midpoint: float
    congestion_level: str


@dataclass(frozen=True)
class _Forecast:
    area_code: str
    area_name: str
    origin: datetime
    target: datetime
    population_min: float
    population_max: float
    midpoint: float


@dataclass(frozen=True)
class _SourceRunSelection:
    source_collection_run_id: str
    canonical_timestamp: datetime
    total_collection_run_count: int
    complete_collection_run_count: int
    selection_tie_count: int


def _fail(code: str) -> None:
    raise AreaPriorityContractError(f"eg8d_area_priority_contract_error: {code}")


def _required(row: Mapping[str, str], name: str) -> str:
    value = row.get(name, "").strip()
    if not value:
        _fail("required_value_missing")
    return value


def _population_range(
    row: Mapping[str, str], lower_name: str, upper_name: str
) -> tuple[float, float]:
    try:
        lower = float(_required(row, lower_name))
        upper = float(_required(row, upper_name))
    except ValueError:
        _fail("population_invalid")
    if not all(math.isfinite(value) for value in (lower, upper)) or lower < 0 or lower > upper:
        _fail("population_invalid")
    return lower, upper


def _midpoint(row: Mapping[str, str], lower_name: str, upper_name: str) -> float:
    lower, upper = _population_range(row, lower_name, upper_name)
    return (lower + upper) / 2


def _time(value: str) -> datetime:
    try:
        return eg8a.parse_kst_datetime(value)
    except ValueError:
        _fail("time_invalid")


def _change_state(change: float) -> tuple[str, str]:
    if change > 0:
        return "INCREASE", "EXPECTED_POPULATION_INCREASE"
    if change < 0:
        return "DECREASE", "EXPECTED_POPULATION_DECREASE"
    return "STABLE", "NO_EXPECTED_POPULATION_CHANGE"


def _is_kst_aware(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and getattr(value.tzinfo, "key", None) == "Asia/Seoul"
    )


def _kst_iso(value: object) -> str | None:
    return eg8a.to_iso8601(value) if _is_kst_aware(value) else None


def _runtime_now() -> datetime:
    return datetime.now(eg8a.SEOUL)


def _execution_provenance(
    *,
    execution_context: _ExecutionContext,
    source_dataset_manifest_sha256: str,
    forecast_absence_simulated: bool,
    user_display_eligible: bool,
    simulated_policy_outcome: str | None = None,
) -> dict[str, object]:
    provenance: dict[str, object] = {
        "validation_context": execution_context.validation_context,
        "synthetic_validation": execution_context.synthetic_validation,
        "operational_observation": execution_context.operational_observation,
        "forecast_absence_simulated": forecast_absence_simulated,
        "source_dataset_modified": False,
        "runtime_clock_source": execution_context.clock_source,
        "evaluation_time_source": execution_context.clock_source,
        "operational_publication_allowed": (
            execution_context.operational_publication_allowed
        ),
        "user_publication_allowed": (
            execution_context.operational_publication_allowed
            and user_display_eligible
        ),
        "use_for_operational_metrics": execution_context.operational_observation,
        "use_for_user_display": (
            execution_context.operational_publication_allowed
            and user_display_eligible
        ),
        "source_dataset_manifest_sha256": source_dataset_manifest_sha256,
        "evaluation_time": eg8a.to_iso8601(execution_context.evaluation_time),
    }
    if simulated_policy_outcome is not None:
        provenance["simulated_policy_outcome"] = simulated_policy_outcome
    return provenance


def _invalid_freshness_result(
    *,
    evaluation_time: object,
    selected_at: object,
    latest_current_at: object,
    target_60: object,
    target_180: object,
    evaluation_mode: str,
) -> FreshnessGateResult:
    horizons = {
        horizon: HorizonFreshnessResult(
            freshness_status="INVALID_TIME_CONTRACT",
            evaluation_time=_kst_iso(evaluation_time),
            selected_snapshot_observed_at=_kst_iso(selected_at),
            forecast_target_at=_kst_iso(target),
            snapshot_age_minutes=None,
            completeness_lag_minutes=None,
            remaining_lead_minutes=None,
            area_result_display_allowed=False,
            spot_evaluation_allowed=False,
            official_recommendation_allowed=False,
            current_only_fallback_allowed=False,
            reason_codes=("INVALID_TIME_CONTRACT",),
            warning_message="시간 계약이 유효하지 않아 결과를 표시할 수 없습니다.",
        )
        for horizon, target in ((60, target_60), (180, target_180))
    }
    return FreshnessGateResult(
        evaluation_mode=evaluation_mode,
        evaluation_time=_kst_iso(evaluation_time),
        latest_available_current_observed_at=_kst_iso(latest_current_at),
        current_only_data_age_minutes=None,
        user_display_eligible=False,
        horizons=horizons,
    )


def evaluate_horizon_freshness(
    *,
    evaluation_time: datetime,
    selected_complete_observed_at: datetime | None,
    latest_available_current_observed_at: datetime | None,
    forecast_target_at_60m: datetime | None,
    forecast_target_at_180m: datetime | None,
    complete_snapshot_exists: bool,
    time_contract_valid: bool,
    evaluation_mode: str = "RUNTIME",
) -> FreshnessGateResult:
    """Evaluate 60/180-minute display eligibility without selecting another run."""
    values = (
        evaluation_time,
        selected_complete_observed_at,
        latest_available_current_observed_at,
        forecast_target_at_60m,
        forecast_target_at_180m,
    )
    required = values if complete_snapshot_exists is True else (evaluation_time,)
    optional_current_valid = (
        latest_available_current_observed_at is None
        or _is_kst_aware(latest_available_current_observed_at)
    )
    if (
        not time_contract_valid
        or type(time_contract_valid) is not bool
        or type(complete_snapshot_exists) is not bool
        or evaluation_mode not in EVALUATION_MODES
        or not all(_is_kst_aware(value) for value in required)
        or not optional_current_valid
        or (
            complete_snapshot_exists is False
            and any(
                value is not None
                for value in (
                    selected_complete_observed_at,
                    forecast_target_at_60m,
                    forecast_target_at_180m,
                )
            )
        )
    ):
        return _invalid_freshness_result(
            evaluation_time=evaluation_time,
            selected_at=selected_complete_observed_at,
            latest_current_at=latest_available_current_observed_at,
            target_60=forecast_target_at_60m,
            target_180=forecast_target_at_180m,
            evaluation_mode=evaluation_mode,
        )

    if not complete_snapshot_exists:
        current_age = None
        if latest_available_current_observed_at is not None:
            current_age = (
                evaluation_time - latest_available_current_observed_at
            ).total_seconds() / 60
        if current_age is not None and current_age < 0:
            return _invalid_freshness_result(
                evaluation_time=evaluation_time,
                selected_at=None,
                latest_current_at=latest_available_current_observed_at,
                target_60=None,
                target_180=None,
                evaluation_mode=evaluation_mode,
            )
        fallback_allowed = (
            evaluation_mode in {"RUNTIME", "SYNTHETIC_VALIDATION"}
            and current_age is not None
            and current_age <= 15
        )
        reasons = ["NO_COMPLETE_SNAPSHOT"]
        if current_age is None:
            reasons.append("CURRENT_NOT_AVAILABLE")
        elif current_age > 15:
            reasons.append("CURRENT_AGE_EXCEEDS_FALLBACK_LIMIT")
        if evaluation_mode == "HISTORICAL_AUDIT":
            reasons.append("HISTORICAL_AUDIT_NOT_USER_ELIGIBLE")
        elif evaluation_mode == "SYNTHETIC_VALIDATION":
            reasons.append("SYNTHETIC_VALIDATION_NOT_USER_ELIGIBLE")
        horizons = {
            horizon: HorizonFreshnessResult(
                freshness_status="NO_COMPLETE_SNAPSHOT",
                evaluation_time=eg8a.to_iso8601(evaluation_time),
                selected_snapshot_observed_at=None,
                forecast_target_at=None,
                snapshot_age_minutes=None,
                completeness_lag_minutes=None,
                remaining_lead_minutes=None,
                area_result_display_allowed=False,
                spot_evaluation_allowed=False,
                official_recommendation_allowed=False,
                current_only_fallback_allowed=fallback_allowed,
                reason_codes=tuple(reasons),
                warning_message=(
                    "완전한 Forecast Snapshot이 없어 최신 Current 상태만 표시할 수 있습니다."
                    if fallback_allowed
                    else "완전한 Forecast Snapshot과 표시 가능한 최신 Current가 없습니다."
                ),
            )
            for horizon in HORIZONS
        }
        return FreshnessGateResult(
            evaluation_mode=evaluation_mode,
            evaluation_time=eg8a.to_iso8601(evaluation_time),
            latest_available_current_observed_at=_kst_iso(
                latest_available_current_observed_at
            ),
            current_only_data_age_minutes=current_age,
            user_display_eligible=evaluation_mode == "RUNTIME" and fallback_allowed,
            horizons=horizons,
        )

    selected = selected_complete_observed_at
    latest = latest_available_current_observed_at
    target_60 = forecast_target_at_60m
    target_180 = forecast_target_at_180m
    if not all(isinstance(value, datetime) for value in (selected, latest, target_60, target_180)):
        return _invalid_freshness_result(
            evaluation_time=evaluation_time,
            selected_at=selected,
            latest_current_at=latest,
            target_60=target_60,
            target_180=target_180,
            evaluation_mode=evaluation_mode,
        )
    snapshot_age = (evaluation_time - selected).total_seconds() / 60
    completeness_lag = (latest - selected).total_seconds() / 60
    if (
        snapshot_age < 0
        or completeness_lag < 0
        or latest > evaluation_time
        or target_60 - selected != timedelta(minutes=60)
        or target_180 - selected != timedelta(minutes=180)
    ):
        return _invalid_freshness_result(
            evaluation_time=evaluation_time,
            selected_at=selected,
            latest_current_at=latest,
            target_60=target_60,
            target_180=target_180,
            evaluation_mode=evaluation_mode,
        )

    horizons: dict[int, HorizonFreshnessResult] = {}
    thresholds = {
        60: (15, 15, 45, 30, 30, 30),
        180: (15, 15, 165, 60, 60, 120),
    }
    for horizon, target in ((60, target_60), (180, target_180)):
        remaining = (target - evaluation_time).total_seconds() / 60
        fresh_age, fresh_lag, fresh_remaining, degraded_age, degraded_lag, degraded_remaining = (
            thresholds[horizon]
        )
        is_fresh = (
            snapshot_age <= fresh_age
            and completeness_lag <= fresh_lag
            and remaining >= fresh_remaining
        )
        is_degraded = (
            not is_fresh
            and snapshot_age <= degraded_age
            and completeness_lag <= degraded_lag
            and remaining >= degraded_remaining
        )
        status = "FRESH" if is_fresh else "DEGRADED" if is_degraded else "STALE_BLOCKED"
        reasons = [
            "FRESH_THRESHOLDS_MET"
            if status == "FRESH"
            else "DEGRADED_THRESHOLDS_MET"
            if status == "DEGRADED"
            else "STALE_BLOCKED"
        ]
        if status != "FRESH":
            if snapshot_age > fresh_age:
                reasons.append("SNAPSHOT_AGE_EXCEEDS_FRESH_LIMIT")
            if completeness_lag > fresh_lag:
                reasons.append("COMPLETENESS_LAG_EXCEEDS_FRESH_LIMIT")
            if remaining < fresh_remaining:
                reasons.append("REMAINING_LEAD_BELOW_FRESH_MINIMUM")
        if status == "STALE_BLOCKED":
            if snapshot_age > degraded_age:
                reasons.append("SNAPSHOT_AGE_EXCEEDS_DEGRADED_LIMIT")
            if completeness_lag > degraded_lag:
                reasons.append("COMPLETENESS_LAG_EXCEEDS_DEGRADED_LIMIT")
            if remaining < degraded_remaining:
                reasons.append("REMAINING_LEAD_BELOW_DEGRADED_MINIMUM")
        if evaluation_mode == "HISTORICAL_AUDIT":
            reasons.append("HISTORICAL_AUDIT_NOT_USER_ELIGIBLE")
        elif evaluation_mode == "SYNTHETIC_VALIDATION":
            reasons.append("SYNTHETIC_VALIDATION_NOT_USER_ELIGIBLE")
        runtime_display = evaluation_mode == "RUNTIME"
        area_allowed = runtime_display and status in {"FRESH", "DEGRADED"}
        spot_allowed = runtime_display and status == "FRESH"
        warning = None
        if status == "DEGRADED":
            warning = (
                f"데이터 기준시각 {eg8a.to_iso8601(selected)}; "
                f"예측 대상시각 {eg8a.to_iso8601(target)}; "
                f"현재 기준 남은 시간 {remaining:g}분. "
                "최신 데이터가 아니며 Area 참고정보입니다."
            )
        elif status == "STALE_BLOCKED":
            warning = "데이터가 오래됐거나 잔여시간이 부족해 Area 결과를 표시할 수 없습니다."
        horizons[horizon] = HorizonFreshnessResult(
            freshness_status=status,
            evaluation_time=eg8a.to_iso8601(evaluation_time),
            selected_snapshot_observed_at=eg8a.to_iso8601(selected),
            forecast_target_at=eg8a.to_iso8601(target),
            snapshot_age_minutes=snapshot_age,
            completeness_lag_minutes=completeness_lag,
            remaining_lead_minutes=remaining,
            area_result_display_allowed=area_allowed,
            spot_evaluation_allowed=spot_allowed,
            official_recommendation_allowed=False,
            current_only_fallback_allowed=False,
            reason_codes=tuple(reasons),
            warning_message=warning,
        )
    return FreshnessGateResult(
        evaluation_mode=evaluation_mode,
        evaluation_time=eg8a.to_iso8601(evaluation_time),
        latest_available_current_observed_at=eg8a.to_iso8601(latest),
        current_only_data_age_minutes=None,
        user_display_eligible=(
            evaluation_mode == "RUNTIME"
            and any(result.area_result_display_allowed for result in horizons.values())
        ),
        horizons=horizons,
    )


def _validated_current_run(
    current_rows: Sequence[Mapping[str, str]],
    *,
    source_collection_run_id: str,
) -> tuple[dict[str, _Current], datetime]:
    if not source_collection_run_id:
        _fail("source_collection_run_id_missing")
    approved = set(eg6b.EG6B_AREA_CODES)
    current_by_area: dict[str, _Current] = {}
    for row in current_rows:
        if row.get("collection_run_id", "").strip() != source_collection_run_id:
            continue
        requested = _required(row, "area_code_requested")
        returned = _required(row, "area_code_returned")
        if requested not in approved:
            continue
        if requested != returned:
            _fail("current_area_mismatch")
        if requested in current_by_area:
            _fail("current_duplicate")
        population_min, population_max = _population_range(
            row, "population_min", "population_max"
        )
        current_by_area[requested] = _Current(
            area_code=requested,
            area_name=_required(row, "area_name"),
            origin=_time(_required(row, "observed_at")),
            population_min=population_min,
            population_max=population_max,
            midpoint=(population_min + population_max) / 2,
            congestion_level=_required(row, "congestion_level"),
        )
    if set(current_by_area) != approved:
        _fail("current_area_set_mismatch")
    canonical_timestamps = {current.origin for current in current_by_area.values()}
    if len(canonical_timestamps) != 1:
        _fail("canonical_timestamp_mismatch")
    canonical_timestamp = next(iter(canonical_timestamps))
    return current_by_area, canonical_timestamp


def _validated_source_run(
    current_rows: Sequence[Mapping[str, str]],
    forecast_rows: Sequence[Mapping[str, str]],
    *,
    source_collection_run_id: str,
) -> tuple[dict[str, _Current], dict[tuple[str, str, str, str], _Forecast], datetime]:
    current_by_area, canonical_timestamp = _validated_current_run(
        current_rows,
        source_collection_run_id=source_collection_run_id,
    )
    approved = set(eg6b.EG6B_AREA_CODES)

    forecast_index: dict[tuple[str, str, str, str], _Forecast] = {}
    for row in forecast_rows:
        run_id = row.get("collection_run_id", "").strip()
        if run_id != source_collection_run_id:
            continue
        requested = _required(row, "area_code_requested")
        returned = _required(row, "area_code_returned")
        if requested not in approved:
            continue
        if requested != returned:
            _fail("forecast_area_mismatch")
        origin = _time(_required(row, "observed_at"))
        if origin != canonical_timestamp:
            _fail("forecast_origin_mismatch")
        target = _time(_required(row, "forecast_at"))
        key = (
            run_id,
            requested,
            eg8a.to_iso8601(origin),
            eg8a.to_iso8601(target),
        )
        if key in forecast_index:
            _fail("forecast_duplicate")
        population_min, population_max = _population_range(
            row, "forecast_population_min", "forecast_population_max"
        )
        forecast_index[key] = _Forecast(
            area_code=requested,
            area_name=_required(row, "area_name"),
            origin=origin,
            target=target,
            population_min=population_min,
            population_max=population_max,
            midpoint=(population_min + population_max) / 2,
        )

    for area_code in eg6b.EG6B_AREA_CODES:
        current = current_by_area[area_code]
        for horizon in HORIZONS:
            target = current.origin + timedelta(minutes=horizon)
            key = (
                source_collection_run_id,
                area_code,
                eg8a.to_iso8601(current.origin),
                eg8a.to_iso8601(target),
            )
            forecast = forecast_index.get(key)
            if forecast is None:
                _fail("forecast_missing")
            if forecast.area_name != current.area_name:
                _fail("area_name_mismatch")
    return current_by_area, forecast_index, canonical_timestamp


def _find_latest_complete_run(
    current_rows: Sequence[Mapping[str, str]],
    forecast_rows: Sequence[Mapping[str, str]],
) -> _SourceRunSelection | None:
    current_by_run: dict[str, list[Mapping[str, str]]] = {}
    forecast_by_run: dict[str, list[Mapping[str, str]]] = {}
    for row in current_rows:
        run_id = row.get("collection_run_id", "").strip()
        if run_id:
            current_by_run.setdefault(run_id, []).append(row)
    for row in forecast_rows:
        run_id = row.get("collection_run_id", "").strip()
        if run_id:
            forecast_by_run.setdefault(run_id, []).append(row)

    run_ids = sorted(set(current_by_run) | set(forecast_by_run))
    complete: list[tuple[datetime, str]] = []
    for run_id in run_ids:
        try:
            _current, _forecast, timestamp = _validated_source_run(
                current_by_run.get(run_id, ()),
                forecast_by_run.get(run_id, ()),
                source_collection_run_id=run_id,
            )
        except AreaPriorityContractError:
            continue
        complete.append((timestamp, run_id))

    if not complete:
        return None
    latest_timestamp = max(timestamp for timestamp, _run_id in complete)
    latest = sorted(run_id for timestamp, run_id in complete if timestamp == latest_timestamp)
    if len(latest) != 1:
        _fail("latest_complete_run_tie")
    return _SourceRunSelection(
        source_collection_run_id=latest[0],
        canonical_timestamp=latest_timestamp,
        total_collection_run_count=len(run_ids),
        complete_collection_run_count=len(complete),
        selection_tie_count=len(latest),
    )


def _select_latest_complete_run(
    current_rows: Sequence[Mapping[str, str]],
    forecast_rows: Sequence[Mapping[str, str]],
) -> _SourceRunSelection:
    selection = _find_latest_complete_run(current_rows, forecast_rows)
    if selection is None:
        _fail("complete_run_not_found")
    return selection


def _select_latest_current_run(
    current_rows: Sequence[Mapping[str, str]],
) -> _SourceRunSelection:
    current_by_run: dict[str, list[Mapping[str, str]]] = {}
    for row in current_rows:
        run_id = row.get("collection_run_id", "").strip()
        if run_id:
            current_by_run.setdefault(run_id, []).append(row)
    if not current_by_run:
        _fail("current_run_not_found")

    approved = set(eg6b.EG6B_AREA_CODES)
    candidates: list[tuple[datetime, str]] = []
    for run_id, rows in current_by_run.items():
        observed = [
            _time(_required(row, "observed_at"))
            for row in rows
            if row.get("area_code_requested", "").strip() in approved
        ]
        if observed:
            candidates.append((max(observed), run_id))
    if not candidates:
        _fail("current_run_not_found")

    latest_timestamp = max(timestamp for timestamp, _run_id in candidates)
    latest = sorted(run_id for timestamp, run_id in candidates if timestamp == latest_timestamp)
    if len(latest) != 1:
        _fail("latest_current_run_tie")
    return _SourceRunSelection(
        source_collection_run_id=latest[0],
        canonical_timestamp=latest_timestamp,
        total_collection_run_count=len(current_by_run),
        complete_collection_run_count=0,
        selection_tie_count=len(latest),
    )


def _latest_current_observed_at(
    current_rows: Sequence[Mapping[str, str]],
) -> datetime:
    observed = [
        _time(_required(row, "observed_at"))
        for row in current_rows
        if row.get("area_code_requested", "").strip() in eg6b.EG6B_AREA_CODES
    ]
    if not observed:
        _fail("current_observed_at_missing")
    return max(observed)


def _build_area_priority_rows(
    current_rows: Sequence[Mapping[str, str]],
    forecast_rows: Sequence[Mapping[str, str]],
    *,
    source_collection_run_id: str,
    generated_at: datetime,
) -> tuple[AreaPriorityRow, ...]:
    """Build deterministic 60/180-minute rankings for one selected source run."""
    if generated_at.tzinfo is None:
        _fail("generated_at_naive")
    current_by_area, forecast_index, _canonical_timestamp = _validated_source_run(
        current_rows,
        forecast_rows,
        source_collection_run_id=source_collection_run_id,
    )

    drafts: list[dict[str, object]] = []
    for area_code in eg6b.EG6B_AREA_CODES:
        current = current_by_area[area_code]
        for horizon in HORIZONS:
            target = current.origin + timedelta(minutes=horizon)
            key = (
                source_collection_run_id,
                area_code,
                eg8a.to_iso8601(current.origin),
                eg8a.to_iso8601(target),
            )
            forecast = forecast_index[key]
            change = forecast.midpoint - current.midpoint
            rate = change / current.midpoint if current.midpoint != 0 else None
            status, reason = _change_state(change)
            drafts.append(
                {
                    "generated_at": eg8a.to_iso8601(generated_at),
                    "source_collection_run_id": source_collection_run_id,
                    "area_code": area_code,
                    "area_name": current.area_name,
                    "prediction_origin_at": eg8a.to_iso8601(current.origin),
                    "prediction_target_at": eg8a.to_iso8601(forecast.target),
                    "horizon_minutes": horizon,
                    "current_population_midpoint": current.midpoint,
                    "forecast_population_midpoint": forecast.midpoint,
                    "expected_population_change": change,
                    "expected_population_change_rate": rate,
                    "change_status": status,
                    "reason_code": reason,
                    "input_validity": (
                        "VALID" if rate is not None else "CHANGE_RATE_UNCOMPUTABLE_CURRENT_ZERO"
                    ),
                }
            )

    results: list[AreaPriorityRow] = []
    for horizon in HORIZONS:
        horizon_rows = [row for row in drafts if row["horizon_minutes"] == horizon]
        opportunity_order = sorted(
            horizon_rows,
            key=lambda row: (
                0 if float(row["expected_population_change"]) > 0 else 1,
                -float(row["expected_population_change"]),
                -float(row["forecast_population_midpoint"]),
                str(row["area_code"]),
            ),
        )
        future_order = sorted(
            horizon_rows,
            key=lambda row: (-float(row["forecast_population_midpoint"]), str(row["area_code"])),
        )
        opportunity_rank = {str(row["area_code"]): rank for rank, row in enumerate(opportunity_order, 1)}
        future_rank = {str(row["area_code"]): rank for rank, row in enumerate(future_order, 1)}
        for row in opportunity_order:
            area_code = str(row["area_code"])
            results.append(
                AreaPriorityRow(
                    **row,
                    opportunity_rank=opportunity_rank[area_code],
                    future_population_rank=future_rank[area_code],
                    rank_difference=opportunity_rank[area_code] - future_rank[area_code],
                )
            )
    return tuple(results)


def _read_stable_file(path: Path, label: str) -> bytes:
    try:
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            _fail(f"{label}_type_invalid")
        payload = path.read_bytes()
        after = path.lstat()
    except OSError:
        _fail(f"{label}_unreadable")
    if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
        _fail(f"{label}_changed_during_read")
    return payload


def _snapshot(path: Path, label: str, expected_sha256: str) -> tuple[bytes, dict[str, object]]:
    payload = _read_stable_file(path, label)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        _fail(f"{label}_sha_mismatch")
    return payload, {"sha256": digest, "byte_size": len(payload)}


def _csv_from_snapshot(
    payload: bytes,
    required_columns: set[str],
    label: str,
) -> list[dict[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            _fail(f"{label}_header_invalid")
        rows = list(reader)
    except (UnicodeError, csv.Error):
        _fail(f"{label}_unreadable")
    if any(
        None in row or any(not isinstance(value, str) for value in row.values())
        for row in rows
    ):
        _fail(f"{label}_row_invalid")
    return rows


def _evaluate_area_priority_in_memory(
    current_rows: Sequence[Mapping[str, str]],
    forecast_rows: Sequence[Mapping[str, str]],
    *,
    execution_context: _ExecutionContext,
) -> _InMemoryAreaPriorityEvaluation:
    """Reuse EG-8D selection, ranking, and freshness without publication."""
    evaluation_time = execution_context.evaluation_time
    evaluation_mode = execution_context.evaluation_mode
    if not _is_kst_aware(evaluation_time):
        _fail("evaluation_time_invalid")

    selection = _find_latest_complete_run(current_rows, forecast_rows)
    if selection is None:
        current_selection = _select_latest_current_run(current_rows)
        _current_by_area, canonical_timestamp = _validated_current_run(
            current_rows,
            source_collection_run_id=current_selection.source_collection_run_id,
        )
        if canonical_timestamp > evaluation_time:
            _fail("current_after_evaluation_time")
        freshness_gate = evaluate_horizon_freshness(
            evaluation_time=evaluation_time,
            selected_complete_observed_at=None,
            latest_available_current_observed_at=canonical_timestamp,
            forecast_target_at_60m=None,
            forecast_target_at_180m=None,
            complete_snapshot_exists=False,
            time_contract_valid=True,
            evaluation_mode=evaluation_mode,
        )
        return _InMemoryAreaPriorityEvaluation((), freshness_gate, {})

    freshness_gate = evaluate_horizon_freshness(
        evaluation_time=evaluation_time,
        selected_complete_observed_at=selection.canonical_timestamp,
        latest_available_current_observed_at=_latest_current_observed_at(current_rows),
        forecast_target_at_60m=selection.canonical_timestamp + timedelta(minutes=60),
        forecast_target_at_180m=selection.canonical_timestamp + timedelta(minutes=180),
        complete_snapshot_exists=True,
        time_contract_valid=True,
        evaluation_mode=evaluation_mode,
    )
    rows = _build_area_priority_rows(
        current_rows,
        forecast_rows,
        source_collection_run_id=selection.source_collection_run_id,
        generated_at=evaluation_time,
    )
    current_by_area, forecast_index, _canonical_timestamp = _validated_source_run(
        current_rows,
        forecast_rows,
        source_collection_run_id=selection.source_collection_run_id,
    )
    population_ranges = {}
    for row in rows:
        forecast = forecast_index[
            (
                selection.source_collection_run_id,
                row.area_code,
                row.prediction_origin_at,
                row.prediction_target_at,
            )
        ]
        current = current_by_area[row.area_code]
        population_ranges[(row.area_code, row.horizon_minutes)] = (
            current.population_min,
            current.population_max,
            forecast.population_min,
            forecast.population_max,
        )
    return _InMemoryAreaPriorityEvaluation(rows, freshness_gate, population_ranges)


def _evaluate_runtime_area_priority_in_memory(
    *,
    current_path: Path,
    forecast_path: Path,
) -> _InMemoryAreaPriorityEvaluation:
    evaluation_time = _runtime_now()
    execution_context = _ExecutionContext(
        evaluation_time=evaluation_time,
        evaluation_mode="RUNTIME",
        validation_context=RUNTIME_CONTEXT,
        operational_observation=True,
        synthetic_validation=False,
        clock_source=SYSTEM_CLOCK,
        operational_publication_allowed=True,
    )
    current_rows = _csv_from_snapshot(
        _read_stable_file(current_path, "current"), CURRENT_REQUIRED_COLUMNS, "current"
    )
    forecast_rows = _csv_from_snapshot(
        _read_stable_file(forecast_path, "forecast"),
        FORECAST_REQUIRED_COLUMNS,
        "forecast",
    )
    return _evaluate_area_priority_in_memory(
        current_rows,
        forecast_rows,
        execution_context=execution_context,
    )


def _validate_manifest(payload: bytes) -> None:
    try:
        manifest = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError):
        _fail("manifest_json_invalid")
    if not isinstance(manifest, dict) or manifest.get("eg8c_run_id") != LOCKED_DATASET_RUN_ID:
        _fail("manifest_contract_invalid")
    artifacts = manifest.get("input_artifacts")
    if not isinstance(artifacts, list):
        _fail("manifest_contract_invalid")
    by_name = {
        item.get("logical_name"): item
        for item in artifacts
        if isinstance(item, dict) and isinstance(item.get("logical_name"), str)
    }
    expected = {
        "population_current_v3": LOCKED_CURRENT_SHA256,
        "population_forecast_v3": LOCKED_FORECAST_SHA256,
    }
    if any(by_name.get(name, {}).get("sha256") != digest for name, digest in expected.items()):
        _fail("manifest_input_sha_mismatch")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _csv_bytes(rows: Sequence[AreaPriorityRow]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(row.as_dict() for row in rows)
    return stream.getvalue().encode()


def _current_only_csv_bytes(rows: Sequence[CurrentOnlyRow]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=CURRENT_ONLY_CSV_FIELDS, lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        payload = row.as_dict()
        payload["reason_codes"] = json.dumps(
            payload["reason_codes"], ensure_ascii=False, separators=(",", ":")
        )
        writer.writerow(payload)
    return stream.getvalue().encode()


def _build_current_only_rows(
    current_by_area: Mapping[str, _Current],
    *,
    freshness_gate: FreshnessGateResult,
    validation_context: str,
    operational_observation: bool,
) -> tuple[CurrentOnlyRow, ...]:
    gate = freshness_gate.horizons[60]
    evaluation_time = freshness_gate.evaluation_time
    current_age = freshness_gate.current_only_data_age_minutes
    if (
        evaluation_time is None
        or current_age is None
        or gate.freshness_status != "NO_COMPLETE_SNAPSHOT"
    ):
        _fail("current_only_gate_invalid")
    return tuple(
        CurrentOnlyRow(
            result_contract=CURRENT_ONLY_CONTRACT,
            record_role="CURRENT_STATE_ROW",
            validation_context=validation_context,
            operational_observation=operational_observation,
            area_code=area_code,
            area_name=current_by_area[area_code].area_name,
            current_population_min=current_by_area[area_code].population_min,
            current_population_max=current_by_area[area_code].population_max,
            current_population_midpoint=current_by_area[area_code].midpoint,
            current_congestion_level=current_by_area[area_code].congestion_level,
            current_observed_at=eg8a.to_iso8601(current_by_area[area_code].origin),
            evaluation_time=evaluation_time,
            current_age_minutes=current_age,
            freshness_status=gate.freshness_status,
            current_only_fallback_allowed=gate.current_only_fallback_allowed,
            area_current_state_display_allowed=freshness_gate.user_display_eligible,
            area_result_display_allowed=False,
            spot_evaluation_allowed=False,
            official_recommendation_allowed=False,
            reason_codes=gate.reason_codes,
            warning_message=gate.warning_message,
            mode=freshness_gate.evaluation_mode,
        )
        for area_code in eg6b.EG6B_AREA_CODES
    )


def _metadata(
    *,
    run_id: str,
    selection: _SourceRunSelection,
    generated_at: datetime,
    rows: tuple[AreaPriorityRow, ...],
    inputs: Mapping[str, Mapping[str, object]],
    freshness_gate: FreshnessGateResult,
    execution_provenance: Mapping[str, object],
) -> dict[str, object]:
    summary: dict[str, object] = {}
    change_summary: dict[str, object] = {}
    for horizon in HORIZONS:
        ranked = [row for row in rows if row.horizon_minutes == horizon]
        positive_count = sum(row.expected_population_change > 0 for row in ranked)
        zero_count = sum(row.expected_population_change == 0 for row in ranked)
        summary[str(horizon)] = {
            "top": {
                "area_code": ranked[0].area_code,
                "area_name": ranked[0].area_name,
                "expected_population_change": ranked[0].expected_population_change,
                "reason_code": ranked[0].reason_code,
            },
            "bottom": {
                "area_code": ranked[-1].area_code,
                "area_name": ranked[-1].area_name,
                "expected_population_change": ranked[-1].expected_population_change,
                "reason_code": ranked[-1].reason_code,
            },
        }
        change_summary[str(horizon)] = {
            "positive_increase_area_count": positive_count,
            "zero_change_area_count": zero_count,
            "decrease_area_count": len(ranked) - positive_count - zero_count,
            "has_positive_increase_candidate": positive_count > 0,
        }
    return {
        **execution_provenance,
        "schema_version": "eg8d-area-priority-metadata-v2",
        "area_priority_run_id": run_id,
        "generated_at": eg8a.to_iso8601(generated_at),
        "evaluation_time": freshness_gate.evaluation_time,
        "source_dataset_run_id": LOCKED_DATASET_RUN_ID,
        "source_collection_run_id": selection.source_collection_run_id,
        "selection_policy": SELECTION_POLICY,
        "dataset_manifest_sha256": inputs["dataset_manifest"]["sha256"],
        "total_collection_run_count": selection.total_collection_run_count,
        "complete_collection_run_count": selection.complete_collection_run_count,
        "selected_run_canonical_timestamp": eg8a.to_iso8601(selection.canonical_timestamp),
        "canonical_timestamp_field": CANONICAL_TIMESTAMP_FIELD,
        "selection_performed_before_ranking": True,
        "selection_tie_count": selection.selection_tie_count,
        "selection_status": "SELECTED",
        "freshness_gate": freshness_gate.as_dict(),
        "input_artifacts": [
            {"logical_name": name, **dict(inputs[name])} for name in sorted(inputs)
        ],
        "horizon_area_counts": {
            str(horizon): sum(row.horizon_minutes == horizon for row in rows)
            for horizon in HORIZONS
        },
        "excluded_areas": [],
        "horizon_change_summary": change_summary,
        "top_bottom_summary": summary,
        "ranking_rules": {
            "opportunity": [
                "positive_change_first",
                "expected_population_change_desc",
                "forecast_population_midpoint_desc",
                "area_code_asc",
            ],
            "future_population": ["forecast_population_midpoint_desc", "area_code_asc"],
            "horizons_combined": False,
            "weighted_score_used": False,
        },
        "forecast_source": FORECAST_SOURCE,
        "evaluation_status": EVALUATION_STATUS,
        "official_model_gate_judgment": None,
        "target_level": TARGET_LEVEL,
        "recommendation_contract_status": "INTERNAL_AREA_RANKING_NOT_OFFICIAL_RECOMMENDATION_OUTPUT",
        "limitations": [
            "서울시 Forecast 기반 예상 유동인구 변화의 표시·우선 검토 순서이며 실제 방문이나 판매 성공을 보장하지 않는다.",
            "변화 0은 현재·미래 인구 범위 중간값 차이가 0이라는 뜻이며 실제 변화 부재나 예측 범위 불확실성 제거를 의미하지 않는다.",
            "한 수집 회차 Snapshot의 잠정 결과로 장기 반복성이나 사용자 가치를 검증하지 않는다.",
            "60분과 180분 순위는 서로 독립적이며 가중치 종합점수를 사용하지 않는다.",
            "Spot·이동시간·담당구역·현장검증 정보는 포함하지 않는다.",
        ],
    }


def _current_only_metadata(
    *,
    run_id: str,
    selection: _SourceRunSelection,
    generated_at: datetime,
    rows: tuple[CurrentOnlyRow, ...],
    inputs: Mapping[str, Mapping[str, object]],
    freshness_gate: FreshnessGateResult,
    execution_provenance: Mapping[str, object],
) -> dict[str, object]:
    gate = freshness_gate.horizons[60]
    allowed = freshness_gate.user_display_eligible
    return {
        **execution_provenance,
        "schema_version": "eg8d-current-area-state-metadata-v1",
        "result_contract": CURRENT_ONLY_CONTRACT,
        "result_status": "CURRENT_ONLY_ALLOWED" if allowed else "CURRENT_ONLY_BLOCKED",
        "current_area_state_run_id": run_id,
        "generated_at": eg8a.to_iso8601(generated_at),
        "evaluation_time": freshness_gate.evaluation_time,
        "evaluation_mode": freshness_gate.evaluation_mode,
        "source_dataset_run_id": LOCKED_DATASET_RUN_ID,
        "source_collection_run_id": selection.source_collection_run_id,
        "selection_policy": "LATEST_CURRENT_LOCKED_SNAPSHOT",
        "dataset_manifest_sha256": inputs["dataset_manifest"]["sha256"],
        "total_collection_run_count": selection.total_collection_run_count,
        "complete_collection_run_count": 0,
        "selected_current_observed_at": eg8a.to_iso8601(selection.canonical_timestamp),
        "canonical_timestamp_field": CANONICAL_TIMESTAMP_FIELD,
        "selection_tie_count": selection.selection_tie_count,
        "selection_status": "SELECTED_CURRENT_ONLY",
        "current_area_state_count": len(rows),
        "current_age_minutes": freshness_gate.current_only_data_age_minutes,
        "freshness_status": gate.freshness_status,
        "current_only_fallback_allowed": gate.current_only_fallback_allowed,
        "area_current_state_display_allowed": allowed,
        "area_result_display_allowed": False,
        "spot_evaluation_allowed": False,
        "official_recommendation_allowed": False,
        "reason_codes": list(gate.reason_codes),
        "warning_message": gate.warning_message,
        "input_artifacts": [
            {"logical_name": name, **dict(inputs[name])} for name in sorted(inputs)
        ],
        "evaluation_status": EVALUATION_STATUS,
        "official_model_gate_judgment": None,
        "target_level": TARGET_LEVEL,
        "limitations": [
            "완전한 Forecast Snapshot이 없어 현재 Area 상태만 기록한다.",
            "미래 변화·순위·Spot·공식 추천 결과를 포함하지 않는다.",
            "이 최신성 기준은 PoC 잠정 정책이며 운영 SLA가 아니다.",
        ],
    }


def _write_exclusive(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
    except OSError:
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: artifact_write_failed") from None


def _sha256(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    except AttributeError:  # Python 3.9 local compatibility; CI/runtime uses 3.12.
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            _fail("source_recheck_failed")
    except OSError:
        _fail("source_recheck_failed")


def _publish(
    *,
    output_root: Path,
    run_id: str,
    payloads: Mapping[str, bytes],
    input_paths: Sequence[Path],
    input_hashes: Mapping[Path, str],
    output_files: set[str] = OUTPUT_FILES,
    manifest_name: str = "area_priority_manifest.json",
    manifest_schema_version: str = "eg8d-area-priority-manifest-v1",
    result_contract: str | None = None,
    manifest_metadata: Mapping[str, object] | None = None,
) -> tuple[Path, dict[str, object]]:
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: run_id_invalid")
    if manifest_name not in output_files or set(payloads) != output_files - {manifest_name}:
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: artifact_set_invalid")
    try:
        mode = output_root.lstat().st_mode
        resolved_root = output_root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: output_root_invalid") from None
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: output_root_invalid")
    if any((parent / ".git").exists() for parent in (resolved_root, *resolved_root.parents)):
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: git_output_forbidden")
    for source in input_paths:
        try:
            source.resolve(strict=True).relative_to(resolved_root)
        except ValueError:
            pass
        except OSError:
            _fail("source_recheck_failed")
        else:
            raise AreaPriorityWriteError("eg8d_area_priority_write_error: input_output_overlap")
    final_run = resolved_root / run_id
    if final_run.exists() or final_run.is_symlink():
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: run_exists")
    try:
        staging = Path(tempfile.mkdtemp(prefix=".eg8d-area-priority-staging-", dir=resolved_root))
    except OSError:
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: staging_create_failed") from None
    published = False
    try:
        for name in sorted(payloads):
            _write_exclusive(staging / name, payloads[name])
        artifacts = [
            {
                "relative_path": name,
                "sha256": hashlib.sha256(payloads[name]).hexdigest(),
                "byte_size": len(payloads[name]),
            }
            for name in sorted(payloads)
        ]
        manifest = {
            "schema_version": manifest_schema_version,
            "hash_algorithm": "sha256",
            "output_artifacts": artifacts,
        }
        if result_contract is not None:
            manifest["result_contract"] = result_contract
        if manifest_metadata is not None:
            manifest.update(manifest_metadata)
        _write_exclusive(staging / manifest_name, _json_bytes(manifest))
        if {path.name for path in staging.iterdir()} != output_files:
            raise AreaPriorityWriteError("eg8d_area_priority_write_error: staged_artifact_set_mismatch")
        for artifact in artifacts:
            path = staging / str(artifact["relative_path"])
            if _sha256(path) != artifact["sha256"] or path.stat().st_size != artifact["byte_size"]:
                raise AreaPriorityWriteError("eg8d_area_priority_write_error: staged_hash_mismatch")
        if any(_sha256(path) != expected for path, expected in input_hashes.items()):
            _fail("source_changed_during_run")
        try:
            eg8c_features._rename_run_root_exclusive(staging, final_run)
        except OSError:
            raise AreaPriorityWriteError("eg8d_area_priority_write_error: publish_failed") from None
        published = True
        return final_run, manifest
    finally:
        if not published and staging.exists():
            try:
                shutil.rmtree(staging)
            except OSError:
                raise AreaPriorityWriteError("eg8d_area_priority_write_error: staging_cleanup_failed") from None


def _execute_eg8d_area_priority(
    *,
    dataset_manifest_path: Path,
    current_path: Path,
    forecast_path: Path,
    output_root: Path,
    run_id: str,
    generated_at: datetime | None,
    execution_context: _ExecutionContext,
) -> AreaPriorityResult:
    evaluation_time = execution_context.evaluation_time
    generated_at = generated_at or evaluation_time
    if not _is_kst_aware(evaluation_time) or not _is_kst_aware(generated_at):
        _fail("evaluation_time_invalid")
    manifest_payload, manifest_info = _snapshot(
        dataset_manifest_path, "manifest", LOCKED_MANIFEST_SHA256
    )
    current_payload, current_info = _snapshot(current_path, "current", LOCKED_CURRENT_SHA256)
    forecast_payload, forecast_info = _snapshot(
        forecast_path, "forecast", LOCKED_FORECAST_SHA256
    )
    _validate_manifest(manifest_payload)
    current_rows = _csv_from_snapshot(current_payload, CURRENT_REQUIRED_COLUMNS, "current")
    forecast_rows = _csv_from_snapshot(forecast_payload, FORECAST_REQUIRED_COLUMNS, "forecast")
    inputs = {
        "dataset_manifest": manifest_info,
        "population_current_v3": current_info,
        "population_forecast_v3": forecast_info,
    }
    paths = (dataset_manifest_path, current_path, forecast_path)
    input_hashes = {
        dataset_manifest_path: str(manifest_info["sha256"]),
        current_path: str(current_info["sha256"]),
        forecast_path: str(forecast_info["sha256"]),
    }
    selection = _find_latest_complete_run(current_rows, forecast_rows)
    if selection is None:
        current_selection = _select_latest_current_run(current_rows)
        current_by_area, canonical_timestamp = _validated_current_run(
            current_rows,
            source_collection_run_id=current_selection.source_collection_run_id,
        )
        if canonical_timestamp != current_selection.canonical_timestamp:
            _fail("canonical_timestamp_mismatch")
        if canonical_timestamp > evaluation_time:
            _fail("current_after_evaluation_time")
        freshness_gate = evaluate_horizon_freshness(
            evaluation_time=evaluation_time,
            selected_complete_observed_at=None,
            latest_available_current_observed_at=canonical_timestamp,
            forecast_target_at_60m=None,
            forecast_target_at_180m=None,
            complete_snapshot_exists=False,
            time_contract_valid=True,
            evaluation_mode=execution_context.evaluation_mode,
        )
        simulated_policy_outcome = None
        if execution_context.synthetic_validation:
            simulated_policy_outcome = (
                "CURRENT_ONLY_ALLOWED"
                if freshness_gate.horizons[60].current_only_fallback_allowed
                else "CURRENT_ONLY_BLOCKED"
            )
        execution_provenance = _execution_provenance(
            execution_context=execution_context,
            source_dataset_manifest_sha256=str(manifest_info["sha256"]),
            forecast_absence_simulated=execution_context.synthetic_validation,
            user_display_eligible=freshness_gate.user_display_eligible,
            simulated_policy_outcome=simulated_policy_outcome,
        )
        rows = _build_current_only_rows(
            current_by_area,
            freshness_gate=freshness_gate,
            validation_context=execution_context.validation_context,
            operational_observation=execution_context.operational_observation,
        )
        metadata = _current_only_metadata(
            run_id=run_id,
            selection=current_selection,
            generated_at=generated_at,
            rows=rows,
            inputs=inputs,
            freshness_gate=freshness_gate,
            execution_provenance=execution_provenance,
        )
        payloads = {
            "current_area_state.csv": _current_only_csv_bytes(rows),
            "current_area_state.json": _json_bytes([row.as_dict() for row in rows]),
            "run_metadata.json": _json_bytes(metadata),
        }
        run_dir, manifest = _publish(
            output_root=output_root,
            run_id=run_id,
            payloads=payloads,
            input_paths=paths,
            input_hashes=input_hashes,
            output_files=CURRENT_ONLY_OUTPUT_FILES,
            manifest_name="current_area_state_manifest.json",
            manifest_schema_version="eg8d-current-area-state-manifest-v1",
            result_contract=CURRENT_ONLY_CONTRACT,
            manifest_metadata=execution_provenance,
        )
        return AreaPriorityResult(run_id, run_dir, rows, metadata, manifest)

    if execution_context.synthetic_validation:
        _fail("synthetic_validation_requires_current_only")
    freshness_gate = evaluate_horizon_freshness(
        evaluation_time=evaluation_time,
        selected_complete_observed_at=selection.canonical_timestamp,
        latest_available_current_observed_at=_latest_current_observed_at(current_rows),
        forecast_target_at_60m=selection.canonical_timestamp + timedelta(minutes=60),
        forecast_target_at_180m=selection.canonical_timestamp + timedelta(minutes=180),
        complete_snapshot_exists=True,
        time_contract_valid=True,
        evaluation_mode=execution_context.evaluation_mode,
    )
    execution_provenance = _execution_provenance(
        execution_context=execution_context,
        source_dataset_manifest_sha256=str(manifest_info["sha256"]),
        forecast_absence_simulated=False,
        user_display_eligible=freshness_gate.user_display_eligible,
    )
    rows = _build_area_priority_rows(
        current_rows,
        forecast_rows,
        source_collection_run_id=selection.source_collection_run_id,
        generated_at=generated_at,
    )
    metadata = _metadata(
        run_id=run_id,
        selection=selection,
        generated_at=generated_at,
        rows=rows,
        inputs=inputs,
        freshness_gate=freshness_gate,
        execution_provenance=execution_provenance,
    )
    payloads = {
        "area_priority.csv": _csv_bytes(rows),
        "area_priority.json": _json_bytes([row.as_dict() for row in rows]),
        "run_metadata.json": _json_bytes(metadata),
    }
    run_dir, manifest = _publish(
        output_root=output_root,
        run_id=run_id,
        payloads=payloads,
        input_paths=paths,
        input_hashes=input_hashes,
        manifest_metadata=execution_provenance,
    )
    return AreaPriorityResult(run_id, run_dir, rows, metadata, manifest)


def _run_eg8d_area_priority(
    *,
    dataset_manifest_path: Path,
    current_path: Path,
    forecast_path: Path,
    output_root: Path,
    run_id: str,
    generated_at: datetime,
    evaluation_time: datetime,
    evaluation_mode: str,
) -> AreaPriorityResult:
    if evaluation_mode == "HISTORICAL_AUDIT":
        execution_context = _ExecutionContext(
            evaluation_time=evaluation_time,
            evaluation_mode="HISTORICAL_AUDIT",
            validation_context=HISTORICAL_CONTEXT,
            operational_observation=False,
            synthetic_validation=False,
            clock_source=INJECTED_CLOCK,
            operational_publication_allowed=False,
        )
    elif evaluation_mode == "SYNTHETIC_VALIDATION":
        execution_context = _ExecutionContext(
            evaluation_time=evaluation_time,
            evaluation_mode="SYNTHETIC_VALIDATION",
            validation_context=SYNTHETIC_CONTEXT,
            operational_observation=False,
            synthetic_validation=True,
            clock_source=INJECTED_CLOCK,
            operational_publication_allowed=False,
        )
    else:
        _fail("execution_context_invalid")
    return _execute_eg8d_area_priority(
        dataset_manifest_path=dataset_manifest_path,
        current_path=current_path,
        forecast_path=forecast_path,
        output_root=output_root,
        run_id=run_id,
        generated_at=generated_at,
        execution_context=execution_context,
    )


def _run_runtime_eg8d_area_priority(
    *,
    dataset_manifest_path: Path,
    current_path: Path,
    forecast_path: Path,
    output_root: Path,
    run_id: str,
    generated_at: datetime | None = None,
) -> AreaPriorityResult:
    evaluation_time = _runtime_now()
    execution_context = _ExecutionContext(
        evaluation_time=evaluation_time,
        evaluation_mode="RUNTIME",
        validation_context=RUNTIME_CONTEXT,
        operational_observation=True,
        synthetic_validation=False,
        clock_source=SYSTEM_CLOCK,
        operational_publication_allowed=True,
    )
    return _execute_eg8d_area_priority(
        dataset_manifest_path=dataset_manifest_path,
        current_path=current_path,
        forecast_path=forecast_path,
        output_root=output_root,
        run_id=run_id,
        generated_at=generated_at,
        execution_context=execution_context,
    )


def run_eg8d_area_priority(
    *,
    dataset_manifest_path: Path,
    current_path: Path,
    forecast_path: Path,
    output_root: Path,
    run_id: str,
    generated_at: datetime | None = None,
) -> AreaPriorityResult:
    """Public bounded-error entry point for one operational EG-8D result run."""
    try:
        return _run_runtime_eg8d_area_priority(
            dataset_manifest_path=dataset_manifest_path,
            current_path=current_path,
            forecast_path=forecast_path,
            output_root=output_root,
            run_id=run_id,
            generated_at=generated_at,
        )
    except (AreaPriorityContractError, AreaPriorityWriteError):
        raise
    except Exception:
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: execution_failed") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EG-8D Area 예상 유동인구 변화 순서")
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--current-path", type=Path, required=True)
    parser.add_argument("--forecast-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = run_eg8d_area_priority(
            dataset_manifest_path=arguments.dataset_manifest,
            current_path=arguments.current_path,
            forecast_path=arguments.forecast_path,
            output_root=arguments.output_root,
            run_id=arguments.run_id,
        )
    except (AreaPriorityContractError, AreaPriorityWriteError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print("eg8d_area_priority_completed")
    print(f"run_id={result.run_id}")
    print(f"row_count={len(result.rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
