from __future__ import annotations

import csv
import hashlib
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from freshmanager import eg6b, eg8a, eg8b, eg8b_b2b


RAW_LOG_HEADER = list(eg8a.RAW_LOG_REQUIRED_COLUMNS)
CURRENT_HEADER = list(eg8a.CURRENT_REQUIRED_COLUMNS)
FORECAST_HEADER = list(eg8a.FORECAST_REQUIRED_COLUMNS)

RUN_A = "11111111-1111-4111-8111-111111111111"
RUN_B = "22222222-2222-4222-8222-222222222222"
RUN_C = "33333333-3333-4333-8333-333333333333"
RUN_D = "44444444-4444-4444-8444-444444444444"

WINDOW_START = datetime.fromisoformat("2026-07-24T01:00:00+09:00")
SNAPSHOT_CUTOFF = datetime.fromisoformat("2026-07-25T07:00:00+09:00")


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


def write_source_csvs(
    directory: Path,
    *,
    current_rows: list[list[str]],
    forecast_rows: list[list[str]],
    raw_log_rows: list[list[str]] | None = None,
) -> tuple[Path, Path, Path]:
    """Write the three v3 source CSVs. Auto-derives raw_log_rows from
    current_rows (one SUCCESS row per distinct (run_id, area)) unless the
    caller supplies its own, mirroring test_eg8b_b2a.py's build_upstream_
    dataset helper."""
    if raw_log_rows is None:
        seen: set[tuple[str, str]] = set()
        raw_log_rows = []
        for row in current_rows:
            key = (row[0], row[3])
            if key not in seen:
                seen.add(key)
                raw_log_rows.append(raw_log_row(run_id=row[0], called_at=row[1], area=row[3]))

    raw_path = write_csv(directory, "raw.csv", RAW_LOG_HEADER, raw_log_rows)
    current_path = write_csv(directory, "current.csv", CURRENT_HEADER, current_rows)
    forecast_path = write_csv(directory, "forecast.csv", FORECAST_HEADER, forecast_rows)
    return raw_path, current_path, forecast_path


def make_current_record(**overrides: object) -> eg8a.NormalizedCurrentRecord:
    base: dict[str, object] = dict(
        collection_run_id=RUN_A,
        called_at="2026-07-24T01:00:05+09:00",
        observed_at="2026-07-24T01:00:00+09:00",
        area_code="POI072",
        area_code_requested="POI072",
        area_code_returned="POI072",
        area_name="여의도",
        congestion_level="여유",
        population_min=30000,
        population_max=32000,
        population_mid=31000.0,
        source_status="SUCCESS",
        duplicate_flag=False,
    )
    base.update(overrides)
    return eg8a.NormalizedCurrentRecord(**base)


def make_forecast_record(**overrides: object) -> eg8a.NormalizedForecastRecord:
    base: dict[str, object] = dict(
        collection_run_id=RUN_A,
        called_at="2026-07-24T01:00:05+09:00",
        observed_at="2026-07-24T01:00:00+09:00",
        forecast_at="2026-07-24T02:00:00+09:00",
        area_code="POI072",
        area_code_requested="POI072",
        area_code_returned="POI072",
        area_name="여의도",
        forecast_congestion_level="보통",
        forecast_population_min=32000,
        forecast_population_max=34000,
        forecast_population_mid=33000.0,
        source_status="SUCCESS",
        duplicate_flag=False,
    )
    base.update(overrides)
    return eg8a.NormalizedForecastRecord(**base)


