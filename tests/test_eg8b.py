from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from freshmanager import eg6b, eg8a, eg8b


RAW_LOG_HEADER = list(eg8a.RAW_LOG_REQUIRED_COLUMNS)
CURRENT_HEADER = list(eg8a.CURRENT_REQUIRED_COLUMNS)
FORECAST_HEADER = list(eg8a.FORECAST_REQUIRED_COLUMNS)

RUN_A = "11111111-1111-4111-8111-111111111111"
RUN_B = "22222222-2222-4222-8222-222222222222"
RUN_C = "33333333-3333-4333-8333-333333333333"
RUN_D = "44444444-4444-4444-8444-444444444444"
RUN_E = "55555555-5555-4555-8555-555555555555"


def write_csv(directory: Path, name: str, header: list[str], rows: list[list[str]]) -> Path:
    path = directory / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def raw_log_row(
    *,
    run_id: str = RUN_A,
    called_at: str = "2026-07-24 08:00:05",
    area: str = "POI072",
    area_name: str = "여의도",
    http_code: str = "200",
    status: str = "SUCCESS",
    raw_json: str = '{"ok":true}',
) -> list[str]:
    return [run_id, called_at, area, area_name, http_code, status, raw_json]


def current_row(
    *,
    run_id: str = RUN_A,
    called_at: str = "2026-07-24 08:00:05",
    observed_at: str = "2026-07-24 08:00",
    area: str = "POI072",
    area_name: str = "여의도",
    congestion: str = "여유",
    pop_min: str = "30000",
    pop_max: str = "32000",
) -> list[str]:
    return [run_id, called_at, observed_at, area, area, area_name, congestion, pop_min, pop_max]


def forecast_row(
    *,
    run_id: str = RUN_A,
    called_at: str = "2026-07-24 08:00:05",
    observed_at: str = "2026-07-24 08:00",
    forecast_at: str = "2026-07-24 10:00",
    area: str = "POI072",
    area_name: str = "여의도",
    congestion: str = "여유",
    pop_min: str = "29000",
    pop_max: str = "31000",
) -> list[str]:
    return [
        run_id, called_at, observed_at, forecast_at, area, area,
        area_name, congestion, pop_min, pop_max,
    ]


def build_upstream_dataset(
    *,
    staging_dir: Path,
    output_root: Path,
    current_rows: list[list[str]],
    forecast_rows: list[list[str]],
    raw_log_rows: list[list[str]] | None = None,
    dataset_id: str | None = None,
) -> eg8a.DatasetExportResult:
    """Build a real EG-8A dataset via normalize_v3_sources + export_dataset,
    using tiny synthetic input CSVs -- more integration-realistic than
    hand-faking a Manifest shape that could drift from eg8a's real one."""
    if raw_log_rows is None:
        seen: set[tuple[str, str]] = set()
        raw_log_rows = []
        for row in current_rows:
            key = (row[0], row[3])
            if key not in seen:
                seen.add(key)
                raw_log_rows.append(raw_log_row(run_id=row[0], called_at=row[1], area=row[3]))

    raw_path = write_csv(staging_dir, "raw.csv", RAW_LOG_HEADER, raw_log_rows)
    current_path = write_csv(staging_dir, "current.csv", CURRENT_HEADER, current_rows)
    forecast_path = write_csv(staging_dir, "forecast.csv", FORECAST_HEADER, forecast_rows)
    result = eg8a.normalize_v3_sources(
        raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path
    )
    return eg8a.export_dataset(
        result,
        output_root=output_root,
        input_paths={
            "raw_log_v3": raw_path,
            "population_current_v3": current_path,
            "population_forecast_v3": forecast_path,
        },
        dataset_id=dataset_id,
    )


def make_current_row(**overrides: object) -> eg8b.CurrentRow:
    base: dict[str, object] = dict(
        collection_run_id=RUN_A,
        called_at="2026-07-24T08:00:05+09:00",
        observed_at="2026-07-24T08:00:00+09:00",
        area_code="POI072",
        congestion_level="여유",
        population_min=30000,
        population_max=32000,
        population_mid=31000.0,
        duplicate_flag=False,
    )
    base.update(overrides)
    return eg8b.CurrentRow(**base)


