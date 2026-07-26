from __future__ import annotations

import csv
import contextlib
import dataclasses
import hashlib
import io
import json
import math
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from freshmanager import eg8a, eg8c_features


RAW_LOG_HEADER = list(eg8a.RAW_LOG_REQUIRED_COLUMNS)
CURRENT_HEADER = list(eg8a.CURRENT_REQUIRED_COLUMNS)
FORECAST_HEADER = list(eg8a.FORECAST_REQUIRED_COLUMNS)

RUN_A = "11111111-1111-4111-8111-111111111111"
AREA = "POI072"


def write_csv(directory: Path, name: str, header: list[str], rows: list[list[str]]) -> Path:
    path = directory / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def raw_log_row(*, run_id: str = RUN_A, called_at: str = "2026-07-24 08:00:05", area: str = AREA) -> list[str]:
    return [run_id, called_at, area, "여의도", "200", "SUCCESS", '{"ok":true}']


def current_row(
    *,
    run_id: str = RUN_A,
    called_at: str = "2026-07-24 08:00:05",
    observed_at: str = "2026-07-24 08:00",
    area: str = AREA,
    congestion: str = "여유",
    pop_min: str = "30000",
    pop_max: str = "32000",
) -> list[str]:
    return [run_id, called_at, observed_at, area, area, "여의도", congestion, pop_min, pop_max]


def forecast_row(
    *,
    run_id: str = RUN_A,
    called_at: str = "2026-07-24 08:00:05",
    observed_at: str = "2026-07-24 08:00",
    forecast_at: str = "2026-07-24 09:00",
    area: str = AREA,
    congestion: str = "여유",
    pop_min: str = "29000",
    pop_max: str = "31000",
) -> list[str]:
    return [run_id, called_at, observed_at, forecast_at, area, area, "여의도", congestion, pop_min, pop_max]


def write_source_csvs(
    directory: Path, *, current_rows: list[list[str]], forecast_rows: list[list[str]]
) -> tuple[Path, Path, Path]:
    seen: set[tuple[str, str]] = set()
    raw_log_rows = []
    for row in current_rows:
        key = (row[0], row[3])
        if key not in seen:
            seen.add(key)
            raw_log_rows.append(raw_log_row(run_id=row[0], area=row[3]))
    raw_path = write_csv(directory, "raw.csv", RAW_LOG_HEADER, raw_log_rows)
    current_path = write_csv(directory, "current.csv", CURRENT_HEADER, current_rows)
    forecast_path = write_csv(directory, "forecast.csv", FORECAST_HEADER, forecast_rows)
    return raw_path, current_path, forecast_path