def make_included_dataset(
    *,
    current_records: tuple[eg8a.NormalizedCurrentRecord, ...] = (),
    forecast_records: tuple[eg8a.NormalizedForecastRecord, ...] = (),
    raw_log_included_count: int = 0,
) -> eg8b_b2b.IncludedDataset:
    return eg8b_b2b.IncludedDataset(
        current_records=current_records,
        forecast_records=forecast_records,
        raw_log_included_count=raw_log_included_count,
    )


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class AnalysisWindowValidationTests(unittest.TestCase):
    def test_naive_window_start_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(directory), current_rows=[current_row()], forecast_rows=[forecast_row()]
            )
            with self.assertRaises(eg8b_b2b.AnalysisWindowError):
                eg8b_b2b.load_included_dataset(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    analysis_window_start=datetime(2026, 7, 24, 1, 0, 0),
                    snapshot_cutoff=SNAPSHOT_CUTOFF,
                )

    def test_naive_cutoff_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(directory), current_rows=[current_row()], forecast_rows=[forecast_row()]
            )
            with self.assertRaises(eg8b_b2b.AnalysisWindowError):
                eg8b_b2b.load_included_dataset(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    analysis_window_start=WINDOW_START,
                    snapshot_cutoff=datetime(2026, 7, 25, 7, 0, 0),
                )

    def test_start_not_before_cutoff_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(directory), current_rows=[current_row()], forecast_rows=[forecast_row()]
            )
            with self.assertRaises(eg8b_b2b.AnalysisWindowError):
                eg8b_b2b.load_included_dataset(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    analysis_window_start=SNAPSHOT_CUTOFF,
                    snapshot_cutoff=WINDOW_START,
                )


