from __future__ import annotations

import csv
import dataclasses
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from freshmanager import eg8a


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "eg8a"

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
    called_at: str = "2026-07-24 09:00:05",
    area_requested: str = "POI072",
    area_name: str = "여의도",
    http_code: str = "200",
    result_status: str = "SUCCESS",
    raw_json: str = '{"ok":true}',
) -> list[str]:
    return [run_id, called_at, area_requested, area_name, http_code, result_status, raw_json]


def current_row(
    *,
    run_id: str = RUN_A,
    called_at: str = "2026-07-24 09:00:05",
    observed_at: str = "2026-07-24 8:35",
    area_requested: str = "POI072",
    area_returned: str = "POI072",
    area_name: str = "여의도",
    congestion: str = "여유",
    population_min: str = "30000",
    population_max: str = "32000",
) -> list[str]:
    return [
        run_id, called_at, observed_at, area_requested, area_returned,
        area_name, congestion, population_min, population_max,
    ]


def forecast_row(
    *,
    run_id: str = RUN_A,
    called_at: str = "2026-07-24 09:00:05",
    observed_at: str = "2026-07-24 8:35",
    forecast_at: str = "2026-07-24 10:00",
    area_requested: str = "POI072",
    area_returned: str = "POI072",
    area_name: str = "여의도",
    congestion: str = "여유",
    population_min: str = "29000",
    population_max: str = "31000",
) -> list[str]:
    return [
        run_id, called_at, observed_at, forecast_at, area_requested,
        area_returned, area_name, congestion, population_min, population_max,
    ]


def make_current_record(**overrides: object) -> eg8a.NormalizedCurrentRecord:
    base: dict[str, object] = dict(
        collection_run_id=RUN_A,
        called_at="2026-07-24T09:00:05+09:00",
        observed_at="2026-07-24T08:35:00+09:00",
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
        called_at="2026-07-24T09:00:05+09:00",
        observed_at="2026-07-24T08:35:00+09:00",
        forecast_at="2026-07-24T10:00:00+09:00",
        area_code="POI072",
        area_code_requested="POI072",
        area_code_returned="POI072",
        area_name="여의도",
        forecast_congestion_level="여유",
        forecast_population_min=29000,
        forecast_population_max=31000,
        forecast_population_mid=30000.0,
        source_status="SUCCESS",
        duplicate_flag=False,
    )
    base.update(overrides)
    return eg8a.NormalizedForecastRecord(**base)


class SourceReaderTests(unittest.TestCase):
    def test_missing_required_column_raises_schema_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            header = [c for c in CURRENT_HEADER if c != "population_max"]
            path = write_csv(directory, "current.csv", header, [current_row()[:-1]])
            with self.assertRaises(eg8a.SchemaValidationError) as ctx:
                eg8a.read_source_csv(path, eg8a.CURRENT_REQUIRED_COLUMNS, "population_current_v3")
            self.assertIn(eg8a.ERROR_MISSING_REQUIRED_COLUMN, str(ctx.exception))

    def test_extra_column_is_preserved_not_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            header = CURRENT_HEADER + ["future_new_column"]
            path = write_csv(directory, "current.csv", header, [current_row() + ["x"]])
            rows, errors = eg8a.read_source_csv(path, eg8a.CURRENT_REQUIRED_COLUMNS, "population_current_v3")
            self.assertEqual(errors, [])
            self.assertEqual(rows[0].raw_row["future_new_column"], "x")

    def test_ragged_row_is_isolated_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = write_csv(
                directory,
                "current.csv",
                CURRENT_HEADER,
                [current_row(), current_row()[:-1]],
            )
            rows, errors = eg8a.read_source_csv(path, eg8a.CURRENT_REQUIRED_COLUMNS, "population_current_v3")
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].error_code, eg8a.ERROR_RAGGED_ROW)

    def test_source_file_is_never_modified(self) -> None:
        path = FIXTURES / "valid_population_current_v3.csv"
        before = path.read_bytes()
        eg8a.read_source_csv(path, eg8a.CURRENT_REQUIRED_COLUMNS, "population_current_v3")
        self.assertEqual(path.read_bytes(), before)


