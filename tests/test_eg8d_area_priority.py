from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
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


def build_rows(
    current: list[dict[str, str]] | None = None,
    forecast: list[dict[str, str]] | None = None,
) -> tuple[eg8d_area_priority.AreaPriorityRow, ...]:
    return eg8d_area_priority.build_area_priority_rows(
        current or current_rows(),
        forecast or forecast_rows(),
        source_collection_run_id=SOURCE_RUN_ID,
        generated_at=GENERATED_AT,
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_locked_inputs(root: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    current_path = root / "population_current_v3.csv"
    forecast_path = root / "population_forecast_v3.csv"
    manifest_path = root / "dataset_manifest.json"
    write_csv(current_path, current_rows())
    write_csv(forecast_path, forecast_rows())
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
        with self.assertRaisesRegex(eg8d_area_priority.AreaPriorityContractError, "forecast_missing"):
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
            result = eg8d_area_priority.run_eg8d_area_priority(
                dataset_manifest_path=manifest_path,
                current_path=current_path,
                forecast_path=forecast_path,
                output_root=output_root,
                run_id=RESULT_RUN_ID,
                source_collection_run_id=SOURCE_RUN_ID,
                generated_at=GENERATED_AT,
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
                eg8d_area_priority.run_eg8d_area_priority(
                    dataset_manifest_path=manifest_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    output_root=output_root,
                    run_id=RESULT_RUN_ID,
                    source_collection_run_id=SOURCE_RUN_ID,
                    generated_at=GENERATED_AT,
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
                    eg8d_area_priority.run_eg8d_area_priority(
                        dataset_manifest_path=manifest_path,
                        current_path=current_path,
                        forecast_path=forecast_path,
                        output_root=root / "area-priority-results",
                        run_id=RESULT_RUN_ID,
                        source_collection_run_id=SOURCE_RUN_ID,
                        generated_at=GENERATED_AT,
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
                    eg8d_area_priority.run_eg8d_area_priority(
                        dataset_manifest_path=manifest_path,
                        current_path=current_path,
                        forecast_path=forecast_path,
                        output_root=output_root,
                        run_id=RESULT_RUN_ID,
                        source_collection_run_id=SOURCE_RUN_ID,
                        generated_at=GENERATED_AT,
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
            source_collection_run_id=SOURCE_RUN_ID,
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
