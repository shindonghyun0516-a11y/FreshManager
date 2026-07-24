from __future__ import annotations

import csv
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


if __name__ == "__main__":
    unittest.main()