class DatetimeAndNumberTests(unittest.TestCase):
    def test_parses_zero_padded_and_non_padded_hour(self) -> None:
        padded = eg8a.parse_kst_datetime("2026-07-24 09:00:05")
        unpadded = eg8a.parse_kst_datetime("2026-07-24 9:00")
        self.assertEqual(padded.utcoffset().total_seconds(), 9 * 3600)
        self.assertEqual(unpadded.hour, 9)

    def test_invalid_datetime_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            eg8a.parse_kst_datetime("not-a-date")
        self.assertIn(eg8a.ERROR_INVALID_DATETIME, str(ctx.exception))

    def test_iso8601_output_has_explicit_kst_offset(self) -> None:
        value = eg8a.parse_kst_datetime("2026-07-24 01:06:06")
        self.assertEqual(eg8a.to_iso8601(value), "2026-07-24T01:06:06+09:00")

    def test_invalid_number_raises(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            eg8a.parse_population_int("abc")
        self.assertIn(eg8a.ERROR_INVALID_NUMBER, str(ctx.exception))


class NormalizeCurrentRowTests(unittest.TestCase):
    def _run(self, raw_row: dict[str, str], *, raw_log_status=None, raw_log_dupes=None):
        source_row = eg8a.SourceRow(source_file="population_current_v3", source_row_number=2, raw_row=raw_row)
        return eg8a._normalize_current_row(
            source_row,
            raw_log_status_by_key=raw_log_status or {},
            raw_log_duplicate_keys=raw_log_dupes or set(),
        )

    def _row(self, **overrides) -> dict[str, str]:
        base = dict(zip(CURRENT_HEADER, current_row()))
        base.update(overrides)
        return base

    def test_valid_row_produces_record_with_float_midpoint(self) -> None:
        result = self._run(
            self._row(population_min="6000", population_max="6501"),
            raw_log_status={(RUN_A, "POI072"): "SUCCESS"},
        )
        self.assertIsInstance(result, eg8a.NormalizedCurrentRecord)
        self.assertEqual(result.population_mid, 6250.5)
        self.assertEqual(result.area_code, "POI072")
        self.assertEqual(result.source_status, "SUCCESS")

    def test_missing_required_value(self) -> None:
        result = self._run(self._row(population_min=""))
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_MISSING_REQUIRED_VALUE)

    def test_area_code_mismatch_preserves_both_values(self) -> None:
        result = self._run(self._row(area_code_returned="POI019"))
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_AREA_CODE_MISMATCH)
        self.assertEqual(result.area_code_requested, "POI072")
        self.assertEqual(result.area_code_returned, "POI019")

    def test_invalid_number(self) -> None:
        result = self._run(self._row(population_min="abc"))
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_INVALID_NUMBER)

    def test_min_greater_than_max(self) -> None:
        result = self._run(self._row(population_min="9000", population_max="8000"))
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_MIN_GREATER_THAN_MAX)

    def test_negative_population(self) -> None:
        result = self._run(self._row(population_min="-100"))
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_NEGATIVE_POPULATION)

    def test_invalid_datetime(self) -> None:
        result = self._run(self._row(called_at="not-a-date"))
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_INVALID_DATETIME)

    def test_raw_log_key_duplicate_excludes_row(self) -> None:
        result = self._run(self._row(), raw_log_dupes={(RUN_A, "POI072")})
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_RAW_LOG_KEY_DUPLICATE)

    def test_raw_log_key_missing_isolates_error_row(self) -> None:
        """Raw Log 키가 없으면 정상 결과에 포함하지 않고 Error Row로만 남긴다
        (source_status=None인 정상 레코드를 만들지 않는다)."""
        result = self._run(self._row())
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_RAW_LOG_KEY_MISSING)
        self.assertIsNotNone(result.raw_row)


class NormalizeForecastRowTests(unittest.TestCase):
    def _run(self, raw_row: dict[str, str], *, raw_log_status=None, raw_log_dupes=None):
        source_row = eg8a.SourceRow(source_file="population_forecast_v3", source_row_number=2, raw_row=raw_row)
        return eg8a._normalize_forecast_row(
            source_row,
            raw_log_status_by_key=raw_log_status or {},
            raw_log_duplicate_keys=raw_log_dupes or set(),
        )

    def _row(self, **overrides) -> dict[str, str]:
        base = dict(zip(FORECAST_HEADER, forecast_row()))
        base.update(overrides)
        return base

    def test_forecast_not_after_observed(self) -> None:
        result = self._run(self._row(forecast_at="2026-07-24 8:00"))
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_FORECAST_NOT_AFTER_OBSERVED)

    def test_forecast_equal_to_observed_is_also_rejected(self) -> None:
        result = self._run(self._row(forecast_at="2026-07-24 8:35"))
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_FORECAST_NOT_AFTER_OBSERVED)

    def test_valid_forecast_row_produces_record(self) -> None:
        result = self._run(self._row(), raw_log_status={(RUN_A, "POI072"): "SUCCESS"})
        self.assertIsInstance(result, eg8a.NormalizedForecastRecord)
        self.assertEqual(result.forecast_population_mid, 30000.0)
        self.assertEqual(result.source_status, "SUCCESS")

    def test_raw_log_key_missing_isolates_error_row(self) -> None:
        result = self._run(self._row())
        self.assertIsInstance(result, eg8a.ErrorRow)
        self.assertEqual(result.error_code, eg8a.ERROR_RAW_LOG_KEY_MISSING)


class StructuralDuplicateDetectionTests(unittest.TestCase):
    """Unit tests for the Source Correlation Key uniqueness pre-passes."""

    def test_duplicate_keys_within_detects_repeated_current_key(self) -> None:
        rows = [
            eg8a.SourceRow("population_current_v3", 2, dict(zip(CURRENT_HEADER, current_row()))),
            eg8a.SourceRow("population_current_v3", 3, dict(zip(CURRENT_HEADER, current_row(population_min="1")))),
            eg8a.SourceRow("population_current_v3", 4, dict(zip(CURRENT_HEADER, current_row(area_requested="POI019", area_returned="POI019")))),
        ]
        duplicates = eg8a._duplicate_keys_within(rows)
        self.assertEqual(duplicates, {(RUN_A, "POI072")})

    def test_forecast_target_duplicate_keys_ignores_different_targets(self) -> None:
        rows = [
            eg8a.SourceRow("population_forecast_v3", 2, dict(zip(FORECAST_HEADER, forecast_row(forecast_at="2026-07-24 10:00")))),
            eg8a.SourceRow("population_forecast_v3", 3, dict(zip(FORECAST_HEADER, forecast_row(forecast_at="2026-07-24 11:00")))),
        ]
        self.assertEqual(eg8a._forecast_target_duplicate_keys(rows), set())

    def test_forecast_target_duplicate_keys_collapses_equivalent_formats(self) -> None:
        rows = [
            eg8a.SourceRow("population_forecast_v3", 2, dict(zip(FORECAST_HEADER, forecast_row(forecast_at="2026-07-24 10:00")))),
            eg8a.SourceRow("population_forecast_v3", 3, dict(zip(FORECAST_HEADER, forecast_row(forecast_at="2026-07-24 10:00:00")))),
        ]
        duplicates = eg8a._forecast_target_duplicate_keys(rows)
        self.assertEqual(len(duplicates), 1)