class LoadIncludedDatasetFilterTests(unittest.TestCase):
    """Window: 2026-07-24T01:00 .. 2026-07-24T03:00 (a short, easy-to-reason
    2-hour window distinct from the real PM window used elsewhere)."""

    WINDOW = datetime.fromisoformat("2026-07-24T01:00:00+09:00")
    CUTOFF = datetime.fromisoformat("2026-07-24T03:00:00+09:00")

    def test_observed_at_before_window_start_excluded(self) -> None:
        rows = [
            current_row(run_id=RUN_A, called_at="2026-07-24 00:55:05", observed_at="2026-07-24 00:55"),
            current_row(run_id=RUN_B, called_at="2026-07-24 01:00:05", observed_at="2026-07-24 01:00"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(directory), current_rows=rows, forecast_rows=[]
            )
            included = eg8b_b2b.load_included_dataset(
                raw_log_path=raw_path,
                current_path=current_path,
                forecast_path=forecast_path,
                analysis_window_start=self.WINDOW,
                snapshot_cutoff=self.CUTOFF,
            )
            self.assertEqual(len(included.current_records), 1)
            self.assertEqual(included.current_records[0].collection_run_id, RUN_B)

    def test_observed_at_equal_to_window_start_included(self) -> None:
        rows = [current_row(run_id=RUN_A, called_at="2026-07-24 01:00:05", observed_at="2026-07-24 01:00")]
        with tempfile.TemporaryDirectory() as directory:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(directory), current_rows=rows, forecast_rows=[]
            )
            included = eg8b_b2b.load_included_dataset(
                raw_log_path=raw_path,
                current_path=current_path,
                forecast_path=forecast_path,
                analysis_window_start=self.WINDOW,
                snapshot_cutoff=self.CUTOFF,
            )
            self.assertEqual(len(included.current_records), 1)

    def test_called_at_after_cutoff_excluded_even_if_observed_at_in_window(self) -> None:
        rows = [
            current_row(run_id=RUN_A, called_at="2026-07-24 03:05:00", observed_at="2026-07-24 02:55"),
            current_row(run_id=RUN_B, called_at="2026-07-24 03:00:00", observed_at="2026-07-24 02:55"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(directory), current_rows=rows, forecast_rows=[]
            )
            included = eg8b_b2b.load_included_dataset(
                raw_log_path=raw_path,
                current_path=current_path,
                forecast_path=forecast_path,
                analysis_window_start=self.WINDOW,
                snapshot_cutoff=self.CUTOFF,
            )
            self.assertEqual(len(included.current_records), 1)
            self.assertEqual(included.current_records[0].collection_run_id, RUN_B)

    def test_raw_log_excluded_when_run_not_included_via_current(self) -> None:
        # RUN_A's Current falls before the Window Start, so it is excluded
        # from included_current -- Raw Log must not independently re-include
        # RUN_A just because its own called_at satisfies the Cutoff.
        current_rows = [
            current_row(run_id=RUN_A, called_at="2026-07-24 00:55:05", observed_at="2026-07-24 00:55"),
            current_row(run_id=RUN_B, called_at="2026-07-24 01:00:05", observed_at="2026-07-24 01:00"),
        ]
        raw_log_rows = [
            raw_log_row(run_id=RUN_A, called_at="2026-07-24 00:55:05"),
            raw_log_row(run_id=RUN_B, called_at="2026-07-24 01:00:05"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(directory), current_rows=current_rows, forecast_rows=[], raw_log_rows=raw_log_rows
            )
            included = eg8b_b2b.load_included_dataset(
                raw_log_path=raw_path,
                current_path=current_path,
                forecast_path=forecast_path,
                analysis_window_start=self.WINDOW,
                snapshot_cutoff=self.CUTOFF,
            )
            self.assertEqual(included.raw_log_included_count, 1)

    def test_raw_log_excluded_when_own_called_at_after_cutoff(self) -> None:
        # RUN_A's Current is included (observed_at/called_at both pass), but
        # a distinct Raw Log row sharing RUN_A's run_id with a later called_at
        # must still be excluded on its own called_at <= cutoff check.
        current_rows = [current_row(run_id=RUN_A, called_at="2026-07-24 01:00:05", observed_at="2026-07-24 01:00")]
        raw_log_rows = [
            raw_log_row(run_id=RUN_A, called_at="2026-07-24 01:00:05", area="POI072"),
            raw_log_row(run_id=RUN_A, called_at="2026-07-24 03:05:00", area="POI099"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(directory), current_rows=current_rows, forecast_rows=[], raw_log_rows=raw_log_rows
            )
            included = eg8b_b2b.load_included_dataset(
                raw_log_path=raw_path,
                current_path=current_path,
                forecast_path=forecast_path,
                analysis_window_start=self.WINDOW,
                snapshot_cutoff=self.CUTOFF,
            )
            self.assertEqual(included.raw_log_included_count, 1)

    def test_source_csvs_never_modified(self) -> None:
        rows = [current_row(run_id=RUN_A, called_at="2026-07-24 01:00:05", observed_at="2026-07-24 01:00")]
        with tempfile.TemporaryDirectory() as directory:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(directory), current_rows=rows, forecast_rows=[]
            )
            hashes_before = {p: sha256_of(p) for p in (raw_path, current_path, forecast_path)}
            eg8b_b2b.load_included_dataset(
                raw_log_path=raw_path,
                current_path=current_path,
                forecast_path=forecast_path,
                analysis_window_start=self.WINDOW,
                snapshot_cutoff=self.CUTOFF,
            )
            hashes_after = {p: sha256_of(p) for p in (raw_path, current_path, forecast_path)}
            self.assertEqual(hashes_before, hashes_after)


class MatchStatusClassificationTests(unittest.TestCase):
    def test_all_five_statuses(self) -> None:
        included = make_included_dataset(
            current_records=(
                make_current_record(area_code="POI072", observed_at="2026-07-24T10:00:00+09:00"),
            ),
            forecast_records=(
                make_forecast_record(  # EXACT_MATCH
                    area_code="POI072",
                    observed_at="2026-07-24T09:00:00+09:00",
                    forecast_at="2026-07-24T10:00:00+09:00",
                ),
                make_forecast_record(  # BEFORE_ANALYSIS_START
                    area_code="POI072",
                    observed_at="2026-07-24T01:00:00+09:00",
                    forecast_at="2026-07-23T23:00:00+09:00",
                ),
                make_forecast_record(  # AFTER_EVALUATION_CUTOFF
                    area_code="POI072",
                    observed_at="2026-07-25T06:00:00+09:00",
                    forecast_at="2026-07-25T08:00:00+09:00",
                ),
                make_forecast_record(  # CURRENT_TARGET_MISSING
                    area_code="POI072",
                    observed_at="2026-07-24T10:00:00+09:00",
                    forecast_at="2026-07-24T11:00:00+09:00",
                ),
                make_forecast_record(  # AREA_NOT_FOUND
                    area_code="POI099",
                    observed_at="2026-07-24T10:00:00+09:00",
                    forecast_at="2026-07-24T10:00:00+09:00",
                ),
            ),
        )

        by_status = eg8b_b2b.classify_forecast_records(
            included, analysis_window_start=WINDOW_START, snapshot_cutoff=SNAPSHOT_CUTOFF
        )

        self.assertEqual(len(by_status[eg8b_b2b.MATCH_STATUS_EXACT_MATCH]), 1)
        self.assertEqual(len(by_status[eg8b_b2b.MATCH_STATUS_BEFORE_ANALYSIS_START]), 1)
        self.assertEqual(len(by_status[eg8b_b2b.MATCH_STATUS_AFTER_EVALUATION_CUTOFF]), 1)
        self.assertEqual(len(by_status[eg8b_b2b.MATCH_STATUS_CURRENT_TARGET_MISSING]), 1)
        self.assertEqual(len(by_status[eg8b_b2b.MATCH_STATUS_AREA_NOT_FOUND]), 1)

    def test_area_not_found_takes_priority_over_cutoff(self) -> None:
        included = make_included_dataset(
            current_records=(make_current_record(area_code="POI072"),),
            forecast_records=(
                make_forecast_record(area_code="POI099", forecast_at="2026-07-30T00:00:00+09:00"),
            ),
        )
        by_status = eg8b_b2b.classify_forecast_records(
            included, analysis_window_start=WINDOW_START, snapshot_cutoff=SNAPSHOT_CUTOFF
        )
        self.assertEqual(len(by_status[eg8b_b2b.MATCH_STATUS_AREA_NOT_FOUND]), 1)
        self.assertEqual(len(by_status[eg8b_b2b.MATCH_STATUS_AFTER_EVALUATION_CUTOFF]), 0)


class EvaluationPairsTests(unittest.TestCase):
    def test_single_pair_hand_computed_metrics(self) -> None:
        origin = make_current_record(
            collection_run_id=RUN_A,
            observed_at="2026-07-24T08:00:00+09:00",
            population_min=30000,
            population_max=32000,
            population_mid=31000.0,
            congestion_level="여유",
        )
        actual = make_current_record(
            collection_run_id=RUN_B,
            observed_at="2026-07-24T08:30:00+09:00",
            population_min=32500,
            population_max=33500,
            population_mid=33000.0,
            congestion_level="보통",
        )
        matched_forecast = make_forecast_record(
            collection_run_id=RUN_A,
            observed_at="2026-07-24T08:00:00+09:00",
            forecast_at="2026-07-24T08:30:00+09:00",
            forecast_population_min=32000,
            forecast_population_max=34000,
            forecast_population_mid=33000.0,
            forecast_congestion_level="보통",
        )
        included = make_included_dataset(current_records=(origin, actual))

        rows, missing = eg8b_b2b.build_evaluation_pairs_rows(included, [matched_forecast])

        self.assertEqual(missing, 0)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["calendar_date"], "2026-07-24")
        self.assertEqual(row["origin_population_mid"], 31000.0)
        self.assertEqual(row["actual_population_mid"], 33000.0)
        self.assertEqual(row["forecast_abs_error"], 0.0)
        self.assertEqual(row["forecast_relative_error"], 0.0)
        self.assertTrue(row["forecast_interval_included"])
        self.assertTrue(row["forecast_congestion_match"])
        self.assertEqual(row["b0_abs_error"], 2000.0)
        self.assertAlmostEqual(row["b0_relative_error"], 2000.0 / 33000.0)
        self.assertFalse(row["b0_interval_included"])
        self.assertFalse(row["b0_congestion_match"])


class OriginLookupMissingTests(unittest.TestCase):
    def test_missing_origin_excluded_and_counted(self) -> None:
        actual = make_current_record(observed_at="2026-07-24T08:30:00+09:00")
        matched_forecast = make_forecast_record(
            observed_at="2026-07-24T08:00:00+09:00", forecast_at="2026-07-24T08:30:00+09:00"
        )
        included = make_included_dataset(current_records=(actual,))

        rows, missing = eg8b_b2b.build_evaluation_pairs_rows(included, [matched_forecast])

        self.assertEqual(rows, [])
        self.assertEqual(missing, 1)


class RelativeErrorZeroActualTests(unittest.TestCase):
    def test_zero_actual_mid_excludes_relative_error_only(self) -> None:
        origin = make_current_record(observed_at="2026-07-24T08:00:00+09:00")
        actual = make_current_record(
            observed_at="2026-07-24T08:30:00+09:00",
            population_min=0,
            population_max=0,
            population_mid=0.0,
        )
        matched_forecast = make_forecast_record(
            observed_at="2026-07-24T08:00:00+09:00", forecast_at="2026-07-24T08:30:00+09:00"
        )
        included = make_included_dataset(current_records=(origin, actual))

        rows, missing = eg8b_b2b.build_evaluation_pairs_rows(included, [matched_forecast])

        self.assertEqual(missing, 0)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["forecast_relative_error"])
        self.assertIsNone(rows[0]["b0_relative_error"])
        self.assertIsNotNone(rows[0]["forecast_abs_error"])

        overall = eg8b_b2b._performance_row("scope", "overall", rows)
        self.assertEqual(overall["pair_count"], 1)
        self.assertEqual(overall["forecast_relative_error_sample_count"], 0)
        self.assertIsNone(overall["forecast_mean_relative_error"])
        self.assertIsNotNone(overall["forecast_mae"])
        self.assertIsNotNone(overall["forecast_median_abs_error"])


