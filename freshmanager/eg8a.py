"""EG-8A CSV Source Reader, Schema Validation, Normalization, Duplicate
Detection, Quality Report, Dataset Manifest, and Output Writer.

Reads the three v3 source sheet CSV exports (Apps Script Runtime output,
manually exported per `docs/data/ML_READY_DATASET_SPEC.md` §3.1) read-only
and produces Normalized Current/Forecast records plus isolated Error Rows
(`normalize_v3_sources`), then flags semantic duplicate observations, builds
a Quality Report and Dataset Manifest, and writes the five V0 output
artifacts to an external output-root with exclusive-create, no-overwrite
semantics (`export_dataset`).

`normalize_v3_sources` enforces Source Correlation Key *structural*
identity: a Current row and a Forecast target are each expected to be
unique per key, and a Raw Log match is expected to be unique and present --
any violation is a Schema/Integrity error, isolated in full, never
partially joined or arbitrarily picked. `duplicate_flag` (computed by
`export_dataset`'s pipeline) is a separate, non-exclusionary signal over
otherwise-valid, already-structurally-unique records: it flags when the
same semantic observation recurs across different collection runs, without
removing any row.
"""

from __future__ import annotations

import csv
import dataclasses
import hashlib
import io
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from . import eg6b

SEOUL = ZoneInfo("Asia/Seoul")
TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")

FRESHMANAGER_EG8A_OUTPUT_ROOT_ENV = "FRESHMANAGER_EG8A_OUTPUT_ROOT"
LOADER_VERSION = "eg8a-loader-v1"
QUALITY_REPORT_SCHEMA_VERSION = "eg8a-quality-report-v1"
DATASET_MANIFEST_SCHEMA_VERSION = "eg8a-dataset-manifest-v1"

CURRENT_OUTPUT_FILENAME = "normalized_current.csv"
FORECAST_OUTPUT_FILENAME = "normalized_forecast.csv"
ERROR_ROWS_OUTPUT_FILENAME = "error_rows.csv"
QUALITY_REPORT_OUTPUT_FILENAME = "quality_report.json"
DATASET_MANIFEST_OUTPUT_FILENAME = "dataset_manifest.json"