class NormalizeV3SourcesIntegrationTests(unittest.TestCase):
    def test_valid_fixtures_produce_expected_shape(self) -> None:
        result = eg8a.normalize_v3_sources(
            raw_log_path=FIXTURES / "valid_raw_log_v3.csv",
            current_path=FIXTURES / "valid_population_current_v3.csv",
            forecast_path=FIXTURES / "valid_population_forecast_v3.csv",
        )
        self.assertEqual(len(result.current_records), 4)
        self.assertEqual(len(result.forecast_records), 8)
        self.assertEqual(result.error_rows, ())
        for record in result.current_records:
            self.assertEqual(record.source_status, "SUCCESS")
        for record in result.forecast_records:
            self.assertEqual(record.source_status, "SUCCESS")

    def test_one_raw_one_current_n_forecast_shape(self) -> None:
        result = eg8a.normalize_v3_sources(
            raw_log_path=FIXTURES / "valid_raw_log_v3.csv",
            current_path=FIXTURES / "valid_population_current_v3.csv",
            forecast_path=FIXTURES / "valid_population_forecast_v3.csv",
        )
        forecast_counts: dict[tuple[str, str], int] = {}
        for record in result.forecast_records:
            key = (record.collection_run_id, record.area_code)
            forecast_counts[key] = forecast_counts.get(key, 0) + 1
        current_keys = {(r.collection_run_id, r.area_code) for r in result.current_records}
        self.assertEqual(set(forecast_counts), current_keys)
        self.assertTrue(all(count == 2 for count in forecast_counts.values()))

    def test_raw_log_key_missing_excludes_current_row_no_null_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            raw_path = write_csv(directory, "raw.csv", RAW_LOG_HEADER, [])
            current_path = write_csv(directory, "current.csv", CURRENT_HEADER, [current_row(area_requested="POI072", area_returned="POI072")])
            forecast_path = write_csv(directory, "forecast.csv", FORECAST_HEADER, [])
            result = eg8a.normalize_v3_sources(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
            )
            self.assertEqual(result.current_records, ())
            error_codes = [e.error_code for e in result.error_rows]
            self.assertIn(eg8a.ERROR_RAW_LOG_KEY_MISSING, error_codes)
            self.assertNotIn(eg8a.ERROR_SOURCE_KEY_MISMATCH, error_codes)
            missing_row = next(e for e in result.error_rows if e.error_code == eg8a.ERROR_RAW_LOG_KEY_MISSING)
            self.assertIsNotNone(missing_row.raw_row)
            self.assertEqual(missing_row.raw_row["area_code_requested"], "POI072")

    def test_raw_log_key_duplicate_excludes_current_and_preserves_all_raw_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            raw_path = write_csv(
                directory, "raw.csv", RAW_LOG_HEADER,
                [raw_log_row(result_status="SUCCESS"), raw_log_row(result_status="SUCCESS")],
            )
            current_path = write_csv(directory, "current.csv", CURRENT_HEADER, [current_row()])
            forecast_path = write_csv(directory, "forecast.csv", FORECAST_HEADER, [forecast_row()])
            result = eg8a.normalize_v3_sources(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
            )
            self.assertEqual(result.current_records, ())
            self.assertEqual(result.forecast_records, ())
            codes = [e.error_code for e in result.error_rows]
            self.assertEqual(codes.count(eg8a.ERROR_RAW_LOG_KEY_DUPLICATE), 2)

    def test_raw_log_only_key_flagged_as_source_key_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            raw_path = write_csv(directory, "raw.csv", RAW_LOG_HEADER, [raw_log_row(area_requested="POI088")])
            current_path = write_csv(directory, "current.csv", CURRENT_HEADER, [])
            forecast_path = write_csv(directory, "forecast.csv", FORECAST_HEADER, [])
            result = eg8a.normalize_v3_sources(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
            )
            self.assertEqual(len(result.error_rows), 1)
            self.assertEqual(result.error_rows[0].error_code, eg8a.ERROR_SOURCE_KEY_MISMATCH)
            self.assertIn("population_current_v3", result.error_rows[0].error_message)
            self.assertIn("population_forecast_v3", result.error_rows[0].error_message)

    def test_current_key_duplicate_isolates_all_rows_none_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            raw_path = write_csv(directory, "raw.csv", RAW_LOG_HEADER, [raw_log_row()])
            current_path = write_csv(
                directory, "current.csv", CURRENT_HEADER,
                [current_row(population_min="30000"), current_row(population_min="30500")],
            )
            forecast_path = write_csv(directory, "forecast.csv", FORECAST_HEADER, [])
            result = eg8a.normalize_v3_sources(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
            )
            self.assertEqual(result.current_records, ())
            duplicate_errors = [e for e in result.error_rows if e.error_code == eg8a.ERROR_CURRENT_KEY_DUPLICATE]
            self.assertEqual(len(duplicate_errors), 2)
            preserved_mins = {e.raw_row["population_min"] for e in duplicate_errors}
            self.assertEqual(preserved_mins, {"30000", "30500"})

    def test_forecast_target_duplicate_isolates_only_that_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            raw_path = write_csv(directory, "raw.csv", RAW_LOG_HEADER, [raw_log_row()])
            current_path = write_csv(directory, "current.csv", CURRENT_HEADER, [])
            forecast_path = write_csv(
                directory, "forecast.csv", FORECAST_HEADER,
                [
                    forecast_row(forecast_at="2026-07-24 10:00", population_min="29000"),
                    forecast_row(forecast_at="2026-07-24 10:00", population_min="29500"),
                    forecast_row(forecast_at="2026-07-24 11:00", population_min="35000", population_max="37000"),
                ],
            )
            result = eg8a.normalize_v3_sources(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
            )
            # the non-duplicated 11:00 target survives normally
            self.assertEqual(len(result.forecast_records), 1)
            self.assertEqual(result.forecast_records[0].forecast_at, "2026-07-24T11:00:00+09:00")
            duplicate_errors = [
                e for e in result.error_rows if e.error_code == eg8a.ERROR_FORECAST_TARGET_DUPLICATE
            ]
            self.assertEqual(len(duplicate_errors), 2)

    def test_ragged_row_does_not_abort_remaining_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            raw_path = write_csv(directory, "raw.csv", RAW_LOG_HEADER, [raw_log_row()])
            current_path = write_csv(
                directory, "current.csv", CURRENT_HEADER,
                [current_row(), current_row()[:-1]],
            )
            forecast_path = write_csv(directory, "forecast.csv", FORECAST_HEADER, [])
            result = eg8a.normalize_v3_sources(
                raw_log_path=raw_path, current_path=current_path, forecast_path=forecast_path,
            )
            self.assertEqual(len(result.current_records), 1)
            ragged = [e for e in result.error_rows if e.error_code == eg8a.ERROR_RAGGED_ROW]
            self.assertEqual(len(ragged), 1)

    def test_no_row_appears_in_both_normal_and_error_results(self) -> None:
        """§6: 정상 결과와 오류 결과에 같은 행을 동시에 포함하지 않는다."""
        result = eg8a.normalize_v3_sources(
            raw_log_path=FIXTURES / "valid_raw_log_v3.csv",
            current_path=FIXTURES / "valid_population_current_v3.csv",
            forecast_path=FIXTURES / "valid_population_forecast_v3.csv",
        )
        normal_keys = {(r.collection_run_id, r.area_code) for r in result.current_records}
        error_keys = {
            (e.collection_run_id, e.area_code_requested)
            for e in result.error_rows
            if e.collection_run_id and e.area_code_requested
        }
        self.assertEqual(normal_keys & error_keys, set())


