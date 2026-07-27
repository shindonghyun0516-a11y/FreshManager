"""EG-8D provisional Area expected-population-change ranking from Seoul Forecast."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import shutil
import stat
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping, Sequence

from . import eg6b, eg8a, eg8c_features


LOCKED_DATASET_RUN_ID = "eg8c-20260727T153257-kst"
LOCKED_MANIFEST_SHA256 = "388a5e6649e6e23d05a442ae9b4f8d0857f8ea382011c2ff07c0af64aae42771"
LOCKED_CURRENT_SHA256 = "28521ff8b52ff1697fcf8eb93da4a5faaf2f625a69fdf117e601f8893d84d719"
LOCKED_FORECAST_SHA256 = "a5c4aaa7d711d289ee05d4ed6903b91f4ea725252ff3b6bc8890b62146441649"

HORIZONS = (60, 180)
FORECAST_SOURCE = "SEOUL_FORECAST"
EVALUATION_STATUS = "PROVISIONAL"
TARGET_LEVEL = "AREA"
OUTPUT_FILES = {
    "area_priority.csv",
    "area_priority.json",
    "run_metadata.json",
    "area_priority_manifest.json",
}
CONTENT_FILES = OUTPUT_FILES - {"area_priority_manifest.json"}
_RUN_ID_PATTERN = re.compile(r"eg8d-area-priority-\d{8}T\d{6}-kst\Z")

CURRENT_REQUIRED_COLUMNS = {
    "collection_run_id",
    "observed_at",
    "area_code_requested",
    "area_code_returned",
    "area_name",
    "population_min",
    "population_max",
}
FORECAST_REQUIRED_COLUMNS = {
    "collection_run_id",
    "observed_at",
    "forecast_at",
    "area_code_requested",
    "area_code_returned",
    "area_name",
    "forecast_population_min",
    "forecast_population_max",
}
CSV_FIELDS = (
    "generated_at",
    "source_collection_run_id",
    "area_code",
    "area_name",
    "prediction_origin_at",
    "prediction_target_at",
    "horizon_minutes",
    "current_population_midpoint",
    "forecast_population_midpoint",
    "expected_population_change",
    "expected_population_change_rate",
    "opportunity_rank",
    "future_population_rank",
    "rank_difference",
    "change_status",
    "reason_code",
    "input_validity",
    "forecast_source",
    "evaluation_status",
    "target_level",
)


class AreaPriorityContractError(ValueError):
    """Raised when locked inputs or the exact Forecast join contract fail."""


class AreaPriorityWriteError(OSError):
    """Raised when an isolated result run cannot be published safely."""


@dataclass(frozen=True)
class AreaPriorityRow:
    generated_at: str
    source_collection_run_id: str
    area_code: str
    area_name: str
    prediction_origin_at: str
    prediction_target_at: str
    horizon_minutes: int
    current_population_midpoint: float
    forecast_population_midpoint: float
    expected_population_change: float
    expected_population_change_rate: float | None
    opportunity_rank: int
    future_population_rank: int
    rank_difference: int
    change_status: str
    reason_code: str
    input_validity: str
    forecast_source: str = FORECAST_SOURCE
    evaluation_status: str = EVALUATION_STATUS
    target_level: str = TARGET_LEVEL

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AreaPriorityResult:
    run_id: str
    run_dir: Path
    rows: tuple[AreaPriorityRow, ...]
    metadata: Mapping[str, object]
    manifest: Mapping[str, object]


@dataclass(frozen=True)
class _Current:
    area_code: str
    area_name: str
    origin: datetime
    midpoint: float


@dataclass(frozen=True)
class _Forecast:
    area_code: str
    area_name: str
    origin: datetime
    target: datetime
    midpoint: float


def _fail(code: str) -> None:
    raise AreaPriorityContractError(f"eg8d_area_priority_contract_error: {code}")


def _required(row: Mapping[str, str], name: str) -> str:
    value = row.get(name, "").strip()
    if not value:
        _fail("required_value_missing")
    return value


def _midpoint(row: Mapping[str, str], lower_name: str, upper_name: str) -> float:
    try:
        lower = float(_required(row, lower_name))
        upper = float(_required(row, upper_name))
    except ValueError:
        _fail("population_invalid")
    if not all(math.isfinite(value) for value in (lower, upper)) or lower < 0 or lower > upper:
        _fail("population_invalid")
    return (lower + upper) / 2


def _time(value: str) -> datetime:
    try:
        return eg8a.parse_kst_datetime(value)
    except ValueError:
        _fail("time_invalid")


def _change_state(change: float) -> tuple[str, str]:
    if change > 0:
        return "INCREASE", "EXPECTED_POPULATION_INCREASE"
    if change < 0:
        return "DECREASE", "EXPECTED_POPULATION_DECREASE"
    return "STABLE", "NO_EXPECTED_POPULATION_CHANGE"


def build_area_priority_rows(
    current_rows: Sequence[Mapping[str, str]],
    forecast_rows: Sequence[Mapping[str, str]],
    *,
    source_collection_run_id: str,
    generated_at: datetime,
) -> tuple[AreaPriorityRow, ...]:
    """Build deterministic 60/180-minute rankings for one explicit source run."""
    if not source_collection_run_id:
        _fail("source_collection_run_id_missing")
    if generated_at.tzinfo is None:
        _fail("generated_at_naive")
    approved = set(eg6b.EG6B_AREA_CODES)
    current_by_area: dict[str, _Current] = {}
    for row in current_rows:
        if row.get("collection_run_id", "").strip() != source_collection_run_id:
            continue
        requested = _required(row, "area_code_requested")
        returned = _required(row, "area_code_returned")
        if requested not in approved:
            continue
        if requested != returned:
            _fail("current_area_mismatch")
        if requested in current_by_area:
            _fail("current_duplicate")
        current_by_area[requested] = _Current(
            area_code=requested,
            area_name=_required(row, "area_name"),
            origin=_time(_required(row, "observed_at")),
            midpoint=_midpoint(row, "population_min", "population_max"),
        )
    if set(current_by_area) != approved:
        _fail("current_area_set_mismatch")

    forecast_index: dict[tuple[str, str, str, str], _Forecast] = {}
    for row in forecast_rows:
        run_id = row.get("collection_run_id", "").strip()
        if run_id != source_collection_run_id:
            continue
        requested = _required(row, "area_code_requested")
        returned = _required(row, "area_code_returned")
        if requested not in approved:
            continue
        if requested != returned:
            _fail("forecast_area_mismatch")
        origin = _time(_required(row, "observed_at"))
        target = _time(_required(row, "forecast_at"))
        key = (
            run_id,
            requested,
            eg8a.to_iso8601(origin),
            eg8a.to_iso8601(target),
        )
        if key in forecast_index:
            _fail("forecast_duplicate")
        forecast_index[key] = _Forecast(
            area_code=requested,
            area_name=_required(row, "area_name"),
            origin=origin,
            target=target,
            midpoint=_midpoint(row, "forecast_population_min", "forecast_population_max"),
        )

    drafts: list[dict[str, object]] = []
    for area_code in eg6b.EG6B_AREA_CODES:
        current = current_by_area[area_code]
        for horizon in HORIZONS:
            target = current.origin + timedelta(minutes=horizon)
            key = (
                source_collection_run_id,
                area_code,
                eg8a.to_iso8601(current.origin),
                eg8a.to_iso8601(target),
            )
            forecast = forecast_index.get(key)
            if forecast is None:
                _fail("forecast_missing")
            if forecast.area_name != current.area_name:
                _fail("area_name_mismatch")
            change = forecast.midpoint - current.midpoint
            rate = change / current.midpoint if current.midpoint != 0 else None
            status, reason = _change_state(change)
            drafts.append(
                {
                    "generated_at": eg8a.to_iso8601(generated_at),
                    "source_collection_run_id": source_collection_run_id,
                    "area_code": area_code,
                    "area_name": current.area_name,
                    "prediction_origin_at": eg8a.to_iso8601(current.origin),
                    "prediction_target_at": eg8a.to_iso8601(forecast.target),
                    "horizon_minutes": horizon,
                    "current_population_midpoint": current.midpoint,
                    "forecast_population_midpoint": forecast.midpoint,
                    "expected_population_change": change,
                    "expected_population_change_rate": rate,
                    "change_status": status,
                    "reason_code": reason,
                    "input_validity": (
                        "VALID" if rate is not None else "CHANGE_RATE_UNCOMPUTABLE_CURRENT_ZERO"
                    ),
                }
            )

    results: list[AreaPriorityRow] = []
    for horizon in HORIZONS:
        horizon_rows = [row for row in drafts if row["horizon_minutes"] == horizon]
        opportunity_order = sorted(
            horizon_rows,
            key=lambda row: (
                0 if float(row["expected_population_change"]) > 0 else 1,
                -float(row["expected_population_change"]),
                -float(row["forecast_population_midpoint"]),
                str(row["area_code"]),
            ),
        )
        future_order = sorted(
            horizon_rows,
            key=lambda row: (-float(row["forecast_population_midpoint"]), str(row["area_code"])),
        )
        opportunity_rank = {str(row["area_code"]): rank for rank, row in enumerate(opportunity_order, 1)}
        future_rank = {str(row["area_code"]): rank for rank, row in enumerate(future_order, 1)}
        for row in opportunity_order:
            area_code = str(row["area_code"])
            results.append(
                AreaPriorityRow(
                    **row,
                    opportunity_rank=opportunity_rank[area_code],
                    future_population_rank=future_rank[area_code],
                    rank_difference=opportunity_rank[area_code] - future_rank[area_code],
                )
            )
    return tuple(results)


def _snapshot(path: Path, label: str, expected_sha256: str) -> tuple[bytes, dict[str, object]]:
    try:
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            _fail(f"{label}_type_invalid")
        payload = path.read_bytes()
        after = path.lstat()
    except OSError:
        _fail(f"{label}_unreadable")
    if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
        _fail(f"{label}_changed_during_read")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        _fail(f"{label}_sha_mismatch")
    return payload, {"sha256": digest, "byte_size": len(payload)}


def _csv_from_snapshot(
    payload: bytes,
    required_columns: set[str],
    label: str,
) -> list[dict[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
            _fail(f"{label}_header_invalid")
        rows = list(reader)
    except (UnicodeError, csv.Error):
        _fail(f"{label}_unreadable")
    if any(None in row for row in rows):
        _fail(f"{label}_row_invalid")
    return rows


def _validate_manifest(payload: bytes) -> None:
    try:
        manifest = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError):
        _fail("manifest_json_invalid")
    if not isinstance(manifest, dict) or manifest.get("eg8c_run_id") != LOCKED_DATASET_RUN_ID:
        _fail("manifest_contract_invalid")
    artifacts = manifest.get("input_artifacts")
    if not isinstance(artifacts, list):
        _fail("manifest_contract_invalid")
    by_name = {
        item.get("logical_name"): item
        for item in artifacts
        if isinstance(item, dict) and isinstance(item.get("logical_name"), str)
    }
    expected = {
        "population_current_v3": LOCKED_CURRENT_SHA256,
        "population_forecast_v3": LOCKED_FORECAST_SHA256,
    }
    if any(by_name.get(name, {}).get("sha256") != digest for name, digest in expected.items()):
        _fail("manifest_input_sha_mismatch")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _csv_bytes(rows: Sequence[AreaPriorityRow]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(row.as_dict() for row in rows)
    return stream.getvalue().encode()


def _metadata(
    *,
    run_id: str,
    source_collection_run_id: str,
    generated_at: datetime,
    rows: tuple[AreaPriorityRow, ...],
    inputs: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    summary: dict[str, object] = {}
    change_summary: dict[str, object] = {}
    for horizon in HORIZONS:
        ranked = [row for row in rows if row.horizon_minutes == horizon]
        positive_count = sum(row.expected_population_change > 0 for row in ranked)
        zero_count = sum(row.expected_population_change == 0 for row in ranked)
        summary[str(horizon)] = {
            "top": {
                "area_code": ranked[0].area_code,
                "area_name": ranked[0].area_name,
                "expected_population_change": ranked[0].expected_population_change,
                "reason_code": ranked[0].reason_code,
            },
            "bottom": {
                "area_code": ranked[-1].area_code,
                "area_name": ranked[-1].area_name,
                "expected_population_change": ranked[-1].expected_population_change,
                "reason_code": ranked[-1].reason_code,
            },
        }
        change_summary[str(horizon)] = {
            "positive_increase_area_count": positive_count,
            "zero_change_area_count": zero_count,
            "decrease_area_count": len(ranked) - positive_count - zero_count,
            "has_positive_increase_candidate": positive_count > 0,
        }
    return {
        "schema_version": "eg8d-area-priority-metadata-v1",
        "area_priority_run_id": run_id,
        "generated_at": eg8a.to_iso8601(generated_at),
        "source_dataset_run_id": LOCKED_DATASET_RUN_ID,
        "source_collection_run_id": source_collection_run_id,
        "input_artifacts": [
            {"logical_name": name, **dict(inputs[name])} for name in sorted(inputs)
        ],
        "horizon_area_counts": {
            str(horizon): sum(row.horizon_minutes == horizon for row in rows)
            for horizon in HORIZONS
        },
        "excluded_areas": [],
        "horizon_change_summary": change_summary,
        "top_bottom_summary": summary,
        "ranking_rules": {
            "opportunity": [
                "positive_change_first",
                "expected_population_change_desc",
                "forecast_population_midpoint_desc",
                "area_code_asc",
            ],
            "future_population": ["forecast_population_midpoint_desc", "area_code_asc"],
            "horizons_combined": False,
            "weighted_score_used": False,
        },
        "forecast_source": FORECAST_SOURCE,
        "evaluation_status": EVALUATION_STATUS,
        "official_model_gate_judgment": None,
        "target_level": TARGET_LEVEL,
        "recommendation_contract_status": "INTERNAL_AREA_RANKING_NOT_OFFICIAL_RECOMMENDATION_OUTPUT",
        "limitations": [
            "서울시 Forecast 기반 예상 유동인구 변화의 표시·우선 검토 순서이며 실제 방문이나 판매 성공을 보장하지 않는다.",
            "변화 0은 현재·미래 인구 범위 중간값 차이가 0이라는 뜻이며 실제 변화 부재나 예측 범위 불확실성 제거를 의미하지 않는다.",
            "한 수집 회차 Snapshot의 잠정 결과로 장기 반복성이나 사용자 가치를 검증하지 않는다.",
            "60분과 180분 순위는 서로 독립적이며 가중치 종합점수를 사용하지 않는다.",
            "Spot·이동시간·담당구역·현장검증 정보는 포함하지 않는다.",
        ],
    }


def _write_exclusive(path: Path, payload: bytes) -> None:
    try:
        with path.open("xb") as handle:
            handle.write(payload)
            handle.flush()
    except OSError:
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: artifact_write_failed") from None


def _sha256(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    except AttributeError:  # Python 3.9 local compatibility; CI/runtime uses 3.12.
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            _fail("source_recheck_failed")
    except OSError:
        _fail("source_recheck_failed")


def _publish(
    *,
    output_root: Path,
    run_id: str,
    payloads: Mapping[str, bytes],
    input_paths: Sequence[Path],
    input_hashes: Mapping[Path, str],
) -> tuple[Path, dict[str, object]]:
    if not _RUN_ID_PATTERN.fullmatch(run_id):
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: run_id_invalid")
    if set(payloads) != CONTENT_FILES:
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: artifact_set_invalid")
    try:
        mode = output_root.lstat().st_mode
        resolved_root = output_root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: output_root_invalid") from None
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: output_root_invalid")
    if any((parent / ".git").exists() for parent in (resolved_root, *resolved_root.parents)):
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: git_output_forbidden")
    for source in input_paths:
        try:
            source.resolve(strict=True).relative_to(resolved_root)
        except ValueError:
            pass
        except OSError:
            _fail("source_recheck_failed")
        else:
            raise AreaPriorityWriteError("eg8d_area_priority_write_error: input_output_overlap")
    final_run = resolved_root / run_id
    if final_run.exists() or final_run.is_symlink():
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: run_exists")
    try:
        staging = Path(tempfile.mkdtemp(prefix=".eg8d-area-priority-staging-", dir=resolved_root))
    except OSError:
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: staging_create_failed") from None
    published = False
    try:
        for name in sorted(payloads):
            _write_exclusive(staging / name, payloads[name])
        artifacts = [
            {
                "relative_path": name,
                "sha256": hashlib.sha256(payloads[name]).hexdigest(),
                "byte_size": len(payloads[name]),
            }
            for name in sorted(payloads)
        ]
        manifest = {
            "schema_version": "eg8d-area-priority-manifest-v1",
            "hash_algorithm": "sha256",
            "output_artifacts": artifacts,
        }
        _write_exclusive(staging / "area_priority_manifest.json", _json_bytes(manifest))
        if {path.name for path in staging.iterdir()} != OUTPUT_FILES:
            raise AreaPriorityWriteError("eg8d_area_priority_write_error: staged_artifact_set_mismatch")
        for artifact in artifacts:
            path = staging / str(artifact["relative_path"])
            if _sha256(path) != artifact["sha256"] or path.stat().st_size != artifact["byte_size"]:
                raise AreaPriorityWriteError("eg8d_area_priority_write_error: staged_hash_mismatch")
        if any(_sha256(path) != expected for path, expected in input_hashes.items()):
            _fail("source_changed_during_run")
        try:
            eg8c_features._rename_run_root_exclusive(staging, final_run)
        except OSError:
            raise AreaPriorityWriteError("eg8d_area_priority_write_error: publish_failed") from None
        published = True
        return final_run, manifest
    finally:
        if not published and staging.exists():
            try:
                shutil.rmtree(staging)
            except OSError:
                raise AreaPriorityWriteError("eg8d_area_priority_write_error: staging_cleanup_failed") from None


def _run_eg8d_area_priority(
    *,
    dataset_manifest_path: Path,
    current_path: Path,
    forecast_path: Path,
    output_root: Path,
    run_id: str,
    source_collection_run_id: str,
    generated_at: datetime | None = None,
) -> AreaPriorityResult:
    resolved_generated_at = generated_at or datetime.now(eg8a.SEOUL)
    manifest_payload, manifest_info = _snapshot(
        dataset_manifest_path, "manifest", LOCKED_MANIFEST_SHA256
    )
    current_payload, current_info = _snapshot(current_path, "current", LOCKED_CURRENT_SHA256)
    forecast_payload, forecast_info = _snapshot(
        forecast_path, "forecast", LOCKED_FORECAST_SHA256
    )
    _validate_manifest(manifest_payload)
    current_rows = _csv_from_snapshot(current_payload, CURRENT_REQUIRED_COLUMNS, "current")
    forecast_rows = _csv_from_snapshot(forecast_payload, FORECAST_REQUIRED_COLUMNS, "forecast")
    rows = build_area_priority_rows(
        current_rows,
        forecast_rows,
        source_collection_run_id=source_collection_run_id,
        generated_at=resolved_generated_at,
    )
    inputs = {
        "dataset_manifest": manifest_info,
        "population_current_v3": current_info,
        "population_forecast_v3": forecast_info,
    }
    metadata = _metadata(
        run_id=run_id,
        source_collection_run_id=source_collection_run_id,
        generated_at=resolved_generated_at,
        rows=rows,
        inputs=inputs,
    )
    payloads = {
        "area_priority.csv": _csv_bytes(rows),
        "area_priority.json": _json_bytes([row.as_dict() for row in rows]),
        "run_metadata.json": _json_bytes(metadata),
    }
    paths = (dataset_manifest_path, current_path, forecast_path)
    run_dir, manifest = _publish(
        output_root=output_root,
        run_id=run_id,
        payloads=payloads,
        input_paths=paths,
        input_hashes={
            dataset_manifest_path: str(manifest_info["sha256"]),
            current_path: str(current_info["sha256"]),
            forecast_path: str(forecast_info["sha256"]),
        },
    )
    return AreaPriorityResult(run_id, run_dir, rows, metadata, manifest)


def run_eg8d_area_priority(
    *,
    dataset_manifest_path: Path,
    current_path: Path,
    forecast_path: Path,
    output_root: Path,
    run_id: str,
    source_collection_run_id: str,
    generated_at: datetime | None = None,
) -> AreaPriorityResult:
    """Public bounded-error entry point for one offline EG-8D result run."""
    try:
        return _run_eg8d_area_priority(
            dataset_manifest_path=dataset_manifest_path,
            current_path=current_path,
            forecast_path=forecast_path,
            output_root=output_root,
            run_id=run_id,
            source_collection_run_id=source_collection_run_id,
            generated_at=generated_at,
        )
    except (AreaPriorityContractError, AreaPriorityWriteError):
        raise
    except Exception:
        raise AreaPriorityWriteError("eg8d_area_priority_write_error: execution_failed") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EG-8D Area 예상 유동인구 변화 순서")
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--current-path", type=Path, required=True)
    parser.add_argument("--forecast-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-collection-run-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = run_eg8d_area_priority(
            dataset_manifest_path=arguments.dataset_manifest,
            current_path=arguments.current_path,
            forecast_path=arguments.forecast_path,
            output_root=arguments.output_root,
            run_id=arguments.run_id,
            source_collection_run_id=arguments.source_collection_run_id,
        )
    except (AreaPriorityContractError, AreaPriorityWriteError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print("eg8d_area_priority_completed")
    print(f"run_id={result.run_id}")
    print(f"row_count={len(result.rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
