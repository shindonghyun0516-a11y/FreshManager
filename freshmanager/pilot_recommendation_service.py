"""JSON-safe ViewModel service for the five-Area initial pilot."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from . import pilot_area_recommendation


ALLOWED_HORIZONS = (60, 180)
CONTRACT_INVALID = "pilot_recommendation_service_error: contract_invalid"
EXECUTION_FAILED = "pilot_recommendation_service_error: execution_failed"
SPOT_OPTION_FIELDS = frozenset(pilot_area_recommendation.SPOT_OPTION_FIELDS)
AREA_FIELDS = (
    "area_code",
    "area_name",
    "current_population_min",
    "current_population_max",
    "current_population_midpoint",
    "forecast_population_min",
    "forecast_population_max",
    "forecast_population_midpoint",
    "expected_population_change",
    "expected_population_change_rate",
)


class PilotRecommendationServiceError(ValueError):
    """Raised when the service cannot safely build a ViewModel."""


def _empty_view(
    *,
    view_status: str,
    horizon_minutes: int | None,
    reason_code: str | None,
    reason_codes: Sequence[str] = (),
    warning_message: str | None = None,
    recommendation_status: str = "UNAVAILABLE",
) -> dict[str, object]:
    return {
        "view_status": view_status,
        "horizon_minutes": horizon_minutes,
        "recommendation_status": recommendation_status,
        "pilot_recommendation_allowed": False,
        "official_recommendation_allowed": False,
        "machine_learning_used_for_recommendation": False,
        "reason_code": reason_code,
        "reason_codes": list(reason_codes),
        "warning_message": warning_message,
        "area": None,
        "sales_time": None,
        "spot_options": [],
        "selected_spot": None,
        "limitations": [],
    }


def _reason_codes(result: Mapping[str, object]) -> list[str]:
    values = result.get("reason_codes")
    if not isinstance(values, (list, tuple)) or any(
        not isinstance(value, str) for value in values
    ):
        raise PilotRecommendationServiceError(CONTRACT_INVALID)
    return list(values)


def _build_view(
    *,
    result: Mapping[str, object],
    horizon_minutes: int,
    selected_spot_option_id: str | None,
) -> dict[str, object]:
    if (
        result.get("horizon_minutes") != horizon_minutes
        or result.get("official_recommendation_allowed") is not False
    ):
        raise PilotRecommendationServiceError(CONTRACT_INVALID)

    reason_code = result.get("reason_code")
    warning_message = result.get("warning_message")
    if reason_code is not None and not isinstance(reason_code, str):
        raise PilotRecommendationServiceError(CONTRACT_INVALID)
    if warning_message is not None and not isinstance(warning_message, str):
        raise PilotRecommendationServiceError(CONTRACT_INVALID)
    reason_codes = _reason_codes(result)
    recommendation = result.get("recommendation")

    if recommendation is None:
        if (
            result.get("recommendation_status") != "UNAVAILABLE"
            or result.get("pilot_recommendation_allowed") is not False
        ):
            raise PilotRecommendationServiceError(CONTRACT_INVALID)
        if selected_spot_option_id is not None:
            if "INVALID_SELECTION" not in reason_codes:
                reason_codes.append("INVALID_SELECTION")
            return _empty_view(
                view_status="INVALID_SELECTION",
                horizon_minutes=horizon_minutes,
                reason_code="INVALID_SELECTION",
                reason_codes=reason_codes,
                warning_message=warning_message,
            )
        return _empty_view(
            view_status="NO_RECOMMENDATION",
            horizon_minutes=horizon_minutes,
            reason_code=reason_code,
            reason_codes=reason_codes,
            warning_message=warning_message,
        )

    if (
        not isinstance(recommendation, Mapping)
        or result.get("recommendation_status") != "AVAILABLE"
        or result.get("pilot_recommendation_allowed") is not True
        or recommendation.get("recommendation_type") != "AREA"
        or recommendation.get("prediction_scope") != "AREA"
        or recommendation.get("recommendation_basis")
        != "SEOUL_OFFICIAL_FORECAST"
        or recommendation.get("recommendation_forecast_source")
        != "SEOUL_OFFICIAL_FORECAST"
        or recommendation.get("horizon_minutes") != horizon_minutes
        or recommendation.get("machine_learning_used_for_recommendation") is not False
        or recommendation.get("spot_id") is not None
        or recommendation.get("fallback_reason") is not None
        or recommendation.get("spot_selection_mode") != "USER_CHOICE"
        or recommendation.get("spot_auto_recommendation") is not False
        or recommendation.get("user_selected_spot_id") is not None
        or not isinstance(recommendation.get("area_code"), str)
    ):
        raise PilotRecommendationServiceError(CONTRACT_INVALID)

    raw_options = recommendation.get("spot_options")
    if not isinstance(raw_options, (list, tuple)) or len(raw_options) != 3:
        raise PilotRecommendationServiceError(CONTRACT_INVALID)
    options = [
        dict(option) for option in raw_options if isinstance(option, Mapping)
    ]
    option_ids = [option.get("spot_option_id") for option in options]
    area_code = recommendation["area_code"]
    if (
        len(options) != 3
        or any(not isinstance(option_id, str) for option_id in option_ids)
        or len(set(option_ids)) != 3
        or any(
            set(option) != SPOT_OPTION_FIELDS
            or option.get("display_order") != order
            or option.get("spot_option_id") != f"{area_code}-OPT-{order:02d}"
            for order, option in enumerate(options, start=1)
        )
    ):
        raise PilotRecommendationServiceError(CONTRACT_INVALID)

    limitations: list[str] = []
    for option in options:
        limitation = option.get("limitations")
        if not isinstance(limitation, str):
            raise PilotRecommendationServiceError(CONTRACT_INVALID)
        if limitation not in limitations:
            limitations.append(limitation)

    try:
        area = {field: recommendation[field] for field in AREA_FIELDS}
        sales_time = {
            "prediction_origin_at": recommendation["prediction_origin_at"],
            "recommendation_target_at": recommendation["recommendation_target_at"],
            "horizon_minutes": horizon_minutes,
            "display_mode": "FORECAST_TARGET_POINT",
        }
    except KeyError:
        raise PilotRecommendationServiceError(CONTRACT_INVALID) from None

    selected_spot = None
    view_status = "AVAILABLE_UNSELECTED"
    if selected_spot_option_id is not None:
        selected_spot = next(
            (
                option
                for option in options
                if option["spot_option_id"] == selected_spot_option_id
            ),
            None,
        )
        if selected_spot is None:
            view_status = "INVALID_SELECTION"
            reason_code = "INVALID_SELECTION"
            if reason_code not in reason_codes:
                reason_codes.append(reason_code)
        else:
            view_status = "AVAILABLE_SELECTED"

    return {
        "view_status": view_status,
        "horizon_minutes": horizon_minutes,
        "recommendation_status": "AVAILABLE",
        "pilot_recommendation_allowed": True,
        "official_recommendation_allowed": False,
        "machine_learning_used_for_recommendation": False,
        "reason_code": reason_code,
        "reason_codes": reason_codes,
        "warning_message": warning_message,
        "area": area,
        "sales_time": sales_time,
        "spot_options": options,
        "selected_spot": selected_spot,
        "limitations": limitations,
    }


def build_pilot_recommendation_view_model(
    *,
    current_path: Path,
    forecast_path: Path,
    spot_options_path: Path,
    horizon_minutes: int,
    selected_spot_option_id: str | None = None,
) -> dict[str, object]:
    """Build one horizon's ViewModel without persistence or publication."""
    if type(horizon_minutes) is not int or horizon_minutes not in ALLOWED_HORIZONS:
        return _empty_view(
            view_status="INPUT_INVALID",
            horizon_minutes=None,
            reason_code="INVALID_HORIZON",
            reason_codes=("INVALID_HORIZON",),
        )
    if selected_spot_option_id is not None and not isinstance(
        selected_spot_option_id, str
    ):
        return _empty_view(
            view_status="INPUT_INVALID",
            horizon_minutes=horizon_minutes,
            reason_code="INPUT_INVALID",
            reason_codes=("INPUT_INVALID",),
        )

    try:
        results = pilot_area_recommendation.build_pilot_area_recommendations(
            current_path=current_path,
            forecast_path=forecast_path,
            spot_options_path=spot_options_path,
        )
    except pilot_area_recommendation.PilotAreaRecommendationError as error:
        if str(error) == "pilot_area_recommendation_error: input_invalid":
            return _empty_view(
                view_status="INPUT_INVALID",
                horizon_minutes=horizon_minutes,
                reason_code="INPUT_INVALID",
                reason_codes=("INPUT_INVALID",),
            )
        raise PilotRecommendationServiceError(EXECUTION_FAILED) from None
    except Exception:
        raise PilotRecommendationServiceError(EXECUTION_FAILED) from None

    try:
        result = results[horizon_minutes]
        if not isinstance(result, Mapping):
            raise TypeError
        view = _build_view(
            result=result,
            horizon_minutes=horizon_minutes,
            selected_spot_option_id=selected_spot_option_id,
        )
        json.dumps(view, allow_nan=False)
        return view
    except PilotRecommendationServiceError:
        raise
    except Exception:
        raise PilotRecommendationServiceError(CONTRACT_INVALID) from None
