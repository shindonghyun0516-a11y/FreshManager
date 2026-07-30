from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from freshmanager import (
    eg8d_area_priority,
    pilot_area_recommendation,
    pilot_recommendation_service,
    pilot_spot_options,
)
from tests.test_pilot_area_recommendation import (
    CURRENT_FIELDS,
    FORECAST_FIELDS,
    FRESH_EVALUATION_TIME,
    source_rows,
    write_csv,
)


VIEW_FIELDS = {
    "view_status",
    "horizon_minutes",
    "recommendation_status",
    "pilot_recommendation_allowed",
    "official_recommendation_allowed",
    "machine_learning_used_for_recommendation",
    "reason_code",
    "reason_codes",
    "warning_message",
    "area",
    "sales_time",
    "spot_options",
    "selected_spot",
    "limitations",
}
AREA_FIELDS = {
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
}
SALES_TIME_FIELDS = {
    "prediction_origin_at",
    "recommendation_target_at",
    "horizon_minutes",
    "display_mode",
}


def spot_options(area_code: str) -> list[dict[str, object]]:
    return [
        {
            "spot_option_id": f"{area_code}-OPT-{order:02d}",
            "spot_name": f"Spot {order}",
            "spot_type": "TRANSIT_EXIT",
            "address": f"Address {order}",
            "latitude": f"37.50{order}",
            "longitude": f"127.00{order}",
            "pin_scope": "TRANSIT_EXIT_PIN",
            "spot_role": "USER_SELECTABLE_OPTION",
            "spot_selection_mode": "USER_CHOICE",
            "display_order": order,
            "field_verification_status": "UNAVAILABLE",
            "operational_suitability_status": "NOT_VERIFIED",
            "limitations": "현장·운영 적합성 미검증",
        }
        for order in (1, 2, 3)
    ]


def available_result(horizon: int, area_code: str = "POI014") -> dict[str, object]:
    return {
        "horizon_minutes": horizon,
        "recommendation_status": "AVAILABLE",
        "freshness_status": "FRESH",
        "official_recommendation_allowed": False,
        "pilot_recommendation_allowed": True,
        "reason_code": None,
        "reason_codes": ("FRESH_RUNTIME_SNAPSHOT",),
        "warning_message": None,
        "recommendation": {
            "recommendation_type": "AREA",
            "prediction_scope": "AREA",
            "recommendation_basis": "SEOUL_OFFICIAL_FORECAST",
            "recommendation_forecast_source": "SEOUL_OFFICIAL_FORECAST",
            "machine_learning_used_for_recommendation": False,
            "source_collection_run_id": "source-run-1",
            "area_code": area_code,
            "area_name": "강남역",
            "prediction_origin_at": "2026-07-29T12:00:00+09:00",
            "prediction_target_at": f"2026-07-29T{13 if horizon == 60 else 15}:00:00+09:00",
            "recommendation_target_at": f"2026-07-29T{13 if horizon == 60 else 15}:00:00+09:00",
            "horizon_minutes": horizon,
            "current_population_min": 90.0,
            "current_population_max": 110.0,
            "current_population_midpoint": 100.0,
            "forecast_population_min": 115.0,
            "forecast_population_max": 135.0,
            "forecast_population_midpoint": 125.0,
            "expected_population_change": 25.0,
            "expected_population_change_rate": 0.25,
            "spot_id": None,
            "fallback_reason": None,
            "spot_selection_mode": "USER_CHOICE",
            "spot_auto_recommendation": False,
            "user_selected_spot_id": None,
            "spot_options": spot_options(area_code),
        },
    }


def unavailable_result(horizon: int) -> dict[str, object]:
    return {
        "horizon_minutes": horizon,
        "recommendation_status": "UNAVAILABLE",
        "freshness_status": "FRESH",
        "official_recommendation_allowed": False,
        "pilot_recommendation_allowed": False,
        "reason_code": "NO_POSITIVE_AREA_OPPORTUNITY",
        "reason_codes": ("NO_POSITIVE_AREA_OPPORTUNITY",),
        "warning_message": None,
        "recommendation": None,
    }


