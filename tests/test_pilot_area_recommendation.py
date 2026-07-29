from __future__ import annotations

import csv
import inspect
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from freshmanager import (
    eg6b,
    eg8a,
    eg8d_area_priority,
    pilot_area_recommendation,
    pilot_spot_options,
)


SOURCE_RUN_ID = "source-run-1"
ORIGIN = datetime(2026, 7, 29, 12, 0, tzinfo=eg8a.SEOUL)
FRESH_EVALUATION_TIME = ORIGIN + timedelta(minutes=15)
PILOT_CODES = tuple(pilot_spot_options.PILOT_AREA_NAMES)
NON_PILOT_CODE = next(
    code for code in eg6b.EG6B_AREA_CODES if code not in PILOT_CODES
)
SPOT_OPTION_FIELDS = {
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
}

CURRENT_FIELDS = (
    "collection_run_id",
    "called_at",
    "observed_at",
    "area_code_requested",
    "area_code_returned",
    "area_name",
    "congestion_level",
    "population_min",
    "population_max",
)
FORECAST_FIELDS = (
    "collection_run_id",
    "called_at",
    "observed_at",
    "forecast_at",
    "area_code_requested",
    "area_code_returned",
    "area_name",
    "forecast_congestion_level",
    "forecast_population_min",
    "forecast_population_max",
)


def area_name(area_code: str) -> str:
    return pilot_spot_options.PILOT_AREA_NAMES.get(area_code, f"Area {area_code}")


