from __future__ import annotations

import csv
import hashlib
import inspect
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from freshmanager import eg6b, eg8a, eg8d_area_priority


SOURCE_RUN_ID = "source-run-1"
RESULT_RUN_ID = "eg8d-area-priority-20260727T160000-kst"
GENERATED_AT = datetime(2026, 7, 27, 16, 0, tzinfo=eg8a.SEOUL)


def current_rows() -> list[dict[str, str]]:
    return [
        {
            "collection_run_id": SOURCE_RUN_ID,
            "called_at": "2026-07-27 14:00",
            "observed_at": "2026-07-27 14:00",
            "area_code_requested": area_code,
            "area_code_returned": area_code,
            "area_name": f"Area {index:02d}",
            "congestion_level": "보통",
            "population_min": str(100 + index * 10),
            "population_max": str(120 + index * 10),
        }
        for index, area_code in enumerate(eg6b.EG6B_AREA_CODES)
    ]


def forecast_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, area_code in enumerate(eg6b.EG6B_AREA_CODES):
        current_mid = 110 + index * 10
        for horizon, target in ((60, "2026-07-27 15:00"), (180, "2026-07-27 17:00")):
            future_mid = current_mid + index - (5 if horizon == 60 else 2)
            rows.append(
                {
                    "collection_run_id": SOURCE_RUN_ID,
                    "called_at": "2026-07-27 14:00",
                    "observed_at": "2026-07-27 14:00",
                    "forecast_at": target,
                    "area_code_requested": area_code,
                    "area_code_returned": area_code,
                    "area_name": f"Area {index:02d}",
                    "forecast_congestion_level": "보통",
                    "forecast_population_min": str(future_mid - 10),
                    "forecast_population_max": str(future_mid + 10),
                }
            )
    return rows