class MetricsByGroupAndComparisonTests(unittest.TestCase):
    def _pair(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = dict(
            area_code="POI072",
            calendar_date="2026-07-24",
            horizon_minutes=30,
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

    def test_metrics_by_date_groups_and_forecast_wins(self) -> None:
        rows = [
            self._pair(calendar_date="2026-07-24"),
            self._pair(calendar_date="2026-07-24", forecast_abs_error=10.0),
            self._pair(calendar_date="2026-07-25", forecast_abs_error=5000.0, b0_abs_error=10.0),
        ]
        by_date = eg8b_b2b.build_metrics_by_date_rows(rows)
        self.assertEqual([r["calendar_date"] for r in by_date], ["2026-07-24", "2026-07-25"])
        day1 = next(r for r in by_date if r["calendar_date"] == "2026-07-24")
        day2 = next(r for r in by_date if r["calendar_date"] == "2026-07-25")
        self.assertEqual(day1["pair_count"], 2)
        self.assertEqual(day1["comparison"], eg8b_b2b.COMPARISON_FORECAST_WIN)
        self.assertEqual(day2["comparison"], eg8b_b2b.COMPARISON_B0_WIN)

    def test_metrics_by_area_and_horizon(self) -> None:
        rows = [
            self._pair(area_code="POI072", horizon_minutes=30),
            self._pair(area_code="POI019", horizon_minutes=60),
        ]
        by_area = eg8b_b2b.build_metrics_by_area_rows(rows)
        by_horizon = eg8b_b2b.build_metrics_by_horizon_rows(rows)
        self.assertEqual([r["area_code"] for r in by_area], ["POI019", "POI072"])
        self.assertEqual([r["horizon_minutes"] for r in by_horizon], [30, 60])

    def test_tie_when_mae_equal(self) -> None:
        rows = [self._pair(forecast_abs_error=100.0, b0_abs_error=100.0)]
        overall = eg8b_b2b._performance_row("scope", "overall", rows)
        self.assertEqual(overall["comparison"], eg8b_b2b.COMPARISON_TIE)

    def test_baseline_comparison_win_tally(self) -> None:
        by_date_rows = [
            {"calendar_date": "2026-07-24", "comparison": eg8b_b2b.COMPARISON_FORECAST_WIN, "forecast_mae": 1.0, "b0_mae": 2.0},
            {"calendar_date": "2026-07-25", "comparison": eg8b_b2b.COMPARISON_B0_WIN, "forecast_mae": 5.0, "b0_mae": 1.0},
        ]
        overall_row = {"comparison": eg8b_b2b.COMPARISON_FORECAST_WIN, "forecast_mae": 1.0, "b0_mae": 2.0}
        comparison = eg8b_b2b.build_baseline_comparison(
            overall_row=overall_row, by_date_rows=by_date_rows, by_area_rows=[], by_horizon_rows=[]
        )
        self.assertEqual(comparison["win_tally"]["by_date"][eg8b_b2b.COMPARISON_FORECAST_WIN], 1)
        self.assertEqual(comparison["win_tally"]["by_date"][eg8b_b2b.COMPARISON_B0_WIN], 1)
        self.assertEqual(comparison["win_tally"]["by_date"][eg8b_b2b.COMPARISON_TIE], 0)


class DatasetCoverageTests(unittest.TestCase):
    def test_run_completeness_cadence_and_duplicate_scoping(self) -> None:
        official_areas = list(eg6b.EG6B_AREA_CODES)
        run_a_records = tuple(
            make_current_record(
                collection_run_id=RUN_A,
                called_at="2026-07-24T01:00:05+09:00",
                observed_at="2026-07-24T01:00:00+09:00",
                area_code=area,
            )
            for area in official_areas
        )
        run_b_partial = (
            make_current_record(
                collection_run_id=RUN_B,
                called_at="2026-07-24T01:05:05+09:00",
                observed_at="2026-07-24T01:05:00+09:00",
                area_code=official_areas[0],
            ),
        )
        included = make_included_dataset(
            current_records=run_a_records + run_b_partial,
            forecast_records=(),
            raw_log_included_count=14,
        )

        coverage = eg8b_b2b.build_dataset_coverage(
            included,
            b2b_run_id="unit-test-run",
            generated_at=datetime(2026, 7, 25, 12, 0, 0, tzinfo=eg8a.SEOUL),
            analysis_window_start=WINDOW_START,
            snapshot_cutoff=SNAPSHOT_CUTOFF,
            match_status_counts={status: 0 for status in eg8b_b2b.MATCH_STATUSES},
        )

        self.assertEqual(coverage["row_counts"]["current"], len(official_areas) + 1)
        self.assertEqual(coverage["run_coverage"]["included_run_count"], 2)
        self.assertEqual(coverage["run_coverage"]["complete_run_count"], 1)
        self.assertEqual(coverage["run_coverage"]["partial_run_count"], 1)
        self.assertEqual(coverage["area_coverage"]["official_area_count"], len(official_areas))
        self.assertEqual(coverage["area_coverage"]["missing_areas"], [])
        self.assertEqual(coverage["five_minute_cadence"]["deviation_count"], 0)
        self.assertEqual(coverage["five_minute_cadence"]["max_gap_minutes"], 5.0)
        self.assertEqual(coverage["calendar_date_count"], 1)
        self.assertEqual(coverage["latest_available_observed_at"], "2026-07-24T01:05:00+09:00")

    def test_duplicate_rate_scoped_to_included_records(self) -> None:
        included = make_included_dataset(
            current_records=(
                make_current_record(duplicate_flag=False),
                make_current_record(collection_run_id=RUN_B, duplicate_flag=True),
            ),
            forecast_records=(),
        )
        coverage = eg8b_b2b.build_dataset_coverage(
            included,
            b2b_run_id="unit-test-run",
            generated_at=datetime(2026, 7, 25, 12, 0, 0, tzinfo=eg8a.SEOUL),
            analysis_window_start=WINDOW_START,
            snapshot_cutoff=SNAPSHOT_CUTOFF,
            match_status_counts={status: 0 for status in eg8b_b2b.MATCH_STATUSES},
        )
        self.assertEqual(coverage["duplicate_counts"]["current"], 1)
        self.assertAlmostEqual(coverage["duplicate_rate"]["current"], 0.5)


class BacktestSummaryTests(unittest.TestCase):
    def test_status_fields_and_dynamic_scope_note(self) -> None:
        overall_row = eg8b_b2b._performance_row("scope", "overall", [])
        dataset_coverage = {"latest_available_observed_at": "2026-07-25T06:30:00+09:00", "calendar_date_count": 2}
        summary = eg8b_b2b.build_multiday_backtest_summary(
            b2b_run_id="unit-test-run",
            generated_at=datetime(2026, 7, 25, 12, 0, 0, tzinfo=eg8a.SEOUL),
            analysis_window_start=WINDOW_START,
            snapshot_cutoff=SNAPSHOT_CUTOFF,
            dataset_coverage=dataset_coverage,
            overall_row=overall_row,
            origin_lookup_missing_count=0,
        )
        self.assertEqual(summary["evaluation_status"], eg8b_b2b.EVALUATION_STATUS_PROVISIONAL)
        self.assertEqual(
            summary["coverage_status"], eg8b_b2b.COVERAGE_STATUS_SHORT_WINDOW_MULTI_DAY_PARTIAL
        )
        self.assertIsNone(summary["gate_judgment"])
        self.assertIn(WINDOW_START.isoformat(), summary["scope_note"])
        self.assertIn(SNAPSHOT_CUTOFF.isoformat(), summary["scope_note"])
        self.assertNotIn("SINGLE_DAY_PARTIAL_COVERAGE", summary["coverage_status"])


class OutputWriterTests(unittest.TestCase):
    def test_run_short_window_backtest_creates_eight_files(self) -> None:
        current_rows = [
            current_row(run_id=RUN_A, called_at="2026-07-24 01:00:05", observed_at="2026-07-24 01:00", pop_min="30000", pop_max="32000"),
            current_row(run_id=RUN_B, called_at="2026-07-24 01:30:05", observed_at="2026-07-24 01:30", pop_min="32500", pop_max="33500"),
        ]
        forecast_rows = [
            forecast_row(run_id=RUN_A, observed_at="2026-07-24 01:00", forecast_at="2026-07-24 01:30", pop_min="32000", pop_max="34000"),
        ]
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=current_rows, forecast_rows=forecast_rows
            )
            result = eg8b_b2b.run_short_window_backtest(
                raw_log_path=raw_path,
                current_path=current_path,
                forecast_path=forecast_path,
                analysis_window_start=WINDOW_START,
                snapshot_cutoff=SNAPSHOT_CUTOFF,
                eg8b_output_root=Path(output_root),
                b2b_run_id="unit-test-run",
            )

            self.assertEqual(result.b2b_run_id, "unit-test-run")
            self.assertEqual(result.phase_dir.name, eg8b_b2b.PHASE_B2B_VERSION)
            created = sorted(p.name for p in result.phase_dir.iterdir())
            self.assertEqual(
                created,
                sorted(
                    [
                        eg8b_b2b.DATASET_COVERAGE_FILENAME,
                        eg8b_b2b.EVALUATION_PAIRS_SCORED_FILENAME,
                        eg8b_b2b.METRICS_BY_DATE_FILENAME,
                        eg8b_b2b.METRICS_BY_AREA_FILENAME,
                        eg8b_b2b.METRICS_BY_HORIZON_FILENAME,
                        eg8b_b2b.BASELINE_COMPARISON_FILENAME,
                        eg8b_b2b.MULTIDAY_BACKTEST_SUMMARY_FILENAME,
                        eg8b_b2b.OUTPUT_MANIFEST_FILENAME,
                    ]
                ),
            )
            self.assertEqual(result.backtest_summary["pair_count"], 1)

    def test_does_not_collide_with_existing_b1_or_b2a_directories(self) -> None:
        # A B1/B2a run under a real eg8a dataset_id shares the same output
        # root; B2b's freshly minted run_id must never land on that path.
        current_rows = [
            current_row(run_id=RUN_A, called_at="2026-07-24 01:00:05", observed_at="2026-07-24 01:00"),
        ]
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as eg8a_root, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=current_rows, forecast_rows=[]
            )
            result = eg8a.normalize_v3_sources(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path
            )
            export = eg8a.export_dataset(
                result,
                output_root=Path(eg8a_root),
                input_paths={
                    "raw_log_v3": raw_path,
                    "population_current_v3": current_path,
                    "population_forecast_v3": forecast_path,
                },
                dataset_id="existing-b1-dataset",
            )
            b1_result = eg8b.run_phase1(export.dataset_dir, eg8b_output_root=Path(output_root))

            b2b_result = eg8b_b2b.run_short_window_backtest(
                raw_log_path=raw_path,
                current_path=current_path,
                forecast_path=forecast_path,
                analysis_window_start=WINDOW_START,
                snapshot_cutoff=SNAPSHOT_CUTOFF,
                eg8b_output_root=Path(output_root),
                b2b_run_id="a-fresh-b2b-run-id",
            )

            self.assertTrue(b1_result.phase_dir.is_dir())
            self.assertTrue((b1_result.phase_dir / eg8b.DATASET_PROFILE_FILENAME).is_file())
            self.assertNotEqual(b2b_result.phase_dir.parent, b1_result.phase_dir.parent)

    def test_phase_b2b_directory_collision_raises_without_overwriting(self) -> None:
        current_rows = [current_row(run_id=RUN_A, called_at="2026-07-24 01:00:05", observed_at="2026-07-24 01:00")]
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=current_rows, forecast_rows=[]
            )
            first = eg8b_b2b.run_short_window_backtest(
                raw_log_path=raw_path,
                current_path=current_path,
                forecast_path=forecast_path,
                analysis_window_start=WINDOW_START,
                snapshot_cutoff=SNAPSHOT_CUTOFF,
                eg8b_output_root=Path(output_root),
                b2b_run_id="fixed-run-id",
            )
            summary_before = (first.phase_dir / eg8b_b2b.MULTIDAY_BACKTEST_SUMMARY_FILENAME).read_bytes()

            with self.assertRaises(eg8b_b2b.EvidenceWriteError):
                eg8b_b2b.run_short_window_backtest(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    analysis_window_start=WINDOW_START,
                    snapshot_cutoff=SNAPSHOT_CUTOFF,
                    eg8b_output_root=Path(output_root),
                    b2b_run_id="fixed-run-id",
                )
            summary_after = (first.phase_dir / eg8b_b2b.MULTIDAY_BACKTEST_SUMMARY_FILENAME).read_bytes()
            self.assertEqual(summary_before, summary_after)

    def test_write_exclusive_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file.txt"
            eg8b_b2b._write_exclusive(path, b"first")
            with self.assertRaises(eg8b_b2b.EvidenceWriteError):
                eg8b_b2b._write_exclusive(path, b"second")
            self.assertEqual(path.read_bytes(), b"first")