class DuplicateDetectorTests(unittest.TestCase):
    """Issue B §1: duplicate_flag is a non-exclusionary signal over already-
    structurally-unique records, distinct from CURRENT_KEY_DUPLICATE /
    FORECAST_TARGET_DUPLICATE (which already hard-exclude on collection_run_id
    key uniqueness before a record ever reaches these functions)."""

    def test_current_first_occurrence_is_false(self) -> None:
        flagged = eg8a._flag_duplicate_current_records([make_current_record()])
        self.assertFalse(flagged[0].duplicate_flag)

    def test_current_second_occurrence_of_same_observation_is_true(self) -> None:
        records = [
            make_current_record(collection_run_id=RUN_A),
            make_current_record(collection_run_id=RUN_B),
        ]
        flagged = eg8a._flag_duplicate_current_records(records)
        self.assertFalse(flagged[0].duplicate_flag)
        self.assertTrue(flagged[1].duplicate_flag)

    def test_current_different_observed_at_is_not_duplicate(self) -> None:
        records = [
            make_current_record(observed_at="2026-07-24T08:35:00+09:00"),
            make_current_record(observed_at="2026-07-24T08:40:00+09:00"),
        ]
        flagged = eg8a._flag_duplicate_current_records(records)
        self.assertFalse(flagged[0].duplicate_flag)
        self.assertFalse(flagged[1].duplicate_flag)

    def test_current_different_area_is_not_duplicate(self) -> None:
        records = [
            make_current_record(area_code="POI072"),
            make_current_record(area_code="POI019"),
        ]
        flagged = eg8a._flag_duplicate_current_records(records)
        self.assertFalse(flagged[0].duplicate_flag)
        self.assertFalse(flagged[1].duplicate_flag)

    def test_current_third_distinct_key_after_a_duplicate_is_false(self) -> None:
        records = [
            make_current_record(area_code="POI072"),
            make_current_record(area_code="POI072"),
            make_current_record(area_code="POI019"),
        ]
        flagged = eg8a._flag_duplicate_current_records(records)
        self.assertFalse(flagged[0].duplicate_flag)
        self.assertTrue(flagged[1].duplicate_flag)
        self.assertFalse(flagged[2].duplicate_flag)

    def test_forecast_first_occurrence_is_false(self) -> None:
        flagged = eg8a._flag_duplicate_forecast_records([make_forecast_record()])
        self.assertFalse(flagged[0].duplicate_flag)

    def test_forecast_normal_five_minute_re_forecast_is_not_duplicate(self) -> None:
        """가장 중요한 회귀 테스트: 서로 다른 collection_run_id가 같은
        forecast_at을 다시 예측하는 것은 정상 5분 재예측이며 중복이 아니다 --
        observed_at이 다르면 forecast_at이 같아도 flag하지 않는다."""
        records = [
            make_forecast_record(
                collection_run_id=RUN_A,
                observed_at="2026-07-24T08:35:00+09:00",
                forecast_at="2026-07-24T10:00:00+09:00",
            ),
            make_forecast_record(
                collection_run_id=RUN_B,
                observed_at="2026-07-24T08:40:00+09:00",
                forecast_at="2026-07-24T10:00:00+09:00",
            ),
        ]
        flagged = eg8a._flag_duplicate_forecast_records(records)
        self.assertFalse(flagged[0].duplicate_flag)
        self.assertFalse(flagged[1].duplicate_flag)

    def test_forecast_same_observed_and_target_is_duplicate(self) -> None:
        records = [
            make_forecast_record(
                observed_at="2026-07-24T08:35:00+09:00",
                forecast_at="2026-07-24T10:00:00+09:00",
            ),
            make_forecast_record(
                collection_run_id=RUN_B,
                observed_at="2026-07-24T08:35:00+09:00",
                forecast_at="2026-07-24T10:00:00+09:00",
            ),
        ]
        flagged = eg8a._flag_duplicate_forecast_records(records)
        self.assertFalse(flagged[0].duplicate_flag)
        self.assertTrue(flagged[1].duplicate_flag)

    def test_via_normalize_v3_sources_fixtures_all_false(self) -> None:
        """실 계약 fixture(2 run × 2 area × 2 target, observed_at이 run마다
        다름)는 전부 duplicate_flag=False여야 한다 -- 정상 5분 재예측 재현."""
        result = eg8a.normalize_v3_sources(
            raw_log_path=FIXTURES / "valid_raw_log_v3.csv",
            current_path=FIXTURES / "valid_population_current_v3.csv",
            forecast_path=FIXTURES / "valid_population_forecast_v3.csv",
        )
        self.assertTrue(all(not r.duplicate_flag for r in result.current_records))
        self.assertTrue(all(not r.duplicate_flag for r in result.forecast_records))


