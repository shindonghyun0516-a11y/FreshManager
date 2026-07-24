"""EG-8A CSV Source Reader, Schema Validation, and Normalization.

Reads the three v3 source sheet CSV exports (Apps Script Runtime output,
manually exported per `docs/data/ML_READY_DATASET_SPEC.md` §3.1) read-only
and produces Normalized Current/Forecast records plus isolated Error Rows.

Quality Report, Dataset Manifest, the final exclusive Output Writer, and
`duplicate_flag` (a downstream data-quality signal over otherwise-valid
rows) are EG-8A Issue B's responsibility and are not implemented here.
This module instead enforces Source Correlation Key *structural* identity:
a Current row and a Forecast target are each expected to be unique per
key, and a Raw Log match is expected to be unique and present -- any
violation is a Schema/Integrity error, isolated in full, never partially
joined or arbitrarily picked.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")

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


@dataclass(frozen=True)
class NormalizationResult:
    current_records: tuple[NormalizedCurrentRecord, ...]
    forecast_records: tuple[NormalizedForecastRecord, ...]
    error_rows: tuple[ErrorRow, ...]


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


def normalize_v3_sources(
    *,
    raw_log_path: Path,
    current_path: Path,
    forecast_path: Path,
) -> NormalizationResult:
    """Read, validate, and normalize the three v3 source sheet CSV exports.

    Read-only: never writes to any of the three input paths. Does not
    write any output file -- callers own persistence (EG-8A Issue B).
    """
    raw_log_rows, error_rows = read_source_csv(
        raw_log_path, RAW_LOG_REQUIRED_COLUMNS, "raw_log_v3"
    )
    current_rows, current_ragged_errors = read_source_csv(
        current_path, CURRENT_REQUIRED_COLUMNS, "population_current_v3"
    )
    forecast_rows, forecast_ragged_errors = read_source_csv(
        forecast_path, FORECAST_REQUIRED_COLUMNS, "population_forecast_v3"
    )
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
        current_records=tuple(current_records),
        forecast_records=tuple(forecast_records),
        error_rows=tuple(error_rows),
    )