def make_bundle(
    *,
    current_rows: tuple[eg8b.CurrentRow, ...] = (),
    forecast_rows: tuple[eg8b.ForecastRow, ...] = (),
    error_rows: tuple[dict[str, str], ...] = (),
    quality_report: dict[str, object] | None = None,
) -> eg8b.DatasetBundle:
    """Hand-build a DatasetBundle for unit-level tests of the build_*
    functions that do not need a real eg8a.export_dataset round trip --
    e.g. scenarios eg8a's own structural guarantees make unreachable via
    the real pipeline (two Current rows sharing one collection_run_id)."""
    return eg8b.DatasetBundle(
        dataset_id="unit-test-dataset",
        dataset_dir=Path("/nonexistent"),
        manifest={},
        quality_report=quality_report if quality_report is not None else {},
        current_rows=current_rows,
        forecast_rows=forecast_rows,
        error_rows=error_rows,
    )


class DatasetBundleValidationTests(unittest.TestCase):
    def test_valid_dataset_loads_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            self.assertEqual(bundle.dataset_id, export.dataset_id)
            self.assertEqual(len(bundle.current_rows), 1)
            self.assertEqual(len(bundle.forecast_rows), 1)
            self.assertEqual(len(bundle.error_rows), 0)

    def test_expected_dataset_id_match_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            bundle = eg8b.load_dataset_bundle(
                export.dataset_dir, expected_dataset_id=export.dataset_id
            )
            self.assertEqual(bundle.dataset_id, export.dataset_id)

    def test_dataset_id_mismatch_raises(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            with self.assertRaises(eg8b.DatasetValidationError) as ctx:
                eg8b.load_dataset_bundle(export.dataset_dir, expected_dataset_id="not-the-real-id")
            self.assertIn(eg8b.ERROR_DATASET_ID_MISMATCH, str(ctx.exception))

    def test_missing_dataset_directory_raises(self) -> None:
        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(eg8b.DatasetValidationError) as ctx:
                eg8b.load_dataset_bundle(Path(output_root) / "does-not-exist")
            self.assertIn(eg8b.ERROR_DATASET_FILE_MISSING, str(ctx.exception))

    def test_missing_output_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            (export.dataset_dir / eg8a.ERROR_ROWS_OUTPUT_FILENAME).unlink()
            with self.assertRaises(eg8b.DatasetValidationError) as ctx:
                eg8b.load_dataset_bundle(export.dataset_dir)
            self.assertIn(eg8b.ERROR_DATASET_FILE_MISSING, str(ctx.exception))

    def test_hash_mismatch_raises(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            current_csv_path = export.dataset_dir / eg8a.CURRENT_OUTPUT_FILENAME
            content = current_csv_path.read_text(encoding="utf-8")
            self.assertIn("여유", content)
            current_csv_path.write_text(content.replace("여유", "붐빔"), encoding="utf-8")
            with self.assertRaises(eg8b.DatasetValidationError) as ctx:
                eg8b.load_dataset_bundle(export.dataset_dir)
            self.assertIn(eg8b.ERROR_DATASET_HASH_MISMATCH, str(ctx.exception))

    def test_row_count_mismatch_raises(self) -> None:
        """Only reachable by tampering the Manifest's own recorded counts --
        tampering a CSV's row content instead would already fail the Hash
        check first, since eg8a.export_dataset hashes the actual bytes."""
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            manifest_path = export.dataset_dir / eg8a.DATASET_MANIFEST_OUTPUT_FILENAME
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_row_counts"]["current_normal_rows"] = 999
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            with self.assertRaises(eg8b.DatasetValidationError) as ctx:
                eg8b.load_dataset_bundle(export.dataset_dir)
            self.assertIn(eg8b.ERROR_DATASET_ROW_COUNT_MISMATCH, str(ctx.exception))


class DatasetProfileTests(unittest.TestCase):
    def test_profile_fields(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[
                    current_row(run_id=RUN_A, area="POI072"),
                    current_row(run_id=RUN_B, area="POI019", called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05"),
                ],
                forecast_rows=[
                    forecast_row(run_id=RUN_A, area="POI072"),
                    forecast_row(run_id=RUN_B, area="POI019", called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05", forecast_at="2026-07-24 10:05"),
                ],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            profile = eg8b.build_dataset_profile(
                bundle, generated_at=eg8a.parse_kst_datetime("2026-07-24 12:00:00")
            )
            self.assertEqual(profile["schema_version"], eg8b.DATASET_PROFILE_SCHEMA_VERSION)
            self.assertEqual(profile["dataset_id"], export.dataset_id)
            self.assertTrue(profile["provenance_validation"]["all_files_present"])
            self.assertTrue(profile["provenance_validation"]["all_output_hashes_match"])
            self.assertTrue(profile["provenance_validation"]["row_counts_match_manifest"])
            self.assertEqual(profile["dataset_readiness"], eg8b.DATASET_READINESS_READY_FOR_PHASE1)
            self.assertEqual(profile["row_counts"]["current_rows"], 2)
            self.assertEqual(profile["row_counts"]["forecast_rows"], 2)
            self.assertEqual(profile["area_coverage"]["unexpected_areas"], [])
            self.assertEqual(profile["collection_run_count"], 2)
            # both Current rows fall on the same KST calendar date
            self.assertEqual(profile["time_range"]["data_date_count"], 1)
            self.assertEqual(profile["time_range"]["data_dates"], ["2026-07-24"])

    def test_duplicate_and_area_match_rate_reuse_quality_report_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row()],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            profile = eg8b.build_dataset_profile(
                bundle, generated_at=eg8a.parse_kst_datetime("2026-07-24 12:00:00")
            )
            recommended = bundle.quality_report["recommended"]
            self.assertEqual(
                profile["duplicate_rate"]["current"],
                recommended["current_duplicate"]["semantic_duplicate_rate"],
            )
            self.assertEqual(
                profile["duplicate_rate"]["forecast"],
                recommended["forecast_target_duplicate"]["semantic_duplicate_rate"],
            )
            self.assertEqual(
                profile["area_code_match_rate"]["current"],
                recommended["area_code_match_rate"]["current"],
            )
            self.assertEqual(
                profile["area_code_match_rate"]["forecast"],
                recommended["area_code_match_rate"]["forecast"],
            )
            # mean/min/max reused verbatim from quality_report.json; median is new
            lag = recommended["collection_lag_seconds"]
            self.assertEqual(profile["collection_lag_seconds"]["current"]["mean"], lag["current"]["mean"])
            self.assertEqual(profile["collection_lag_seconds"]["current"]["min"], lag["current"]["min"])
            self.assertEqual(profile["collection_lag_seconds"]["current"]["max"], lag["current"]["max"])
            self.assertIsInstance(profile["collection_lag_seconds"]["current"]["median"], float)


class AreaCurrentSummaryTests(unittest.TestCase):
    def test_per_area_statistics(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[
                    current_row(run_id=RUN_A, area="POI072", observed_at="2026-07-24 08:00", pop_min="30000", pop_max="32000", congestion="여유"),
                    current_row(run_id=RUN_B, area="POI072", called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05", pop_min="34000", pop_max="36000", congestion="보통"),
                ],
                forecast_rows=[
                    forecast_row(run_id=RUN_A, area="POI072", observed_at="2026-07-24 08:00", forecast_at="2026-07-24 10:00"),
                    forecast_row(run_id=RUN_B, area="POI072", called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05", forecast_at="2026-07-24 10:05"),
                ],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            rows = eg8b.build_area_current_summary_rows(bundle)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["area_code"], "POI072")
            self.assertEqual(row["row_count"], 2)
            self.assertEqual(row["unique_collection_run_count"], 2)
            self.assertEqual(row["population_min_min"], 30000)
            self.assertEqual(row["population_min_max"], 34000)
            self.assertEqual(row["population_mid_median"], 33000.0)
            self.assertEqual(row["consecutive_pairs_within_6min"], 1)
            self.assertEqual(row["consecutive_pairs_total"], 1)
            self.assertAlmostEqual(row["max_observation_gap_minutes"], 5.0)
            self.assertEqual(row["error_row_count"], 0)
            congestion_counts = json.loads(row["congestion_level_counts_json"])
            self.assertEqual(congestion_counts, {"여유": 1, "보통": 1})

    def test_no_areas_produces_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[],
                forecast_rows=[],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            self.assertEqual(eg8b.build_area_current_summary_rows(bundle), [])

    def test_single_observation_has_null_max_gap(self) -> None:
        bundle = make_bundle(current_rows=(make_current_row(),))
        rows = eg8b.build_area_current_summary_rows(bundle)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["max_observation_gap_minutes"])
        self.assertEqual(rows[0]["unique_collection_run_count"], 1)

    def test_unique_run_count_can_differ_from_row_count(self) -> None:
        """Structurally unreachable via eg8a.export_dataset (which hard-
        excludes any two rows sharing a (collection_run_id, area) Source
        Correlation Key as CURRENT_KEY_DUPLICATE) -- exercised here at the
        eg8b unit level to prove unique_collection_run_count is computed
        independently of row_count, not derived from it."""
        bundle = make_bundle(
            current_rows=(
                make_current_row(observed_at="2026-07-24T08:00:00+09:00"),
                make_current_row(observed_at="2026-07-24T08:05:00+09:00"),
            )
        )
        rows = eg8b.build_area_current_summary_rows(bundle)
        self.assertEqual(rows[0]["row_count"], 2)
        self.assertEqual(rows[0]["unique_collection_run_count"], 1)

    def test_error_row_count_with_attribution_fallback(self) -> None:
        bundle = make_bundle(
            current_rows=(
                make_current_row(area_code="POI072"),
                make_current_row(area_code="POI019", collection_run_id=RUN_B),
            ),
            error_rows=(
                {"area_code_requested": "POI072", "area_code_returned": ""},
                {"area_code_requested": "", "area_code_returned": "POI019"},
                {"area_code_requested": "", "area_code_returned": ""},
            ),
        )
        rows = {row["area_code"]: row for row in eg8b.build_area_current_summary_rows(bundle)}
        self.assertEqual(rows["POI072"]["error_row_count"], 1)
        self.assertEqual(rows["POI019"]["error_row_count"], 1)
        total_attributed = sum(row["error_row_count"] for row in rows.values())
        self.assertEqual(total_attributed, 2)  # the fully-blank error row is never attributed


class TimeCoverageTests(unittest.TestCase):
    def test_run_rows_gaps_completeness_and_deviation(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[
                    current_row(run_id=RUN_A, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00"),
                    current_row(run_id=RUN_B, called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05"),
                    current_row(run_id=RUN_C, called_at="2026-07-24 08:15:05", observed_at="2026-07-24 08:15"),
                ],
                forecast_rows=[],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            rows = eg8b.build_time_coverage_rows(bundle)
            run_rows = [r for r in rows if r["record_type"] == eg8b.RECORD_TYPE_RUN]
            self.assertEqual(len(run_rows), 3)

            # first run: no previous -> null gap and null deviation
            self.assertIsNone(run_rows[0]["gap_from_previous_run_minutes"])
            self.assertIsNone(run_rows[0]["five_minute_contract_deviation"])

            # exactly 5 minutes -> not a deviation
            self.assertAlmostEqual(run_rows[1]["gap_from_previous_run_minutes"], 5.0)
            self.assertFalse(run_rows[1]["five_minute_contract_deviation"])

            # 10 minutes -> a deviation
            self.assertAlmostEqual(run_rows[2]["gap_from_previous_run_minutes"], 10.0)
            self.assertTrue(run_rows[2]["five_minute_contract_deviation"])

            # The official Area set is always the real 13-code panel
            # (eg6b.EG6B_AREA_CODES), never just what a synthetic test
            # happens to query -- a single-Area dataset like this one can
            # therefore never be COMPLETE. See
            # test_complete_run_when_all_official_areas_present for the
            # COMPLETE path exercised with the full 13-code set.
            for run_row in run_rows:
                self.assertEqual(run_row["run_completeness"], eg8b.RUN_COMPLETENESS_PARTIAL)

    def test_partial_run_when_area_missing(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                raw_log_rows=[
                    raw_log_row(run_id=RUN_A, area="POI072"),
                    raw_log_row(run_id=RUN_A, area="POI019"),
                    raw_log_row(run_id=RUN_B, area="POI072"),
                ],
                current_rows=[
                    current_row(run_id=RUN_A, area="POI072"),
                    current_row(run_id=RUN_A, area="POI019"),
                    current_row(run_id=RUN_B, area="POI072", called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05"),
                ],
                forecast_rows=[],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            run_rows = [
                r for r in eg8b.build_time_coverage_rows(bundle) if r["record_type"] == eg8b.RECORD_TYPE_RUN
            ]
            by_run = {r["collection_run_id"]: r for r in run_rows}
            # Neither run's Area set equals the real 13-code official panel,
            # so both are PARTIAL regardless of how many Areas they cover
            # relative to each other.
            self.assertEqual(by_run[RUN_A]["run_completeness"], eg8b.RUN_COMPLETENESS_PARTIAL)
            self.assertEqual(by_run[RUN_B]["run_completeness"], eg8b.RUN_COMPLETENESS_PARTIAL)

    def test_complete_run_when_all_official_areas_present(self) -> None:
        official_codes = eg6b.EG6B_AREA_CODES
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                raw_log_rows=[
                    raw_log_row(run_id=RUN_A, called_at="2026-07-24 08:00:05", area=area)
                    for area in official_codes
                ]
                + [raw_log_row(run_id=RUN_B, called_at="2026-07-24 08:05:05", area="POI072")],
                current_rows=[
                    current_row(run_id=RUN_A, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00", area=area)
                    for area in official_codes
                ]
                + [current_row(run_id=RUN_B, called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05", area="POI072")],
                forecast_rows=[],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            run_rows = [
                r for r in eg8b.build_time_coverage_rows(bundle) if r["record_type"] == eg8b.RECORD_TYPE_RUN
            ]
            by_run = {r["collection_run_id"]: r for r in run_rows}
            self.assertEqual(by_run[RUN_A]["run_completeness"], eg8b.RUN_COMPLETENESS_COMPLETE)
            self.assertEqual(by_run[RUN_A]["area_count"], len(official_codes))
            self.assertEqual(by_run[RUN_B]["run_completeness"], eg8b.RUN_COMPLETENESS_PARTIAL)

    def test_hour_rows_aggregate_and_run_fields_blank(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[
                    current_row(run_id=RUN_A, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00"),
                    current_row(run_id=RUN_B, called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05"),
                    current_row(run_id=RUN_C, called_at="2026-07-24 09:00:05", observed_at="2026-07-24 09:00"),
                ],
                forecast_rows=[],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            rows = eg8b.build_time_coverage_rows(bundle)
            hour_rows = [r for r in rows if r["record_type"] == eg8b.RECORD_TYPE_HOUR]
            self.assertEqual(len(hour_rows), 2)
            by_hour = {r["hour_of_day"]: r for r in hour_rows}
            self.assertEqual(by_hour[8]["hour_current_row_count"], 2)
            self.assertEqual(by_hour[8]["hour_distinct_observed_at_count"], 2)
            self.assertEqual(by_hour[8]["hour_date"], "2026-07-24")
            self.assertEqual(by_hour[9]["hour_current_row_count"], 1)
            for hour_row in hour_rows:
                self.assertIsNone(hour_row["collection_run_id"])
                self.assertIsNone(hour_row["run_completeness"])
            run_rows = [r for r in rows if r["record_type"] == eg8b.RECORD_TYPE_RUN]
            for run_row in run_rows:
                self.assertIsNone(run_row["hour_date"])
                self.assertIsNone(run_row["hour_current_row_count"])
            # RUN rows precede HOUR rows, both internally ordered
            self.assertEqual([r["record_type"] for r in rows], [eg8b.RECORD_TYPE_RUN] * 3 + [eg8b.RECORD_TYPE_HOUR] * 2)


class ForecastMatchTests(unittest.TestCase):
    def test_five_way_match_status_classification(self) -> None:
        """가장 중요한 회귀 테스트: EXACT_MATCH·BEFORE_DATASET_START·
        AFTER_DATASET_END·CURRENT_TARGET_MISSING·AREA_NOT_FOUND 5개 상태를
        Area별 관측 범위를 기준으로 정확히 구분해야 한다."""
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                raw_log_rows=[
                    raw_log_row(run_id=RUN_B, called_at="2026-07-24 08:00:05", area="POI072"),
                    raw_log_row(run_id=RUN_C, called_at="2026-07-24 08:10:05", area="POI072"),
                    raw_log_row(run_id=RUN_D, called_at="2026-07-24 07:00:05", area="POI072"),
                    raw_log_row(run_id=RUN_E, called_at="2026-07-24 09:00:05", area="POI019"),
                ],
                current_rows=[
                    # POI072's own observed range is [08:00, 08:10]; 08:05 is
                    # deliberately absent (an internal gap, not a boundary).
                    current_row(run_id=RUN_B, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00", area="POI072"),
                    current_row(run_id=RUN_C, called_at="2026-07-24 08:10:05", observed_at="2026-07-24 08:10", area="POI072", pop_min="31000", pop_max="33000"),
                    # POI019 has zero Current rows anywhere.
                ],
                forecast_rows=[
                    # RUN_D snapshot 07:00 -> target 07:50, before POI072's range start (08:00)
                    forecast_row(run_id=RUN_D, called_at="2026-07-24 07:00:05", observed_at="2026-07-24 07:00", forecast_at="2026-07-24 07:50", area="POI072"),
                    # RUN_B snapshot 08:00 -> target 08:05, inside range, no exact Current
                    forecast_row(run_id=RUN_B, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00", forecast_at="2026-07-24 08:05", area="POI072"),
                    # RUN_B -> target 08:10, exact match with RUN_C's Current
                    forecast_row(run_id=RUN_B, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00", forecast_at="2026-07-24 08:10", area="POI072"),
                    # RUN_B -> target 08:20, after POI072's range end (08:10)
                    forecast_row(run_id=RUN_B, called_at="2026-07-24 08:00:05", observed_at="2026-07-24 08:00", forecast_at="2026-07-24 08:20", area="POI072"),
                    # RUN_E -> POI019 has no Current data at all
                    forecast_row(run_id=RUN_E, called_at="2026-07-24 09:00:05", observed_at="2026-07-24 09:00", forecast_at="2026-07-24 09:05", area="POI019"),
                ],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            summary = eg8b.build_forecast_match_summary(bundle)
            self.assertEqual(summary["total_forecast_rows"], 5)
            self.assertEqual(
                summary["status_counts"],
                {
                    eg8b.MATCH_STATUS_EXACT_MATCH: 1,
                    eg8b.MATCH_STATUS_BEFORE_DATASET_START: 1,
                    eg8b.MATCH_STATUS_AFTER_DATASET_END: 1,
                    eg8b.MATCH_STATUS_CURRENT_TARGET_MISSING: 1,
                    eg8b.MATCH_STATUS_AREA_NOT_FOUND: 1,
                },
            )
            self.assertEqual(summary["exact_match_rows"], 1)
            self.assertEqual(summary["match_failure_rows"], 4)
            # backward-compatible derived fields
            self.assertEqual(summary["no_match_dataset_boundary_rows"], 2)  # BEFORE + AFTER
            self.assertEqual(summary["no_match_other_rows"], 2)  # MISSING + NOT_FOUND

            pairs = eg8b.build_forecast_evaluation_pairs_rows(bundle)
            self.assertEqual(len(pairs), 1)
            self.assertEqual(pairs[0]["forecast_at"], "2026-07-24T08:10:00+09:00")
            self.assertEqual(pairs[0]["current_population_min"], 31000)
            self.assertEqual(pairs[0]["horizon_minutes"], 10)

    def test_no_forecast_rows_yields_zero_totals(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(output_root),
                current_rows=[current_row()],
                forecast_rows=[],
            )
            bundle = eg8b.load_dataset_bundle(export.dataset_dir)
            summary = eg8b.build_forecast_match_summary(bundle)
            self.assertEqual(summary["total_forecast_rows"], 0)
            self.assertIsNone(summary["exact_match_rate"])
            self.assertEqual(eg8b.build_forecast_evaluation_pairs_rows(bundle), [])


class OutputWriterTests(unittest.TestCase):
    def test_run_phase1_creates_five_files(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as upstream_root, tempfile.TemporaryDirectory() as eg8b_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(upstream_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row(forecast_at="2026-07-24 09:00")],
            )
            result = eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(eg8b_root))
            for filename in (
                eg8b.DATASET_PROFILE_FILENAME,
                eg8b.AREA_CURRENT_SUMMARY_FILENAME,
                eg8b.TIME_COVERAGE_FILENAME,
                eg8b.FORECAST_MATCH_SUMMARY_FILENAME,
                eg8b.FORECAST_EVALUATION_PAIRS_FILENAME,
            ):
                self.assertTrue((result.phase_dir / filename).is_file())
            self.assertEqual(result.phase_dir.name, eg8b.PHASE1_VERSION)
            self.assertEqual(result.phase_dir.parent.name, export.dataset_id)

    def test_upstream_dataset_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as upstream_root, tempfile.TemporaryDirectory() as eg8b_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(upstream_root),
                current_rows=[current_row()],
                forecast_rows=[forecast_row(forecast_at="2026-07-24 09:00")],
            )
            before = {
                path.name: path.read_bytes() for path in export.dataset_dir.iterdir() if path.is_file()
            }
            eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(eg8b_root))
            after = {
                path.name: path.read_bytes() for path in export.dataset_dir.iterdir() if path.is_file()
            }
            self.assertEqual(before, after)

    def test_phase1_directory_collision_raises_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as upstream_root, tempfile.TemporaryDirectory() as eg8b_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(upstream_root),
                current_rows=[current_row()],
                forecast_rows=[],
            )
            first = eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(eg8b_root))
            profile_before = (first.phase_dir / eg8b.DATASET_PROFILE_FILENAME).read_bytes()
            with self.assertRaises(eg8b.EvidenceWriteError):
                eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(eg8b_root))
            profile_after = (first.phase_dir / eg8b.DATASET_PROFILE_FILENAME).read_bytes()
            self.assertEqual(profile_before, profile_after)

    def test_dataset_id_directory_may_preexist(self) -> None:
        """<dataset_id> is allowed to already exist so a later phase/version
        can coexist under the same parent; only phase1-v1 is exclusive."""
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as upstream_root, tempfile.TemporaryDirectory() as eg8b_root:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(upstream_root),
                current_rows=[current_row()],
                forecast_rows=[],
            )
            (Path(eg8b_root) / export.dataset_id).mkdir()
            result = eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(eg8b_root))
            self.assertTrue(result.phase_dir.is_dir())

    def test_write_exclusive_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.txt"
            eg8b._write_exclusive(path, b"first")
            with self.assertRaises(eg8b.EvidenceWriteError):
                eg8b._write_exclusive(path, b"second")
            self.assertEqual(path.read_bytes(), b"first")


class DeterminismTests(unittest.TestCase):
    def test_same_generated_at_produces_byte_identical_output(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as upstream_root, tempfile.TemporaryDirectory() as root_a, tempfile.TemporaryDirectory() as root_b:
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(upstream_root),
                current_rows=[
                    current_row(run_id=RUN_A),
                    current_row(run_id=RUN_B, called_at="2026-07-24 08:05:05", observed_at="2026-07-24 08:05"),
                ],
                forecast_rows=[forecast_row(run_id=RUN_A, forecast_at="2026-07-24 09:00")],
            )
            fixed_time = eg8a.parse_kst_datetime("2026-07-24 12:00:00")
            result_a = eg8b.run_phase1(
                export.dataset_dir, eg8b_output_root=Path(root_a), generated_at=fixed_time
            )
            result_b = eg8b.run_phase1(
                export.dataset_dir, eg8b_output_root=Path(root_b), generated_at=fixed_time
            )
            for filename in (
                eg8b.DATASET_PROFILE_FILENAME,
                eg8b.AREA_CURRENT_SUMMARY_FILENAME,
                eg8b.TIME_COVERAGE_FILENAME,
                eg8b.FORECAST_MATCH_SUMMARY_FILENAME,
                eg8b.FORECAST_EVALUATION_PAIRS_FILENAME,
            ):
                content_a = (result_a.phase_dir / filename).read_bytes()
                content_b = (result_b.phase_dir / filename).read_bytes()
                self.assertEqual(content_a, content_b, f"{filename} differs between runs")


class ResolveOutputRootTests(unittest.TestCase):
    def test_missing_env_raises(self) -> None:
        with self.assertRaises(eg8b.OutputRootConfigurationError):
            eg8b.resolve_output_root_from_env({})

    def test_nonexistent_path_raises(self) -> None:
        with self.assertRaises(eg8b.OutputRootConfigurationError):
            eg8b.resolve_output_root_from_env(
                {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV: "/no/such/path/at/all/eg8b"}
            )

    def test_valid_directory_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resolved = eg8b.resolve_output_root_from_env({eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV: tmp})
            self.assertTrue(resolved.is_dir())


if __name__ == "__main__":
    unittest.main()