class QualityReportTests(unittest.TestCase):
    """Issue B §4: build_quality_report against ML_READY_DATASET_SPEC.md
    §10/§13's must_produce/recommended split. No pass/fail threshold logic
    should exist anywhere in the output (§13 leaves thresholds OPEN_DECISION)."""

    GENERATED_AT = eg8a.parse_kst_datetime("2026-07-24 12:00:00")

    def _build_result(self) -> eg8a.NormalizationResult:
        current_records = (
            make_current_record(area_code="POI072", collection_run_id=RUN_A),
            make_current_record(
                area_code="POI019",
                collection_run_id=RUN_A,
                observed_at="2026-07-24T08:36:00+09:00",
            ),
        )
        forecast_records = (
            make_forecast_record(area_code="POI072", collection_run_id=RUN_A),
            make_forecast_record(
                area_code="POI019",
                collection_run_id=RUN_A,
                observed_at="2026-07-24T08:36:00+09:00",
            ),
        )
        error_rows = (
            eg8a.ErrorRow(
                source_file="population_current_v3",
                source_row_number=5,
                collection_run_id=RUN_B,
                area_code_requested="POI072",
                area_code_returned=None,
                error_code=eg8a.ERROR_MISSING_REQUIRED_VALUE,
                error_message="missing",
                raw_row={"collection_run_id": RUN_B},
            ),
            eg8a.ErrorRow(
                source_file="population_forecast_v3",
                source_row_number=6,
                collection_run_id=RUN_B,
                area_code_requested="POI072",
                area_code_returned="POI072",
                error_code=eg8a.ERROR_INVALID_NUMBER,
                error_message="bad number",
                raw_row={"collection_run_id": RUN_B},
            ),
        )
        return eg8a.NormalizationResult(
            current_records=current_records,
            forecast_records=forecast_records,
            error_rows=error_rows,
            raw_log_input_row_count=3,
            current_input_row_count=3,
            forecast_input_row_count=3,
        )

    def test_row_counts(self) -> None:
        report = eg8a.build_quality_report(
            self._build_result(), dataset_id="ds-1", generated_at=self.GENERATED_AT
        )
        counts = report["must_produce"]["row_counts"]
        self.assertEqual(counts["raw_log_v3_input_rows"], 3)
        self.assertEqual(counts["population_current_v3_input_rows"], 3)
        self.assertEqual(counts["population_forecast_v3_input_rows"], 3)
        self.assertEqual(counts["current_normal_rows"], 2)
        self.assertEqual(counts["forecast_normal_rows"], 2)
        self.assertEqual(counts["error_rows_total"], 2)
        self.assertEqual(
            counts["error_rows_by_code"],
            {eg8a.ERROR_MISSING_REQUIRED_VALUE: 1, eg8a.ERROR_INVALID_NUMBER: 1},
        )

    def test_area_row_counts_and_consistency(self) -> None:
        report = eg8a.build_quality_report(
            self._build_result(), dataset_id="ds-1", generated_at=self.GENERATED_AT
        )
        area = report["must_produce"]["area_row_counts"]
        self.assertEqual(len(area["official_area_codes"]), 13)
        self.assertEqual(area["unexpected_area_codes"], [])
        per_area_by_code = {row["area_code"]: row for row in area["per_area"]}
        self.assertEqual(per_area_by_code["POI072"]["current_row_count"], 1)
        self.assertEqual(per_area_by_code["POI072"]["forecast_row_count"], 1)
        self.assertNotIn("POI072", area["areas_with_zero_current_rows"])
        self.assertIn("POI072", [c["area_code"] for c in area["per_area"]])
        consistency = report["must_produce"]["area_code_consistency"]
        self.assertEqual(consistency["official_area_count"], 13)
        self.assertTrue(consistency["current_area_codes_all_official"])
        self.assertTrue(consistency["forecast_area_codes_all_official"])

    def test_success_and_missing_rates(self) -> None:
        report = eg8a.build_quality_report(
            self._build_result(), dataset_id="ds-1", generated_at=self.GENERATED_AT
        )
        must = report["must_produce"]
        self.assertAlmostEqual(must["missing_value_rate"]["current"], 1 / 3)
        self.assertEqual(must["missing_value_rate"]["forecast"], 0.0)
        self.assertAlmostEqual(must["numeric_conversion_success_rate"]["forecast"], 2 / 3)
        self.assertEqual(must["numeric_conversion_success_rate"]["current"], 1.0)
        self.assertEqual(must["time_parse_success_rate"]["current"], 1.0)
        self.assertEqual(must["time_parse_success_rate"]["forecast"], 1.0)

    def test_zero_denominator_rates_are_none(self) -> None:
        empty_result = eg8a.NormalizationResult(
            current_records=(),
            forecast_records=(),
            error_rows=(),
            raw_log_input_row_count=0,
            current_input_row_count=0,
            forecast_input_row_count=0,
        )
        report = eg8a.build_quality_report(
            empty_result, dataset_id="ds-1", generated_at=self.GENERATED_AT
        )
        must = report["must_produce"]
        self.assertIsNone(must["time_parse_success_rate"]["current"])
        self.assertIsNone(must["missing_value_rate"]["forecast"])

    def test_duplicate_metrics(self) -> None:
        result = self._build_result()
        result = dataclasses.replace(
            result,
            current_records=(
                dataclasses.replace(result.current_records[0], duplicate_flag=True),
                result.current_records[1],
            ),
            error_rows=result.error_rows
            + (
                eg8a.ErrorRow(
                    source_file="population_current_v3",
                    source_row_number=7,
                    collection_run_id=RUN_B,
                    area_code_requested="POI019",
                    area_code_returned=None,
                    error_code=eg8a.ERROR_CURRENT_KEY_DUPLICATE,
                    error_message="dup",
                    raw_row={"collection_run_id": RUN_B},
                ),
            ),
        )
        report = eg8a.build_quality_report(
            result, dataset_id="ds-1", generated_at=self.GENERATED_AT
        )
        current_dup = report["recommended"]["current_duplicate"]
        self.assertEqual(current_dup["structural_duplicate_rows_excluded"], 1)
        self.assertEqual(current_dup["semantic_duplicate_rows_flagged"], 1)
        self.assertAlmostEqual(current_dup["semantic_duplicate_rate"], 0.5)

    def test_no_threshold_fields_present(self) -> None:
        report = eg8a.build_quality_report(
            self._build_result(), dataset_id="ds-1", generated_at=self.GENERATED_AT
        )
        self.assertEqual(
            set(report),
            {"schema_version", "dataset_id", "generated_at", "must_produce", "recommended"},
        )
        serialized = json.dumps(report).lower()
        self.assertNotIn("threshold", serialized)
        self.assertNotIn('"pass"', serialized)


