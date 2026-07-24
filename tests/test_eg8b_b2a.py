from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from freshmanager import eg8a, eg8b, eg8b_b2a


RAW_LOG_HEADER = list(eg8a.RAW_LOG_REQUIRED_COLUMNS)
CURRENT_HEADER = list(eg8a.CURRENT_REQUIRED_COLUMNS)
FORECAST_HEADER = list(eg8a.FORECAST_REQUIRED_COLUMNS)

RUN_A = "11111111-1111-4111-8111-111111111111"
RUN_B = "22222222-2222-4222-8222-222222222222"


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


def build_full_pipeline(
    *,
    staging_dir: Path,
    eg8a_output_root: Path,
    eg8b_output_root: Path,
    current_rows: list[list[str]],
    forecast_rows: list[list[str]],
    raw_log_rows: list[list[str]] | None = None,
    dataset_id: str | None = None,
    b1_generated_at: datetime | None = None,
) -> tuple[eg8a.DatasetExportResult, eg8b.Eg8bAnalysisResult]:
    """EG-8A normalize+export -> EG-8B B1 run_phase1, so B2a tests exercise
    the real upstream chain rather than hand-faked B1 output shapes."""
    export = build_upstream_dataset(
        staging_dir=staging_dir,
        output_root=eg8a_output_root,
        current_rows=current_rows,
        forecast_rows=forecast_rows,
        raw_log_rows=raw_log_rows,
        dataset_id=dataset_id,
    )
    b1_result = eg8b.run_phase1(
        export.dataset_dir, eg8b_output_root=eg8b_output_root, generated_at=b1_generated_at
    )
    return export, b1_result


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
    """Hand-build a DatasetBundle for unit-level tests that do not need a
    real eg8a.export_dataset round trip."""
    return eg8b.DatasetBundle(
        dataset_id="unit-test-dataset",
        dataset_dir=Path("/nonexistent"),
        manifest={},
        quality_report=quality_report if quality_report is not None else {},
        current_rows=current_rows,
        forecast_rows=forecast_rows,
        error_rows=error_rows,
    )


def make_pair_row(**overrides: object) -> eg8b_b2a.PairRow:
    base: dict[str, object] = dict(
        area_code="POI072",
        forecast_collection_run_id=RUN_A,
        forecast_called_at="2026-07-24T08:00:05+09:00",
        forecast_observed_at="2026-07-24T08:00:00+09:00",
        forecast_at="2026-07-24T08:30:00+09:00",
        horizon_minutes=30,
        forecast_congestion_level="보통",
        forecast_population_min=32000,
        forecast_population_max=34000,
        forecast_population_mid=33000.0,
        forecast_duplicate_flag=False,
        actual_collection_run_id=RUN_B,
        actual_called_at="2026-07-24T08:30:05+09:00",
        actual_congestion_level="보통",
        actual_population_min=32500,
        actual_population_max=33500,
        actual_population_mid=33000.0,
        actual_duplicate_flag=False,
    )
    base.update(overrides)
    return eg8b_b2a.PairRow(**base)


def make_b1_bundle(**overrides: object) -> eg8b_b2a.B1OutputBundle:
    base: dict[str, object] = dict(
        dataset_id="unit-test-dataset",
        dataset_profile={"dataset_id": "unit-test-dataset"},
        forecast_match_summary={"exact_match_rows": 0},
        pairs=(),
    )
    base.update(overrides)
    return eg8b_b2a.B1OutputBundle(**base)