class PilotRecommendationServiceTests(unittest.TestCase):
    def call_service(
        self,
        *,
        horizon: object = 60,
        selected_spot_option_id: object = None,
        core_result: dict[str, object] | None = None,
    ) -> dict[str, object]:
        result = (
            available_result(int(horizon))
            if core_result is None
            else core_result
        )
        with mock.patch.object(
            pilot_area_recommendation,
            "build_pilot_area_recommendations",
            return_value={
                60: available_result(60),
                180: available_result(180),
                int(horizon): result,
            },
        ):
            return pilot_recommendation_service.build_pilot_recommendation_view_model(
                current_path=Path("current.csv"),
                forecast_path=Path("forecast.csv"),
                spot_options_path=Path("spots.csv"),
                horizon_minutes=horizon,
                selected_spot_option_id=selected_spot_option_id,
            )

    def test_60_minute_result_is_available_before_selection(self) -> None:
        view = self.call_service()

        self.assertEqual(set(view), VIEW_FIELDS)
        self.assertEqual(view["view_status"], "AVAILABLE_UNSELECTED")
        self.assertEqual(set(view["area"]), AREA_FIELDS)
        self.assertEqual(view["area"]["area_code"], "POI014")
        self.assertEqual(set(view["sales_time"]), SALES_TIME_FIELDS)
        self.assertEqual(view["sales_time"]["horizon_minutes"], 60)
        self.assertIsNone(view["selected_spot"])

    def test_180_minute_result_returns_the_selected_spot(self) -> None:
        view = self.call_service(
            horizon=180,
            selected_spot_option_id="POI014-OPT-02",
        )

        self.assertEqual(view["view_status"], "AVAILABLE_SELECTED")
        self.assertEqual(view["horizon_minutes"], 180)
        self.assertEqual(view["selected_spot"]["spot_option_id"], "POI014-OPT-02")

    def test_no_recommendation_preserves_core_reason(self) -> None:
        view = self.call_service(core_result=unavailable_result(60))

        self.assertEqual(view["view_status"], "NO_RECOMMENDATION")
        self.assertEqual(view["reason_code"], "NO_POSITIVE_AREA_OPPORTUNITY")
        self.assertEqual(view["reason_codes"], ["NO_POSITIVE_AREA_OPPORTUNITY"])
        self.assertIsNone(view["area"])
        self.assertIsNone(view["sales_time"])
        self.assertEqual(view["spot_options"], [])

    def test_non_current_spot_ids_are_invalid_selections(self) -> None:
        for selected in ("POI072-OPT-01", "DOES-NOT-EXIST"):
            with self.subTest(selected=selected):
                view = self.call_service(selected_spot_option_id=selected)
                self.assertEqual(view["view_status"], "INVALID_SELECTION")
                self.assertEqual(view["reason_code"], "INVALID_SELECTION")
                self.assertIsNone(view["selected_spot"])
                self.assertEqual(len(view["spot_options"]), 3)

    def test_selection_is_invalid_when_recommendation_is_unavailable(self) -> None:
        view = self.call_service(
            core_result=unavailable_result(60),
            selected_spot_option_id="POI014-OPT-01",
        )

        self.assertEqual(view["view_status"], "INVALID_SELECTION")
        self.assertIn("NO_POSITIVE_AREA_OPPORTUNITY", view["reason_codes"])
        self.assertIn("INVALID_SELECTION", view["reason_codes"])

    def test_spot_options_remain_three_unranked_user_choices(self) -> None:
        view = self.call_service(selected_spot_option_id="POI014-OPT-01")

        self.assertEqual(len(view["spot_options"]), 3)
        forbidden = {
            "spot_rank",
            "spot_score",
            "spot_recommendation_reason",
            "spot_population",
            "spot_congestion",
            "default_spot",
        }
        self.assertTrue(
            all(forbidden.isdisjoint(option) for option in view["spot_options"])
        )
        self.assertTrue(forbidden.isdisjoint(view["selected_spot"]))

    def test_sales_time_is_a_forecast_point_not_an_invented_interval(self) -> None:
        sales_time = self.call_service()["sales_time"]

        self.assertEqual(sales_time["display_mode"], "FORECAST_TARGET_POINT")
        self.assertNotIn("sales_start_at", sales_time)
        self.assertNotIn("sales_end_at", sales_time)

    def test_view_model_is_json_serializable_without_nan(self) -> None:
        view = self.call_service(selected_spot_option_id="POI014-OPT-03")

        encoded = json.dumps(view, allow_nan=False)
        self.assertEqual(json.loads(encoded), view)

    def test_invalid_horizon_is_bounded_before_core_execution(self) -> None:
        for invalid in (30, "60", 60.0, True):
            with self.subTest(invalid=invalid), mock.patch.object(
                pilot_area_recommendation,
                "build_pilot_area_recommendations",
            ) as core:
                view = pilot_recommendation_service.build_pilot_recommendation_view_model(
                    current_path=Path("current.csv"),
                    forecast_path=Path("forecast.csv"),
                    spot_options_path=Path("spots.csv"),
                    horizon_minutes=invalid,
                )
                self.assertEqual(view["view_status"], "INPUT_INVALID")
                self.assertEqual(view["reason_code"], "INVALID_HORIZON")
                self.assertIsNone(view["horizon_minutes"])
                core.assert_not_called()

    def test_non_string_selection_is_input_invalid(self) -> None:
        view = self.call_service(selected_spot_option_id=123)

        self.assertEqual(view["view_status"], "INPUT_INVALID")
        self.assertEqual(view["reason_code"], "INPUT_INVALID")

    def test_known_core_input_error_does_not_expose_path_or_exception(self) -> None:
        with mock.patch.object(
            pilot_area_recommendation,
            "build_pilot_area_recommendations",
            side_effect=pilot_area_recommendation.PilotAreaRecommendationError(
                "pilot_area_recommendation_error: input_invalid"
            ),
        ):
            view = pilot_recommendation_service.build_pilot_recommendation_view_model(
                current_path=Path("/private/user/current.csv"),
                forecast_path=Path("/private/user/forecast.csv"),
                spot_options_path=Path("/private/user/spots.csv"),
                horizon_minutes=60,
            )

        rendered = json.dumps(view)
        self.assertEqual(view["view_status"], "INPUT_INVALID")
        self.assertNotIn("/private/", rendered)
        self.assertNotIn("pilot_area_recommendation_error", rendered)

    def test_unexpected_core_error_is_replaced_with_bounded_service_error(self) -> None:
        with mock.patch.object(
            pilot_area_recommendation,
            "build_pilot_area_recommendations",
            side_effect=RuntimeError("/private/user/secret.csv"),
        ):
            with self.assertRaisesRegex(
                pilot_recommendation_service.PilotRecommendationServiceError,
                "^pilot_recommendation_service_error: execution_failed$",
            ) as captured:
                pilot_recommendation_service.build_pilot_recommendation_view_model(
                    current_path=Path("current.csv"),
                    forecast_path=Path("forecast.csv"),
                    spot_options_path=Path("spots.csv"),
                    horizon_minutes=60,
                )

        self.assertNotIn("/private/", str(captured.exception))

    def test_official_recommendation_and_machine_learning_remain_disabled(self) -> None:
        view = self.call_service()

        self.assertFalse(view["official_recommendation_allowed"])
        self.assertFalse(view["machine_learning_used_for_recommendation"])

    def test_core_safety_flags_cannot_be_laundered_by_the_service(self) -> None:
        for field, value in (
            ("official_recommendation_allowed", True),
            ("machine_learning_used_for_recommendation", True),
        ):
            with self.subTest(field=field):
                result = available_result(60)
                if field == "official_recommendation_allowed":
                    result[field] = value
                else:
                    result["recommendation"][field] = value
                with self.assertRaisesRegex(
                    pilot_recommendation_service.PilotRecommendationServiceError,
                    "contract_invalid",
                ):
                    self.call_service(core_result=result)

    def test_core_area_and_spot_contract_regressions_are_rejected(self) -> None:
        mutations = (
            ("prediction_scope", "SPOT"),
            ("recommendation_basis", "UNAPPROVED_SOURCE"),
            ("recommendation_forecast_source", "UNAPPROVED_SOURCE"),
            ("spot_id", "POI014-OPT-01"),
            ("fallback_reason", "UNAPPROVED_FALLBACK"),
            ("user_selected_spot_id", "POI014-OPT-01"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                result = available_result(60)
                result["recommendation"][field] = value
                with self.assertRaisesRegex(
                    pilot_recommendation_service.PilotRecommendationServiceError,
                    "contract_invalid",
                ):
                    self.call_service(core_result=result)

        for mutation in ("other_area", "forbidden_field"):
            with self.subTest(mutation=mutation):
                result = available_result(60)
                first = result["recommendation"]["spot_options"][0]
                if mutation == "other_area":
                    first["spot_option_id"] = "POI072-OPT-01"
                else:
                    first["spot_rank"] = 1
                with self.assertRaisesRegex(
                    pilot_recommendation_service.PilotRecommendationServiceError,
                    "contract_invalid",
                ):
                    self.call_service(core_result=result)

    def test_non_json_values_and_mismatched_horizon_are_rejected(self) -> None:
        for value in (Path("not-json"), float("nan")):
            with self.subTest(value=repr(value)):
                result = available_result(60)
                result["recommendation"]["current_population_min"] = value
                with self.assertRaisesRegex(
                    pilot_recommendation_service.PilotRecommendationServiceError,
                    "contract_invalid",
                ):
                    self.call_service(core_result=result)

        with self.assertRaisesRegex(
            pilot_recommendation_service.PilotRecommendationServiceError,
            "contract_invalid",
        ):
            self.call_service(core_result=unavailable_result(180))

    def test_core_is_called_exactly_once(self) -> None:
        with mock.patch.object(
            pilot_area_recommendation,
            "build_pilot_area_recommendations",
            return_value={60: available_result(60), 180: available_result(180)},
        ) as core:
            pilot_recommendation_service.build_pilot_recommendation_view_model(
                current_path=Path("current.csv"),
                forecast_path=Path("forecast.csv"),
                spot_options_path=Path("spots.csv"),
                horizon_minutes=60,
            )

        core.assert_called_once_with(
            current_path=Path("current.csv"),
            forecast_path=Path("forecast.csv"),
            spot_options_path=Path("spots.csv"),
        )

    def test_public_service_uses_real_core_without_writing_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current_path = root / "current.csv"
            forecast_path = root / "forecast.csv"
            current, forecast = source_rows(changes_60={"POI014": 25})
            write_csv(current_path, current, CURRENT_FIELDS)
            write_csv(forecast_path, forecast, FORECAST_FIELDS)
            before = {path.name for path in root.iterdir()}

            with mock.patch.object(
                eg8d_area_priority,
                "_runtime_now",
                return_value=FRESH_EVALUATION_TIME,
            ):
                view = pilot_recommendation_service.build_pilot_recommendation_view_model(
                    current_path=current_path,
                    forecast_path=forecast_path,
                    spot_options_path=pilot_spot_options.PILOT_SPOT_OPTIONS_PATH,
                    horizon_minutes=60,
                )

            self.assertEqual(view["view_status"], "AVAILABLE_UNSELECTED")
            self.assertEqual(json.loads(json.dumps(view, allow_nan=False)), view)
            self.assertEqual({path.name for path in root.iterdir()}, before)

    def test_module_adds_no_web_framework_database_or_ml_dependency(self) -> None:
        source = inspect.getsource(pilot_recommendation_service).lower()

        self.assertEqual(
            set(
                inspect.signature(
                    pilot_recommendation_service.build_pilot_recommendation_view_model
                ).parameters
            ),
            {
                "current_path",
                "forecast_path",
                "spot_options_path",
                "horizon_minutes",
                "selected_spot_option_id",
            },
        )

        for forbidden in (
            "fastapi",
            "flask",
            "django",
            "sqlalchemy",
            "sqlite3",
            "sklearn",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