class DatasetManifestTests(unittest.TestCase):
    GENERATED_AT = eg8a.parse_kst_datetime("2026-07-24 12:00:00")

    def test_sha256_file_matches_hashlib(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.bin"
            payload = b"hello world" * 100
            path.write_bytes(payload)
            self.assertEqual(eg8a._sha256_file(path), hashlib.sha256(payload).hexdigest())

    def _minimal_result(self) -> eg8a.NormalizationResult:
        return eg8a.NormalizationResult(
            current_records=(make_current_record(),),
            forecast_records=(make_forecast_record(),),
            error_rows=(),
            raw_log_input_row_count=1,
            current_input_row_count=1,
            forecast_input_row_count=1,
        )

    def test_manifest_fields(self) -> None:
        manifest = eg8a.build_dataset_manifest(
            dataset_id="ds-123",
            generated_at=self.GENERATED_AT,
            result=self._minimal_result(),
            input_artifacts=[{"logical_name": "raw_log_v3", "sha256": "a" * 64, "byte_size": 10}],
            output_artifacts=[
                {"relative_path": "normalized_current.csv", "sha256": "b" * 64, "byte_size": 20}
            ],
        )
        self.assertEqual(manifest["schema_version"], eg8a.DATASET_MANIFEST_SCHEMA_VERSION)
        self.assertEqual(manifest["dataset_id"], "ds-123")
        self.assertEqual(manifest["dataset_version"], "ds-123")
        self.assertEqual(manifest["loader_version"], eg8a.LOADER_VERSION)
        self.assertEqual(manifest["hash_algorithm"], "sha256")
        self.assertEqual(manifest["source_row_counts"]["current_normal_rows"], 1)

    def test_input_artifacts_carry_no_path_field(self) -> None:
        manifest = eg8a.build_dataset_manifest(
            dataset_id="ds-123",
            generated_at=self.GENERATED_AT,
            result=self._minimal_result(),
            input_artifacts=[{"logical_name": "raw_log_v3", "sha256": "a" * 64, "byte_size": 10}],
            output_artifacts=[],
        )
        for artifact in manifest["input_artifacts"]:
            self.assertNotIn("path", artifact)
            self.assertNotIn("relative_path", artifact)
            self.assertNotIn("absolute_path", artifact)
            self.assertIn("logical_name", artifact)


class OutputWriterTests(unittest.TestCase):
    def test_write_current_csv_header_and_bool_true_serialization(self) -> None:
        payload = eg8a.write_current_csv([make_current_record(duplicate_flag=True)])
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
        self.assertEqual(reader.fieldnames, list(eg8a.CURRENT_CSV_FIELDNAMES))
        self.assertEqual(next(reader)["duplicate_flag"], "true")

    def test_write_forecast_csv_bool_false_serialization(self) -> None:
        payload = eg8a.write_forecast_csv([make_forecast_record(duplicate_flag=False)])
        row = next(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
        self.assertEqual(row["duplicate_flag"], "false")

    def test_write_error_rows_csv_raw_row_json_round_trips(self) -> None:
        error = eg8a.ErrorRow(
            source_file="population_current_v3",
            source_row_number=2,
            collection_run_id=RUN_A,
            area_code_requested="POI072",
            area_code_returned=None,
            error_code=eg8a.ERROR_MISSING_REQUIRED_VALUE,
            error_message="x",
            raw_row={"extra_column": "kept", "population_min": "1"},
        )
        payload = eg8a.write_error_rows_csv([error])
        row = next(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
        self.assertEqual(
            json.loads(row["raw_row_json"]), {"extra_column": "kept", "population_min": "1"}
        )

    def test_write_error_rows_csv_none_raw_row_is_empty_string(self) -> None:
        error = eg8a.ErrorRow(
            source_file="__source_correlation__",
            source_row_number=None,
            collection_run_id=RUN_A,
            area_code_requested="POI072",
            area_code_returned=None,
            error_code=eg8a.ERROR_SOURCE_KEY_MISMATCH,
            error_message="x",
            raw_row=None,
        )
        row = next(csv.DictReader(io.StringIO(eg8a.write_error_rows_csv([error]).decode("utf-8"))))
        self.assertEqual(row["raw_row_json"], "")

    def _minimal_result(self) -> eg8a.NormalizationResult:
        return eg8a.NormalizationResult(
            current_records=(make_current_record(),),
            forecast_records=(make_forecast_record(),),
            error_rows=(),
            raw_log_input_row_count=1,
            current_input_row_count=1,
            forecast_input_row_count=1,
        )

    def _write_input_csvs(self, directory: Path) -> dict[str, Path]:
        return {
            "raw_log_v3": write_csv(directory, "raw.csv", RAW_LOG_HEADER, [raw_log_row()]),
            "population_current_v3": write_csv(
                directory, "current.csv", CURRENT_HEADER, [current_row()]
            ),
            "population_forecast_v3": write_csv(
                directory, "forecast.csv", FORECAST_HEADER, [forecast_row()]
            ),
        }

    def test_export_dataset_creates_five_files(self) -> None:
        with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_root:
            inputs = self._write_input_csvs(Path(input_dir))
            export_result = eg8a.export_dataset(
                self._minimal_result(), output_root=Path(output_root), input_paths=inputs
            )
            for filename in (
                eg8a.CURRENT_OUTPUT_FILENAME,
                eg8a.FORECAST_OUTPUT_FILENAME,
                eg8a.ERROR_ROWS_OUTPUT_FILENAME,
                eg8a.QUALITY_REPORT_OUTPUT_FILENAME,
                eg8a.DATASET_MANIFEST_OUTPUT_FILENAME,
            ):
                self.assertTrue((export_result.dataset_dir / filename).is_file())
            manifest = json.loads(
                (export_result.dataset_dir / eg8a.DATASET_MANIFEST_OUTPUT_FILENAME).read_text()
            )
            self.assertEqual(len(manifest["output_artifacts"]), 4)
            self.assertEqual(len(manifest["input_artifacts"]), 3)

    def test_export_dataset_input_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_root:
            inputs = self._write_input_csvs(Path(input_dir))
            before = {name: path.read_bytes() for name, path in inputs.items()}
            eg8a.export_dataset(
                self._minimal_result(), output_root=Path(output_root), input_paths=inputs
            )
            after = {name: path.read_bytes() for name, path in inputs.items()}
            self.assertEqual(before, after)

    def test_export_dataset_rejects_wrong_input_path_keys(self) -> None:
        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(eg8a.DatasetWriteError):
                eg8a.export_dataset(
                    self._minimal_result(),
                    output_root=Path(output_root),
                    input_paths={"raw_log_v3": Path("x")},
                )

    def test_write_exclusive_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.txt"
            eg8a._write_exclusive(path, b"first")
            with self.assertRaises(eg8a.DatasetWriteError):
                eg8a._write_exclusive(path, b"second")
            self.assertEqual(path.read_bytes(), b"first")

    def test_export_dataset_same_dataset_id_same_root_collides(self) -> None:
        with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as output_root:
            inputs = self._write_input_csvs(Path(input_dir))
            eg8a.export_dataset(
                self._minimal_result(),
                output_root=Path(output_root),
                input_paths=inputs,
                dataset_id="fixed-id",
            )
            with self.assertRaises(eg8a.DatasetWriteError):
                eg8a.export_dataset(
                    self._minimal_result(),
                    output_root=Path(output_root),
                    input_paths=inputs,
                    dataset_id="fixed-id",
                )

    def test_resolve_output_root_from_env_missing_raises(self) -> None:
        with self.assertRaises(eg8a.OutputRootConfigurationError):
            eg8a.resolve_output_root_from_env({})

    def test_resolve_output_root_from_env_nonexistent_raises(self) -> None:
        with self.assertRaises(eg8a.OutputRootConfigurationError):
            eg8a.resolve_output_root_from_env(
                {eg8a.FRESHMANAGER_EG8A_OUTPUT_ROOT_ENV: "/no/such/path/at/all/eg8a"}
            )

    def test_resolve_output_root_from_env_valid_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            resolved = eg8a.resolve_output_root_from_env(
                {eg8a.FRESHMANAGER_EG8A_OUTPUT_ROOT_ENV: tmp}
            )
            self.assertTrue(resolved.is_dir())


class DeterministicReExecutionTests(unittest.TestCase):
    """Issue B §5/§6: same input + same dataset_id/generated_at ⇒ byte-
    identical output across two independent export_dataset calls."""

    def _write_input_csvs(self, directory: Path) -> dict[str, Path]:
        return {
            "raw_log_v3": write_csv(
                directory,
                "raw.csv",
                RAW_LOG_HEADER,
                [raw_log_row(), raw_log_row(run_id=RUN_B, area_requested="POI019")],
            ),
            "population_current_v3": write_csv(
                directory,
                "current.csv",
                CURRENT_HEADER,
                [
                    current_row(),
                    current_row(run_id=RUN_B, area_requested="POI019", area_returned="POI019"),
                ],
            ),
            "population_forecast_v3": write_csv(
                directory,
                "forecast.csv",
                FORECAST_HEADER,
                [
                    forecast_row(),
                    forecast_row(run_id=RUN_B, area_requested="POI019", area_returned="POI019"),
                ],
            ),
        }

    def test_same_dataset_id_and_generated_at_produce_byte_identical_output(self) -> None:
        with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as root_a, tempfile.TemporaryDirectory() as root_b:
            inputs = self._write_input_csvs(Path(input_dir))
            result = eg8a.normalize_v3_sources(
                raw_log_path=inputs["raw_log_v3"],
                current_path=inputs["population_current_v3"],
                forecast_path=inputs["population_forecast_v3"],
            )
            fixed_id = "11111111-1111-4111-8111-111111111111"
            fixed_time = eg8a.parse_kst_datetime("2026-07-24 12:00:00")
            export_a = eg8a.export_dataset(
                result,
                output_root=Path(root_a),
                input_paths=inputs,
                dataset_id=fixed_id,
                generated_at=fixed_time,
            )
            export_b = eg8a.export_dataset(
                result,
                output_root=Path(root_b),
                input_paths=inputs,
                dataset_id=fixed_id,
                generated_at=fixed_time,
            )
            for filename in (
                eg8a.CURRENT_OUTPUT_FILENAME,
                eg8a.FORECAST_OUTPUT_FILENAME,
                eg8a.ERROR_ROWS_OUTPUT_FILENAME,
                eg8a.QUALITY_REPORT_OUTPUT_FILENAME,
                eg8a.DATASET_MANIFEST_OUTPUT_FILENAME,
            ):
                content_a = (export_a.dataset_dir / filename).read_bytes()
                content_b = (export_b.dataset_dir / filename).read_bytes()
                self.assertEqual(content_a, content_b, f"{filename} differs between runs")

    def test_unspecified_dataset_id_differs_but_csv_content_matches(self) -> None:
        with tempfile.TemporaryDirectory() as input_dir, tempfile.TemporaryDirectory() as root_a, tempfile.TemporaryDirectory() as root_b:
            inputs = self._write_input_csvs(Path(input_dir))
            result = eg8a.normalize_v3_sources(
                raw_log_path=inputs["raw_log_v3"],
                current_path=inputs["population_current_v3"],
                forecast_path=inputs["population_forecast_v3"],
            )
            export_a = eg8a.export_dataset(result, output_root=Path(root_a), input_paths=inputs)
            export_b = eg8a.export_dataset(result, output_root=Path(root_b), input_paths=inputs)
            self.assertNotEqual(export_a.dataset_id, export_b.dataset_id)
            for filename in (
                eg8a.CURRENT_OUTPUT_FILENAME,
                eg8a.FORECAST_OUTPUT_FILENAME,
                eg8a.ERROR_ROWS_OUTPUT_FILENAME,
            ):
                content_a = (export_a.dataset_dir / filename).read_bytes()
                content_b = (export_b.dataset_dir / filename).read_bytes()
                self.assertEqual(content_a, content_b, f"{filename} differs between runs")


if __name__ == "__main__":
    unittest.main()
