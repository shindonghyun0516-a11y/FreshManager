"""Command-line entry point for the EG-4 sample-only offline collector."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from .collector import Collector, HttpResponse
from .config import ConfigError, load_api_key
from .storage import FileStorage


class SampleFileClient:
    """Read one approved sample file; it never opens a socket."""

    def __init__(self, sample_path: Path) -> None:
        self.sample_path = sample_path

    def fetch_population(self, area_code: str, api_key: str, timeout_seconds: float) -> HttpResponse:
        del api_key, timeout_seconds
        if area_code != "POI072":
            raise ValueError("validation_error: offline sample is only for POI072")
        return HttpResponse(status_code=200, body=self.sample_path.read_bytes())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="여의도 POI072 오프라인 수집 검증")
    parser.add_argument("--env-file", type=Path, required=True, help="Dummy Key가 있는 임시 .env 경로")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/reference/seoul_121_places.csv"),
        help="읽기 전용 공식 장소 CSV",
    )
    parser.add_argument(
        "--sample",
        type=Path,
        default=Path("data/samples/population_yeouido_sample.json"),
        help="읽기 전용 공식 여의도 샘플",
    )
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/population"))
    parser.add_argument("--metadata-root", type=Path, default=Path("data/processed/collection_logs"))
    return parser


def run(
    argv: list[str] | None = None,
    *,
    storage_factory: Callable[[Path, Path], FileStorage] = FileStorage,
) -> int:
    arguments = build_parser().parse_args(argv)
    collector = Collector(
        arguments.csv,
        SampleFileClient(arguments.sample),
        storage_factory(arguments.raw_root, arguments.metadata_root),
    )
    request = collector.prepare_request("POI072")
    try:
        api_key = load_api_key(arguments.env_file)
    except ConfigError:
        result = collector.record_config_error(request)
        print(f"request_id={request.request_id}")
        print(f"collection_status={result.status}")
        if result.metadata_path is not None:
            print(f"metadata_path={result.metadata_path}")
        return 1
    result = collector.collect(api_key, request=request)
    print(f"request_id={request.request_id}")
    print(f"collection_status={result.status}")
    if result.metadata_path is not None:
        print(f"metadata_path={result.metadata_path}")
    return 0 if result.status == "success" else 1


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
