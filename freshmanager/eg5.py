"""EG-5 fixed three-place collection CLI with isolated per-place failures."""

from __future__ import annotations

import argparse
import hashlib
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .collector import Collector, HttpResponse, Place, load_place
from .config import load_api_key
from .http_adapter import SeoulPopulationHttpClient, Transport, UrllibTransport
from .storage import FileStorage


EG5_AREA_CODES = (
    "POI019",
    "POI013",
    "POI014",
)
EG5_AREA_NAMES = {
    "POI019": "구로디지털단지역",
    "POI013": "가산디지털단지역",
    "POI014": "강남역",
}
STAGE_NAME = "eg5_representative_3"
STAGE_PATH = Path("stages") / STAGE_NAME
RAW_OUTPUT_PATH = STAGE_PATH / "data/raw/population"
METADATA_OUTPUT_PATH = STAGE_PATH / "data/processed/collection_logs"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_TIMEOUT_SECONDS = 60.0
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_CSV_PATH = PROJECT_ROOT / "data/reference/seoul_121_places.csv"
COMMON_FAILURE_STATUSES = {"config_error", "storage_error", "security_error"}
PROBE_FILE_PREFIX = ".eg5-write-probe-"
PROBE_PAYLOAD = b"eg5-storage-probe"


class CliInputError(ValueError):
    """Raised for a CLI value that must be rejected before side effects."""


class SafeArgumentParser(argparse.ArgumentParser):
    """Convert parser failures into a fixed, non-sensitive CLI result."""

    def error(self, message: str) -> None:
        del message
        raise CliInputError("input_error")


@dataclass(frozen=True)
class Eg5Summary:
    target_count: int
    success_count: int
    failure_count: int
    failed_area_codes: tuple[str, ...]
    retry_count: int
    stage: str
    exit_code: int


class _LazyHttpClient:
    """Create the approved network transport only when the first request starts."""

    def __init__(self, transport_factory: Callable[[], Transport]) -> None:
        self._transport_factory = transport_factory
        self._client: SeoulPopulationHttpClient | None = None

    def fetch_population(self, area_code: str, api_key: str, timeout_seconds: float) -> HttpResponse:
        if self._client is None:
            self._client = SeoulPopulationHttpClient(self._transport_factory())
        return self._client.fetch_population(area_code, api_key, timeout_seconds)


def _timeout_value(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("invalid timeout") from error
    if not math.isfinite(timeout) or not 0 < timeout <= MAX_TIMEOUT_SECONDS:
        raise argparse.ArgumentTypeError("invalid timeout")
    return timeout


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(description="EG-5 대표 3장소 단일 회차 수집")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout", type=_timeout_value, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="PM 실제 호출 승인을 대체하지 않는 명시적 실행 의사 확인",
    )
    return parser


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validated_output_paths(value: Path) -> tuple[Path, Path]:
    try:
        output_root = value.expanduser().resolve()
        project_root = PROJECT_ROOT.resolve()
        stage_root = (output_root / STAGE_PATH).resolve()
        raw_root = (output_root / RAW_OUTPUT_PATH).resolve()
        metadata_root = (output_root / METADATA_OUTPUT_PATH).resolve()
    except (OSError, RuntimeError) as error:
        raise CliInputError("input_error") from error

    if output_root == output_root.parent or (output_root.exists() and not output_root.is_dir()):
        raise CliInputError("input_error")
    if not all(_is_within(path, output_root) for path in (stage_root, raw_root, metadata_root)):
        raise CliInputError("input_error")

    protected_roots = [
        project_root / ".git",
        project_root / "work log",
        project_root / "data/reference",
        project_root / "data/samples",
        project_root / "data/raw",
        project_root / "data/processed",
        project_root / "data/quality",
        project_root / "logs",
        project_root / "tests/fixtures",
    ]
    resolved_protected = [path.resolve() for path in protected_roots]
    if any(
        _is_within(candidate, protected)
        for candidate in (output_root, stage_root, raw_root, metadata_root)
        for protected in resolved_protected
    ):
        raise CliInputError("input_error")
    if any(path.exists() and not path.is_dir() for path in (stage_root, raw_root, metadata_root)):
        raise CliInputError("input_error")
    return raw_root, metadata_root


def _load_approved_places(csv_path: Path) -> tuple[Place, ...]:
    if len(EG5_AREA_CODES) != 3 or len(set(EG5_AREA_CODES)) != 3:
        raise ValueError("validation_error")
    places = tuple(load_place(csv_path, area_code) for area_code in EG5_AREA_CODES)
    if any(place.area_name != EG5_AREA_NAMES.get(place.area_code) for place in places):
        raise ValueError("validation_error")
    return places


