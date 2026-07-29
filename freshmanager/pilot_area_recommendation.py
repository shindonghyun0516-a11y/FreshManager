"""In-memory five-Area initial pilot recommendation core."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from . import eg8d_area_priority, pilot_spot_options


SPOT_OPTION_FIELDS = (
    "spot_option_id",
    "spot_name",
    "spot_type",
    "address",
    "latitude",
    "longitude",
    "pin_scope",
    "spot_role",
    "spot_selection_mode",
    "display_order",
    "field_verification_status",
    "operational_suitability_status",
    "limitations",
)


class PilotAreaRecommendationError(ValueError):
    """Raised when pilot recommendation inputs or contracts are invalid."""


def _spot_options_by_area(
    options: Sequence[Mapping[str, str]],
) -> dict[str, tuple[dict[str, object], ...]]:
    grouped: dict[str, list[Mapping[str, str]]] = {
        area_code: [] for area_code in pilot_spot_options.PILOT_AREA_NAMES
    }
    for option in options:
        area_code = option.get("pilot_area_code", "")
        if (
            area_code not in grouped
            or option.get("pilot_area_name")
            != pilot_spot_options.PILOT_AREA_NAMES[area_code]
        ):
            raise ValueError("pilot_area_recommendation_contract_error: area_spot_link_invalid")
        grouped[area_code].append(option)

    result: dict[str, tuple[dict[str, object], ...]] = {}
    for area_code, rows in grouped.items():
        if [row.get("display_order") for row in rows] != ["1", "2", "3"]:
            raise ValueError(
                "pilot_area_recommendation_contract_error: spot_option_order_invalid"
            )
        result[area_code] = tuple(
            {
                field: int(row[field]) if field == "display_order" else row[field]
                for field in SPOT_OPTION_FIELDS
            }
            for row in rows
        )
    return result


def _build_horizon_recommendations(
    evaluation: eg8d_area_priority._InMemoryAreaPriorityEvaluation,
    spot_options: Sequence[Mapping[str, str]],
) -> dict[int, dict[str, object]]:
    options_by_area = _spot_options_by_area(spot_options)
    pilot_codes = set(pilot_spot_options.PILOT_AREA_NAMES)
    results: dict[int, dict[str, object]] = {}

    for horizon in eg8d_area_priority.HORIZONS:
        freshness = evaluation.freshness_gate.horizons[horizon]
        horizon_rows = tuple(
            row
            for row in evaluation.rows
            if row.horizon_minutes == horizon and row.area_code in pilot_codes
        )
        if horizon_rows and (
            len(horizon_rows) != len(pilot_codes)
            or {row.area_code for row in horizon_rows} != pilot_codes
            or any(
                row.area_name != pilot_spot_options.PILOT_AREA_NAMES[row.area_code]
                for row in horizon_rows
            )
            or len({row.opportunity_rank for row in horizon_rows}) != len(horizon_rows)
        ):
            raise ValueError(
                "pilot_area_recommendation_contract_error: pilot_area_rows_invalid"
            )

        eligible = (
            evaluation.freshness_gate.evaluation_mode == "RUNTIME"
            and evaluation.freshness_gate.user_display_eligible
            and freshness.freshness_status == "FRESH"
            and freshness.area_result_display_allowed
        )
        base = {
            "horizon_minutes": horizon,
            "recommendation_status": "UNAVAILABLE",
            "freshness_status": freshness.freshness_status,
            "official_recommendation_allowed": False,
            "pilot_recommendation_allowed": False,
            "reason_code": None,
            "reason_codes": freshness.reason_codes,
            "warning_message": freshness.warning_message,
            "recommendation": None,
        }
        if not eligible:
            results[horizon] = base
            continue

        positive = tuple(
            row for row in horizon_rows if row.expected_population_change > 0
        )
        if not positive:
            base["reason_code"] = "NO_POSITIVE_AREA_OPPORTUNITY"
            base["reason_codes"] = (*freshness.reason_codes, base["reason_code"])
            results[horizon] = base
            continue

        selected = min(positive, key=lambda row: row.opportunity_rank)
        current_min, current_max, forecast_min, forecast_max = (
            evaluation.population_ranges[(selected.area_code, horizon)]
        )
        base["recommendation_status"] = "AVAILABLE"
        base["pilot_recommendation_allowed"] = True
        base["reason_codes"] = (*freshness.reason_codes, selected.reason_code)
        base["recommendation"] = {
            "recommendation_type": "AREA",
            "prediction_scope": "AREA",
            "recommendation_basis": "SEOUL_OFFICIAL_FORECAST",
            "recommendation_forecast_source": "SEOUL_OFFICIAL_FORECAST",
            "machine_learning_used_for_recommendation": False,
            "source_collection_run_id": selected.source_collection_run_id,
            "area_code": selected.area_code,
            "area_name": selected.area_name,
            "prediction_origin_at": selected.prediction_origin_at,
            "prediction_target_at": selected.prediction_target_at,
            "recommendation_target_at": selected.prediction_target_at,
            "horizon_minutes": horizon,
            "current_population_min": current_min,
            "current_population_max": current_max,
            "current_population_midpoint": selected.current_population_midpoint,
            "forecast_population_min": forecast_min,
            "forecast_population_max": forecast_max,
            "forecast_population_midpoint": selected.forecast_population_midpoint,
            "expected_population_change": selected.expected_population_change,
            "expected_population_change_rate": (
                selected.expected_population_change_rate
            ),
            "spot_id": None,
            "fallback_reason": None,
            "spot_selection_mode": "USER_CHOICE",
            "spot_auto_recommendation": False,
            "user_selected_spot_id": None,
            "spot_options": options_by_area[selected.area_code],
        }
        results[horizon] = base

    return results


def build_pilot_area_recommendations(
    *,
    current_path: Path,
    forecast_path: Path,
    spot_options_path: Path,
) -> dict[int, dict[str, object]]:
    """Return independent 60/180-minute pilot results without publication."""
    try:
        evaluation = eg8d_area_priority._evaluate_runtime_area_priority_in_memory(
            current_path=current_path,
            forecast_path=forecast_path,
        )
        options = pilot_spot_options.load_pilot_spot_options(spot_options_path)
        return _build_horizon_recommendations(evaluation, options)
    except PilotAreaRecommendationError:
        raise
    except (
        eg8d_area_priority.AreaPriorityContractError,
        pilot_spot_options.PilotSpotOptionsError,
    ):
        raise PilotAreaRecommendationError(
            "pilot_area_recommendation_error: input_invalid"
        ) from None
    except Exception:
        raise PilotAreaRecommendationError(
            "pilot_area_recommendation_error: execution_failed"
        ) from None