def make_pairs_row(**overrides: object) -> dict[str, object]:
    """A hand-built row shaped like build_b0_baseline_pairs_rows' own output
    dicts, for testing build_area_performance_rows/build_horizon_performance_rows
    directly without a full pipeline round trip."""
    base: dict[str, object] = dict(
        area_code="POI072",
        forecast_collection_run_id=RUN_A,
        forecast_called_at="2026-07-24T08:00:05+09:00",
        forecast_observed_at="2026-07-24T08:00:00+09:00",
        forecast_at="2026-07-24T08:30:00+09:00",
        horizon_minutes=30,
        origin_collection_run_id=RUN_A,
        origin_called_at="2026-07-24T08:00:05+09:00",
        origin_population_min=30000,
        origin_population_max=32000,
        origin_population_mid=31000.0,
        origin_congestion_level="여유",
        origin_duplicate_flag=False,
        forecast_population_min=32000,
        forecast_population_max=34000,
        forecast_population_mid=33000.0,
        forecast_congestion_level="보통",
        forecast_duplicate_flag=False,
        actual_population_min=32500,
        actual_population_max=33500,
        actual_population_mid=33000.0,
        actual_congestion_level="보통",
        actual_duplicate_flag=False,
        forecast_abs_error=0.0,
        forecast_relative_error=0.0,
        forecast_interval_included=True,
        forecast_congestion_match=True,
        b0_abs_error=2000.0,
        b0_relative_error=2000.0 / 33000.0,
        b0_interval_included=False,
        b0_congestion_match=False,
    )
    base.update(overrides)
    return base


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


# A single hand-verifiable scenario reused by several test classes:
# RUN_A's Current @ 08:00 is B0's Origin (min=30000, max=32000, mid=31000,
# 여유). RUN_A's Forecast targets 08:30 (min=32000, max=34000, mid=33000,
# 보통). RUN_B's Current @ 08:30 is the ground truth Actual (min=32500,
# max=33500, mid=33000, 보통) that B1 Exact-Matches the Forecast against.
# RUN_B also carries a dummy Forecast (targeting 10:30, unused in
# assertions) purely so its Source Correlation Key triple is complete and
# it does not produce an unrelated SOURCE_KEY_MISMATCH error row.
_SCENARIO_CURRENT_ROWS = [
    current_row(run_id=RUN_A, observed_at="2026-07-24 08:00", pop_min="30000", pop_max="32000", congestion="여유"),
    current_row(run_id=RUN_B, called_at="2026-07-24 08:30:05", observed_at="2026-07-24 08:30", pop_min="32500", pop_max="33500", congestion="보통"),
]
_SCENARIO_FORECAST_ROWS = [
    forecast_row(run_id=RUN_A, observed_at="2026-07-24 08:00", forecast_at="2026-07-24 08:30", pop_min="32000", pop_max="34000", congestion="보통"),
    forecast_row(run_id=RUN_B, called_at="2026-07-24 08:30:05", observed_at="2026-07-24 08:30", forecast_at="2026-07-24 10:30", pop_min="1", pop_max="2", congestion="여유"),
]


