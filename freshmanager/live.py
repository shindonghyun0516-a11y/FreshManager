"""Explicitly approved single-request CLI for Seoul POI072 collection."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Callable

from .collector import Collector, HttpResponse
from .config import ConfigError, load_api_key
from .http_adapter import SeoulPopulationHttpClient, Transport, UrllibTransport
from .storage import FileStorage


AREA_CODE = "POI072"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_TIMEOUT_SECONDS = 60.0
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_CSV_PATH = PROJECT_ROOT / "data/reference/seoul_121_places.csv"
RAW_OUTPUT_PATH = Path("data/raw/population")
METADATA_OUTPUT_PATH = Path("data/processed/collection_logs")


class CliInputError(ValueError):
    """Raised for a CLI value that must be rejected before side effects."""


class SafeArgumentParser(argparse.ArgumentParser):
    """Convert parser failures into a fixed, non-sensitive CLI result."""

    def error(self, message: str) -> None:
        del message
        raise CliInputError("input_error")


class _LazyHttpClient:
    """Create the approved network transport only after CSV validation."""

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
    parser = SafeArgumentParser(description="여의도 POI072 단일 실제 수집 실행")
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout", type=_timeout_value, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--execute-live",
        action="store_true",
        help="PM 외부 실행 승인을 대체하지 않는 명시적 실행 의사 확인",
    )
    return parser


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validated_output_root(value: Path) -> Path:
    try:
        output_root = value.expanduser().resolve()
        project_root = PROJECT_ROOT.resolve()
    except (OSError, RuntimeError) as error:
        raise CliInputError("input_error") from error

    if output_root.exists() and not output_root.is_dir():
        raise CliInputError("input_error")

    protected_roots = [
        project_root / ".git",
        project_root / "work log",
        project_root / "data/reference",
        project_root / "data/samples",
        project_root / "tests/fixtures",
    ]
    if any(_is_within(output_root, protected.resolve()) for protected in protected_roots):
        raise CliInputError("input_error")
    return output_root


def _report_result(request_id: str, status: str, *, raw_saved: bool, metadata_saved: bool) -> None:
    print(f"request_id={request_id}")
    print(f"collection_status={status}")
    print(f"raw_saved={'true' if raw_saved else 'false'}")
    print(f"metadata_saved={'true' if metadata_saved else 'false'}")


def run(
    argv: list[str] | None = None,
    *,
    transport_factory: Callable[[], Transport] | None = None,
    storage_factory: Callable[[Path, Path], FileStorage] = FileStorage,
) -> int:
    try:
        arguments = build_parser().parse_args(argv)
    except CliInputError:
        print("input_error: 실행 옵션을 확인하세요")
        return 2

    if not arguments.execute_live:
        print("execution_not_approved: --execute-live 옵션이 필요합니다")
        return 2

    try:
        output_root = _validated_output_root(arguments.output_root)
    except CliInputError:
        print("input_error: 안전한 출력 경로를 지정해야 합니다")
        return 2

    try:
        storage = storage_factory(
            output_root / RAW_OUTPUT_PATH,
            output_root / METADATA_OUTPUT_PATH,
        )
        client = _LazyHttpClient(transport_factory or UrllibTransport)
        collector = Collector(
            OFFICIAL_CSV_PATH,
            client,
            storage,
            timeout_seconds=arguments.timeout,
        )
        request = collector.prepare_request(AREA_CODE)
        try:
            api_key = load_api_key(arguments.env_file)
        except ConfigError:
            result = collector.record_config_error(request)
            _report_result(
                request.request_id,
                result.status,
                raw_saved=False,
                metadata_saved=result.metadata_path is not None,
            )
            return 1

        result = collector.collect(api_key, AREA_CODE, request=request)
        _report_result(
            request.request_id,
            result.status,
            raw_saved=result.metadata.get("raw_file_path") is not None,
            metadata_saved=result.metadata_path is not None,
        )
        return 0 if result.status == "success" else 1
    except Exception:
        print("internal_error: 실행을 안전하게 완료하지 못했습니다")
        return 3


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