RAW_LOG_REQUIRED_COLUMNS = (
    "collection_run_id",
    "called_at",
    "area_code_requested",
    "area_name",
    "http_code",
    "result_status",
    "raw_json_or_error",
)
CURRENT_REQUIRED_COLUMNS = (
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
FORECAST_REQUIRED_COLUMNS = (
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

# Error codes -- ML_READY_DATASET_SPEC.md §11 candidate set, extended with
# the structural Source Correlation Key uniqueness codes from Issue A
# integrity review (CURRENT_KEY_DUPLICATE, FORECAST_TARGET_DUPLICATE).
ERROR_MISSING_REQUIRED_COLUMN = "MISSING_REQUIRED_COLUMN"
ERROR_MISSING_REQUIRED_VALUE = "MISSING_REQUIRED_VALUE"
ERROR_RAGGED_ROW = "RAGGED_ROW"
ERROR_INVALID_DATETIME = "INVALID_DATETIME"
ERROR_INVALID_NUMBER = "INVALID_NUMBER"
ERROR_AREA_CODE_MISMATCH = "AREA_CODE_MISMATCH"
ERROR_MIN_GREATER_THAN_MAX = "MIN_GREATER_THAN_MAX"
ERROR_NEGATIVE_POPULATION = "NEGATIVE_POPULATION"
ERROR_FORECAST_NOT_AFTER_OBSERVED = "FORECAST_NOT_AFTER_OBSERVED"
ERROR_RAW_LOG_KEY_MISSING = "RAW_LOG_KEY_MISSING"
ERROR_RAW_LOG_KEY_DUPLICATE = "RAW_LOG_KEY_DUPLICATE"
ERROR_CURRENT_KEY_DUPLICATE = "CURRENT_KEY_DUPLICATE"
ERROR_FORECAST_TARGET_DUPLICATE = "FORECAST_TARGET_DUPLICATE"
ERROR_SOURCE_KEY_MISMATCH = "SOURCE_KEY_MISMATCH"

SourceKey = tuple[str, str]
ForecastTargetKey = tuple[str, str, datetime]
ObservationKey = tuple[str, str]
ForecastObservationKey = tuple[str, str, str]


class SchemaValidationError(ValueError):
    """Raised when a Source CSV is missing a required column (header-level)."""


@dataclass(frozen=True)
class SourceRow:
    source_file: str
    source_row_number: int
    raw_row: Mapping[str, str]


@dataclass(frozen=True)
class ErrorRow:
    source_file: str
    source_row_number: int | None
    collection_run_id: str | None
    area_code_requested: str | None
    area_code_returned: str | None
    error_code: str
    error_message: str
    raw_row: Mapping[str, str] | None


@dataclass(frozen=True)
class NormalizedCurrentRecord:
    collection_run_id: str
    called_at: str
    observed_at: str
    area_code: str
    area_code_requested: str
    area_code_returned: str
    area_name: str
    congestion_level: str
    population_min: int
    population_max: int
    population_mid: float
    source_status: str
    duplicate_flag: bool


@dataclass(frozen=True)
class NormalizedForecastRecord:
    collection_run_id: str
    called_at: str
    observed_at: str
    forecast_at: str
    area_code: str
    area_code_requested: str
    area_code_returned: str
    area_name: str
    forecast_congestion_level: str
    forecast_population_min: int
    forecast_population_max: int
    forecast_population_mid: float
    source_status: str
    duplicate_flag: bool


@dataclass(frozen=True)
class NormalizationResult:
    current_records: tuple[NormalizedCurrentRecord, ...]
    forecast_records: tuple[NormalizedForecastRecord, ...]
    error_rows: tuple[ErrorRow, ...]
    raw_log_input_row_count: int
    current_input_row_count: int
    forecast_input_row_count: int


def read_source_csv(
    path: Path,
    required_columns: Sequence[str],
    source_label: str,
) -> tuple[list[SourceRow], list[ErrorRow]]:
    """Read one v3 source sheet CSV read-only; never writes to `path`.

    Missing required columns abort the whole file (SchemaValidationError).
    Extra columns are preserved, not rejected. Ragged rows are isolated as
    Error Rows instead of aborting the read.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as error:
            raise SchemaValidationError(
                f"{ERROR_MISSING_REQUIRED_COLUMN}: {source_label} is empty"
            ) from error
        missing = [column for column in required_columns if column not in header]
        if missing:
            raise SchemaValidationError(
                f"{ERROR_MISSING_REQUIRED_COLUMN}: {source_label} missing {missing}"
            )
        if len(set(header)) != len(header):
            raise SchemaValidationError(
                f"{ERROR_MISSING_REQUIRED_COLUMN}: {source_label} duplicate header columns"
            )
        good_rows: list[SourceRow] = []
        error_rows: list[ErrorRow] = []
        for line_number, values in enumerate(reader, start=2):
            if len(values) != len(header):
                error_rows.append(
                    ErrorRow(
                        source_file=source_label,
                        source_row_number=line_number,
                        collection_run_id=None,
                        area_code_requested=None,
                        area_code_returned=None,
                        error_code=ERROR_RAGGED_ROW,
                        error_message=(
                            f"expected {len(header)} columns, got {len(values)}"
                        ),
                        raw_row=None,
                    )
                )
                continue
            good_rows.append(
                SourceRow(
                    source_file=source_label,
                    source_row_number=line_number,
                    raw_row=dict(zip(header, values)),
                )
            )
        return good_rows, error_rows


def parse_kst_datetime(value: str) -> datetime:
    """Parse a naive v3-sheet timestamp string as Asia/Seoul-aware.

    Accepts both zero-padded and non-zero-padded hour forms observed in
    real Export samples (e.g. ``2026-07-24 0:35`` and ``2026-07-24 00:35``).
    """
    for time_format in TIME_FORMATS:
        try:
            naive = datetime.strptime(value, time_format)
        except ValueError:
            continue
        return naive.replace(tzinfo=SEOUL)
    raise ValueError(f"{ERROR_INVALID_DATETIME}: {value!r}")


def to_iso8601(value: datetime) -> str:
    return value.isoformat()


def parse_population_int(value: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{ERROR_INVALID_NUMBER}: {value!r}") from error


def _require_nonempty(raw_row: Mapping[str, str], field_name: str) -> str:
    value = raw_row.get(field_name)
    if value is None or value.strip() == "":
        raise ValueError(f"{ERROR_MISSING_REQUIRED_VALUE}: {field_name}")
    return value


def _row_key(row: SourceRow) -> SourceKey | None:
    run_id = row.raw_row.get("collection_run_id", "").strip()
    area = row.raw_row.get("area_code_requested", "").strip()
    return (run_id, area) if run_id and area else None


def _seen_keys(rows: Sequence[SourceRow]) -> set[SourceKey]:
    keys: set[SourceKey] = set()
    for row in rows:
        key = _row_key(row)
        if key is not None:
            keys.add(key)
    return keys


def _duplicate_keys_within(rows: Sequence[SourceRow]) -> set[SourceKey]:
    """Return Source Correlation Keys that appear more than once in `rows`."""
    counts: dict[SourceKey, int] = {}
    for row in rows:
        key = _row_key(row)
        if key is not None:
            counts[key] = counts.get(key, 0) + 1
    return {key for key, count in counts.items() if count > 1}


def _forecast_target_duplicate_keys(rows: Sequence[SourceRow]) -> set[ForecastTargetKey]:
    """Return (run_id, area_code_requested, forecast_at) triples seen more than
    once. Uses the *parsed* instant so differently-formatted-but-identical
    timestamps still collide, matching EG-7's canonical signature precedent.
    Rows whose own forecast_at fails to parse are excluded here and left to
    their own INVALID_DATETIME classification."""
    counts: dict[ForecastTargetKey, int] = {}
    for row in rows:
        key = _row_key(row)
        forecast_raw = row.raw_row.get("forecast_at", "").strip()
        if key is None or not forecast_raw:
            continue
        try:
            forecast_at = parse_kst_datetime(forecast_raw)
        except ValueError:
            continue
        target_key = (key[0], key[1], forecast_at)
        counts[target_key] = counts.get(target_key, 0) + 1
    return {key for key, count in counts.items() if count > 1}


def _build_raw_log_index(
    raw_log_rows: Sequence[SourceRow],
) -> tuple[dict[SourceKey, str], set[SourceKey]]:
    """Return {key: result_status} for unique keys, and the set of duplicate keys."""
    seen: dict[SourceKey, int] = {}
    status_by_key: dict[SourceKey, str] = {}
    for row in raw_log_rows:
        key = _row_key(row)
        if key is None:
            continue
        seen[key] = seen.get(key, 0) + 1
        status_by_key[key] = row.raw_row.get("result_status", "")
    duplicate_keys = {key for key, count in seen.items() if count > 1}
    for key in duplicate_keys:
        status_by_key.pop(key, None)
    return status_by_key, duplicate_keys


def _error(
    row: SourceRow,
    error_code: str,
    error_message: str,
    *,
    run_id: str | None = None,
    requested: str | None = None,
    returned: str | None = None,
) -> ErrorRow:
    return ErrorRow(
        source_file=row.source_file,
        source_row_number=row.source_row_number,
        collection_run_id=run_id or row.raw_row.get("collection_run_id") or None,
        area_code_requested=requested or row.raw_row.get("area_code_requested") or None,
        area_code_returned=returned or row.raw_row.get("area_code_returned") or None,
        error_code=error_code,
        error_message=error_message,
        raw_row=row.raw_row,
    )


def _normalize_current_row(
    row: SourceRow,
    *,
    raw_log_status_by_key: Mapping[SourceKey, str],
    raw_log_duplicate_keys: set[SourceKey],
) -> NormalizedCurrentRecord | ErrorRow:
    raw = row.raw_row
    try:
        run_id = _require_nonempty(raw, "collection_run_id")
        called_raw = _require_nonempty(raw, "called_at")
        observed_raw = _require_nonempty(raw, "observed_at")
        requested = _require_nonempty(raw, "area_code_requested")
        returned = _require_nonempty(raw, "area_code_returned")
        area_name = _require_nonempty(raw, "area_name")
        congestion = _require_nonempty(raw, "congestion_level")
        min_raw = _require_nonempty(raw, "population_min")
        max_raw = _require_nonempty(raw, "population_max")
    except ValueError as error:
        return _error(row, ERROR_MISSING_REQUIRED_VALUE, str(error))

    if requested != returned:
        return _error(
            row,
            ERROR_AREA_CODE_MISMATCH,
            f"area_code_requested={requested!r} != area_code_returned={returned!r}",
            requested=requested,
            returned=returned,
        )

    try:
        called_at = parse_kst_datetime(called_raw)
        observed_at = parse_kst_datetime(observed_raw)
    except ValueError as error:
        return _error(row, ERROR_INVALID_DATETIME, str(error))

    try:
        population_min = parse_population_int(min_raw)
        population_max = parse_population_int(max_raw)
    except ValueError as error:
        return _error(row, ERROR_INVALID_NUMBER, str(error))

    if population_min < 0 or population_max < 0:
        return _error(
            row,
            ERROR_NEGATIVE_POPULATION,
            f"population_min={population_min} population_max={population_max}",
        )
    if population_min > population_max:
        return _error(
            row,
            ERROR_MIN_GREATER_THAN_MAX,
            f"population_min={population_min} > population_max={population_max}",
        )

    key = (run_id, requested)
    if key in raw_log_duplicate_keys:
        return _error(
            row,
            ERROR_RAW_LOG_KEY_DUPLICATE,
            f"raw_log_v3 has multiple rows for key {key}",
        )
    if key not in raw_log_status_by_key:
        return _error(
            row,
            ERROR_RAW_LOG_KEY_MISSING,
            f"raw_log_v3 has no row for key {key}",
        )

    return NormalizedCurrentRecord(
        collection_run_id=run_id,
        called_at=to_iso8601(called_at),
        observed_at=to_iso8601(observed_at),
        area_code=requested,
        area_code_requested=requested,
        area_code_returned=returned,
        area_name=area_name,
        congestion_level=congestion,
        population_min=population_min,
        population_max=population_max,
        population_mid=(population_min + population_max) / 2,
        source_status=raw_log_status_by_key[key],
        duplicate_flag=False,
    )


def _normalize_forecast_row(
    row: SourceRow,
    *,
    raw_log_status_by_key: Mapping[SourceKey, str],
    raw_log_duplicate_keys: set[SourceKey],
) -> NormalizedForecastRecord | ErrorRow:
    raw = row.raw_row
    try:
        run_id = _require_nonempty(raw, "collection_run_id")
        called_raw = _require_nonempty(raw, "called_at")
        observed_raw = _require_nonempty(raw, "observed_at")
        forecast_raw = _require_nonempty(raw, "forecast_at")
        requested = _require_nonempty(raw, "area_code_requested")
        returned = _require_nonempty(raw, "area_code_returned")
        area_name = _require_nonempty(raw, "area_name")
        congestion = _require_nonempty(raw, "forecast_congestion_level")
        min_raw = _require_nonempty(raw, "forecast_population_min")
        max_raw = _require_nonempty(raw, "forecast_population_max")
    except ValueError as error:
        return _error(row, ERROR_MISSING_REQUIRED_VALUE, str(error))

    if requested != returned:
        return _error(
            row,
            ERROR_AREA_CODE_MISMATCH,
            f"area_code_requested={requested!r} != area_code_returned={returned!r}",
            requested=requested,
            returned=returned,
        )

    try:
        called_at = parse_kst_datetime(called_raw)
        observed_at = parse_kst_datetime(observed_raw)
        forecast_at = parse_kst_datetime(forecast_raw)
    except ValueError as error:
        return _error(row, ERROR_INVALID_DATETIME, str(error))

    if forecast_at <= observed_at:
        return _error(
            row,
            ERROR_FORECAST_NOT_AFTER_OBSERVED,
            f"forecast_at={forecast_at.isoformat()} <= observed_at={observed_at.isoformat()}",
        )

    try:
        population_min = parse_population_int(min_raw)
        population_max = parse_population_int(max_raw)
    except ValueError as error:
        return _error(row, ERROR_INVALID_NUMBER, str(error))

    if population_min < 0 or population_max < 0:
        return _error(
            row,
            ERROR_NEGATIVE_POPULATION,
            f"forecast_population_min={population_min} forecast_population_max={population_max}",
        )
    if population_min > population_max:
        return _error(
            row,
            ERROR_MIN_GREATER_THAN_MAX,
            f"forecast_population_min={population_min} > forecast_population_max={population_max}",
        )

    key = (run_id, requested)
    if key in raw_log_duplicate_keys:
        return _error(
            row,
            ERROR_RAW_LOG_KEY_DUPLICATE,
            f"raw_log_v3 has multiple rows for key {key}",
        )
    if key not in raw_log_status_by_key:
        return _error(
            row,
            ERROR_RAW_LOG_KEY_MISSING,
            f"raw_log_v3 has no row for key {key}",
        )

    return NormalizedForecastRecord(
        collection_run_id=run_id,
        called_at=to_iso8601(called_at),
        observed_at=to_iso8601(observed_at),
        forecast_at=to_iso8601(forecast_at),
        area_code=requested,
        area_code_requested=requested,
        area_code_returned=returned,
        area_name=area_name,
        forecast_congestion_level=congestion,
        forecast_population_min=population_min,
        forecast_population_max=population_max,
        forecast_population_mid=(population_min + population_max) / 2,
        source_status=raw_log_status_by_key[key],
        duplicate_flag=False,
    )


def _reconcile_source_keys(
    *,
    raw_log_keys: set[SourceKey],
    current_keys: set[SourceKey],
    forecast_keys: set[SourceKey],
) -> list[ErrorRow]:
    """Flag Source Correlation Keys not already fully explained by per-row
    checks.

    A Current/Forecast row whose own key is absent from raw_log_v3 is
    already isolated per-row as RAW_LOG_KEY_MISSING -- this pass does not
    repeat that. It covers the two directions per-row checks cannot see:
    a raw_log_v3 key with no Current/Forecast counterpart at all, and a
    Current key with no Forecast counterpart (or vice versa).
    """
    mismatches: list[ErrorRow] = []
    for key in sorted(raw_log_keys | current_keys | forecast_keys):
        in_raw = key in raw_log_keys
        in_current = key in current_keys
        in_forecast = key in forecast_keys
        if not in_raw and (in_current or in_forecast):
            continue  # already reported per-row as RAW_LOG_KEY_MISSING
        if in_raw and in_current and in_forecast:
            continue
        missing_from = [
            name
            for name, present in (
                ("raw_log_v3", in_raw),
                ("population_current_v3", in_current),
                ("population_forecast_v3", in_forecast),
            )
            if not present
        ]
        mismatches.append(
            ErrorRow(
                source_file="__source_correlation__",
                source_row_number=None,
                collection_run_id=key[0],
                area_code_requested=key[1],
                area_code_returned=None,
                error_code=ERROR_SOURCE_KEY_MISMATCH,
                error_message=f"key {key} missing from: {missing_from}",
                raw_row=None,
            )
        )
    return mismatches


def _flag_duplicate_current_records(
    records: Sequence[NormalizedCurrentRecord],
) -> tuple[NormalizedCurrentRecord, ...]:
    """Flag (never exclude) Current records whose semantic observation --
    (area_code, observed_at) -- already appeared earlier in `records`, in
    source row order. `collection_run_id` is deliberately excluded from the
    key: by the time a record reaches this function, its Source Correlation
    Key (which includes collection_run_id) is already guaranteed unique by
    normalize_v3_sources's structural CURRENT_KEY_DUPLICATE pre-pass. This
    is a separate, non-exclusionary signal for the same semantic
    observation recurring across different collection runs."""
    seen: set[ObservationKey] = set()
    flagged: list[NormalizedCurrentRecord] = []
    for record in records:
        key: ObservationKey = (record.area_code, record.observed_at)
        flagged.append(dataclasses.replace(record, duplicate_flag=key in seen))
        seen.add(key)
    return tuple(flagged)


def _flag_duplicate_forecast_records(
    records: Sequence[NormalizedForecastRecord],
) -> tuple[NormalizedForecastRecord, ...]:
    """Flag (never exclude) Forecast records whose semantic observation --
    (area_code, observed_at, forecast_at) -- already appeared earlier in
    `records`, in source row order. `observed_at` must be part of the key:
    different collection runs legitimately re-forecast the same
    `forecast_at` target on every 5-minute cycle, so a key of
    (area_code, forecast_at) alone would flag nearly every row as a
    duplicate in normal operation. `collection_run_id` is excluded for the
    same structural-uniqueness reason as the Current variant above."""
    seen: set[ForecastObservationKey] = set()
    flagged: list[NormalizedForecastRecord] = []
    for record in records:
        key: ForecastObservationKey = (
            record.area_code,
            record.observed_at,
            record.forecast_at,
        )
        flagged.append(dataclasses.replace(record, duplicate_flag=key in seen))
        seen.add(key)
    return tuple(flagged)


def normalize_v3_sources(
    *,
    raw_log_path: Path,
    current_path: Path,
    forecast_path: Path,
) -> NormalizationResult:
    """Read, validate, and normalize the three v3 source sheet CSV exports.

    Read-only: never writes to any of the three input paths. Does not
    write any output file -- use `export_dataset` for persistence.
    """
    raw_log_rows, error_rows = read_source_csv(
        raw_log_path, RAW_LOG_REQUIRED_COLUMNS, "raw_log_v3"
    )
    raw_log_input_row_count = len(raw_log_rows) + len(error_rows)
    current_rows, current_ragged_errors = read_source_csv(
        current_path, CURRENT_REQUIRED_COLUMNS, "population_current_v3"
    )
    current_input_row_count = len(current_rows) + len(current_ragged_errors)
    forecast_rows, forecast_ragged_errors = read_source_csv(
        forecast_path, FORECAST_REQUIRED_COLUMNS, "population_forecast_v3"
    )
    forecast_input_row_count = len(forecast_rows) + len(forecast_ragged_errors)
    error_rows.extend(current_ragged_errors)
    error_rows.extend(forecast_ragged_errors)

    raw_log_status_by_key, raw_log_duplicate_keys = _build_raw_log_index(raw_log_rows)
    current_duplicate_keys = _duplicate_keys_within(current_rows)
    forecast_target_duplicate_keys = _forecast_target_duplicate_keys(forecast_rows)

    current_records: list[NormalizedCurrentRecord] = []
    for row in current_rows:
        key = _row_key(row)
        if key is not None and key in current_duplicate_keys:
            error_rows.append(
                _error(
                    row,
                    ERROR_CURRENT_KEY_DUPLICATE,
                    f"population_current_v3 has multiple rows for key {key}",
                )
            )
            continue
        outcome = _normalize_current_row(
            row,
            raw_log_status_by_key=raw_log_status_by_key,
            raw_log_duplicate_keys=raw_log_duplicate_keys,
        )
        if isinstance(outcome, ErrorRow):
            error_rows.append(outcome)
        else:
            current_records.append(outcome)

    forecast_records: list[NormalizedForecastRecord] = []
    for row in forecast_rows:
        key = _row_key(row)
        forecast_raw = row.raw_row.get("forecast_at", "").strip()
        target_key: ForecastTargetKey | None = None
        if key is not None and forecast_raw:
            try:
                target_key = (key[0], key[1], parse_kst_datetime(forecast_raw))
            except ValueError:
                target_key = None
        if target_key is not None and target_key in forecast_target_duplicate_keys:
            error_rows.append(
                _error(
                    row,
                    ERROR_FORECAST_TARGET_DUPLICATE,
                    f"population_forecast_v3 has multiple rows for target {target_key}",
                )
            )
            continue
        outcome = _normalize_forecast_row(
            row,
            raw_log_status_by_key=raw_log_status_by_key,
            raw_log_duplicate_keys=raw_log_duplicate_keys,
        )
        if isinstance(outcome, ErrorRow):
            error_rows.append(outcome)
        else:
            forecast_records.append(outcome)

    error_rows.extend(
        _reconcile_source_keys(
            raw_log_keys=set(raw_log_status_by_key) | raw_log_duplicate_keys,
            current_keys=_seen_keys(current_rows),
            forecast_keys=_seen_keys(forecast_rows),
        )
    )

    return NormalizationResult(
        current_records=_flag_duplicate_current_records(current_records),
        forecast_records=_flag_duplicate_forecast_records(forecast_records),
        error_rows=tuple(error_rows),
        raw_log_input_row_count=raw_log_input_row_count,
        current_input_row_count=current_input_row_count,
        forecast_input_row_count=forecast_input_row_count,
    )


# ---------------------------------------------------------------------------
# Quality Report (ML_READY_DATASET_SPEC.md §10/§13)
# ---------------------------------------------------------------------------


def _tally_error_codes(error_rows: Sequence[ErrorRow]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for error in error_rows:
        counts[error.error_code] = counts.get(error.error_code, 0) + 1
    return counts


def _error_count(
    error_rows: Sequence[ErrorRow], *, source_file: str, error_code: str
) -> int:
    return sum(
        1
        for error in error_rows
        if error.source_file == source_file and error.error_code == error_code
    )


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _mean_min_max(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "min": None, "max": None}
    return {"mean": sum(values) / len(values), "min": min(values), "max": max(values)}


def _collection_lag_seconds(
    records: Sequence[NormalizedCurrentRecord | NormalizedForecastRecord],
) -> list[float]:
    return [
        (
            datetime.fromisoformat(record.called_at)
            - datetime.fromisoformat(record.observed_at)
        ).total_seconds()
        for record in records
    ]


def build_quality_report(
    result: NormalizationResult,
    *,
    dataset_id: str,
    generated_at: datetime,
) -> dict[str, object]:
    """Build the EG-8A Quality Report.

    Reports §10's quality metrics split into §13's "반드시 산출"/"권장"
    groups. Contains no pass/fail threshold logic -- §13 leaves thresholds
    as `OPEN_DECISION`. "시간대별 데이터 커버리지" is not produced: no
    bucketing scheme (hourly? per collection slot?) is defined anywhere in
    the spec.
    """
    error_code_tally = _tally_error_codes(result.error_rows)
    official_area_codes = list(eg6b.EG6B_AREA_CODES)
    official_area_set = set(official_area_codes)
    current_area_codes = {record.area_code for record in result.current_records}
    forecast_area_codes = {record.area_code for record in result.forecast_records}

    per_area = [
        {
            "area_code": area_code,
            "current_row_count": sum(
                1 for record in result.current_records if record.area_code == area_code
            ),
            "forecast_row_count": sum(
                1 for record in result.forecast_records if record.area_code == area_code
            ),
        }
        for area_code in official_area_codes
    ]

    current_duplicate_flagged = sum(
        1 for record in result.current_records if record.duplicate_flag
    )
    forecast_duplicate_flagged = sum(
        1 for record in result.forecast_records if record.duplicate_flag
    )

    current_observed_values = [record.observed_at for record in result.current_records]
    forecast_observed_values = [record.observed_at for record in result.forecast_records]
    forecast_at_values = [record.forecast_at for record in result.forecast_records]

    return {
        "schema_version": QUALITY_REPORT_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "generated_at": to_iso8601(generated_at),
        "must_produce": {
            "row_counts": {
                "raw_log_v3_input_rows": result.raw_log_input_row_count,
                "population_current_v3_input_rows": result.current_input_row_count,
                "population_forecast_v3_input_rows": result.forecast_input_row_count,
                "current_normal_rows": len(result.current_records),
                "forecast_normal_rows": len(result.forecast_records),
                "error_rows_total": len(result.error_rows),
                "error_rows_by_code": error_code_tally,
            },
            "required_columns_present": True,
            "area_row_counts": {
                "official_area_codes": official_area_codes,
                "per_area": per_area,
                "unexpected_area_codes": sorted(
                    (current_area_codes | forecast_area_codes) - official_area_set
                ),
                "areas_with_zero_current_rows": sorted(official_area_set - current_area_codes),
                "areas_with_zero_forecast_rows": sorted(official_area_set - forecast_area_codes),
            },
            "area_code_consistency": {
                "official_area_count": len(official_area_codes),
                "current_area_codes_all_official": current_area_codes.issubset(
                    official_area_set
                ),
                "forecast_area_codes_all_official": forecast_area_codes.issubset(
                    official_area_set
                ),
            },
            "time_parse_success_rate": {
                "current": _rate(
                    result.current_input_row_count
                    - _error_count(
                        result.error_rows,
                        source_file="population_current_v3",
                        error_code=ERROR_INVALID_DATETIME,
                    ),
                    result.current_input_row_count,
                ),
                "forecast": _rate(
                    result.forecast_input_row_count
                    - _error_count(
                        result.error_rows,
                        source_file="population_forecast_v3",
                        error_code=ERROR_INVALID_DATETIME,
                    ),
                    result.forecast_input_row_count,
                ),
            },
            "numeric_conversion_success_rate": {
                "current": _rate(
                    result.current_input_row_count
                    - _error_count(
                        result.error_rows,
                        source_file="population_current_v3",
                        error_code=ERROR_INVALID_NUMBER,
                    ),
                    result.current_input_row_count,
                ),
                "forecast": _rate(
                    result.forecast_input_row_count
                    - _error_count(
                        result.error_rows,
                        source_file="population_forecast_v3",
                        error_code=ERROR_INVALID_NUMBER,
                    ),
                    result.forecast_input_row_count,
                ),
            },
            "missing_value_rate": {
                "current": _rate(
                    _error_count(
                        result.error_rows,
                        source_file="population_current_v3",
                        error_code=ERROR_MISSING_REQUIRED_VALUE,
                    ),
                    result.current_input_row_count,
                ),
                "forecast": _rate(
                    _error_count(
                        result.error_rows,
                        source_file="population_forecast_v3",
                        error_code=ERROR_MISSING_REQUIRED_VALUE,
                    ),
                    result.forecast_input_row_count,
                ),
            },
        },
        "recommended": {
            "current_duplicate": {
                "structural_duplicate_rows_excluded": error_code_tally.get(
                    ERROR_CURRENT_KEY_DUPLICATE, 0
                ),
                "semantic_duplicate_rows_flagged": current_duplicate_flagged,
                "semantic_duplicate_rate": _rate(
                    current_duplicate_flagged, len(result.current_records)
                ),
            },
            "forecast_target_duplicate": {
                "structural_duplicate_rows_excluded": error_code_tally.get(
                    ERROR_FORECAST_TARGET_DUPLICATE, 0
                ),
                "semantic_duplicate_rows_flagged": forecast_duplicate_flagged,
                "semantic_duplicate_rate": _rate(
                    forecast_duplicate_flagged, len(result.forecast_records)
                ),
            },
            "collection_lag_seconds": {
                "current": _mean_min_max(_collection_lag_seconds(result.current_records)),
                "forecast": _mean_min_max(_collection_lag_seconds(result.forecast_records)),
            },
            "area_code_match_rate": {
                "current": _rate(
                    result.current_input_row_count
                    - _error_count(
                        result.error_rows,
                        source_file="population_current_v3",
                        error_code=ERROR_AREA_CODE_MISMATCH,
                    ),
                    result.current_input_row_count,
                ),
                "forecast": _rate(
                    result.forecast_input_row_count
                    - _error_count(
                        result.error_rows,
                        source_file="population_forecast_v3",
                        error_code=ERROR_AREA_CODE_MISMATCH,
                    ),
                    result.forecast_input_row_count,
                ),
            },
            "data_date_range": {
                "current_observed_at_min": min(current_observed_values, default=None),
                "current_observed_at_max": max(current_observed_values, default=None),
                "forecast_observed_at_min": min(forecast_observed_values, default=None),
                "forecast_observed_at_max": max(forecast_observed_values, default=None),
                "forecast_at_min": min(forecast_at_values, default=None),
                "forecast_at_max": max(forecast_at_values, default=None),
            },
        },
    }


# ---------------------------------------------------------------------------
# Dataset Manifest (ML_READY_DATASET_SPEC.md §12.1)
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_dataset_manifest(
    *,
    dataset_id: str,
    generated_at: datetime,
    result: NormalizationResult,
    input_artifacts: Sequence[Mapping[str, object]],
    output_artifacts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build the EG-8A Dataset Manifest.

    `input_artifacts` entries carry no path (only logical_name/sha256/
    byte_size) -- input CSVs live outside the repository at an arbitrary
    Export location, and recording their path would leak local filesystem
    details (AGENTS.md §12/§18 "절대경로를 기록·출력하지 않는다"). Output
    artifact paths are relative to this run's own output directory, which
    is safe to record.
    """
    return {
        "schema_version": DATASET_MANIFEST_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "dataset_version": dataset_id,
        "loader_version": LOADER_VERSION,
        "generated_at": to_iso8601(generated_at),
        "hash_algorithm": "sha256",
        "source_row_counts": {
            "raw_log_v3_input_rows": result.raw_log_input_row_count,
            "population_current_v3_input_rows": result.current_input_row_count,
            "population_forecast_v3_input_rows": result.forecast_input_row_count,
            "current_normal_rows": len(result.current_records),
            "forecast_normal_rows": len(result.forecast_records),
            "error_rows_total": len(result.error_rows),
        },
        "input_artifacts": [dict(artifact) for artifact in input_artifacts],
        "output_artifacts": [dict(artifact) for artifact in output_artifacts],
    }


# ---------------------------------------------------------------------------
# Output Writer (ML_READY_DATASET_SPEC.md §12.1) -- exclusive create, never
# overwrites an existing file or dataset directory.
# ---------------------------------------------------------------------------


class DatasetWriteError(OSError):
    """Raised when a Loader output file or directory cannot be written safely."""


class OutputRootConfigurationError(DatasetWriteError):
    """Raised when FRESHMANAGER_EG8A_OUTPUT_ROOT is unset or invalid."""


def resolve_output_root_from_env(environ: Mapping[str, str]) -> Path:
    """Resolve the external Loader output-root from the environment.

    Never defaults to a path inside the repository; fails closed with a
    non-sensitive error if the variable is unset or does not name an
    existing directory. Never returns the value in an error message.
    """
    value = environ.get(FRESHMANAGER_EG8A_OUTPUT_ROOT_ENV)
    if not value:
        raise OutputRootConfigurationError(
            f"dataset_write_error: {FRESHMANAGER_EG8A_OUTPUT_ROOT_ENV} is not set"
        )
    try:
        resolved = Path(value).expanduser().resolve(strict=True)
    except OSError as error:
        raise OutputRootConfigurationError(
            f"dataset_write_error: {FRESHMANAGER_EG8A_OUTPUT_ROOT_ENV} does not exist"
        ) from error
    if not resolved.is_dir():
        raise OutputRootConfigurationError(
            f"dataset_write_error: {FRESHMANAGER_EG8A_OUTPUT_ROOT_ENV} is not a directory"
        )
    return resolved


def _write_exclusive(path: Path, payload: bytes) -> None:
    """Write `payload` to `path`; raise DatasetWriteError instead of ever
    overwriting an existing file (mkstemp + fsync + os.link, mirroring
    storage.py's FileStorage._write_exclusive algorithm)."""
    partial_path: Path | None = None
    try:
        descriptor, partial_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".partial", dir=path.parent
        )
        partial_path = Path(partial_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(partial_path, path)
    except FileExistsError as error:
        raise DatasetWriteError(
            f"dataset_write_error: {path.name} already exists"
        ) from error
    except OSError as error:
        raise DatasetWriteError(
            f"dataset_write_error: failed to write {path.name}"
        ) from error
    finally:
        if partial_path is not None:
            try:
                partial_path.unlink()
            except OSError:
                pass


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


CURRENT_CSV_FIELDNAMES = (
    "collection_run_id",
    "called_at",
    "observed_at",
    "area_code",
    "area_code_requested",
    "area_code_returned",
    "area_name",
    "congestion_level",
    "population_min",
    "population_max",
    "population_mid",
    "source_status",
    "duplicate_flag",
)
FORECAST_CSV_FIELDNAMES = (
    "collection_run_id",
    "called_at",
    "observed_at",
    "forecast_at",
    "area_code",
    "area_code_requested",
    "area_code_returned",
    "area_name",
    "forecast_congestion_level",
    "forecast_population_min",
    "forecast_population_max",
    "forecast_population_mid",
    "source_status",
    "duplicate_flag",
)
ERROR_ROWS_CSV_FIELDNAMES = (
    "source_file",
    "source_row_number",
    "collection_run_id",
    "area_code_requested",
    "area_code_returned",
    "error_code",
    "error_message",
    "raw_row_json",
)


def _write_csv_rows(fieldnames: Sequence[str], rows: Sequence[Mapping[str, object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(fieldnames))
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def write_current_csv(records: Sequence[NormalizedCurrentRecord]) -> bytes:
    rows = []
    for record in records:
        row = dataclasses.asdict(record)
        row["duplicate_flag"] = _bool_str(record.duplicate_flag)
        rows.append(row)
    return _write_csv_rows(CURRENT_CSV_FIELDNAMES, rows)


def write_forecast_csv(records: Sequence[NormalizedForecastRecord]) -> bytes:
    rows = []
    for record in records:
        row = dataclasses.asdict(record)
        row["duplicate_flag"] = _bool_str(record.duplicate_flag)
        rows.append(row)
    return _write_csv_rows(FORECAST_CSV_FIELDNAMES, rows)


def write_error_rows_csv(errors: Sequence[ErrorRow]) -> bytes:
    rows = [
        {
            "source_file": error.source_file,
            "source_row_number": error.source_row_number,
            "collection_run_id": error.collection_run_id,
            "area_code_requested": error.area_code_requested,
            "area_code_returned": error.area_code_returned,
            "error_code": error.error_code,
            "error_message": error.error_message,
            "raw_row_json": (
                json.dumps(dict(error.raw_row), ensure_ascii=False, sort_keys=True)
                if error.raw_row is not None
                else ""
            ),
        }
        for error in errors
    ]
    return _write_csv_rows(ERROR_ROWS_CSV_FIELDNAMES, rows)


def write_json_document(document: Mapping[str, object]) -> bytes:
    return (json.dumps(dict(document), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


@dataclass(frozen=True)
class DatasetExportResult:
    dataset_id: str
    dataset_dir: Path
    quality_report: Mapping[str, object]
    manifest: Mapping[str, object]


_INPUT_LOGICAL_NAMES = ("raw_log_v3", "population_current_v3", "population_forecast_v3")


def export_dataset(
    result: NormalizationResult,
    *,
    output_root: Path,
    input_paths: Mapping[str, Path],
    dataset_id: str | None = None,
    generated_at: datetime | None = None,
) -> DatasetExportResult:
    """Write the five V0 output artifacts for one Loader run.

    `output_root` must already exist (never auto-created -- use
    `resolve_output_root_from_env` to validate it first). Each run gets its
    own `<output_root>/<dataset_id>/` directory, created exclusively: a
    colliding `dataset_id` raises before any file is touched. Each of the
    five files is itself written with exclusive-create semantics (never
    overwrites), so a partial or completed prior run can never be silently
    replaced.

    `input_paths` must have exactly the keys "raw_log_v3",
    "population_current_v3", "population_forecast_v3", each mapping to the
    Path of the source CSV Export that was passed to `normalize_v3_sources`
    to build `result`.
    """
    if set(input_paths) != set(_INPUT_LOGICAL_NAMES):
        raise DatasetWriteError(
            f"dataset_write_error: input_paths must have exactly {sorted(_INPUT_LOGICAL_NAMES)}"
        )

    resolved_root = output_root.expanduser().resolve(strict=True)
    if not resolved_root.is_dir():
        raise DatasetWriteError("dataset_write_error: output root is not a directory")

    resolved_dataset_id = dataset_id if dataset_id is not None else str(uuid.uuid4())
    if not resolved_dataset_id or Path(resolved_dataset_id).name != resolved_dataset_id:
        raise DatasetWriteError("dataset_write_error: dataset_id must be a single path segment")
    resolved_generated_at = (
        generated_at if generated_at is not None else datetime.now(SEOUL)
    )

    dataset_dir = resolved_root / resolved_dataset_id
    try:
        dataset_dir.mkdir(exist_ok=False)
    except FileExistsError as error:
        raise DatasetWriteError(
            f"dataset_write_error: dataset directory already exists for {resolved_dataset_id}"
        ) from error

    current_payload = write_current_csv(result.current_records)
    forecast_payload = write_forecast_csv(result.forecast_records)
    error_rows_payload = write_error_rows_csv(result.error_rows)
    _write_exclusive(dataset_dir / CURRENT_OUTPUT_FILENAME, current_payload)
    _write_exclusive(dataset_dir / FORECAST_OUTPUT_FILENAME, forecast_payload)
    _write_exclusive(dataset_dir / ERROR_ROWS_OUTPUT_FILENAME, error_rows_payload)

    input_artifacts = [
        {
            "logical_name": logical_name,
            "sha256": _sha256_file(input_paths[logical_name]),
            "byte_size": input_paths[logical_name].stat().st_size,
        }
        for logical_name in _INPUT_LOGICAL_NAMES
    ]
    output_artifacts = [
        {
            "relative_path": CURRENT_OUTPUT_FILENAME,
            "sha256": _sha256_bytes(current_payload),
            "byte_size": len(current_payload),
        },
        {
            "relative_path": FORECAST_OUTPUT_FILENAME,
            "sha256": _sha256_bytes(forecast_payload),
            "byte_size": len(forecast_payload),
        },
        {
            "relative_path": ERROR_ROWS_OUTPUT_FILENAME,
            "sha256": _sha256_bytes(error_rows_payload),
            "byte_size": len(error_rows_payload),
        },
    ]

    quality_report = build_quality_report(
        result, dataset_id=resolved_dataset_id, generated_at=resolved_generated_at
    )
    quality_report_payload = write_json_document(quality_report)
    _write_exclusive(dataset_dir / QUALITY_REPORT_OUTPUT_FILENAME, quality_report_payload)
    output_artifacts.append(
        {
            "relative_path": QUALITY_REPORT_OUTPUT_FILENAME,
            "sha256": _sha256_bytes(quality_report_payload),
            "byte_size": len(quality_report_payload),
        }
    )

    manifest = build_dataset_manifest(
        dataset_id=resolved_dataset_id,
        generated_at=resolved_generated_at,
        result=result,
        input_artifacts=input_artifacts,
        output_artifacts=output_artifacts,
    )
    manifest_payload = write_json_document(manifest)
    _write_exclusive(dataset_dir / DATASET_MANIFEST_OUTPUT_FILENAME, manifest_payload)

    return DatasetExportResult(
        dataset_id=resolved_dataset_id,
        dataset_dir=dataset_dir,
        quality_report=quality_report,
        manifest=manifest,
    )