def source_rows(
    *,
    changes_60: dict[str, float] | None = None,
    changes_180: dict[str, float] | None = None,
    current_midpoints: dict[str, float] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    changes = {
        60: changes_60 or {},
        180: changes_180 or {},
    }
    current_midpoints = current_midpoints or {}
    current: list[dict[str, str]] = []
    forecast: list[dict[str, str]] = []
    observed_at = ORIGIN.strftime("%Y-%m-%d %H:%M")
    for area_code in eg6b.EG6B_AREA_CODES:
        midpoint = current_midpoints.get(area_code, 100.0)
        current.append(
            {
                "collection_run_id": SOURCE_RUN_ID,
                "called_at": observed_at,
                "observed_at": observed_at,
                "area_code_requested": area_code,
                "area_code_returned": area_code,
                "area_name": area_name(area_code),
                "congestion_level": "보통",
                "population_min": str(midpoint - 10),
                "population_max": str(midpoint + 10),
            }
        )
        for horizon in eg8d_area_priority.HORIZONS:
            change = changes[horizon].get(area_code, -1.0)
            forecast_midpoint = midpoint + change
            forecast.append(
                {
                    "collection_run_id": SOURCE_RUN_ID,
                    "called_at": observed_at,
                    "observed_at": observed_at,
                    "forecast_at": (ORIGIN + timedelta(minutes=horizon)).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "area_code_requested": area_code,
                    "area_code_returned": area_code,
                    "area_name": area_name(area_code),
                    "forecast_congestion_level": "보통",
                    "forecast_population_min": str(forecast_midpoint - 10),
                    "forecast_population_max": str(forecast_midpoint + 10),
                }
            )
    return current, forecast


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
    fieldnames: tuple[str, ...],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class PilotAreaRecommendationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.current_path = self.root / "population_current_v3.csv"
        self.forecast_path = self.root / "population_forecast_v3.csv"
        self.spot_options_path = pilot_spot_options.PILOT_SPOT_OPTIONS_PATH

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_core(
        self,
        *,
        changes_60: dict[str, float] | None = None,
        changes_180: dict[str, float] | None = None,
        current_midpoints: dict[str, float] | None = None,
        evaluation_time: datetime = FRESH_EVALUATION_TIME,
        forecast_rows_override: list[dict[str, str]] | None = None,
        spot_options_path: Path | None = None,
    ) -> dict[int, dict[str, object]]:
        current, forecast = source_rows(
            changes_60=changes_60,
            changes_180=changes_180,
            current_midpoints=current_midpoints,
        )
        write_csv(self.current_path, current, CURRENT_FIELDS)
        write_csv(
            self.forecast_path,
            forecast if forecast_rows_override is None else forecast_rows_override,
            FORECAST_FIELDS,
        )
        with mock.patch.object(
            eg8d_area_priority, "_runtime_now", return_value=evaluation_time
        ):
            return pilot_area_recommendation.build_pilot_area_recommendations(
                current_path=self.current_path,
                forecast_path=self.forecast_path,
                spot_options_path=spot_options_path or self.spot_options_path,
            )

    def runtime_evaluation(
        self,
        *,
        changes_60: dict[str, float] | None = None,
    ) -> eg8d_area_priority._InMemoryAreaPriorityEvaluation:
        current, forecast = source_rows(changes_60=changes_60)
        write_csv(self.current_path, current, CURRENT_FIELDS)
        write_csv(self.forecast_path, forecast, FORECAST_FIELDS)
        with mock.patch.object(
            eg8d_area_priority,
            "_runtime_now",
            return_value=FRESH_EVALUATION_TIME,
        ):
            return eg8d_area_priority._evaluate_runtime_area_priority_in_memory(
                current_path=self.current_path,
                forecast_path=self.forecast_path,
            )

    def test_public_api_owns_runtime_context_and_performs_no_publication(self) -> None:
        parameters = inspect.signature(
            pilot_area_recommendation.build_pilot_area_recommendations
        ).parameters
        self.assertEqual(
            set(parameters), {"current_path", "forecast_path", "spot_options_path"}
        )
        self.assertNotIn("evaluation_time", parameters)
        self.assertNotIn("evaluation_mode", parameters)
        self.assertNotIn("output_root", parameters)
        common_parameters = inspect.signature(
            eg8d_area_priority._evaluate_area_priority_in_memory
        ).parameters
        self.assertIn("execution_context", common_parameters)
        self.assertNotIn("evaluation_time", common_parameters)
        self.assertNotIn("evaluation_mode", common_parameters)
        self.assertEqual(
            set(
                inspect.signature(
                    eg8d_area_priority._evaluate_runtime_area_priority_in_memory
                ).parameters
            ),
            {"current_path", "forecast_path"},
        )
        self.assertEqual(
            (
                eg8d_area_priority.LOCKED_DATASET_RUN_ID,
                eg8d_area_priority.LOCKED_MANIFEST_SHA256,
                eg8d_area_priority.LOCKED_CURRENT_SHA256,
                eg8d_area_priority.LOCKED_FORECAST_SHA256,
            ),
            (
                "eg8c-20260727T153257-kst",
                "388a5e6649e6e23d05a442ae9b4f8d0857f8ea382011c2ff07c0af64aae42771",
                "28521ff8b52ff1697fcf8eb93da4a5faaf2f625a69fdf117e601f8893d84d719",
                "a5c4aaa7d711d289ee05d4ed6903b91f4ea725252ff3b6bc8890b62146441649",
            ),
        )
        self.assertNotIn("current_population_min", eg8d_area_priority.CSV_FIELDS)
        self.assertNotIn("forecast_population_min", eg8d_area_priority.CSV_FIELDS)
        with mock.patch.object(
            eg8d_area_priority,
            "_publish",
            side_effect=AssertionError("publication must not be called"),
        ) as publish:
            self.run_core(changes_60={"POI014": 25})
        publish.assert_not_called()

    def test_compares_only_five_pilot_areas_and_keeps_horizons_independent(self) -> None:
        results = self.run_core(
            changes_60={"POI014": 30, NON_PILOT_CODE: 10_000},
            changes_180={"POI072": 40, NON_PILOT_CODE: 20_000},
        )

        self.assertEqual(set(results), {60, 180})
        self.assertEqual(results[60]["recommendation"]["area_code"], "POI014")
        self.assertEqual(results[180]["recommendation"]["area_code"], "POI072")
        for horizon in (60, 180):
            self.assertEqual(results[horizon]["recommendation_status"], "AVAILABLE")
            self.assertIn("freshness_status", results[horizon])
            self.assertIn("reason_codes", results[horizon])
            self.assertIn("warning_message", results[horizon])
            recommendation = results[horizon]["recommendation"]
            self.assertIn(recommendation["area_code"], PILOT_CODES)
            self.assertEqual(recommendation["horizon_minutes"], horizon)

    def test_selects_only_positive_change_and_returns_no_recommendation_otherwise(self) -> None:
        results = self.run_core(
            changes_60={"POI014": 1},
            changes_180={code: 0 for code in PILOT_CODES},
        )

        self.assertGreater(
            results[60]["recommendation"]["expected_population_change"], 0
        )
        self.assertIsNone(results[180]["recommendation"])
        self.assertEqual(results[180]["recommendation_status"], "UNAVAILABLE")
        self.assertFalse(results[180]["pilot_recommendation_allowed"])
        self.assertEqual(
            results[180]["reason_code"], "NO_POSITIVE_AREA_OPPORTUNITY"
        )

    def test_reuses_all_three_existing_tie_breaks(self) -> None:
        cases = (
            (
                {"POI032": 20, "POI088": 10},
                {},
                "POI032",
            ),
            (
                {"POI032": 20, "POI088": 20},
                {"POI032": 100, "POI088": 120},
                "POI088",
            ),
            (
                {"POI014": 20, "POI025": 20},
                {"POI014": 100, "POI025": 100},
                "POI014",
            ),
        )
        for changes, midpoints, expected in cases:
            with self.subTest(expected=expected):
                results = self.run_core(
                    changes_60=changes,
                    current_midpoints=midpoints,
                )
                self.assertEqual(
                    results[60]["recommendation"]["area_code"], expected
                )

    def test_fresh_runtime_recommendation_contains_ranges_and_unranked_spot_choices(self) -> None:
        results = self.run_core(changes_60={"POI014": 25})
        horizon = results[60]
        recommendation = horizon["recommendation"]

        self.assertTrue(horizon["pilot_recommendation_allowed"])
        self.assertEqual(horizon["freshness_status"], "FRESH")
        self.assertFalse(horizon["official_recommendation_allowed"])
        self.assertEqual(horizon["recommendation_status"], "AVAILABLE")
        self.assertIn("FRESH_THRESHOLDS_MET", horizon["reason_codes"])
        self.assertIn("EXPECTED_POPULATION_INCREASE", horizon["reason_codes"])
        self.assertEqual(recommendation["recommendation_type"], "AREA")
        self.assertEqual(
            recommendation["recommendation_basis"], "SEOUL_OFFICIAL_FORECAST"
        )
        self.assertEqual(
            recommendation["recommendation_forecast_source"],
            "SEOUL_OFFICIAL_FORECAST",
        )
        self.assertFalse(recommendation["machine_learning_used_for_recommendation"])
        self.assertEqual(recommendation["source_collection_run_id"], SOURCE_RUN_ID)
        self.assertEqual(
            recommendation["recommendation_target_at"],
            "2026-07-29T13:00:00+09:00",
        )
        self.assertEqual(recommendation["expected_population_change_rate"], 0.25)
        self.assertEqual(recommendation["current_population_min"], 90)
        self.assertEqual(recommendation["current_population_max"], 110)
        self.assertEqual(recommendation["forecast_population_min"], 115)
        self.assertEqual(recommendation["forecast_population_max"], 135)
        self.assertEqual(recommendation["spot_selection_mode"], "USER_CHOICE")
        self.assertFalse(recommendation["spot_auto_recommendation"])
        self.assertIsNone(recommendation["user_selected_spot_id"])
        self.assertEqual(len(recommendation["spot_options"]), 3)
        self.assertEqual(
            [option["display_order"] for option in recommendation["spot_options"]],
            [1, 2, 3],
        )
        self.assertTrue(
            all(set(option) == SPOT_OPTION_FIELDS for option in recommendation["spot_options"])
        )
        forbidden = {
            "spot_rank",
            "rank",
            "default",
            "recommended",
            "expected_population_change",
            "forecast_population_midpoint",
            "congestion_level",
        }
        self.assertTrue(
            all(forbidden.isdisjoint(option) for option in recommendation["spot_options"])
        )

    def test_degraded_and_stale_horizons_do_not_recommend(self) -> None:
        degraded = self.run_core(
            changes_60={"POI014": 25},
            changes_180={"POI014": 25},
            evaluation_time=ORIGIN + timedelta(minutes=30),
        )
        stale = self.run_core(
            changes_60={"POI014": 25},
            changes_180={"POI014": 25},
            evaluation_time=ORIGIN + timedelta(minutes=61),
        )

        self.assertEqual(degraded[60]["freshness_status"], "DEGRADED")
        self.assertEqual(degraded[60]["recommendation_status"], "UNAVAILABLE")
        self.assertIsNotNone(degraded[60]["warning_message"])
        self.assertIsNone(degraded[60]["recommendation"])
        self.assertFalse(degraded[60]["pilot_recommendation_allowed"])
        self.assertEqual(stale[60]["freshness_status"], "STALE_BLOCKED")
        self.assertIsNone(stale[60]["recommendation"])
        self.assertEqual(stale[180]["freshness_status"], "STALE_BLOCKED")
        self.assertIsNone(stale[180]["recommendation"])

    def test_freshness_is_independent_per_horizon(self) -> None:
        results = self.run_core(
            changes_60={"POI014": 25},
            changes_180={"POI072": 25},
            evaluation_time=ORIGIN + timedelta(minutes=31),
        )

        self.assertEqual(results[60]["freshness_status"], "STALE_BLOCKED")
        self.assertIsNone(results[60]["recommendation"])
        self.assertEqual(results[180]["freshness_status"], "DEGRADED")
        self.assertIsNone(results[180]["recommendation"])

    def test_area_result_display_gate_is_required(self) -> None:
        evaluation = self.runtime_evaluation(changes_60={"POI014": 25})
        blocked_60 = replace(
            evaluation.freshness_gate.horizons[60],
            area_result_display_allowed=False,
        )
        gate = replace(
            evaluation.freshness_gate,
            horizons={**evaluation.freshness_gate.horizons, 60: blocked_60},
        )
        blocked = replace(evaluation, freshness_gate=gate)
        options = pilot_spot_options.load_pilot_spot_options(self.spot_options_path)

        results = pilot_area_recommendation._build_horizon_recommendations(
            blocked, options
        )

        self.assertEqual(results[60]["recommendation_status"], "UNAVAILABLE")
        self.assertFalse(results[60]["pilot_recommendation_allowed"])
        self.assertIsNone(results[60]["recommendation"])

    def test_area_recommendation_does_not_require_spot_evaluation_gate(self) -> None:
        evaluation = self.runtime_evaluation(changes_60={"POI014": 25})
        area_only_60 = replace(
            evaluation.freshness_gate.horizons[60],
            spot_evaluation_allowed=False,
        )
        gate = replace(
            evaluation.freshness_gate,
            horizons={**evaluation.freshness_gate.horizons, 60: area_only_60},
        )
        area_only = replace(evaluation, freshness_gate=gate)
        options = pilot_spot_options.load_pilot_spot_options(self.spot_options_path)

        results = pilot_area_recommendation._build_horizon_recommendations(
            area_only, options
        )

        self.assertEqual(results[60]["recommendation_status"], "AVAILABLE")
        self.assertTrue(results[60]["pilot_recommendation_allowed"])
        self.assertEqual(results[60]["recommendation"]["recommendation_type"], "AREA")

    def test_current_only_input_does_not_recommend(self) -> None:
        results = self.run_core(
            changes_60={"POI014": 25},
            forecast_rows_override=[],
        )

        for horizon in (60, 180):
            self.assertEqual(results[horizon]["recommendation_status"], "UNAVAILABLE")
            self.assertIsNone(results[horizon]["recommendation"])
            self.assertFalse(results[horizon]["pilot_recommendation_allowed"])
            self.assertIn("NO_COMPLETE_SNAPSHOT", results[horizon]["reason_codes"])

    def test_historical_and_synthetic_results_are_never_recommendations(self) -> None:
        evaluation = self.runtime_evaluation(changes_60={"POI014": 25})
        options = pilot_spot_options.load_pilot_spot_options(self.spot_options_path)
        for mode in ("HISTORICAL_AUDIT", "SYNTHETIC_VALIDATION"):
            gate = replace(
                evaluation.freshness_gate,
                evaluation_mode=mode,
                user_display_eligible=False,
            )
            historical = replace(evaluation, freshness_gate=gate)
            results = pilot_area_recommendation._build_horizon_recommendations(
                historical, options
            )
            for horizon in (60, 180):
                self.assertIsNone(results[horizon]["recommendation"])
                self.assertFalse(results[horizon]["pilot_recommendation_allowed"])

    def test_bad_area_spot_link_is_blocked(self) -> None:
        bad_spot_path = self.root / "pilot_spot_options.csv"
        with self.spot_options_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["pilot_area_name"] = "Wrong Area"
        write_csv(
            bad_spot_path,
            rows,
            pilot_spot_options.PILOT_SPOT_OPTION_HEADERS,
        )

        with self.assertRaises(
            pilot_area_recommendation.PilotAreaRecommendationError
        ):
            self.run_core(
                changes_60={"POI032": 25},
                spot_options_path=bad_spot_path,
            )

    def test_short_csv_row_returns_a_bounded_contract_error(self) -> None:
        current, forecast = source_rows(changes_60={"POI014": 25})
        write_csv(self.current_path, current, CURRENT_FIELDS)
        write_csv(self.forecast_path, forecast, FORECAST_FIELDS)
        lines = self.current_path.read_text(encoding="utf-8").splitlines()
        lines[1] = lines[1].rsplit(",", 1)[0]
        self.current_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with mock.patch.object(
            eg8d_area_priority,
            "_runtime_now",
            return_value=FRESH_EVALUATION_TIME,
        ), self.assertRaisesRegex(
            pilot_area_recommendation.PilotAreaRecommendationError,
            r"^pilot_area_recommendation_error: input_invalid$",
        ):
            pilot_area_recommendation.build_pilot_area_recommendations(
                current_path=self.current_path,
                forecast_path=self.forecast_path,
                spot_options_path=self.spot_options_path,
            )


if __name__ == "__main__":
    unittest.main()