def _official_csv_digest(csv_path: Path) -> str:
    if not csv_path.is_file():
        raise ValueError("validation_error")
    digest = hashlib.sha256()
    with csv_path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe_storage_root(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    probe_path = root / f"{PROBE_FILE_PREFIX}{uuid.uuid4().hex}.probe"
    try:
        with probe_path.open("xb") as probe:
            probe.write(PROBE_PAYLOAD)
            probe.flush()
    finally:
        if probe_path.exists():
            probe_path.unlink()


def _probe_storage_roots(raw_root: Path, metadata_root: Path) -> None:
    _probe_storage_root(raw_root)
    _probe_storage_root(metadata_root)


def _make_summary(successful_area_codes: set[str], exit_code: int) -> Eg5Summary:
    failed_area_codes = tuple(code for code in EG5_AREA_CODES if code not in successful_area_codes)
    return Eg5Summary(
        target_count=len(EG5_AREA_CODES),
        success_count=len(successful_area_codes),
        failure_count=len(failed_area_codes),
        failed_area_codes=failed_area_codes,
        retry_count=0,
        stage=STAGE_NAME,
        exit_code=exit_code,
    )


def _report_place(
    area_code: str,
    request_id: str,
    collection_status: str,
    *,
    raw_saved: bool,
    metadata_saved: bool,
) -> None:
    print("EG5_PLACE_RESULT")
    print(f"area_code={area_code}")
    print(f"request_id={request_id}")
    print(f"collection_status={collection_status}")
    print(f"raw_saved={'true' if raw_saved else 'false'}")
    print(f"metadata_saved={'true' if metadata_saved else 'false'}")


def _report_summary(summary: Eg5Summary) -> None:
    print("EG5_COLLECTION_SUMMARY")
    print(f"target_count={summary.target_count}")
    print(f"success_count={summary.success_count}")
    print(f"failure_count={summary.failure_count}")
    print(f"failed_area_codes={','.join(summary.failed_area_codes)}")
    print(f"retry_count={summary.retry_count}")
    print(f"stage={summary.stage}")
    print(f"exit_code={summary.exit_code}")


def _finish(successful_area_codes: set[str], exit_code: int) -> int:
    _report_summary(_make_summary(successful_area_codes, exit_code))
    return exit_code


def _run(
    argv: list[str] | None = None,
    *,
    transport_factory: Callable[[], Transport] | None = None,
    storage_factory: Callable[[Path, Path], FileStorage] = FileStorage,
    official_csv_path: Path | None = None,
    successful_area_codes: set[str],
) -> int:
    try:
        arguments = build_parser().parse_args(argv)
    except CliInputError:
        return _finish(successful_area_codes, 2)

    if not arguments.execute_live:
        return _finish(successful_area_codes, 2)

    try:
        csv_path = official_csv_path if official_csv_path is not None else OFFICIAL_CSV_PATH
        raw_root, metadata_root = _validated_output_paths(arguments.output_root)
        csv_digest = _official_csv_digest(csv_path)
        places = _load_approved_places(csv_path)
        if _official_csv_digest(csv_path) != csv_digest:
            raise ValueError("validation_error")
        api_key = load_api_key(arguments.env_file)
        _probe_storage_roots(raw_root, metadata_root)
        storage = storage_factory(raw_root, metadata_root)
        client = _LazyHttpClient(transport_factory if transport_factory is not None else UrllibTransport)
        collector = Collector(
            csv_path,
            client,
            storage,
            timeout_seconds=arguments.timeout,
        )
    except Exception:
        return _finish(successful_area_codes, 2)

    request_ids: set[str] = set()
    for place in places:
        try:
            if _official_csv_digest(csv_path) != csv_digest:
                return _finish(successful_area_codes, 2)
            request = collector.prepare_request(place.area_code)
            if request.request_id in request_ids:
                return _finish(successful_area_codes, 2)
            request_ids.add(request.request_id)
            result = collector.collect(api_key, place.area_code, request=request)
        except Exception:
            return _finish(successful_area_codes, 2)

        collection_status = result.status
        raw_saved = result.metadata.get("raw_file_path") is not None
        metadata_saved = result.metadata_path is not None
        if collection_status == "success":
            successful_area_codes.add(place.area_code)
        _report_place(
            place.area_code,
            request.request_id,
            collection_status,
            raw_saved=raw_saved,
            metadata_saved=metadata_saved,
        )
        try:
            if _official_csv_digest(csv_path) != csv_digest:
                return _finish(successful_area_codes, 2)
        except Exception:
            return _finish(successful_area_codes, 2)
        if collection_status in COMMON_FAILURE_STATUSES:
            return _finish(successful_area_codes, 2)

    return _finish(successful_area_codes, 0 if len(successful_area_codes) == len(EG5_AREA_CODES) else 1)


def _finish_after_internal_error(successful_area_codes: set[str]) -> int:
    try:
        return _finish(successful_area_codes, 2)
    except Exception:
        return 2


def run(
    argv: list[str] | None = None,
    *,
    transport_factory: Callable[[], Transport] | None = None,
    storage_factory: Callable[[Path, Path], FileStorage] = FileStorage,
    official_csv_path: Path | None = None,
) -> int:
    successful_area_codes: set[str] = set()
    try:
        return _run(
            argv,
            transport_factory=transport_factory,
            storage_factory=storage_factory,
            official_csv_path=official_csv_path,
            successful_area_codes=successful_area_codes,
        )
    except Exception:
        return _finish_after_internal_error(successful_area_codes)


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