class DeterminismTests(unittest.TestCase):
    def test_same_generated_at_and_run_id_produce_byte_identical_output(self) -> None:
        fixed_time = datetime(2026, 7, 25, 12, 0, 0, tzinfo=eg8a.SEOUL)
        current_rows = [
            current_row(run_id=RUN_A, called_at="2026-07-24 01:00:05", observed_at="2026-07-24 01:00", pop_min="30000", pop_max="32000"),
            current_row(run_id=RUN_B, called_at="2026-07-24 01:30:05", observed_at="2026-07-24 01:30", pop_min="32500", pop_max="33500"),
        ]
        forecast_rows = [
            forecast_row(run_id=RUN_A, observed_at="2026-07-24 01:00", forecast_at="2026-07-24 01:30", pop_min="32000", pop_max="34000"),
        ]
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as root_1, tempfile.TemporaryDirectory() as root_2:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=current_rows, forecast_rows=forecast_rows
            )
            result_1 = eg8b_b2b.run_short_window_backtest(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
                analysis_window_start=WINDOW_START, snapshot_cutoff=SNAPSHOT_CUTOFF,
                eg8b_output_root=Path(root_1), b2b_run_id="fixed-run-id", generated_at=fixed_time,
            )
            result_2 = eg8b_b2b.run_short_window_backtest(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
                analysis_window_start=WINDOW_START, snapshot_cutoff=SNAPSHOT_CUTOFF,
                eg8b_output_root=Path(root_2), b2b_run_id="fixed-run-id", generated_at=fixed_time,
            )

            for filename in sorted(p.name for p in result_1.phase_dir.iterdir()):
                content_1 = (result_1.phase_dir / filename).read_bytes()
                content_2 = (result_2.phase_dir / filename).read_bytes()
                self.assertEqual(content_1, content_2, f"{filename} differs")


class ResolveOutputRootTests(unittest.TestCase):
    def test_missing_env_raises(self) -> None:
        with self.assertRaises(eg8b_b2b.OutputRootConfigurationError):
            eg8b_b2b.resolve_output_root_from_env({})

    def test_nonexistent_path_raises(self) -> None:
        with self.assertRaises(eg8b_b2b.OutputRootConfigurationError):
            eg8b_b2b.resolve_output_root_from_env(
                {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV: "/nonexistent/path/for/eg8b_b2b"}
            )

    def test_valid_directory_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolved = eg8b_b2b.resolve_output_root_from_env(
                {eg8b.FRESHMANAGER_EG8B_OUTPUT_ROOT_ENV: directory}
            )
            self.assertEqual(resolved, Path(directory).resolve())


if __name__ == "__main__":
    unittest.main()