def make_current_record(**overrides: object) -> eg8a.NormalizedCurrentRecord:
    base: dict[str, object] = dict(
        collection_run_id=RUN_A,
        called_at="2026-07-24T08:00:05+09:00",
        observed_at="2026-07-24T08:00:00+09:00",
        area_code=AREA,
        area_code_requested=AREA,
        area_code_returned=AREA,
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
        called_at="2026-07-24T08:00:05+09:00",
        observed_at="2026-07-24T08:00:00+09:00",
        forecast_at="2026-07-24T09:00:00+09:00",
        area_code=AREA,
        area_code_requested=AREA,
        area_code_returned=AREA,
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


def build_full_current_history(*, origin: datetime, area: str = AREA, minutes_back: int = 65) -> tuple[eg8a.NormalizedCurrentRecord, ...]:
    """A complete, gap-free 5-minute grid of Current records from
    `origin - minutes_back` through `origin` inclusive, values increasing
    linearly so Lag/Rolling/Delta are hand-verifiable."""
    records = []
    steps = minutes_back // 5
    for k in range(steps, -1, -1):
        t = origin - timedelta(minutes=5 * k)
        base_pop = 30000 + (steps - k) * 100
        records.append(
            make_current_record(
                observed_at=t.isoformat(),
                called_at=(t + timedelta(seconds=5)).isoformat(),
                population_min=base_pop,
                population_max=base_pop + 2000,
            )
        )
    return tuple(records)


def matching_label_provenance(*, target_at: str, area_code: str) -> eg8c_features.FeatureProvenance:
    """Minimal FeatureProvenance carrying only a correct Label source, for
    hand-built CandidateRow Fixtures whose actual test target is unrelated
    to Label Provenance -- so check 5 (label_target_wrong_area) doesn't
    misfire as an unintended side effect on a Fixture testing something
    else entirely."""
    return eg8c_features.FeatureProvenance(
        current_source_at=None, current_source_area=None,
        lag_source_at={}, lag_source_area={},
        rolling_source_at={}, rolling_source_area={},
        label_source_at=target_at, label_source_area=area_code,
    )


class TimeFeatureAndHorizonTests(unittest.TestCase):
    def test_exact_60_and_180_are_supported_no_tolerance(self) -> None:
        current = build_full_current_history(origin=datetime.fromisoformat("2026-07-24T08:00:00+09:00"))
        target_area_record = make_current_record(
            observed_at="2026-07-24T09:00:00+09:00", called_at="2026-07-24T09:00:05+09:00"
        )
        forecasts = (
            make_forecast_record(forecast_at="2026-07-24T09:00:00+09:00"),  # 60min exact
            make_forecast_record(forecast_at="2026-07-24T08:55:00+09:00"),  # 55min -- unsupported
            make_forecast_record(forecast_at="2026-07-24T08:35:00+09:00"),  # 35min -- unsupported
        )
        rows = eg8c_features.build_candidate_rows(current + (target_area_record,), forecasts)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].horizon_minutes, 60)

    def test_time_feature_values(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T08:07:00+09:00")  # Friday
        current = build_full_current_history(origin=origin)
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        target_actual = make_current_record(observed_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(current + (target_actual,), (forecast,))
        self.assertEqual(len(rows), 1)
        feature = rows[0].feature
        self.assertEqual(feature["hour"], 8)
        self.assertEqual(feature["minute"], 7)
        self.assertEqual(feature["day_of_week"], 4)  # Friday = 4 (Mon=0)
        self.assertFalse(feature["is_weekend"])
        self.assertAlmostEqual(feature["hour_sin"], math.sin(2 * math.pi * 8 / 24))
        self.assertAlmostEqual(feature["day_of_week_cos"], math.cos(2 * math.pi * 4 / 7))

    def test_saturday_is_weekend(self) -> None:
        origin = datetime.fromisoformat("2026-07-25T08:00:00+09:00")  # Saturday
        current = build_full_current_history(origin=origin)
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        target_actual = make_current_record(observed_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(current + (target_actual,), (forecast,))
        self.assertTrue(rows[0].feature["is_weekend"])
        self.assertEqual(rows[0].feature["day_of_week"], 5)


class LagAndDeltaFeatureTests(unittest.TestCase):
    def test_exact_lag_and_delta_hand_computed(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        current = build_full_current_history(origin=origin, minutes_back=65)
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        target_actual = make_current_record(observed_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(current + (target_actual,), (forecast,))
        self.assertEqual(len(rows), 1)
        feature = rows[0].feature

        origin_record = next(r for r in current if r.observed_at == origin.isoformat())
        lag5_record = next(r for r in current if r.observed_at == (origin - timedelta(minutes=5)).isoformat())
        origin_mid = (origin_record.population_min + origin_record.population_max) / 2
        lag5_mid = (lag5_record.population_min + lag5_record.population_max) / 2

        self.assertAlmostEqual(feature["current_population_midpoint"], origin_mid)
        self.assertAlmostEqual(feature["population_lag_5m"], lag5_mid)
        self.assertAlmostEqual(feature["population_delta_5m"], origin_mid - lag5_mid)

    def test_missing_lag_marks_feature_invalid(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        # Only 30 minutes of history -- 60m Lag/Rolling cannot be computed.
        current = build_full_current_history(origin=origin, minutes_back=30)
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        target_actual = make_current_record(observed_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(current + (target_actual,), (forecast,))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNone(row.feature["population_lag_60m"])
        self.assertFalse(row.feature_valid)
        self.assertIn("population_lag_60m", row.feature_missing_reason)

    def test_no_interpolation_gap_leaves_lag_none(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        current = list(build_full_current_history(origin=origin, minutes_back=65))
        # Remove the exact 5-minute-lag point to create a gap.
        current = [r for r in current if r.observed_at != (origin - timedelta(minutes=5)).isoformat()]
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        target_actual = make_current_record(observed_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(tuple(current) + (target_actual,), (forecast,))
        self.assertIsNone(rows[0].feature["population_lag_5m"])


class RollingFeatureTests(unittest.TestCase):
    def test_rolling_mean_and_population_stdev_hand_computed(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        current = build_full_current_history(origin=origin, minutes_back=65)
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        target_actual = make_current_record(observed_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(current + (target_actual,), (forecast,))
        feature = rows[0].feature

        points = []
        for k in range(1, 4):  # 15min window = 3 points
            t = origin - timedelta(minutes=5 * k)
            record = next(r for r in current if r.observed_at == t.isoformat())
            points.append((record.population_min + record.population_max) / 2)
        import statistics as _stats

        self.assertAlmostEqual(feature["rolling_mean_15m"], _stats.mean(points))

        points30 = []
        for k in range(1, 7):
            t = origin - timedelta(minutes=5 * k)
            record = next(r for r in current if r.observed_at == t.isoformat())
            points30.append((record.population_min + record.population_max) / 2)
        self.assertAlmostEqual(feature["rolling_std_30m"], _stats.pstdev(points30))

    def test_incomplete_window_is_none_not_partial(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        current = list(build_full_current_history(origin=origin, minutes_back=65))
        # Remove one point inside the 30-minute window -> incomplete, must be None (not computed from remaining 5).
        current = [r for r in current if r.observed_at != (origin - timedelta(minutes=20)).isoformat()]
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        target_actual = make_current_record(observed_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(tuple(current) + (target_actual,), (forecast,))
        self.assertIsNone(rows[0].feature["rolling_mean_30m"])


class LabelTests(unittest.TestCase):
    def test_exact_target_match(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        current = build_full_current_history(origin=origin, minutes_back=65)
        target = make_current_record(
            observed_at=(origin + timedelta(minutes=60)).isoformat(), population_min=40000, population_max=42000
        )
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(current + (target,), (forecast,))
        self.assertTrue(rows[0].label_valid)
        self.assertAlmostEqual(rows[0].label_value, 41000.0)

    def test_missing_target_actual(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        current = build_full_current_history(origin=origin, minutes_back=65)
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(current, (forecast,))
        self.assertFalse(rows[0].label_valid)
        self.assertEqual(rows[0].label_missing_reason, "target_actual_not_found_in_snapshot")

    def test_area_mismatch_does_not_match_label(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        current = build_full_current_history(origin=origin, minutes_back=65)
        wrong_area_target = make_current_record(observed_at=(origin + timedelta(minutes=60)).isoformat(), area_code="POI019")
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(current + (wrong_area_target,), (forecast,))
        self.assertFalse(rows[0].label_valid)


class SplitAssignmentTests(unittest.TestCase):
    def _eligible_row(self, origin_iso: str, area: str = AREA) -> eg8c_features.CandidateRow:
        return eg8c_features.CandidateRow(
            row_id=f"{area}_{origin_iso}_60",
            area_code=area,
            prediction_origin_at=origin_iso,
            prediction_target_at=origin_iso,
            horizon_minutes=60,
            source_collection_run_id=RUN_A,
            feature={},
            feature_valid=True,
            feature_missing_reason=None,
            label_value=1.0,
            label_valid=True,
            label_missing_reason=None,
        )

    def test_chronological_80_20_split(self) -> None:
        origins = [f"2026-07-24T{h:02d}:00:00+09:00" for h in range(10)]
        rows = [self._eligible_row(o) for o in origins]
        assignment = eg8c_features.build_split_assignment(rows)
        train = [o for o in origins if assignment[f"{AREA}_{o}_60"]["split"] == eg8c_features.SPLIT_TRAIN]
        validation = [o for o in origins if assignment[f"{AREA}_{o}_60"]["split"] == eg8c_features.SPLIT_VALIDATION]
        self.assertEqual(len(train), 8)
        self.assertEqual(len(validation), 2)
        self.assertTrue(max(train) < min(validation))

    def test_same_origin_multiple_areas_same_split(self) -> None:
        origins = [f"2026-07-24T{h:02d}:00:00+09:00" for h in range(10)]
        rows = [self._eligible_row(o, area=a) for o in origins for a in (AREA, "POI019")]
        assignment = eg8c_features.build_split_assignment(rows)
        for o in origins:
            splits = {assignment[f"{a}_{o}_60"]["split"] for a in (AREA, "POI019")}
            self.assertEqual(len(splits), 1)

    def test_invalid_rows_are_excluded(self) -> None:
        row = eg8c_features.CandidateRow(
            row_id="x", area_code=AREA, prediction_origin_at="2026-07-24T08:00:00+09:00",
            prediction_target_at="2026-07-24T09:00:00+09:00", horizon_minutes=60,
            source_collection_run_id=RUN_A, feature={}, feature_valid=False,
            feature_missing_reason="missing_mandatory_fields:x", label_value=None,
            label_valid=False, label_missing_reason="target_actual_not_found_in_snapshot",
        )
        assignment = eg8c_features.build_split_assignment([row])
        self.assertEqual(assignment["x"]["split"], eg8c_features.SPLIT_EXCLUDED)

    def test_no_test_split_ever_produced(self) -> None:
        origins = [f"2026-07-24T{h:02d}:00:00+09:00" for h in range(20)]
        rows = [self._eligible_row(o) for o in origins]
        assignment = eg8c_features.build_split_assignment(rows)
        splits = {v["split"] for v in assignment.values()}
        self.assertNotIn("TEST", splits)


class LeakageReportTests(unittest.TestCase):
    def test_clean_dataset_passes(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        current = build_full_current_history(origin=origin, minutes_back=65)
        target = make_current_record(observed_at=(origin + timedelta(minutes=60)).isoformat())
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(current + (target,), (forecast,))
        assignment = eg8c_features.build_split_assignment(rows)
        report = eg8c_features.build_leakage_report(rows, assignment)
        self.assertEqual(report["total_violation_count"], 0)
        self.assertEqual(report["final_verdict"], "PASS")

    def test_duplicate_row_id_detected(self) -> None:
        row = eg8c_features.CandidateRow(
            row_id="dup", area_code=AREA, prediction_origin_at="2026-07-24T08:00:00+09:00",
            prediction_target_at="2026-07-24T09:00:00+09:00", horizon_minutes=60,
            source_collection_run_id=RUN_A, feature={}, feature_valid=False,
            feature_missing_reason="x", label_value=None, label_valid=False, label_missing_reason="x",
        )
        report = eg8c_features.build_leakage_report([row, row], {"dup": {"split": "EXCLUDED", "split_reason": "x"}})
        self.assertEqual(report["checks"]["duplicate_row_id"]["violation_count"], 1)
        # Already isolated: this row's label_valid=False, so check 5 skips
        # it entirely (nothing to verify without a valid Label). Asserted
        # explicitly rather than assumed.
        self.assertEqual(report["checks"]["label_target_wrong_area"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "FAIL")

    def test_same_origin_split_conflict_detected(self) -> None:
        row_a = eg8c_features.CandidateRow(
            row_id="a", area_code=AREA, prediction_origin_at="2026-07-24T08:00:00+09:00",
            prediction_target_at="2026-07-24T09:00:00+09:00", horizon_minutes=60,
            source_collection_run_id=RUN_A, feature={}, feature_valid=True,
            feature_missing_reason=None, label_value=1.0, label_valid=True, label_missing_reason=None,
            feature_provenance=matching_label_provenance(target_at="2026-07-24T09:00:00+09:00", area_code=AREA),
        )
        row_b = eg8c_features.CandidateRow(
            row_id="b", area_code="POI019", prediction_origin_at="2026-07-24T08:00:00+09:00",
            prediction_target_at="2026-07-24T09:00:00+09:00", horizon_minutes=60,
            source_collection_run_id=RUN_A, feature={}, feature_valid=True,
            feature_missing_reason=None, label_value=1.0, label_valid=True, label_missing_reason=None,
            feature_provenance=matching_label_provenance(target_at="2026-07-24T09:00:00+09:00", area_code="POI019"),
        )
        assignment = {
            "a": {"split": eg8c_features.SPLIT_TRAIN, "split_reason": "x"},
            "b": {"split": eg8c_features.SPLIT_VALIDATION, "split_reason": "x"},
        }
        report = eg8c_features.build_leakage_report([row_a, row_b], assignment)
        self.assertEqual(report["checks"]["same_origin_split_across_boundary"]["violation_count"], 1)
        self.assertEqual(report["checks"]["label_target_wrong_area"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "FAIL")

    def test_cutoff_not_applicable_when_none_supplied(self) -> None:
        report = eg8c_features.build_leakage_report([], {})
        self.assertFalse(report["checks"]["post_cutoff_forecast_used"]["applicable"])
        self.assertEqual(report["checks"]["post_cutoff_forecast_used"]["violation_count"], 0)


class LeakageNegativeFixtureTests(unittest.TestCase):
    """PM-specified violation-inducing Negative Tests, one per named
    Leakage check. Each poisons exactly one thing a real bug could poison
    and asserts: the target check fails, a clean counterpart passes, and
    (for NT-1/NT-3) no unrelated check fails for the same reason."""

    def test_nt1_lag_source_timestamp_equals_origin_is_flagged(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        current = build_full_current_history(origin=origin, minutes_back=65)
        target_actual = make_current_record(observed_at=(origin + timedelta(minutes=60)).isoformat())
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=(origin + timedelta(minutes=60)).isoformat())
        rows = eg8c_features.build_candidate_rows(current + (target_actual,), (forecast,))
        self.assertEqual(len(rows), 1)
        clean_row = rows[0]
        self.assertIsNotNone(clean_row.feature["population_lag_5m"])

        # Poison: the 5-minute Lag value stays as-is, but its recorded
        # Provenance now (falsely) claims it was sourced from Origin
        # itself -- a same-Area, same-instant leak the feature value alone
        # would never reveal.
        poisoned_lag_source_at = dict(clean_row.feature_provenance.lag_source_at)
        poisoned_lag_source_at[5] = origin.isoformat()
        poisoned_provenance = dataclasses.replace(clean_row.feature_provenance, lag_source_at=poisoned_lag_source_at)
        poisoned_row = dataclasses.replace(clean_row, feature_provenance=poisoned_provenance)

        assignment = eg8c_features.build_split_assignment([poisoned_row])
        report = eg8c_features.build_leakage_report([poisoned_row], assignment)
        self.assertGreater(report["checks"]["lag_timestamp_not_before_origin"]["violation_count"], 0)
        self.assertIn(poisoned_row.row_id, report["checks"]["lag_timestamp_not_before_origin"]["violation_row_ids"])
        # Independence: poisoning only the Lag Provenance must not also
        # trip check 10, which never inspects lag_source_at's exact value
        # against origin - lag_minutes (that precision is check 2's own
        # duty; check 10 only bounds Lag Source by Origin).
        self.assertEqual(report["checks"]["future_actual_used_as_feature"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "FAIL")

        clean_assignment = eg8c_features.build_split_assignment([clean_row])
        clean_report = eg8c_features.build_leakage_report([clean_row], clean_assignment)
        self.assertEqual(clean_report["checks"]["lag_timestamp_not_before_origin"]["violation_count"], 0)
        self.assertEqual(clean_report["final_verdict"], "PASS")

    def test_nt2_target_at_or_before_origin_is_flagged(self) -> None:
        row = eg8c_features.CandidateRow(
            row_id="nt2", area_code=AREA,
            prediction_origin_at="2026-07-24T09:00:00+09:00",
            prediction_target_at="2026-07-24T09:00:00+09:00",  # target == origin
            horizon_minutes=60, source_collection_run_id=RUN_A,
            feature={}, feature_valid=False, feature_missing_reason="x",
            label_value=1.0, label_valid=True, label_missing_reason=None,
            # Label Provenance matches this row's own (broken) target, so
            # only label_target_before_origin fires here, not check 5.
            feature_provenance=matching_label_provenance(target_at="2026-07-24T09:00:00+09:00", area_code=AREA),
        )
        report = eg8c_features.build_leakage_report([row], {row.row_id: {"split": "EXCLUDED", "split_reason": "x"}})
        self.assertGreater(report["checks"]["label_target_before_origin"]["violation_count"], 0)
        self.assertIn(row.row_id, report["checks"]["label_target_before_origin"]["violation_row_ids"])
        self.assertEqual(report["checks"]["label_target_wrong_area"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "FAIL")

        clean_row = dataclasses.replace(
            row, row_id="nt2-clean", prediction_target_at="2026-07-24T10:00:00+09:00",
            feature_provenance=matching_label_provenance(target_at="2026-07-24T10:00:00+09:00", area_code=AREA),
        )
        clean_report = eg8c_features.build_leakage_report(
            [clean_row], {clean_row.row_id: {"split": "EXCLUDED", "split_reason": "x"}}
        )
        self.assertEqual(clean_report["checks"]["label_target_before_origin"]["violation_count"], 0)
        self.assertEqual(clean_report["checks"]["label_target_wrong_area"]["violation_count"], 0)

    def test_nt3_feature_provenance_sourced_from_target_is_flagged(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        target_at = origin + timedelta(minutes=60)
        current = build_full_current_history(origin=origin, minutes_back=65)
        target_actual = make_current_record(observed_at=target_at.isoformat())
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=target_at.isoformat())
        rows = eg8c_features.build_candidate_rows(current + (target_actual,), (forecast,))
        self.assertEqual(len(rows), 1)
        clean_row = rows[0]

        # Poison: claim the current-state Feature was actually sourced at
        # the row's own Prediction Target -- i.e. the Target Actual leaked
        # into a Feature. Origin/Target themselves are untouched.
        poisoned_provenance = dataclasses.replace(clean_row.feature_provenance, current_source_at=target_at.isoformat())
        poisoned_row = dataclasses.replace(clean_row, feature_provenance=poisoned_provenance)

        assignment = eg8c_features.build_split_assignment([poisoned_row])
        report = eg8c_features.build_leakage_report([poisoned_row], assignment)
        self.assertGreater(report["checks"]["future_actual_used_as_feature"]["violation_count"], 0)
        self.assertIn(poisoned_row.row_id, report["checks"]["future_actual_used_as_feature"]["violation_row_ids"])
        # Must not also trip label_target_before_origin -- that check only
        # looks at origin/target metadata, which this fixture never touches.
        self.assertEqual(report["checks"]["label_target_before_origin"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "FAIL")

        clean_assignment = eg8c_features.build_split_assignment([clean_row])
        clean_report = eg8c_features.build_leakage_report([clean_row], clean_assignment)
        self.assertEqual(clean_report["checks"]["future_actual_used_as_feature"]["violation_count"], 0)
        self.assertEqual(clean_report["final_verdict"], "PASS")

    def test_nt4_feature_valid_true_with_missing_mandatory_field_is_flagged(self) -> None:
        row = eg8c_features.CandidateRow(
            row_id="nt4", area_code=AREA,
            prediction_origin_at="2026-07-24T09:00:00+09:00",
            prediction_target_at="2026-07-24T10:00:00+09:00",
            horizon_minutes=60, source_collection_run_id=RUN_A,
            feature={name: None for name in eg8c_features.MANDATORY_FEATURE_FIELDS},
            feature_valid=True,  # contract violation: claims valid while every mandatory field is None
            feature_missing_reason=None,
            label_value=1.0, label_valid=True, label_missing_reason=None,
            feature_provenance=matching_label_provenance(target_at="2026-07-24T10:00:00+09:00", area_code=AREA),
        )
        report = eg8c_features.build_leakage_report([row], {row.row_id: {"split": "TRAIN", "split_reason": "x"}})
        self.assertGreater(report["checks"]["missing_value_silently_filled"]["violation_count"], 0)
        self.assertIn(row.row_id, report["checks"]["missing_value_silently_filled"]["violation_row_ids"])
        self.assertEqual(report["checks"]["label_target_wrong_area"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "FAIL")

        # The honest outcome for the same missing fields is EXCLUDED
        # (feature_valid=False), not a silent fill -- must not be flagged.
        honest_row = dataclasses.replace(
            row, row_id="nt4-honest", feature_valid=False, feature_missing_reason="missing_mandatory_fields:x"
        )
        honest_report = eg8c_features.build_leakage_report(
            [honest_row], {honest_row.row_id: {"split": "EXCLUDED", "split_reason": "feature_invalid"}}
        )
        self.assertEqual(honest_report["checks"]["missing_value_silently_filled"]["violation_count"], 0)
        self.assertEqual(honest_report["checks"]["label_target_wrong_area"]["violation_count"], 0)

    def test_nt5_origin_after_cutoff_is_flagged(self) -> None:
        cutoff = datetime.fromisoformat("2026-07-24T12:00:00+09:00")
        row = eg8c_features.CandidateRow(
            row_id="nt5", area_code=AREA,
            prediction_origin_at="2026-07-24T13:00:00+09:00",  # after cutoff
            prediction_target_at="2026-07-24T14:00:00+09:00",
            horizon_minutes=60, source_collection_run_id=RUN_A,
            feature={}, feature_valid=False, feature_missing_reason="x",
            label_value=None, label_valid=False, label_missing_reason="x",
        )
        report = eg8c_features.build_leakage_report(
            [row], {row.row_id: {"split": "EXCLUDED", "split_reason": "x"}}, snapshot_cutoff=cutoff
        )
        self.assertTrue(report["checks"]["post_cutoff_forecast_used"]["applicable"])
        self.assertGreater(report["checks"]["post_cutoff_forecast_used"]["violation_count"], 0)
        self.assertIn(row.row_id, report["checks"]["post_cutoff_forecast_used"]["violation_row_ids"])
        self.assertEqual(report["final_verdict"], "FAIL")

        before_cutoff_row = dataclasses.replace(
            row, row_id="nt5-clean", prediction_origin_at="2026-07-24T11:00:00+09:00"
        )
        clean_report = eg8c_features.build_leakage_report(
            [before_cutoff_row], {before_cutoff_row.row_id: {"split": "EXCLUDED", "split_reason": "x"}}, snapshot_cutoff=cutoff
        )
        self.assertEqual(clean_report["checks"]["post_cutoff_forecast_used"]["violation_count"], 0)

    def _build_single_clean_row(self, *, origin: datetime, horizon_minutes: int = 60) -> eg8c_features.CandidateRow:
        target_at = origin + timedelta(minutes=horizon_minutes)
        current = build_full_current_history(origin=origin, minutes_back=65)
        target_actual = make_current_record(observed_at=target_at.isoformat())
        forecast = make_forecast_record(observed_at=origin.isoformat(), forecast_at=target_at.isoformat())
        rows = eg8c_features.build_candidate_rows(current + (target_actual,), (forecast,))
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_nt6_rolling_source_between_origin_and_target_is_flagged(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T10:00:00+09:00")
        clean_row = self._build_single_clean_row(origin=origin)
        self.assertIsNotNone(clean_row.feature["rolling_mean_15m"])

        # Poison: one of rolling_mean_15m's recorded source points now
        # claims 10:10 -- strictly after Origin (10:00) but still before
        # Target (11:00). The pre-fix check (bounded by Target) would have
        # missed this; the Origin-bounded check must not.
        poisoned_at = origin + timedelta(minutes=10)
        original_sources = clean_row.feature_provenance.rolling_source_at[15]
        poisoned_rolling_source_at = dict(clean_row.feature_provenance.rolling_source_at)
        poisoned_rolling_source_at[15] = (poisoned_at.isoformat(),) + original_sources[1:]
        poisoned_provenance = dataclasses.replace(clean_row.feature_provenance, rolling_source_at=poisoned_rolling_source_at)
        poisoned_row = dataclasses.replace(clean_row, feature_provenance=poisoned_provenance)

        assignment = eg8c_features.build_split_assignment([poisoned_row])
        report = eg8c_features.build_leakage_report([poisoned_row], assignment)
        self.assertGreater(report["checks"]["future_actual_used_as_feature"]["violation_count"], 0)
        self.assertIn(poisoned_row.row_id, report["checks"]["future_actual_used_as_feature"]["violation_row_ids"])
        self.assertEqual(report["checks"]["label_target_before_origin"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "FAIL")

    def test_nt7_missing_rolling_provenance_with_value_present_is_flagged(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T10:00:00+09:00")
        clean_row = self._build_single_clean_row(origin=origin)
        self.assertIsNotNone(clean_row.feature["rolling_mean_30m"])

        # Poison: the Rolling Mean value is still real, but its recorded
        # Provenance is wiped -- a value must never exist without a
        # recorded source (fail-closed).
        poisoned_rolling_source_at = dict(clean_row.feature_provenance.rolling_source_at)
        poisoned_rolling_source_at[30] = ()
        poisoned_provenance = dataclasses.replace(clean_row.feature_provenance, rolling_source_at=poisoned_rolling_source_at)
        poisoned_row = dataclasses.replace(clean_row, feature_provenance=poisoned_provenance)

        assignment = eg8c_features.build_split_assignment([poisoned_row])
        report = eg8c_features.build_leakage_report([poisoned_row], assignment)
        self.assertGreater(report["checks"]["future_actual_used_as_feature"]["violation_count"], 0)
        self.assertIn(poisoned_row.row_id, report["checks"]["future_actual_used_as_feature"]["violation_row_ids"])
        self.assertEqual(report["final_verdict"], "FAIL")

    def test_nt8_current_source_after_origin_is_flagged(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T10:00:00+09:00")
        clean_row = self._build_single_clean_row(origin=origin)

        poisoned_at = origin + timedelta(minutes=5)
        poisoned_provenance = dataclasses.replace(clean_row.feature_provenance, current_source_at=poisoned_at.isoformat())
        poisoned_row = dataclasses.replace(clean_row, feature_provenance=poisoned_provenance)

        assignment = eg8c_features.build_split_assignment([poisoned_row])
        report = eg8c_features.build_leakage_report([poisoned_row], assignment)
        self.assertGreater(report["checks"]["future_actual_used_as_feature"]["violation_count"], 0)
        self.assertIn(poisoned_row.row_id, report["checks"]["future_actual_used_as_feature"]["violation_row_ids"])
        self.assertEqual(report["final_verdict"], "FAIL")

    def test_nt9_current_source_equal_to_origin_is_clean(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T10:00:00+09:00")
        clean_row = self._build_single_clean_row(origin=origin)
        self.assertEqual(clean_row.feature_provenance.current_source_at, origin.isoformat())

        assignment = eg8c_features.build_split_assignment([clean_row])
        report = eg8c_features.build_leakage_report([clean_row], assignment)
        self.assertEqual(report["checks"]["future_actual_used_as_feature"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "PASS")

    def test_nt10_rolling_source_area_mismatch_is_flagged(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T10:00:00+09:00")
        clean_row = self._build_single_clean_row(origin=origin)
        self.assertIsNotNone(clean_row.feature["rolling_mean_15m"])
        other_area = "POI019"
        self.assertNotEqual(clean_row.area_code, other_area)

        # Poison: the 15-minute Rolling window's recorded Source Timestamps
        # stay valid (still before Origin), but its recorded Source Area
        # now claims a different Area than the Candidate's own.
        poisoned_rolling_source_area = dict(clean_row.feature_provenance.rolling_source_area)
        poisoned_rolling_source_area[15] = other_area
        poisoned_provenance = dataclasses.replace(clean_row.feature_provenance, rolling_source_area=poisoned_rolling_source_area)
        poisoned_row = dataclasses.replace(clean_row, feature_provenance=poisoned_provenance)

        assignment = eg8c_features.build_split_assignment([poisoned_row])
        report = eg8c_features.build_leakage_report([poisoned_row], assignment)
        self.assertGreater(report["checks"]["future_actual_used_as_feature"]["violation_count"], 0)
        self.assertIn(poisoned_row.row_id, report["checks"]["future_actual_used_as_feature"]["violation_row_ids"])
        self.assertEqual(report["checks"]["label_target_before_origin"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "FAIL")

    def test_nt11_label_provenance_missing_is_flagged(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T10:00:00+09:00")
        clean_row = self._build_single_clean_row(origin=origin)
        self.assertTrue(clean_row.label_valid)
        self.assertIsNotNone(clean_row.label_value)

        # Poison: the Label value/valid flag stay real, but its recorded
        # Provenance is wiped -- fail-closed, must not silently PASS.
        poisoned_provenance = dataclasses.replace(
            clean_row.feature_provenance, label_source_at=None, label_source_area=None
        )
        poisoned_row = dataclasses.replace(clean_row, feature_provenance=poisoned_provenance)

        assignment = eg8c_features.build_split_assignment([poisoned_row])
        report = eg8c_features.build_leakage_report([poisoned_row], assignment)
        self.assertGreater(report["checks"]["label_target_wrong_area"]["violation_count"], 0)
        self.assertIn(poisoned_row.row_id, report["checks"]["label_target_wrong_area"]["violation_row_ids"])
        self.assertEqual(report["checks"]["label_target_before_origin"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "FAIL")

    def test_nt12_label_source_timestamp_mismatch_is_flagged(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T10:00:00+09:00")
        clean_row = self._build_single_clean_row(origin=origin)
        target_at = datetime.fromisoformat(clean_row.prediction_target_at)
        poisoned_at = target_at - timedelta(minutes=5)

        poisoned_provenance = dataclasses.replace(clean_row.feature_provenance, label_source_at=poisoned_at.isoformat())
        poisoned_row = dataclasses.replace(clean_row, feature_provenance=poisoned_provenance)

        assignment = eg8c_features.build_split_assignment([poisoned_row])
        report = eg8c_features.build_leakage_report([poisoned_row], assignment)
        self.assertGreater(report["checks"]["label_target_wrong_area"]["violation_count"], 0)
        self.assertIn(poisoned_row.row_id, report["checks"]["label_target_wrong_area"]["violation_row_ids"])
        self.assertEqual(report["checks"]["label_target_before_origin"]["violation_count"], 0)
        self.assertEqual(report["final_verdict"], "FAIL")

    def test_nt13_label_source_area_mismatch_is_flagged(self) -> None:
        origin = datetime.fromisoformat("2026-07-24T10:00:00+09:00")
        clean_row = self._build_single_clean_row(origin=origin)
        other_area = "POI019"
        self.assertNotEqual(clean_row.area_code, other_area)

        poisoned_provenance = dataclasses.replace(clean_row.feature_provenance, label_source_area=other_area)
        poisoned_row = dataclasses.replace(clean_row, feature_provenance=poisoned_provenance)

        assignment = eg8c_features.build_split_assignment([poisoned_row])
        report = eg8c_features.build_leakage_report([poisoned_row], assignment)
        self.assertGreater(report["checks"]["label_target_wrong_area"]["violation_count"], 0)
        self.assertIn(poisoned_row.row_id, report["checks"]["label_target_wrong_area"]["violation_row_ids"])
        self.assertEqual(report["final_verdict"], "FAIL")


class OutputWriterTests(unittest.TestCase):
    def test_run_eg8c_dataset_build_creates_eight_files(self) -> None:
        current_rows = []
        origin_dt = datetime.fromisoformat("2026-07-24T09:00:00+09:00")
        for k in range(13, -1, -1):
            t = origin_dt - timedelta(minutes=5 * k)
            current_rows.append(current_row(observed_at=t.strftime("%Y-%m-%d %H:%M"), called_at=t.strftime("%Y-%m-%d %H:%M:%S")))
        target_t = origin_dt + timedelta(minutes=60)
        current_rows.append(current_row(observed_at=target_t.strftime("%Y-%m-%d %H:%M"), called_at=target_t.strftime("%Y-%m-%d %H:%M:%S")))
        forecast_rows = [
            forecast_row(
                observed_at=origin_dt.strftime("%Y-%m-%d %H:%M"),
                called_at=origin_dt.strftime("%Y-%m-%d %H:%M:%S"),
                forecast_at=target_t.strftime("%Y-%m-%d %H:%M"),
            )
        ]
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=current_rows, forecast_rows=forecast_rows
            )
            result = eg8c_features.run_eg8c_dataset_build(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
                eg8c_output_root=Path(output_root), eg8c_run_id="unit-test-run",
            )
            self.assertEqual(result.eg8c_run_id, "unit-test-run")
            self.assertEqual(result.phase_dir.name, eg8c_features.PHASE_EG8C_VERSION)
            created = sorted(p.name for p in result.phase_dir.iterdir())
            expected = sorted(
                [
                    eg8c_features.FEATURE_DATASET_FILENAME,
                    eg8c_features.LABEL_DATASET_FILENAME,
                    eg8c_features.SPLIT_ASSIGNMENT_FILENAME,
                    eg8c_features.FEATURE_DICTIONARY_FILENAME,
                    eg8c_features.LABEL_CONTRACT_FILENAME,
                    eg8c_features.LEAKAGE_REPORT_FILENAME,
                    eg8c_features.DATASET_COVERAGE_FILENAME,
                    eg8c_features.DATASET_MANIFEST_FILENAME,
                ]
            )
            self.assertEqual(created, expected)

            manifest = json.loads(
                (result.phase_dir / eg8c_features.DATASET_MANIFEST_FILENAME).read_text(
                    encoding="utf-8"
                )
            )
            input_paths = {
                "raw_log_v3": raw_path,
                "population_current_v3": current_path,
                "population_forecast_v3": forecast_path,
            }
            for artifact in manifest["input_artifacts"]:
                source = input_paths[artifact["logical_name"]]
                payload = source.read_bytes()
                self.assertEqual(artifact["sha256"], hashlib.sha256(payload).hexdigest())
                self.assertEqual(artifact["byte_size"], len(payload))
            self.assertEqual(len(manifest["output_artifacts"]), 7)
            for artifact in manifest["output_artifacts"]:
                payload = (result.phase_dir / artifact["relative_path"]).read_bytes()
                self.assertEqual(artifact["sha256"], hashlib.sha256(payload).hexdigest())
                self.assertEqual(artifact["byte_size"], len(payload))

    def test_invalid_run_ids_are_rejected_before_creating_output(self) -> None:
        invalid_values = (
            "",
            "   ",
            ".",
            "..",
            "../outside",
            "outside/child",
            r"outside\child",
            "bad\0run",
        )
        for value in invalid_values:
            with self.subTest(run_id=repr(value)), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                output_root = base / "output"
                output_root.mkdir()
                raw_path, current_path, forecast_path = write_source_csvs(
                    base, current_rows=[current_row()], forecast_rows=[]
                )

                with self.assertRaises(eg8c_features.EvidenceWriteError):
                    eg8c_features.run_eg8c_dataset_build(
                        raw_log_path=raw_path,
                        current_path=current_path,
                        forecast_path=forecast_path,
                        eg8c_output_root=output_root,
                        eg8c_run_id=value,
                    )

                self.assertEqual(list(output_root.iterdir()), [])
                self.assertEqual({path.name for path in base.iterdir()}, {"output", "raw.csv", "current.csv", "forecast.csv"})

    def test_absolute_run_id_is_rejected_before_creating_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output_root = base / "output"
            output_root.mkdir()
            outside = base / "outside"
            raw_path, current_path, forecast_path = write_source_csvs(
                base, current_rows=[current_row()], forecast_rows=[]
            )

            with self.assertRaises(eg8c_features.EvidenceWriteError):
                eg8c_features.run_eg8c_dataset_build(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    eg8c_output_root=output_root,
                    eg8c_run_id=str(outside),
                )

            self.assertEqual(list(output_root.iterdir()), [])
            self.assertFalse(outside.exists())

    def test_existing_run_file_is_rejected_without_modification(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=[current_row()], forecast_rows=[]
            )
            existing = Path(output_root) / "fixed-run"
            existing.write_bytes(b"sentinel")

            with self.assertRaises(eg8c_features.EvidenceWriteError):
                eg8c_features.run_eg8c_dataset_build(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    eg8c_output_root=Path(output_root),
                    eg8c_run_id="fixed-run",
                )

            self.assertEqual(existing.read_bytes(), b"sentinel")

    def test_existing_run_directory_is_rejected_without_modification(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=[current_row()], forecast_rows=[]
            )
            existing = Path(output_root) / "fixed-run"
            existing.mkdir()
            marker = existing / "sentinel"
            marker.write_bytes(b"sentinel")

            with self.assertRaises(eg8c_features.EvidenceWriteError):
                eg8c_features.run_eg8c_dataset_build(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    eg8c_output_root=Path(output_root),
                    eg8c_run_id="fixed-run",
                )

            self.assertEqual(list(existing.iterdir()), [marker])
            self.assertEqual(marker.read_bytes(), b"sentinel")

    def test_existing_run_symlink_is_rejected_without_modification(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=[current_row()], forecast_rows=[]
            )
            target = Path(staging) / "symlink-target"
            target.mkdir()
            marker = target / "sentinel"
            marker.write_bytes(b"sentinel")
            existing = Path(output_root) / "fixed-run"
            try:
                existing.symlink_to(target, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"symlink unavailable: {type(error).__name__}")

            with self.assertRaises(eg8c_features.EvidenceWriteError):
                eg8c_features.run_eg8c_dataset_build(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    eg8c_output_root=Path(output_root),
                    eg8c_run_id="fixed-run",
                )

            self.assertTrue(existing.is_symlink())
            self.assertEqual(list(target.iterdir()), [marker])
            self.assertEqual(marker.read_bytes(), b"sentinel")

    def test_input_change_during_build_rejects_final_run(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=[current_row()], forecast_rows=[]
            )
            real_write = eg8c_features._write_exclusive
            changed = False

            def write_then_change_input(path: Path, payload: bytes) -> None:
                nonlocal changed
                real_write(path, payload)
                if not changed:
                    changed = True
                    with current_path.open("ab") as source:
                        source.write(b"\n")

            with mock.patch.object(
                eg8c_features, "_write_exclusive", side_effect=write_then_change_input
            ), self.assertRaises(eg8c_features.EvidenceWriteError):
                eg8c_features.run_eg8c_dataset_build(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    eg8c_output_root=Path(output_root),
                    eg8c_run_id="changed-input-run",
                )

            self.assertEqual(list(Path(output_root).iterdir()), [])

    def test_same_bytes_input_replacement_during_build_rejects_final_run(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            source_root = Path(staging)
            raw_path, current_path, forecast_path = write_source_csvs(
                source_root, current_rows=[current_row()], forecast_rows=[]
            )
            real_write = eg8c_features._write_exclusive
            replaced = False

            def write_then_replace_input(path: Path, payload: bytes) -> None:
                nonlocal replaced
                real_write(path, payload)
                if not replaced:
                    replaced = True
                    replacement = source_root / "replacement.csv"
                    replacement.write_bytes(current_path.read_bytes())
                    replacement.replace(current_path)

            with mock.patch.object(
                eg8c_features, "_write_exclusive", side_effect=write_then_replace_input
            ), self.assertRaises(eg8c_features.EvidenceWriteError):
                eg8c_features.run_eg8c_dataset_build(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    eg8c_output_root=Path(output_root),
                    eg8c_run_id="replaced-input-run",
                )

            self.assertEqual(list(Path(output_root).iterdir()), [])

    def test_partial_output_failure_rejects_final_run_and_cleans_staging(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=[current_row()], forecast_rows=[]
            )
            real_write = eg8c_features._write_exclusive

            def fail_after_first_output(path: Path, payload: bytes) -> None:
                if path.name == eg8c_features.LABEL_DATASET_FILENAME:
                    raise eg8c_features.EvidenceWriteError("synthetic write failure")
                real_write(path, payload)

            with mock.patch.object(
                eg8c_features, "_write_exclusive", side_effect=fail_after_first_output
            ), self.assertRaises(eg8c_features.EvidenceWriteError):
                eg8c_features.run_eg8c_dataset_build(
                    raw_log_path=raw_path,
                    current_path=current_path,
                    forecast_path=forecast_path,
                    eg8c_output_root=Path(output_root),
                    eg8c_run_id="partial-output-run",
                )

            self.assertEqual(list(Path(output_root).iterdir()), [])

    def test_phase_directory_collision_raises_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=[current_row()], forecast_rows=[]
            )
            first = eg8c_features.run_eg8c_dataset_build(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
                eg8c_output_root=Path(output_root), eg8c_run_id="fixed-run",
            )
            manifest_before = (first.phase_dir / eg8c_features.DATASET_MANIFEST_FILENAME).read_bytes()
            with self.assertRaises(eg8c_features.EvidenceWriteError):
                eg8c_features.run_eg8c_dataset_build(
                    raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
                    eg8c_output_root=Path(output_root), eg8c_run_id="fixed-run",
                )
            manifest_after = (first.phase_dir / eg8c_features.DATASET_MANIFEST_FILENAME).read_bytes()
            self.assertEqual(manifest_before, manifest_after)

    def test_source_csvs_never_modified(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=[current_row()], forecast_rows=[]
            )
            def sha256_of(p: Path) -> str:
                return hashlib.sha256(p.read_bytes()).hexdigest()

            before = {p: sha256_of(p) for p in (raw_path, current_path, forecast_path)}
            eg8c_features.run_eg8c_dataset_build(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
                eg8c_output_root=Path(output_root), eg8c_run_id="hash-check-run",
            )
            after = {p: sha256_of(p) for p in (raw_path, current_path, forecast_path)}
            self.assertEqual(before, after)


class DeterminismTests(unittest.TestCase):
    def test_same_run_id_and_generated_at_produce_byte_identical_output(self) -> None:
        fixed_time = datetime(2026, 7, 25, 12, 0, 0, tzinfo=eg8a.SEOUL)
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as root_1, tempfile.TemporaryDirectory() as root_2:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=[current_row()], forecast_rows=[]
            )
            result_1 = eg8c_features.run_eg8c_dataset_build(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
                eg8c_output_root=Path(root_1), eg8c_run_id="fixed-run", generated_at=fixed_time,
            )
            result_2 = eg8c_features.run_eg8c_dataset_build(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
                eg8c_output_root=Path(root_2), eg8c_run_id="fixed-run", generated_at=fixed_time,
            )
            for filename in sorted(p.name for p in result_1.phase_dir.iterdir()):
                self.assertEqual(
                    (result_1.phase_dir / filename).read_bytes(),
                    (result_2.phase_dir / filename).read_bytes(),
                    f"{filename} differs",
                )


class CliTests(unittest.TestCase):
    def test_help_exits_zero(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
            eg8c_features.main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--current-path", stdout.getvalue())
        self.assertIn("--run-id", stdout.getvalue())

    def test_missing_required_arguments_exits_nonzero(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            eg8c_features.main([])

        self.assertNotEqual(raised.exception.code, 0)
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_invalid_run_id_returns_nonzero_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=[current_row()], forecast_rows=[]
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = eg8c_features.main(
                    [
                        "--current-path",
                        str(current_path),
                        "--forecast-path",
                        str(forecast_path),
                        "--error-path",
                        str(raw_path),
                        "--output-root",
                        output_root,
                        "--run-id",
                        "../outside",
                    ]
                )

            self.assertNotEqual(exit_code, 0)
            self.assertNotIn("Traceback", stderr.getvalue())
            self.assertEqual(list(Path(output_root).iterdir()), [])

    def test_synthetic_run_creates_exactly_eight_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as staging, tempfile.TemporaryDirectory() as output_root:
            raw_path, current_path, forecast_path = write_source_csvs(
                Path(staging), current_rows=[current_row()], forecast_rows=[]
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = eg8c_features.main(
                    [
                        "--current-path",
                        str(current_path),
                        "--forecast-path",
                        str(forecast_path),
                        "--error-path",
                        str(raw_path),
                        "--output-root",
                        output_root,
                        "--run-id",
                        "eg8c-20260726T190000-kst",
                    ]
                )

            phase_dir = (
                Path(output_root)
                / "eg8c-20260726T190000-kst"
                / eg8c_features.PHASE_EG8C_VERSION
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(list(phase_dir.iterdir())), 8)
            self.assertIn("run_id=eg8c-20260726T190000-kst", stdout.getvalue())


class ResolveOutputRootTests(unittest.TestCase):
    def test_missing_env_raises(self) -> None:
        with self.assertRaises(eg8c_features.OutputRootConfigurationError):
            eg8c_features.resolve_output_root_from_env({})

    def test_valid_directory_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resolved = eg8c_features.resolve_output_root_from_env({"FRESHMANAGER_EG8B_OUTPUT_ROOT": directory})
            self.assertEqual(resolved, Path(directory).resolve())


if __name__ == "__main__":
    unittest.main()