class B1OutputBundleValidationTests(unittest.TestCase):
    def test_missing_phase_dir_raises(self) -> None:
        with self.assertRaises(eg8b_b2a.B1OutputValidationError) as ctx:
            eg8b_b2a.load_b1_output_bundle(Path("/nonexistent/phase1-v1"))
        self.assertIn(eg8b_b2a.ERROR_B1_OUTPUT_FILE_MISSING, str(ctx.exception))

    def test_missing_output_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as eg8a_root, tempfile.TemporaryDirectory() as eg8b_root:
            _export, b1_result = build_full_pipeline(
                staging_dir=Path(staging),
                eg8a_output_root=Path(eg8a_root),
                eg8b_output_root=Path(eg8b_root),
                current_rows=_SCENARIO_CURRENT_ROWS,
                forecast_rows=_SCENARIO_FORECAST_ROWS,
            )
            (b1_result.phase_dir / eg8b.TIME_COVERAGE_FILENAME).unlink()
            with self.assertRaises(eg8b_b2a.B1OutputValidationError) as ctx:
                eg8b_b2a.load_b1_output_bundle(b1_result.phase_dir)
            self.assertIn(eg8b_b2a.ERROR_B1_OUTPUT_FILE_MISSING, str(ctx.exception))

    def test_dataset_id_mismatch_raises(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as eg8a_root, tempfile.TemporaryDirectory() as eg8b_root:
            _export, b1_result = build_full_pipeline(
                staging_dir=Path(staging),
                eg8a_output_root=Path(eg8a_root),
                eg8b_output_root=Path(eg8b_root),
                current_rows=_SCENARIO_CURRENT_ROWS,
                forecast_rows=_SCENARIO_FORECAST_ROWS,
            )
            with self.assertRaises(eg8b_b2a.B1OutputValidationError) as ctx:
                eg8b_b2a.load_b1_output_bundle(
                    b1_result.phase_dir, expected_dataset_id="00000000-0000-4000-8000-000000000000"
                )
            self.assertIn(eg8b_b2a.ERROR_B1_DATASET_ID_MISMATCH, str(ctx.exception))

    def test_exact_match_count_mismatch_raises(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as eg8a_root, tempfile.TemporaryDirectory() as eg8b_root:
            _export, b1_result = build_full_pipeline(
                staging_dir=Path(staging),
                eg8a_output_root=Path(eg8a_root),
                eg8b_output_root=Path(eg8b_root),
                current_rows=_SCENARIO_CURRENT_ROWS,
                forecast_rows=_SCENARIO_FORECAST_ROWS,
            )
            summary_path = b1_result.phase_dir / eg8b.FORECAST_MATCH_SUMMARY_FILENAME
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["exact_match_rows"] = summary["exact_match_rows"] + 1
            summary_path.unlink()
            summary_path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(eg8b_b2a.B1OutputValidationError) as ctx:
                eg8b_b2a.load_b1_output_bundle(b1_result.phase_dir)
            self.assertIn(eg8b_b2a.ERROR_B1_EXACT_MATCH_COUNT_MISMATCH, str(ctx.exception))

    def test_valid_bundle_loads_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as eg8a_root, tempfile.TemporaryDirectory() as eg8b_root:
            export, b1_result = build_full_pipeline(
                staging_dir=Path(staging),
                eg8a_output_root=Path(eg8a_root),
                eg8b_output_root=Path(eg8b_root),
                current_rows=_SCENARIO_CURRENT_ROWS,
                forecast_rows=_SCENARIO_FORECAST_ROWS,
            )
            bundle = eg8b_b2a.load_b1_output_bundle(
                b1_result.phase_dir, expected_dataset_id=export.dataset_id
            )
            self.assertEqual(bundle.dataset_id, export.dataset_id)
            self.assertEqual(len(bundle.pairs), 1)
            self.assertEqual(bundle.pairs[0].area_code, "POI072")
            self.assertEqual(bundle.pairs[0].horizon_minutes, 30)


class B0BaselineComputationTests(unittest.TestCase):
    def test_single_pair_hand_computed_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as eg8a_root, tempfile.TemporaryDirectory() as eg8b_root:
            export, b1_result = build_full_pipeline(
                staging_dir=Path(staging),
                eg8a_output_root=Path(eg8a_root),
                eg8b_output_root=Path(eg8b_root),
                current_rows=_SCENARIO_CURRENT_ROWS,
                forecast_rows=_SCENARIO_FORECAST_ROWS,
            )
            b1_bundle = eg8b_b2a.load_b1_output_bundle(b1_result.phase_dir)
            eg8a_bundle = eg8b.load_dataset_bundle(export.dataset_dir, expected_dataset_id=b1_bundle.dataset_id)

            rows, missing = eg8b_b2a.build_b0_baseline_pairs_rows(b1_bundle, eg8a_bundle)

            self.assertEqual(missing, 0)
            self.assertEqual(len(rows), 1)
            row = rows[0]

            self.assertEqual(row["origin_population_min"], 30000)
            self.assertEqual(row["origin_population_max"], 32000)
            self.assertEqual(row["origin_population_mid"], 31000.0)
            self.assertEqual(row["origin_congestion_level"], "여유")

            self.assertEqual(row["forecast_population_mid"], 33000.0)
            self.assertEqual(row["actual_population_mid"], 33000.0)

            self.assertEqual(row["forecast_abs_error"], 0.0)
            self.assertEqual(row["forecast_relative_error"], 0.0)
            self.assertTrue(row["forecast_interval_included"])
            self.assertTrue(row["forecast_congestion_match"])

            self.assertEqual(row["b0_abs_error"], 2000.0)
            self.assertAlmostEqual(row["b0_relative_error"], 2000.0 / 33000.0)
            self.assertFalse(row["b0_interval_included"])
            self.assertFalse(row["b0_congestion_match"])


class BacktestSummaryTests(unittest.TestCase):
    def test_evaluation_and_coverage_status_are_always_provisional_single_day(self) -> None:
        b1_bundle = make_b1_bundle()
        summary = eg8b_b2a.build_backtest_summary(
            generated_at=datetime(2026, 7, 24, 12, 0, 0, tzinfo=eg8a.SEOUL),
            b1_bundle=b1_bundle,
            eg8a_dataset_id=b1_bundle.dataset_id,
            pairs_rows=[make_pairs_row()],
            origin_lookup_missing_count=0,
        )

        self.assertEqual(summary["evaluation_status"], eg8b_b2a.EVALUATION_STATUS_PROVISIONAL)
        self.assertEqual(summary["evaluation_status"], "PROVISIONAL")
        self.assertEqual(summary["coverage_status"], eg8b_b2a.COVERAGE_STATUS_SINGLE_DAY_PARTIAL)
        self.assertEqual(summary["coverage_status"], "SINGLE_DAY_PARTIAL_COVERAGE")
        self.assertIsNone(summary["gate_judgment"])


class OriginLookupMissingTests(unittest.TestCase):
    def test_missing_origin_excluded_and_counted(self) -> None:
        pair = make_pair_row(forecast_observed_at="2026-07-24T09:00:00+09:00")
        eg8a_bundle = make_bundle(current_rows=(make_current_row(observed_at="2026-07-24T08:00:00+09:00"),))
        b1_bundle = make_b1_bundle(pairs=(pair,))

        rows, missing = eg8b_b2a.build_b0_baseline_pairs_rows(b1_bundle, eg8a_bundle)

        self.assertEqual(rows, [])
        self.assertEqual(missing, 1)

    def test_found_origin_not_counted_as_missing(self) -> None:
        pair = make_pair_row(forecast_observed_at="2026-07-24T08:00:00+09:00")
        eg8a_bundle = make_bundle(current_rows=(make_current_row(observed_at="2026-07-24T08:00:00+09:00"),))
        b1_bundle = make_b1_bundle(pairs=(pair,))

        rows, missing = eg8b_b2a.build_b0_baseline_pairs_rows(b1_bundle, eg8a_bundle)

        self.assertEqual(len(rows), 1)
        self.assertEqual(missing, 0)


class RelativeErrorZeroActualTests(unittest.TestCase):
    def test_zero_actual_mid_excludes_relative_error_only(self) -> None:
        pair = make_pair_row(
            forecast_observed_at="2026-07-24T08:00:00+09:00",
            actual_population_min=0,
            actual_population_max=0,
            actual_population_mid=0.0,
        )
        eg8a_bundle = make_bundle(current_rows=(make_current_row(observed_at="2026-07-24T08:00:00+09:00"),))
        b1_bundle = make_b1_bundle(pairs=(pair,))

        rows, missing = eg8b_b2a.build_b0_baseline_pairs_rows(b1_bundle, eg8a_bundle)

        self.assertEqual(missing, 0)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNone(row["forecast_relative_error"])
        self.assertIsNone(row["b0_relative_error"])
        self.assertIsNotNone(row["forecast_abs_error"])
        self.assertIsNotNone(row["b0_abs_error"])

        area_rows = eg8b_b2a.build_area_performance_rows(rows)
        self.assertEqual(len(area_rows), 1)
        self.assertEqual(area_rows[0]["pair_count"], 1)
        self.assertEqual(area_rows[0]["forecast_relative_error_sample_count"], 0)
        self.assertIsNone(area_rows[0]["forecast_mean_relative_error"])
        self.assertIsNotNone(area_rows[0]["forecast_mae"])


class AreaPerformanceTests(unittest.TestCase):
    def test_aggregates_across_multiple_areas(self) -> None:
        rows = [
            make_pairs_row(area_code="POI072"),
            make_pairs_row(area_code="POI072", forecast_abs_error=10.0, b0_abs_error=20.0),
            make_pairs_row(area_code="POI019", forecast_abs_error=5.0, b0_abs_error=1.0),
        ]

        area_rows = eg8b_b2a.build_area_performance_rows(rows)

        self.assertEqual([r["area_code"] for r in area_rows], ["POI019", "POI072"])
        poi072 = next(r for r in area_rows if r["area_code"] == "POI072")
        poi019 = next(r for r in area_rows if r["area_code"] == "POI019")
        self.assertEqual(poi072["pair_count"], 2)
        self.assertEqual(poi019["pair_count"], 1)
        self.assertAlmostEqual(poi072["forecast_mae"], (0.0 + 10.0) / 2)
        self.assertTrue(poi072["forecast_mae_lower_than_b0"])
        self.assertFalse(poi019["forecast_mae_lower_than_b0"])

    def test_no_rows_produces_empty_list(self) -> None:
        self.assertEqual(eg8b_b2a.build_area_performance_rows([]), [])


class HorizonPerformanceTests(unittest.TestCase):
    def test_aggregates_across_multiple_horizons(self) -> None:
        rows = [
            make_pairs_row(horizon_minutes=30),
            make_pairs_row(horizon_minutes=30),
            make_pairs_row(horizon_minutes=60),
        ]

        horizon_rows = eg8b_b2a.build_horizon_performance_rows(rows)

        self.assertEqual([r["horizon_minutes"] for r in horizon_rows], [30, 60])
        self.assertEqual(horizon_rows[0]["pair_count"], 2)
        self.assertEqual(horizon_rows[1]["pair_count"], 1)


class OutputWriterTests(unittest.TestCase):
    def test_run_backtest_creates_four_files_and_preserves_b1_output(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as eg8a_root, tempfile.TemporaryDirectory() as eg8b_root:
            export, b1_result = build_full_pipeline(
                staging_dir=Path(staging),
                eg8a_output_root=Path(eg8a_root),
                eg8b_output_root=Path(eg8b_root),
                current_rows=_SCENARIO_CURRENT_ROWS,
                forecast_rows=_SCENARIO_FORECAST_ROWS,
            )
            b1_hashes_before = {
                p.name: sha256_of(p) for p in b1_result.phase_dir.iterdir() if p.is_file()
            }

            result = eg8b_b2a.run_backtest(
                export.dataset_dir,
                b1_result.phase_dir,
                eg8b_output_root=Path(eg8b_root),
            )

            self.assertEqual(result.dataset_id, export.dataset_id)
            self.assertEqual(result.phase_dir.name, eg8b_b2a.PHASE_B2A_VERSION)
            created = sorted(p.name for p in result.phase_dir.iterdir())
            self.assertEqual(
                created,
                sorted(
                    [
                        eg8b_b2a.B0_BASELINE_PAIRS_FILENAME,
                        eg8b_b2a.AREA_PERFORMANCE_FILENAME,
                        eg8b_b2a.HORIZON_PERFORMANCE_FILENAME,
                        eg8b_b2a.BACKTEST_SUMMARY_FILENAME,
                    ]
                ),
            )

            self.assertTrue((Path(eg8b_root) / export.dataset_id / "phase1-v1").is_dir())
            self.assertTrue((Path(eg8b_root) / export.dataset_id / eg8b_b2a.PHASE_B2A_VERSION).is_dir())
            b1_hashes_after = {
                p.name: sha256_of(p) for p in b1_result.phase_dir.iterdir() if p.is_file()
            }
            self.assertEqual(b1_hashes_before, b1_hashes_after)

    def test_phase_b2a_directory_collision_raises_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as eg8a_root, tempfile.TemporaryDirectory() as eg8b_root:
            export, b1_result = build_full_pipeline(
                staging_dir=Path(staging),
                eg8a_output_root=Path(eg8a_root),
                eg8b_output_root=Path(eg8b_root),
                current_rows=_SCENARIO_CURRENT_ROWS,
                forecast_rows=_SCENARIO_FORECAST_ROWS,
            )
            first = eg8b_b2a.run_backtest(
                export.dataset_dir, b1_result.phase_dir, eg8b_output_root=Path(eg8b_root)
            )
            summary_before = (first.phase_dir / eg8b_b2a.BACKTEST_SUMMARY_FILENAME).read_bytes()

            with self.assertRaises(eg8b_b2a.EvidenceWriteError):
                eg8b_b2a.run_backtest(
                    export.dataset_dir, b1_result.phase_dir, eg8b_output_root=Path(eg8b_root)
                )

            summary_after = (first.phase_dir / eg8b_b2a.BACKTEST_SUMMARY_FILENAME).read_bytes()
            self.assertEqual(summary_before, summary_after)

    def test_write_exclusive_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file.txt"
            eg8b_b2a._write_exclusive(path, b"first")
            with self.assertRaises(eg8b_b2a.EvidenceWriteError):
                eg8b_b2a._write_exclusive(path, b"second")
            self.assertEqual(path.read_bytes(), b"first")


class DeterminismTests(unittest.TestCase):
    def test_same_generated_at_produces_byte_identical_output(self) -> None:
        fixed_time = datetime(2026, 7, 24, 12, 0, 0, tzinfo=eg8a.SEOUL)
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as eg8a_root, \
                tempfile.TemporaryDirectory() as eg8b_root_1, tempfile.TemporaryDirectory() as eg8b_root_2:
            # One EG-8A dataset (read-only input, reused for both runs) but
            # two independent B1 runs -- one per eg8b_output_root -- since
            # run_phase1 itself is exclusive-create per output root.
            export = build_upstream_dataset(
                staging_dir=Path(staging),
                output_root=Path(eg8a_root),
                current_rows=_SCENARIO_CURRENT_ROWS,
                forecast_rows=_SCENARIO_FORECAST_ROWS,
            )
            b1_result = eg8b.run_phase1(
                export.dataset_dir, eg8b_output_root=Path(eg8b_root_1), generated_at=fixed_time
            )
            b1_result_2 = eg8b.run_phase1(
                export.dataset_dir, eg8b_output_root=Path(eg8b_root_2), generated_at=fixed_time
            )

            result_1 = eg8b_b2a.run_backtest(
                export.dataset_dir,
                b1_result.phase_dir,
                eg8b_output_root=Path(eg8b_root_1),
                generated_at=fixed_time,
            )
            result_2 = eg8b_b2a.run_backtest(
                export.dataset_dir,
                b1_result_2.phase_dir,
                eg8b_output_root=Path(eg8b_root_2),
                generated_at=fixed_time,
            )

            for filename in sorted(p.name for p in result_1.phase_dir.iterdir()):
                content_1 = (result_1.phase_dir / filename).read_bytes()
                content_2 = (result_2.phase_dir / filename).read_bytes()
                self.assertEqual(content_1, content_2, f"{filename} differs")


class ResolveOutputRootTests(unittest.TestCase):
    def test_missing_env_raises(self) -> None:
        with self.assertRaises(eg8b_b2a.OutputRootConfigurationError):
            eg8b_b2a.resolve_output_root_from_env({})

    def test_nonexistent_path_raises(self) -> None:
        with self.assertRaises(eg8b_b2a.OutputRootConfigurationError):
            eg8b_b2a.resolve_output_root_from_env(
                {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV: "/nonexistent/path/for/eg8b_b2a"}
            )

    def test_valid_directory_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolved = eg8b_b2a.resolve_output_root_from_env(
                {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV: directory}
            )
            self.assertEqual(resolved, Path(directory).resolve())


if __name__ == "__main__":
    unittest.main()