def source_run_rows(
    run_id: str,
    origin: datetime,
    *,
    forecast_adjustment: int = 0,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    observed_at = origin.strftime("%Y-%m-%d %H:%M")
    current = current_rows()
    forecasts = forecast_rows()
    for row in current:
        row["collection_run_id"] = run_id
        row["called_at"] = observed_at
        row["observed_at"] = observed_at
    for index, row in enumerate(forecasts):
        horizon = 60 if index % 2 == 0 else 180
        row["collection_run_id"] = run_id
        row["called_at"] = observed_at
        row["observed_at"] = observed_at
        row["forecast_at"] = (origin + timedelta(minutes=horizon)).strftime("%Y-%m-%d %H:%M")
        row["forecast_population_min"] = str(int(row["forecast_population_min"]) + forecast_adjustment)
        row["forecast_population_max"] = str(int(row["forecast_population_max"]) + forecast_adjustment)
    return current, forecasts


def build_rows(
    current: list[dict[str, str]] | None = None,
    forecast: list[dict[str, str]] | None = None,
) -> tuple[eg8d_area_priority.AreaPriorityRow, ...]:
    return eg8d_area_priority._build_area_priority_rows(
        current or current_rows(),
        forecast or forecast_rows(),
        source_collection_run_id=SOURCE_RUN_ID,
        generated_at=GENERATED_AT,
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freshness_gate(
    *,
    evaluation_time: datetime = datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
    selected_at: datetime | None = datetime(2026, 7, 27, 14, 0, tzinfo=eg8a.SEOUL),
    latest_current_at: datetime | None = datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
    target_60: datetime | None = datetime(2026, 7, 27, 15, 0, tzinfo=eg8a.SEOUL),
    target_180: datetime | None = datetime(2026, 7, 27, 17, 0, tzinfo=eg8a.SEOUL),
    complete_snapshot_exists: bool = True,
    time_contract_valid: bool = True,
    evaluation_mode: str = "RUNTIME",
) -> eg8d_area_priority.FreshnessGateResult:
    return eg8d_area_priority.evaluate_horizon_freshness(
        evaluation_time=evaluation_time,
        selected_complete_observed_at=selected_at,
        latest_available_current_observed_at=latest_current_at,
        forecast_target_at_60m=target_60,
        forecast_target_at_180m=target_180,
        complete_snapshot_exists=complete_snapshot_exists,
        time_contract_valid=time_contract_valid,
        evaluation_mode=evaluation_mode,
    )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_locked_inputs(
    root: Path,
    *,
    current: list[dict[str, str]] | None = None,
    forecast: list[dict[str, str]] | None = None,
) -> tuple[Path, Path, Path, dict[str, str]]:
    current_path = root / "population_current_v3.csv"
    forecast_path = root / "population_forecast_v3.csv"
    manifest_path = root / "dataset_manifest.json"
    write_csv(current_path, current if current is not None else current_rows())
    write_csv(forecast_path, forecast if forecast is not None else forecast_rows())
    hashes = {"current": sha256(current_path), "forecast": sha256(forecast_path)}
    manifest = {
        "schema_version": "eg8c-output-manifest-v1",
        "eg8c_run_id": eg8d_area_priority.LOCKED_DATASET_RUN_ID,
        "input_artifacts": [
            {
                "logical_name": "population_current_v3",
                "sha256": hashes["current"],
                "byte_size": current_path.stat().st_size,
            },
            {
                "logical_name": "population_forecast_v3",
                "sha256": hashes["forecast"],
                "byte_size": forecast_path.stat().st_size,
            },
        ],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    hashes["manifest"] = sha256(manifest_path)
    return manifest_path, current_path, forecast_path, hashes


class AreaPrioritySourceSelectionTests(unittest.TestCase):
    def test_public_builder_does_not_accept_arbitrary_source_run_id(self) -> None:
        self.assertNotIn(
            "source_collection_run_id",
            inspect.signature(eg8d_area_priority.run_eg8d_area_priority).parameters,
        )

    def test_cli_does_not_accept_arbitrary_source_run_id(self) -> None:
        options = {
            option
            for action in eg8d_area_priority.build_parser()._actions
            for option in action.option_strings
        }
        self.assertNotIn("--source-collection-run-id", options)

    def test_public_runtime_builder_does_not_accept_evaluation_controls(self) -> None:
        parameters = inspect.signature(
            eg8d_area_priority.run_eg8d_area_priority
        ).parameters
        self.assertNotIn("evaluation_time", parameters)
        self.assertNotIn("evaluation_mode", parameters)

    def test_runtime_internal_path_accepts_no_execution_controls(self) -> None:
        runtime_path = getattr(
            eg8d_area_priority, "_run_runtime_eg8d_area_priority", None
        )
        self.assertIsNotNone(runtime_path)
        parameters = inspect.signature(runtime_path).parameters
        self.assertFalse(
            {
                "evaluation_time",
                "evaluation_mode",
                "validation_context",
                "operational_observation",
                "clock_source",
                "synthetic_validation",
            }
            & set(parameters)
        )

    def test_common_executor_accepts_only_a_fixed_execution_context(self) -> None:
        parameters = inspect.signature(
            eg8d_area_priority._execute_eg8d_area_priority
        ).parameters
        self.assertTrue(
            {
                "evaluation_time",
                "evaluation_mode",
                "validation_context",
                "operational_observation",
                "synthetic_validation",
                "clock_source",
                "operational_publication_allowed",
            }.isdisjoint(parameters)
        )
        self.assertIn("execution_context", parameters)

    def test_cli_does_not_accept_evaluation_controls(self) -> None:
        options = {
            option
            for action in eg8d_area_priority.build_parser()._actions
            for option in action.option_strings
        }
        self.assertNotIn("--evaluation-time", options)
        self.assertNotIn("--evaluation-mode", options)

    def test_single_complete_run_is_selected(self) -> None:
        current, forecasts = source_run_rows(SOURCE_RUN_ID, GENERATED_AT)

        selection = eg8d_area_priority._select_latest_complete_run(current, forecasts)

        self.assertEqual(selection.source_collection_run_id, SOURCE_RUN_ID)
        self.assertEqual(selection.canonical_timestamp, GENERATED_AT)
        self.assertEqual(selection.total_collection_run_count, 1)
        self.assertEqual(selection.complete_collection_run_count, 1)

    def test_latest_complete_run_is_selected_independent_of_input_order(self) -> None:
        old_current, old_forecasts = source_run_rows("old-run", GENERATED_AT - timedelta(minutes=5))
        new_current, new_forecasts = source_run_rows("new-run", GENERATED_AT)
        current = old_current + new_current
        forecasts = old_forecasts + new_forecasts

        forward = eg8d_area_priority._select_latest_complete_run(current, forecasts)
        reversed_input = eg8d_area_priority._select_latest_complete_run(
            list(reversed(current)), list(reversed(forecasts))
        )

        self.assertEqual(forward.source_collection_run_id, "new-run")
        self.assertEqual(reversed_input, forward)
        self.assertEqual(forward.total_collection_run_count, 2)
        self.assertEqual(forward.complete_collection_run_count, 2)

    def test_newer_incomplete_runs_are_excluded(self) -> None:
        old_current, old_forecasts = source_run_rows("old-complete", GENERATED_AT)
        for defect in ("area", "60", "180"):
            with self.subTest(defect=defect):
                new_current, new_forecasts = source_run_rows(
                    "new-incomplete", GENERATED_AT + timedelta(minutes=5)
                )
                if defect == "area":
                    new_current = new_current[1:]
                else:
                    target = (GENERATED_AT + timedelta(minutes=5, hours=int(defect) // 60)).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    new_forecasts = [row for row in new_forecasts if not (
                        row["area_code_requested"] == eg6b.EG6B_AREA_CODES[0]
                        and row["forecast_at"] == target
                    )]

                selection = eg8d_area_priority._select_latest_complete_run(
                    old_current + new_current, old_forecasts + new_forecasts
                )

                self.assertEqual(selection.source_collection_run_id, "old-complete")
                self.assertEqual(selection.complete_collection_run_count, 1)

    def test_duplicate_rows_make_the_newer_run_incomplete(self) -> None:
        old_current, old_forecasts = source_run_rows("old-complete", GENERATED_AT)
        for duplicate_kind in ("current", "forecast"):
            with self.subTest(duplicate_kind=duplicate_kind):
                new_current, new_forecasts = source_run_rows(
                    "new-duplicate", GENERATED_AT + timedelta(minutes=5)
                )
                if duplicate_kind == "current":
                    new_current.append(dict(new_current[0]))
                else:
                    new_forecasts.append(dict(new_forecasts[0]))

                selection = eg8d_area_priority._select_latest_complete_run(
                    old_current + new_current, old_forecasts + new_forecasts
                )

                self.assertEqual(selection.source_collection_run_id, "old-complete")

    def test_selection_is_independent_of_area_ranking_values(self) -> None:
        old_current, old_forecasts = source_run_rows(
            "old-better-result", GENERATED_AT, forecast_adjustment=10_000
        )
        new_current, new_forecasts = source_run_rows(
            "new-worse-result", GENERATED_AT + timedelta(minutes=5), forecast_adjustment=-50
        )

        selection = eg8d_area_priority._select_latest_complete_run(
            old_current + new_current, old_forecasts + new_forecasts
        )

        self.assertEqual(selection.source_collection_run_id, "new-worse-result")

    def test_no_complete_run_fails(self) -> None:
        current, forecasts = source_run_rows(SOURCE_RUN_ID, GENERATED_AT)

        with self.assertRaisesRegex(
            eg8d_area_priority.AreaPriorityContractError, "complete_run_not_found"
        ):
            eg8d_area_priority._select_latest_complete_run(current[1:], forecasts)

    def test_latest_canonical_timestamp_tie_fails(self) -> None:
        first_current, first_forecasts = source_run_rows("first-run", GENERATED_AT)
        second_current, second_forecasts = source_run_rows("second-run", GENERATED_AT)

        with self.assertRaisesRegex(
            eg8d_area_priority.AreaPriorityContractError, "latest_complete_run_tie"
        ):
            eg8d_area_priority._select_latest_complete_run(
                first_current + second_current, first_forecasts + second_forecasts
            )


class AreaPriorityCalculationTests(unittest.TestCase):
    def test_only_the_approved_thirteen_areas_are_processed(self) -> None:
        rows = build_rows()
        self.assertEqual({row.area_code for row in rows}, set(eg6b.EG6B_AREA_CODES))
        self.assertEqual(len(rows), 26)

    def test_sixty_and_one_hundred_eighty_minute_results_are_separate(self) -> None:
        rows = build_rows()
        self.assertEqual({row.horizon_minutes for row in rows}, {60, 180})
        self.assertEqual(sum(row.horizon_minutes == 60 for row in rows), 13)
        self.assertEqual(sum(row.horizon_minutes == 180 for row in rows), 13)

    def test_join_requires_the_source_collection_run_id(self) -> None:
        forecasts = forecast_rows()
        forecasts[0]["collection_run_id"] = "different-run"
        with self.assertRaisesRegex(eg8d_area_priority.AreaPriorityContractError, "forecast_missing"):
            build_rows(forecast=forecasts)

    def test_join_requires_the_area_code(self) -> None:
        forecasts = forecast_rows()
        forecasts[0]["area_code_requested"] = "POI999"
        forecasts[0]["area_code_returned"] = "POI999"
        with self.assertRaisesRegex(eg8d_area_priority.AreaPriorityContractError, "forecast_missing"):
            build_rows(forecast=forecasts)

    def test_join_requires_the_prediction_origin(self) -> None:
        forecasts = forecast_rows()
        forecasts[0]["observed_at"] = "2026-07-27 14:05"
        with self.assertRaisesRegex(
            eg8d_area_priority.AreaPriorityContractError, "forecast_origin_mismatch"
        ):
            build_rows(forecast=forecasts)

    def test_join_requires_the_prediction_target(self) -> None:
        forecasts = forecast_rows()
        forecasts[0]["forecast_at"] = "2026-07-27 15:05"
        with self.assertRaisesRegex(eg8d_area_priority.AreaPriorityContractError, "forecast_missing"):
            build_rows(forecast=forecasts)

    def test_missing_forecast_fails_without_substitution(self) -> None:
        with self.assertRaisesRegex(eg8d_area_priority.AreaPriorityContractError, "forecast_missing"):
            build_rows(forecast=forecast_rows()[1:])

    def test_duplicate_forecast_fails_without_arbitrary_selection(self) -> None:
        forecasts = forecast_rows()
        forecasts.append(dict(forecasts[0]))
        with self.assertRaisesRegex(eg8d_area_priority.AreaPriorityContractError, "forecast_duplicate"):
            build_rows(forecast=forecasts)

    def test_missing_population_is_not_replaced_with_zero(self) -> None:
        current = current_rows()
        current[0]["population_min"] = ""
        with self.assertRaisesRegex(eg8d_area_priority.AreaPriorityContractError, "population_invalid"):
            build_rows(current=current)

    def test_midpoints_and_expected_change_are_exact(self) -> None:
        row = next(row for row in build_rows() if row.area_code == eg6b.EG6B_AREA_CODES[0] and row.horizon_minutes == 60)
        self.assertEqual(row.current_population_midpoint, 110.0)
        self.assertEqual(row.forecast_population_midpoint, 105.0)
        self.assertEqual(row.expected_population_change, -5.0)

    def test_expected_change_rate_is_exact(self) -> None:
        row = next(row for row in build_rows() if row.area_code == eg6b.EG6B_AREA_CODES[1] and row.horizon_minutes == 60)
        self.assertAlmostEqual(row.expected_population_change_rate or 0.0, -4.0 / 120.0)

    def test_zero_current_midpoint_records_uncomputable_rate(self) -> None:
        current = current_rows()
        current[0]["population_min"] = "0"
        current[0]["population_max"] = "0"
        row = next(row for row in build_rows(current=current) if row.area_code == eg6b.EG6B_AREA_CODES[0] and row.horizon_minutes == 60)
        self.assertIsNone(row.expected_population_change_rate)
        self.assertEqual(row.input_validity, "CHANGE_RATE_UNCOMPUTABLE_CURRENT_ZERO")

    def test_positive_change_areas_are_ranked_before_nonpositive_areas(self) -> None:
        rows = [row for row in build_rows() if row.horizon_minutes == 60]
        positive_ranks = [row.opportunity_rank for row in rows if row.expected_population_change > 0]
        nonpositive_ranks = [row.opportunity_rank for row in rows if row.expected_population_change <= 0]
        self.assertLess(max(positive_ranks), min(nonpositive_ranks))

    def test_change_amount_descending_determines_rank(self) -> None:
        rows = sorted((row for row in build_rows() if row.horizon_minutes == 60), key=lambda row: row.opportunity_rank)
        positive_changes = [row.expected_population_change for row in rows if row.expected_population_change > 0]
        self.assertEqual(positive_changes, sorted(positive_changes, reverse=True))

    def test_future_population_breaks_equal_change_ties(self) -> None:
        forecasts = forecast_rows()
        for row in forecasts:
            if row["forecast_at"] == "2026-07-27 15:00" and row["area_code_requested"] in eg6b.EG6B_AREA_CODES[:2]:
                index = eg6b.EG6B_AREA_CODES.index(row["area_code_requested"])
                current_mid = 110 + index * 10
                row["forecast_population_min"] = str(current_mid)
                row["forecast_population_max"] = str(current_mid + 20)
        rows = {row.area_code: row for row in build_rows(forecast=forecasts) if row.horizon_minutes == 60}
        self.assertLess(rows[eg6b.EG6B_AREA_CODES[1]].opportunity_rank, rows[eg6b.EG6B_AREA_CODES[0]].opportunity_rank)

    def test_area_code_breaks_all_remaining_ties(self) -> None:
        current = current_rows()
        forecasts = forecast_rows()
        tied = sorted(eg6b.EG6B_AREA_CODES[:2])
        for row in current:
            if row["area_code_requested"] in tied:
                row["population_min"], row["population_max"] = "100", "120"
        for row in forecasts:
            if row["area_code_requested"] in tied and row["forecast_at"] == "2026-07-27 15:00":
                row["forecast_population_min"], row["forecast_population_max"] = "110", "130"
        rows = {row.area_code: row for row in build_rows(current, forecasts) if row.horizon_minutes == 60}
        self.assertLess(rows[tied[0]].opportunity_rank, rows[tied[1]].opportunity_rank)

    def test_horizon_rankings_are_independent(self) -> None:
        rows = build_rows()
        sixty = min((row for row in rows if row.horizon_minutes == 60), key=lambda row: row.opportunity_rank)
        one_eighty = min((row for row in rows if row.horizon_minutes == 180), key=lambda row: row.opportunity_rank)
        self.assertEqual(sixty.opportunity_rank, 1)
        self.assertEqual(one_eighty.opportunity_rank, 1)

    def test_future_population_rank_is_descending_and_separate(self) -> None:
        current = current_rows()
        forecasts = forecast_rows()
        current[0]["population_min"], current[0]["population_max"] = "990", "1010"
        forecasts[0]["forecast_population_min"], forecasts[0]["forecast_population_max"] = "890", "910"
        rows = sorted(
            (row for row in build_rows(current, forecasts) if row.horizon_minutes == 60),
            key=lambda row: row.future_population_rank,
        )
        self.assertEqual(
            [row.forecast_population_midpoint for row in rows],
            sorted((row.forecast_population_midpoint for row in rows), reverse=True),
        )
        self.assertTrue(
            all(
                row.rank_difference == row.opportunity_rank - row.future_population_rank
                for row in rows
            )
        )
        self.assertTrue(any(row.rank_difference != 0 for row in rows))

    def test_same_input_and_generated_at_are_deterministic(self) -> None:
        self.assertEqual(build_rows(), build_rows())

    def test_output_has_no_weighted_or_spot_fields(self) -> None:
        output = build_rows()[0].as_dict()
        self.assertEqual(tuple(output), eg8d_area_priority.CSV_FIELDS)
        keys = set(output)
        self.assertFalse(keys & {"score", "weighted_score", "spot_id", "spot_name"})

    def test_output_has_no_sales_revenue_or_conversion_language(self) -> None:
        payload = json.dumps([row.as_dict() for row in build_rows()], ensure_ascii=False)
        for forbidden in ("판매", "매출", "구매전환"):
            self.assertNotIn(forbidden, payload)


class AreaPriorityFreshnessGateTests(unittest.TestCase):
    def test_evaluation_time_is_an_explicit_required_core_argument(self) -> None:
        parameter = inspect.signature(
            eg8d_area_priority.evaluate_horizon_freshness
        ).parameters["evaluation_time"]
        self.assertIs(parameter.default, inspect.Parameter.empty)

    def test_case_a_is_fresh_at_both_exact_boundaries(self) -> None:
        result = freshness_gate()

        self.assertEqual(result.horizons[60].freshness_status, "FRESH")
        self.assertEqual(result.horizons[180].freshness_status, "FRESH")
        self.assertEqual(result.horizons[60].snapshot_age_minutes, 15.0)
        self.assertEqual(result.horizons[60].completeness_lag_minutes, 15.0)
        self.assertEqual(result.horizons[60].remaining_lead_minutes, 45.0)
        self.assertEqual(result.horizons[180].remaining_lead_minutes, 165.0)

    def test_case_b_blocks_sixty_but_degrades_one_eighty(self) -> None:
        result = freshness_gate(
            evaluation_time=datetime(2026, 7, 27, 14, 35, tzinfo=eg8a.SEOUL)
        )

        self.assertEqual(result.horizons[60].freshness_status, "STALE_BLOCKED")
        self.assertEqual(result.horizons[180].freshness_status, "DEGRADED")
        self.assertEqual(result.horizons[60].remaining_lead_minutes, 25.0)
        self.assertEqual(result.horizons[180].remaining_lead_minutes, 145.0)

    def test_case_c_blocks_both_expired_horizons(self) -> None:
        result = freshness_gate(
            evaluation_time=datetime(2026, 7, 28, 7, 43, tzinfo=eg8a.SEOUL)
        )

        self.assertEqual(result.horizons[60].freshness_status, "STALE_BLOCKED")
        self.assertEqual(result.horizons[180].freshness_status, "STALE_BLOCKED")
        self.assertIn("STALE_BLOCKED", result.horizons[60].reason_codes)
        self.assertLess(result.horizons[60].remaining_lead_minutes or 0, 0)
        self.assertLess(result.horizons[180].remaining_lead_minutes or 0, 0)

    def test_sixty_minute_degraded_boundaries_allow_only_area_display(self) -> None:
        result = freshness_gate(
            evaluation_time=datetime(2026, 7, 27, 14, 30, tzinfo=eg8a.SEOUL),
            latest_current_at=datetime(2026, 7, 27, 14, 30, tzinfo=eg8a.SEOUL),
        ).horizons[60]

        self.assertEqual(result.freshness_status, "DEGRADED")
        self.assertEqual(result.snapshot_age_minutes, 30.0)
        self.assertEqual(result.completeness_lag_minutes, 30.0)
        self.assertEqual(result.remaining_lead_minutes, 30.0)
        self.assertTrue(result.area_result_display_allowed)
        self.assertFalse(result.spot_evaluation_allowed)
        self.assertFalse(result.official_recommendation_allowed)
        warning = result.warning_message or ""
        for expected in ("데이터 기준시각", "예측 대상시각", "남은 시간", "최신 데이터가 아니며", "Area 참고정보"):
            self.assertIn(expected, warning)

    def test_sixty_minute_age_over_thirty_is_blocked(self) -> None:
        result = freshness_gate(
            evaluation_time=datetime(2026, 7, 27, 14, 31, tzinfo=eg8a.SEOUL),
            latest_current_at=datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
        ).horizons[60]
        self.assertEqual(result.freshness_status, "STALE_BLOCKED")

    def test_sixty_minute_remaining_under_thirty_is_blocked(self) -> None:
        result = freshness_gate(
            evaluation_time=datetime(2026, 7, 27, 14, 31, tzinfo=eg8a.SEOUL),
            latest_current_at=datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
        ).horizons[60]
        self.assertEqual(result.freshness_status, "STALE_BLOCKED")
        self.assertLess(result.remaining_lead_minutes or 0, 30)

    def test_one_eighty_degraded_boundaries_allow_only_area_display(self) -> None:
        result = freshness_gate(
            evaluation_time=datetime(2026, 7, 27, 15, 0, tzinfo=eg8a.SEOUL),
            latest_current_at=datetime(2026, 7, 27, 15, 0, tzinfo=eg8a.SEOUL),
        ).horizons[180]

        self.assertEqual(result.freshness_status, "DEGRADED")
        self.assertEqual(result.snapshot_age_minutes, 60.0)
        self.assertEqual(result.completeness_lag_minutes, 60.0)
        self.assertEqual(result.remaining_lead_minutes, 120.0)
        self.assertTrue(result.area_result_display_allowed)
        self.assertFalse(result.spot_evaluation_allowed)

    def test_one_eighty_age_over_sixty_is_blocked(self) -> None:
        result = freshness_gate(
            evaluation_time=datetime(2026, 7, 27, 15, 1, tzinfo=eg8a.SEOUL),
            latest_current_at=datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
        ).horizons[180]
        self.assertEqual(result.freshness_status, "STALE_BLOCKED")

    def test_one_eighty_remaining_under_one_twenty_is_blocked(self) -> None:
        result = freshness_gate(
            evaluation_time=datetime(2026, 7, 27, 15, 1, tzinfo=eg8a.SEOUL),
            latest_current_at=datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
        ).horizons[180]
        self.assertEqual(result.freshness_status, "STALE_BLOCKED")
        self.assertLess(result.remaining_lead_minutes or 0, 120)

    def test_fresh_runtime_allows_area_and_internal_spot_but_never_recommendation(self) -> None:
        for result in freshness_gate().horizons.values():
            self.assertTrue(result.area_result_display_allowed)
            self.assertTrue(result.spot_evaluation_allowed)
            self.assertFalse(result.official_recommendation_allowed)

    def test_timezone_naive_or_non_seoul_inputs_are_invalid(self) -> None:
        invalid_values = (
            {"evaluation_time": datetime(2026, 7, 27, 14, 15)},
            {"selected_at": datetime(2026, 7, 27, 14, 0)},
            {"latest_current_at": datetime(2026, 7, 27, 14, 15)},
            {"target_60": datetime(2026, 7, 27, 15, 0)},
            {"evaluation_time": datetime.fromisoformat("2026-07-27T05:15:00+00:00")},
            {"evaluation_time": datetime.fromisoformat("2026-07-27T14:15:00+09:00")},
            {"evaluation_time": "not-a-time"},
        )
        for values in invalid_values:
            with self.subTest(values=values):
                statuses = {
                    result.freshness_status for result in freshness_gate(**values).horizons.values()
                }
                self.assertEqual(statuses, {"INVALID_TIME_CONTRACT"})

    def test_explicit_invalid_flag_and_time_reversals_are_invalid(self) -> None:
        invalid_cases = (
            {"time_contract_valid": False},
            {"evaluation_time": datetime(2026, 7, 27, 13, 59, tzinfo=eg8a.SEOUL)},
            {"latest_current_at": datetime(2026, 7, 27, 13, 59, tzinfo=eg8a.SEOUL)},
            {"latest_current_at": datetime(2026, 7, 27, 14, 16, tzinfo=eg8a.SEOUL)},
            {"target_60": datetime(2026, 7, 27, 13, 59, tzinfo=eg8a.SEOUL)},
            {"target_60": datetime(2026, 7, 27, 15, 1, tzinfo=eg8a.SEOUL)},
            {"complete_snapshot_exists": 1},
            {"time_contract_valid": 1},
        )
        for values in invalid_cases:
            with self.subTest(values=values):
                statuses = {
                    result.freshness_status for result in freshness_gate(**values).horizons.values()
                }
                self.assertEqual(statuses, {"INVALID_TIME_CONTRACT"})

    def test_no_complete_snapshot_allows_only_fresh_current_fallback(self) -> None:
        result = freshness_gate(
            selected_at=None,
            latest_current_at=datetime(2026, 7, 27, 14, 0, tzinfo=eg8a.SEOUL),
            target_60=None,
            target_180=None,
            complete_snapshot_exists=False,
        )
        self.assertEqual(result.current_only_data_age_minutes, 15.0)

        self.assertEqual(
            {horizon.freshness_status for horizon in result.horizons.values()},
            {"NO_COMPLETE_SNAPSHOT"},
        )
        for horizon in result.horizons.values():
            self.assertFalse(horizon.area_result_display_allowed)
            self.assertFalse(horizon.spot_evaluation_allowed)
            self.assertTrue(horizon.current_only_fallback_allowed)

    def test_no_complete_snapshot_blocks_old_current_fallback(self) -> None:
        result = freshness_gate(
            selected_at=None,
            latest_current_at=datetime(2026, 7, 27, 13, 59, tzinfo=eg8a.SEOUL),
            target_60=None,
            target_180=None,
            complete_snapshot_exists=False,
        )
        self.assertTrue(
            all(not horizon.current_only_fallback_allowed for horizon in result.horizons.values())
        )

    def test_historical_audit_is_never_user_display_eligible(self) -> None:
        result = freshness_gate(evaluation_mode="HISTORICAL_AUDIT")

        self.assertFalse(result.user_display_eligible)
        for horizon in result.horizons.values():
            self.assertEqual(horizon.freshness_status, "FRESH")
            self.assertFalse(horizon.area_result_display_allowed)
            self.assertFalse(horizon.spot_evaluation_allowed)
            self.assertIn("HISTORICAL_AUDIT_NOT_USER_ELIGIBLE", horizon.reason_codes)

    def test_result_is_deterministic_and_has_required_horizon_fields(self) -> None:
        first = freshness_gate()
        second = freshness_gate()
        self.assertEqual(first, second)
        required = {
            "freshness_status",
            "evaluation_time",
            "selected_snapshot_observed_at",
            "forecast_target_at",
            "snapshot_age_minutes",
            "completeness_lag_minutes",
            "remaining_lead_minutes",
            "area_result_display_allowed",
            "spot_evaluation_allowed",
            "official_recommendation_allowed",
            "current_only_fallback_allowed",
            "reason_codes",
            "warning_message",
        }
        self.assertEqual(set(first.horizons[60].as_dict()), required)

    def test_stale_gate_does_not_reselect_a_different_source_run(self) -> None:
        old_current, old_forecasts = source_run_rows(
            "old-complete", datetime(2026, 7, 27, 14, 0, tzinfo=eg8a.SEOUL)
        )
        new_current, new_forecasts = source_run_rows(
            "new-incomplete", datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL)
        )
        new_forecasts = new_forecasts[1:]

        selection = eg8d_area_priority._select_latest_complete_run(
            old_current + new_current, old_forecasts + new_forecasts
        )
        result = freshness_gate(
            evaluation_time=datetime(2026, 7, 28, 7, 43, tzinfo=eg8a.SEOUL),
            selected_at=selection.canonical_timestamp,
        )

        self.assertEqual(selection.source_collection_run_id, "old-complete")
        self.assertEqual(
            {horizon.freshness_status for horizon in result.horizons.values()},
            {"STALE_BLOCKED"},
        )


class AreaPriorityPublicationTests(unittest.TestCase):
    def run_once(self, root: Path) -> tuple[eg8d_area_priority.AreaPriorityResult, tuple[Path, Path, Path]]:
        manifest_path, current_path, forecast_path, hashes = write_locked_inputs(root)
        output_root = root / "area-priority-results"
        output_root.mkdir()
        with (
            mock.patch.object(eg8d_area_priority, "LOCKED_MANIFEST_SHA256", hashes["manifest"]),
            mock.patch.object(eg8d_area_priority, "LOCKED_CURRENT_SHA256", hashes["current"]),
            mock.patch.object(eg8d_area_priority, "LOCKED_FORECAST_SHA256", hashes["forecast"]),
        ):
            result = eg8d_area_priority._run_eg8d_area_priority(
                dataset_manifest_path=manifest_path,
                current_path=current_path,
                forecast_path=forecast_path,
                output_root=output_root,
                run_id=RESULT_RUN_ID,
                generated_at=GENERATED_AT,
                evaluation_time=datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
                evaluation_mode="HISTORICAL_AUDIT",
            )
        return result, (manifest_path, current_path, forecast_path)

    def test_run_publishes_exactly_four_verified_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result, _inputs = self.run_once(Path(directory))
            self.assertEqual(
                {path.name for path in result.run_dir.iterdir()},
                {
                    "area_priority.csv",
                    "area_priority.json",
                    "run_metadata.json",
                    "area_priority_manifest.json",
                },
            )
            for artifact in result.manifest["output_artifacts"]:
                path = result.run_dir / artifact["relative_path"]
                self.assertEqual(sha256(path), artifact["sha256"])
                self.assertEqual(path.stat().st_size, artifact["byte_size"])

    def run_current_only(
        self,
        root: Path,
        *,
        age_minutes: int,
        evaluation_mode: str = "SYNTHETIC_VALIDATION",
        current: list[dict[str, str]] | None = None,
    ) -> eg8d_area_priority.AreaPriorityResult:
        manifest_path, current_path, forecast_path, hashes = write_locked_inputs(
            root,
            current=current,
            forecast=forecast_rows()[1:],
        )
        output_root = root / "area-priority-results"
        output_root.mkdir()
        with (
            mock.patch.object(eg8d_area_priority, "LOCKED_MANIFEST_SHA256", hashes["manifest"]),
            mock.patch.object(eg8d_area_priority, "LOCKED_CURRENT_SHA256", hashes["current"]),
            mock.patch.object(eg8d_area_priority, "LOCKED_FORECAST_SHA256", hashes["forecast"]),
        ):
            return eg8d_area_priority._run_eg8d_area_priority(
                dataset_manifest_path=manifest_path,
                current_path=current_path,
                forecast_path=forecast_path,
                output_root=output_root,
                run_id=RESULT_RUN_ID,
                generated_at=GENERATED_AT,
                evaluation_time=datetime(
                    2026, 7, 27, 14, 0, tzinfo=eg8a.SEOUL
                )
                + timedelta(minutes=age_minutes),
                evaluation_mode=evaluation_mode,
            )

    def test_runtime_complete_snapshot_uses_forecast_path_deterministically(self) -> None:
        results: list[eg8d_area_priority.AreaPriorityResult] = []
        output_file_states: list[tuple[bool, bool]] = []
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for directory in (first, second):
                root = Path(directory)
                manifest_path, current_path, forecast_path, hashes = write_locked_inputs(root)
                output_root = root / "area-priority-results"
                output_root.mkdir()
                with (
                    mock.patch.object(
                        eg8d_area_priority, "LOCKED_MANIFEST_SHA256", hashes["manifest"]
                    ),
                    mock.patch.object(
                        eg8d_area_priority, "LOCKED_CURRENT_SHA256", hashes["current"]
                    ),
                    mock.patch.object(
                        eg8d_area_priority, "LOCKED_FORECAST_SHA256", hashes["forecast"]
                    ),
                    mock.patch.object(
                        eg8d_area_priority,
                        "_runtime_now",
                        return_value=datetime(
                            2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL
                        ),
                    ),
                ):
                    results.append(
                        eg8d_area_priority.run_eg8d_area_priority(
                            dataset_manifest_path=manifest_path,
                            current_path=current_path,
                            forecast_path=forecast_path,
                            output_root=output_root,
                            run_id=RESULT_RUN_ID,
                            generated_at=GENERATED_AT,
                        )
                    )
                output_file_states.append(
                    (
                        (results[-1].run_dir / "area_priority.csv").is_file(),
                        (results[-1].run_dir / "current_area_state.csv").exists(),
                    )
                )

        first_result, second_result = results
        self.assertEqual(first_result.rows, second_result.rows)
        self.assertEqual(first_result.metadata, second_result.metadata)
        self.assertEqual(first_result.metadata["evaluation_time"], "2026-07-27T14:15:00+09:00")
        self.assertEqual(first_result.metadata["freshness_gate"]["evaluation_mode"], "RUNTIME")
        self.assertTrue(
            first_result.metadata["freshness_gate"]["horizons"]["60"][
                "area_result_display_allowed"
            ]
        )
        self.assertTrue(
            first_result.metadata["freshness_gate"]["horizons"]["60"][
                "spot_evaluation_allowed"
            ]
        )
        self.assertFalse(
            first_result.metadata["freshness_gate"]["horizons"]["60"][
                "official_recommendation_allowed"
            ]
        )
        self.assertEqual(output_file_states, [(True, False), (True, False)])

    def test_current_only_ten_minutes_publishes_thirteen_current_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_current_only(Path(directory), age_minutes=10)

            self.assertEqual(
                {path.name for path in result.run_dir.iterdir()},
                {
                    "current_area_state.csv",
                    "current_area_state.json",
                    "run_metadata.json",
                    "current_area_state_manifest.json",
                },
            )
            payload = json.loads(
                (result.run_dir / "current_area_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(payload), 13)
            expected_fields = {
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
                "result_contract",
                "record_role",
                "validation_context",
                "operational_observation",
            }
            forbidden_fields = {
                "forecast_population_midpoint",
                "prediction_target_at",
                "horizon_minutes",
                "expected_population_change",
                "expected_population_change_rate",
                "opportunity_rank",
                "future_population_rank",
                "rank_difference",
            }
            self.assertEqual(set(payload[0]), expected_fields)
            self.assertFalse(set(payload[0]) & forbidden_fields)
            self.assertTrue(all(row["current_only_fallback_allowed"] for row in payload))
            self.assertTrue(all(not row["area_current_state_display_allowed"] for row in payload))
            self.assertTrue(all(not row["area_result_display_allowed"] for row in payload))
            self.assertTrue(all(not row["spot_evaluation_allowed"] for row in payload))
            self.assertTrue(all(not row["official_recommendation_allowed"] for row in payload))
            self.assertEqual({row["current_age_minutes"] for row in payload}, {10.0})
            self.assertEqual({row["mode"] for row in payload}, {"SYNTHETIC_VALIDATION"})
            self.assertEqual(
                {row["result_contract"] for row in payload},
                {"CURRENT_AREA_STATE_ONLY_V1"},
            )
            self.assertEqual({row["record_role"] for row in payload}, {"CURRENT_STATE_ROW"})
            self.assertEqual(
                {row["validation_context"] for row in payload},
                {"SYNTHETIC_CURRENT_ONLY_VALIDATION"},
            )
            self.assertTrue(all(not row["operational_observation"] for row in payload))
            self.assertEqual(result.metadata["result_status"], "CURRENT_ONLY_BLOCKED")
            self.assertEqual(
                result.metadata["simulated_policy_outcome"], "CURRENT_ONLY_ALLOWED"
            )
            self.assertEqual(
                result.metadata["current_area_state_run_id"], RESULT_RUN_ID
            )
            self.assertNotIn("area_priority_run_id", result.metadata)
            self.assertNotIn("ranking_rules", result.metadata)
            self.assertNotIn("top_bottom_summary", result.metadata)

            for document in (result.metadata, result.manifest):
                self.assertEqual(
                    document["validation_context"],
                    "SYNTHETIC_CURRENT_ONLY_VALIDATION",
                )
                self.assertTrue(document["synthetic_validation"])
                self.assertFalse(document["operational_observation"])
                self.assertTrue(document["forecast_absence_simulated"])
                self.assertFalse(document["source_dataset_modified"])
                self.assertEqual(document["runtime_clock_source"], "INJECTED_TEST_CLOCK")
                self.assertFalse(document["operational_publication_allowed"])
                self.assertFalse(document["user_publication_allowed"])
                self.assertFalse(document["use_for_operational_metrics"])
                self.assertFalse(document["use_for_user_display"])
                self.assertEqual(
                    document["source_dataset_manifest_sha256"],
                    result.metadata["dataset_manifest_sha256"],
                )
                self.assertEqual(
                    document["simulated_policy_outcome"], "CURRENT_ONLY_ALLOWED"
                )

    def test_current_only_fifteen_minute_boundary_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_current_only(Path(directory), age_minutes=15)

        self.assertEqual({row.current_age_minutes for row in result.rows}, {15.0})
        self.assertTrue(all(row.current_only_fallback_allowed for row in result.rows))

    def test_current_only_sixteen_minutes_is_published_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_current_only(Path(directory), age_minutes=16)

        self.assertEqual(len(result.rows), 13)
        self.assertEqual(result.metadata["result_status"], "CURRENT_ONLY_BLOCKED")
        self.assertTrue(all(not row.current_only_fallback_allowed for row in result.rows))
        self.assertTrue(all(not row.area_current_state_display_allowed for row in result.rows))
        self.assertTrue(
            all("CURRENT_AGE_EXCEEDS_FALLBACK_LIMIT" in row.reason_codes for row in result.rows)
        )
        self.assertEqual(
            result.metadata["simulated_policy_outcome"], "CURRENT_ONLY_BLOCKED"
        )
        self.assertEqual(
            result.manifest["simulated_policy_outcome"], "CURRENT_ONLY_BLOCKED"
        )

    def test_current_only_historical_audit_is_published_as_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_current_only(
                Path(directory), age_minutes=10, evaluation_mode="HISTORICAL_AUDIT"
            )

        self.assertEqual(result.metadata["result_status"], "CURRENT_ONLY_BLOCKED")
        self.assertTrue(
            all(
                not row.area_current_state_display_allowed
                and not row.area_result_display_allowed
                and not row.spot_evaluation_allowed
                and not row.official_recommendation_allowed
                for row in result.rows
            )
        )
        self.assertTrue(
            all("HISTORICAL_AUDIT_NOT_USER_ELIGIBLE" in row.reason_codes for row in result.rows)
        )

    def test_public_runtime_current_only_uses_one_system_clock_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, current_path, forecast_path, hashes = write_locked_inputs(
                root, forecast=forecast_rows()[1:]
            )
            output_root = root / "area-priority-results"
            output_root.mkdir()
            runtime_now = datetime(2026, 7, 27, 14, 10, tzinfo=eg8a.SEOUL)
            with (
                mock.patch.object(eg8d_area_priority, "LOCKED_MANIFEST_SHA256", hashes["manifest"]),
                mock.patch.object(eg8d_area_priority, "LOCKED_CURRENT_SHA256", hashes["current"]),
                mock.patch.object(eg8d_area_priority, "LOCKED_FORECAST_SHA256", hashes["forecast"]),
                mock.patch.object(
                    eg8d_area_priority, "_runtime_now", return_value=runtime_now
                ) as runtime_clock,
                mock.patch.dict(
                    "os.environ",
                    {
                        "EG8D_EVALUATION_TIME": "2000-01-01T00:00:00+09:00",
                        "EG8D_EVALUATION_MODE": "HISTORICAL_AUDIT",
                    },
                ),
            ):
                result = eg8d_area_priority.run_eg8d_area_priority(
                    dataset_manifest_path=manifest_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    output_root=output_root,
                    run_id=RESULT_RUN_ID,
                )

            runtime_clock.assert_called_once_with()
            expected_time = "2026-07-27T14:10:00+09:00"
            payload = json.loads(
                (result.run_dir / "current_area_state.json").read_text(encoding="utf-8")
            )
            with (result.run_dir / "current_area_state.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual({row["evaluation_time"] for row in payload}, {expected_time})
            self.assertEqual({row["evaluation_time"] for row in csv_rows}, {expected_time})
            self.assertEqual(result.metadata["evaluation_time"], expected_time)
            self.assertEqual(result.metadata["generated_at"], expected_time)
            self.assertEqual(result.manifest["evaluation_time"], expected_time)
            self.assertEqual(result.metadata["evaluation_mode"], "RUNTIME")
            self.assertEqual(
                result.metadata["runtime_clock_source"], "SYSTEM_CLOCK_ASIA_SEOUL"
            )
            self.assertFalse(result.metadata["synthetic_validation"])
            self.assertTrue(result.metadata["operational_observation"])
            self.assertFalse(result.metadata["forecast_absence_simulated"])
            self.assertNotIn("simulated_policy_outcome", result.metadata)
            self.assertNotIn("simulated_policy_outcome", result.manifest)

    def assert_injected_runtime_is_rejected(
        self,
        evaluation_time: datetime,
        *,
        runner,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, current_path, forecast_path, hashes = write_locked_inputs(root)
            output_root = root / "area-priority-results"
            output_root.mkdir()
            with (
                mock.patch.object(eg8d_area_priority, "LOCKED_MANIFEST_SHA256", hashes["manifest"]),
                mock.patch.object(eg8d_area_priority, "LOCKED_CURRENT_SHA256", hashes["current"]),
                mock.patch.object(eg8d_area_priority, "LOCKED_FORECAST_SHA256", hashes["forecast"]),
                self.assertRaisesRegex(
                    eg8d_area_priority.AreaPriorityContractError,
                    "execution_context_invalid",
                ),
            ):
                runner(
                    dataset_manifest_path=manifest_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    output_root=output_root,
                    run_id=RESULT_RUN_ID,
                    generated_at=GENERATED_AT,
                    evaluation_time=evaluation_time,
                    evaluation_mode="RUNTIME",
                )
            self.assertEqual(list(output_root.iterdir()), [])

    def test_internal_past_time_cannot_be_published_as_runtime(self) -> None:
        self.assert_injected_runtime_is_rejected(
            datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
            runner=eg8d_area_priority._run_eg8d_area_priority,
        )

    def test_internal_runtime_is_rejected_even_at_system_clock_value(self) -> None:
        runtime_clock_value = datetime(2026, 7, 28, 14, 15, tzinfo=eg8a.SEOUL)
        with mock.patch.object(
            eg8d_area_priority, "_runtime_now", return_value=runtime_clock_value
        ) as runtime_clock:
            self.assert_injected_runtime_is_rejected(
                runtime_clock_value,
                runner=eg8d_area_priority._run_eg8d_area_priority,
            )
        runtime_clock.assert_not_called()

    def test_common_executor_uses_fixed_context_without_reading_runtime_clock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, current_path, forecast_path, hashes = write_locked_inputs(root)
            output_root = root / "area-priority-results"
            output_root.mkdir()
            execution_context = eg8d_area_priority._ExecutionContext(
                evaluation_time=datetime(
                    2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL
                ),
                evaluation_mode="HISTORICAL_AUDIT",
                validation_context="HISTORICAL_AUDIT",
                operational_observation=False,
                synthetic_validation=False,
                clock_source="INJECTED_TEST_CLOCK",
                operational_publication_allowed=False,
            )
            with (
                mock.patch.object(
                    eg8d_area_priority, "LOCKED_MANIFEST_SHA256", hashes["manifest"]
                ),
                mock.patch.object(
                    eg8d_area_priority, "LOCKED_CURRENT_SHA256", hashes["current"]
                ),
                mock.patch.object(
                    eg8d_area_priority, "LOCKED_FORECAST_SHA256", hashes["forecast"]
                ),
                mock.patch.object(eg8d_area_priority, "_runtime_now") as runtime_clock,
            ):
                result = eg8d_area_priority._execute_eg8d_area_priority(
                    dataset_manifest_path=manifest_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    output_root=output_root,
                    run_id=RESULT_RUN_ID,
                    generated_at=GENERATED_AT,
                    execution_context=execution_context,
                )

            runtime_clock.assert_not_called()
            self.assertEqual(
                result.metadata["freshness_gate"]["evaluation_mode"],
                "HISTORICAL_AUDIT",
            )
            self.assertFalse(result.metadata["operational_publication_allowed"])

    def test_common_executor_cannot_start_runtime_from_raw_controls(self) -> None:
        for evaluation_time in (
            datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
            None,
        ):
            with self.subTest(evaluation_time=evaluation_time):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    manifest_path, current_path, forecast_path, _hashes = (
                        write_locked_inputs(root)
                    )
                    output_root = root / "area-priority-results"
                    output_root.mkdir()
                    with (
                        mock.patch.object(
                            eg8d_area_priority,
                            "_runtime_now",
                            return_value=datetime(
                                2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL
                            ),
                        ) as runtime_clock,
                        self.assertRaises(TypeError),
                    ):
                        eg8d_area_priority._execute_eg8d_area_priority(
                            dataset_manifest_path=manifest_path,
                            current_path=current_path,
                            forecast_path=forecast_path,
                            output_root=output_root,
                            run_id=RESULT_RUN_ID,
                            generated_at=GENERATED_AT,
                            evaluation_time=evaluation_time,
                            evaluation_mode="RUNTIME",
                        )
                    runtime_clock.assert_not_called()
                    self.assertEqual(list(output_root.iterdir()), [])

    def test_current_only_future_current_is_rejected_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(
                eg8d_area_priority.AreaPriorityContractError,
                "current_after_evaluation_time",
            ):
                self.run_current_only(root, age_minutes=-1)
            self.assertEqual(list((root / "area-priority-results").iterdir()), [])

    def test_current_only_missing_or_duplicate_area_is_rejected(self) -> None:
        for defect, current in (
            ("current_area_set_mismatch", current_rows()[1:]),
            ("current_duplicate", current_rows() + [dict(current_rows()[0])]),
        ):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(
                    eg8d_area_priority.AreaPriorityContractError,
                    defect,
                ):
                    self.run_current_only(Path(directory), age_minutes=10, current=current)

    def test_source_inputs_are_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, current_path, forecast_path, hashes = write_locked_inputs(root)
            output_root = root / "area-priority-results"
            output_root.mkdir()
            before = {path: sha256(path) for path in (manifest_path, current_path, forecast_path)}
            with (
                mock.patch.object(eg8d_area_priority, "LOCKED_MANIFEST_SHA256", hashes["manifest"]),
                mock.patch.object(eg8d_area_priority, "LOCKED_CURRENT_SHA256", hashes["current"]),
                mock.patch.object(eg8d_area_priority, "LOCKED_FORECAST_SHA256", hashes["forecast"]),
            ):
                eg8d_area_priority._run_eg8d_area_priority(
                    dataset_manifest_path=manifest_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    output_root=output_root,
                    run_id=RESULT_RUN_ID,
                    generated_at=GENERATED_AT,
                    evaluation_time=datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
                    evaluation_mode="HISTORICAL_AUDIT",
                )
            self.assertEqual(before, {path: sha256(path) for path in before})

    def test_existing_result_run_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_once(root)
            manifest_path, current_path, forecast_path, hashes = write_locked_inputs(root)
            with (
                mock.patch.object(eg8d_area_priority, "LOCKED_MANIFEST_SHA256", hashes["manifest"]),
                mock.patch.object(eg8d_area_priority, "LOCKED_CURRENT_SHA256", hashes["current"]),
                mock.patch.object(eg8d_area_priority, "LOCKED_FORECAST_SHA256", hashes["forecast"]),
            ):
                with self.assertRaisesRegex(eg8d_area_priority.AreaPriorityWriteError, "run_exists"):
                    eg8d_area_priority._run_eg8d_area_priority(
                        dataset_manifest_path=manifest_path,
                        current_path=current_path,
                        forecast_path=forecast_path,
                        output_root=root / "area-priority-results",
                        run_id=RESULT_RUN_ID,
                        generated_at=GENERATED_AT,
                        evaluation_time=datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
                        evaluation_mode="HISTORICAL_AUDIT",
                    )

    def test_locked_input_hash_mismatch_fails_before_publish(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path, current_path, forecast_path, hashes = write_locked_inputs(root)
            output_root = root / "area-priority-results"
            output_root.mkdir()
            with (
                mock.patch.object(eg8d_area_priority, "LOCKED_MANIFEST_SHA256", hashes["manifest"]),
                mock.patch.object(eg8d_area_priority, "LOCKED_CURRENT_SHA256", "0" * 64),
                mock.patch.object(eg8d_area_priority, "LOCKED_FORECAST_SHA256", hashes["forecast"]),
            ):
                with self.assertRaisesRegex(eg8d_area_priority.AreaPriorityContractError, "current_sha_mismatch"):
                    eg8d_area_priority._run_eg8d_area_priority(
                        dataset_manifest_path=manifest_path,
                        current_path=current_path,
                        forecast_path=forecast_path,
                        output_root=output_root,
                        run_id=RESULT_RUN_ID,
                        generated_at=GENERATED_AT,
                        evaluation_time=datetime(2026, 7, 27, 14, 15, tzinfo=eg8a.SEOUL),
                        evaluation_mode="HISTORICAL_AUDIT",
                    )
            self.assertEqual(list(output_root.iterdir()), [])

    def test_metadata_records_counts_summaries_and_limitations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result, _inputs = self.run_once(Path(directory))
            metadata = json.loads((result.run_dir / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["horizon_area_counts"], {"60": 13, "180": 13})
            self.assertEqual(set(metadata["horizon_change_summary"]), {"60", "180"})
            self.assertEqual(metadata["excluded_areas"], [])
            self.assertEqual(set(metadata["top_bottom_summary"]), {"60", "180"})
            limitations = " ".join(metadata["limitations"])
            self.assertIn("실제 방문이나 판매 성공을 보장하지 않는다", limitations)
            self.assertIn("중간값 차이가 0", limitations)
            self.assertIn("장기 반복성이나 사용자 가치", limitations)
            self.assertEqual(metadata["forecast_source"], "SEOUL_FORECAST")
            self.assertEqual(metadata["evaluation_status"], "PROVISIONAL")
            self.assertEqual(metadata["selection_policy"], "LATEST_COMPLETE_LOCKED_SNAPSHOT")
            self.assertEqual(metadata["source_collection_run_id"], SOURCE_RUN_ID)
            self.assertEqual(metadata["total_collection_run_count"], 1)
            self.assertEqual(metadata["complete_collection_run_count"], 1)
            self.assertEqual(metadata["canonical_timestamp_field"], "observed_at")
            self.assertEqual(
                metadata["selected_run_canonical_timestamp"], "2026-07-27T14:00:00+09:00"
            )
            self.assertTrue(metadata["selection_performed_before_ranking"])
            self.assertEqual(metadata["selection_tie_count"], 1)
            self.assertEqual(metadata["selection_status"], "SELECTED")
            self.assertEqual(metadata["dataset_manifest_sha256"], sha256(_inputs[0]))
            self.assertEqual(metadata["schema_version"], "eg8d-area-priority-metadata-v2")
            self.assertEqual(metadata["evaluation_time"], "2026-07-27T14:15:00+09:00")
            self.assertEqual(metadata["freshness_gate"]["evaluation_mode"], "HISTORICAL_AUDIT")
            self.assertFalse(metadata["freshness_gate"]["user_display_eligible"])
            self.assertEqual(
                metadata["freshness_gate"]["horizons"]["60"]["freshness_status"],
                "FRESH",
            )

    def test_metadata_marks_horizon_without_positive_increase_candidate(self) -> None:
        forecasts = forecast_rows()
        for index, area_code in enumerate(eg6b.EG6B_AREA_CODES):
            for row in forecasts:
                if (
                    row["area_code_requested"] == area_code
                    and row["forecast_at"] == "2026-07-27 17:00"
                ):
                    current_midpoint = 110 + index * 10
                    row["forecast_population_min"] = str(current_midpoint - 10)
                    row["forecast_population_max"] = str(current_midpoint + 10)
        metadata = eg8d_area_priority._metadata(
            run_id=RESULT_RUN_ID,
            selection=eg8d_area_priority._SourceRunSelection(
                source_collection_run_id=SOURCE_RUN_ID,
                canonical_timestamp=datetime(2026, 7, 27, 14, 0, tzinfo=eg8a.SEOUL),
                total_collection_run_count=1,
                complete_collection_run_count=1,
                selection_tie_count=1,
            ),
            generated_at=GENERATED_AT,
            rows=build_rows(forecast=forecasts),
            inputs={
                name: {"sha256": "0" * 64, "byte_size": 0}
                for name in (
                    "dataset_manifest",
                    "population_current_v3",
                    "population_forecast_v3",
                )
            },
            freshness_gate=freshness_gate(),
            execution_provenance={},
        )

        self.assertEqual(
            metadata["horizon_change_summary"]["180"],
            {
                "positive_increase_area_count": 0,
                "zero_change_area_count": 13,
                "decrease_area_count": 0,
                "has_positive_increase_candidate": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
