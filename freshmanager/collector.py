"""Offline-first single-place population collector for EG-4."""

from __future__ import annotations

import csv
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from .storage import FileStorage, StorageError


EXPECTED_HEADERS = ["CATEGORY", "NO", "AREA_CD", "AREA_NM", "ENG_NM"]
CURRENT_POPULATION_FIELDS = [
    "AREA_NM",
    "AREA_CD",
    "AREA_CONGEST_LVL",
    "AREA_CONGEST_MSG",
    "AREA_PPLTN_MIN",
    "AREA_PPLTN_MAX",
    "MALE_PPLTN_RATE",
    "FEMALE_PPLTN_RATE",
    "PPLTN_RATE_0",
    "PPLTN_RATE_10",
    "PPLTN_RATE_20",
    "PPLTN_RATE_30",
    "PPLTN_RATE_40",
    "PPLTN_RATE_50",
    "PPLTN_RATE_60",
    "PPLTN_RATE_70",
    "RESNT_PPLTN_RATE",
    "NON_RESNT_PPLTN_RATE",
    "REPLACE_YN",
    "PPLTN_TIME",
    "FCST_YN",
]
FORECAST_FIELDS = ["FCST_TIME", "FCST_CONGEST_LVL", "FCST_PPLTN_MIN", "FCST_PPLTN_MAX"]
METADATA_FIELDS = (
    "request_id",
    "area_code",
    "endpoint_name",
    "requested_at",
    "received_at",
    "http_status",
    "collection_status",
    "raw_file_path",
)
ENDPOINT_NAME = "citydata_ppltn"
SEOUL = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class Place:
    category: str
    number: str
    area_code: str
    area_name: str
    english_name: str


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    body: bytes


@dataclass(frozen=True)
class CollectionRequest:
    request_id: str
    requested_at: datetime
    area_code: str
    endpoint_name: str = ENDPOINT_NAME


class HttpClient(Protocol):
    def fetch_population(self, area_code: str, api_key: str, timeout_seconds: float) -> HttpResponse:
        """Return one response without logging the key or a complete URL."""


@dataclass(frozen=True)
class CollectionResult:
    metadata: dict[str, object]
    metadata_path: Path | None
    population: dict[str, object] | None

    @property
    def status(self) -> str:
        return str(self.metadata["collection_status"])


def now_seoul() -> datetime:
    return datetime.now(SEOUL)


def load_place(csv_path: Path, area_code: str = "POI072") -> Place:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        if list(reader.fieldnames or ()) != EXPECTED_HEADERS:
            raise ValueError("validation_error: 공식 CSV 헤더 불일치")
        matches = [row for row in reader if str(row.get("AREA_CD") or "").strip() == area_code]
    if len(matches) != 1:
        raise ValueError("validation_error: 장소코드가 없거나 중복됨")
    row = matches[0]
    place = Place(
        category=str(row["CATEGORY"]).strip(),
        number=str(row["NO"]).strip(),
        area_code=str(row["AREA_CD"]).strip(),
        area_name=str(row["AREA_NM"]).strip(),
        english_name=str(row["ENG_NM"]).strip(),
    )
    if area_code == "POI072" and place.area_name != "여의도":
        raise ValueError("validation_error: POI072 장소명이 여의도가 아님")
    return place


def _is_xml_service_error_envelope(payload: bytes) -> bool:
    try:
        root = ElementTree.fromstring(payload)
    except (ElementTree.ParseError, LookupError):
        return False
    if root.tag != "RESULT":
        return False
    direct_child_tags = {child.tag for child in root}
    return "CODE" in direct_child_tags and "MESSAGE" in direct_child_tags


def parse_population_response(payload: bytes, place: Place) -> dict[str, object]:
    try:
        document = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        if _is_xml_service_error_envelope(payload):
            raise ValueError("api_error: XML 서비스 오류") from None
        raise ValueError("parse_error") from error
    if not isinstance(document, dict):
        raise ValueError("validation_error: 응답 최상위 객체 없음")
    result = document.get("RESULT")
    if not isinstance(result, dict) or "RESULT.CODE" not in result or "RESULT.MESSAGE" not in result:
        raise ValueError("validation_error: RESULT 구조 누락")
    if result["RESULT.CODE"] != "INFO-000":
        raise ValueError("api_error: RESULT.CODE 오류")
    items = document.get("SeoulRtd.citydata_ppltn")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise ValueError("validation_error: 장소 객체는 정확히 1개여야 함")
    population = items[0]
    if population.get("AREA_CD") != place.area_code or population.get("AREA_NM") != place.area_name:
        raise ValueError("validation_error: 응답 장소 불일치")
    missing = [field for field in CURRENT_POPULATION_FIELDS if field not in population]
    if missing:
        raise ValueError("validation_error: 현재 인구 필드 누락")
    try:
        current_minimum = int(str(population["AREA_PPLTN_MIN"]).strip())
        current_maximum = int(str(population["AREA_PPLTN_MAX"]).strip())
    except (TypeError, ValueError) as error:
        raise ValueError("validation_error: 현재 인구 형식 오류") from error
    if current_minimum > current_maximum:
        raise ValueError("validation_error: 현재 인구 최소값이 최대값보다 큼")

    normalized_forecasts: list[dict[str, object]] = []
    if population.get("FCST_YN") == "Y":
        forecasts = population.get("FCST_PPLTN")
        if not isinstance(forecasts, list) or not forecasts:
            raise ValueError("validation_error: 미래예측 배열 누락")
        for forecast in forecasts:
            if not isinstance(forecast, dict) or any(field not in forecast for field in FORECAST_FIELDS):
                raise ValueError("validation_error: 미래예측 필드 누락")
            try:
                minimum = int(str(forecast["FCST_PPLTN_MIN"]).strip())
                maximum = int(str(forecast["FCST_PPLTN_MAX"]).strip())
            except (TypeError, ValueError) as error:
                raise ValueError("validation_error: 미래예측 인구 형식 오류") from error
            if minimum > maximum:
                raise ValueError("validation_error: 미래예측 최소값이 최대값보다 큼")
            normalized_forecasts.append(
                {
                    "forecast_target_time": forecast["FCST_TIME"],
                    "forecast_congestion_level": forecast["FCST_CONGEST_LVL"],
                    "forecast_population_min": minimum,
                    "forecast_population_max": maximum,
                }
            )
    return {
        "area_code": population["AREA_CD"],
        "area_name": population["AREA_NM"],
        "population_reference_time": population["PPLTN_TIME"],
        "congestion_level": population["AREA_CONGEST_LVL"],
        "population_min": current_minimum,
        "population_max": current_maximum,
        "forecast_available": population["FCST_YN"] == "Y",
        "forecasts": normalized_forecasts,
    }


class Collector:
    def __init__(
        self,
        csv_path: Path,
        client: HttpClient,
        storage: FileStorage,
        *,
        clock: Callable[[], datetime] = now_seoul,
        request_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.csv_path = csv_path
        self.client = client
        self.storage = storage
        self.clock = clock
        self.request_id_factory = request_id_factory
        self.timeout_seconds = timeout_seconds

    def prepare_request(self, area_code: str = "POI072") -> CollectionRequest:
        return CollectionRequest(
            request_id=str(self.request_id_factory()),
            requested_at=self.clock(),
            area_code=area_code,
        )

    def _metadata(
        self,
        *,
        request: CollectionRequest,
        received_at: datetime,
        http_status: int | None,
        status: str,
        raw_path: Path | None,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            "request_id": request.request_id,
            "area_code": request.area_code,
            "endpoint_name": request.endpoint_name,
            "requested_at": request.requested_at.isoformat(),
            "received_at": received_at.isoformat(),
            "http_status": http_status,
            "collection_status": status,
            "raw_file_path": raw_path.as_posix() if raw_path else None,
        }
        if tuple(metadata) != METADATA_FIELDS:
            raise RuntimeError("metadata contract mismatch")
        return metadata

    def _store_metadata(
        self,
        metadata: dict[str, object],
        requested_at: datetime,
        request_id: str,
        population: dict[str, object] | None,
    ) -> CollectionResult:
        try:
            metadata_path = self.storage.save_metadata(requested_at, request_id, metadata)
        except StorageError:
            failed_metadata = dict(metadata)
            failed_metadata["collection_status"] = "storage_error"
            return CollectionResult(failed_metadata, None, population)
        return CollectionResult(metadata, metadata_path, population)

    def record_config_error(self, request: CollectionRequest) -> CollectionResult:
        metadata = self._metadata(
            request=request,
            received_at=self.clock(),
            http_status=None,
            status="config_error",
            raw_path=None,
        )
        return self._store_metadata(metadata, request.requested_at, request.request_id, None)

    def collect(
        self,
        api_key: str,
        area_code: str = "POI072",
        *,
        request: CollectionRequest | None = None,
    ) -> CollectionResult:
        active_request = request or self.prepare_request(area_code)
        if active_request.area_code != area_code or active_request.endpoint_name != ENDPOINT_NAME:
            raise ValueError("validation_error: 요청 문맥 불일치")
        if not api_key:
            return self.record_config_error(active_request)

        try:
            place = load_place(self.csv_path, area_code)
        except (OSError, UnicodeDecodeError, csv.Error, ValueError):
            metadata = self._metadata(
                request=active_request,
                received_at=self.clock(),
                http_status=None,
                status="validation_error",
                raw_path=None,
            )
            return self._store_metadata(
                metadata,
                active_request.requested_at,
                active_request.request_id,
                None,
            )

        try:
            response = self.client.fetch_population(place.area_code, api_key, self.timeout_seconds)
        except TimeoutError:
            metadata = self._metadata(
                request=active_request,
                received_at=self.clock(),
                http_status=None,
                status="timeout",
                raw_path=None,
            )
            return self._store_metadata(
                metadata,
                active_request.requested_at,
                active_request.request_id,
                None,
            )
        except OSError:
            metadata = self._metadata(
                request=active_request,
                received_at=self.clock(),
                http_status=None,
                status="api_error",
                raw_path=None,
            )
            return self._store_metadata(
                metadata,
                active_request.requested_at,
                active_request.request_id,
                None,
            )

        received_at = self.clock()
        try:
            raw_path = self.storage.save_raw(
                place.area_code,
                active_request.requested_at,
                active_request.request_id,
                response.body,
            )
        except StorageError:
            metadata = self._metadata(
                request=active_request,
                received_at=received_at,
                http_status=response.status_code,
                status="storage_error",
                raw_path=None,
            )
            return self._store_metadata(
                metadata,
                active_request.requested_at,
                active_request.request_id,
                None,
            )

        if not 200 <= response.status_code < 300:
            metadata = self._metadata(
                request=active_request,
                received_at=received_at,
                http_status=response.status_code,
                status="api_error",
                raw_path=raw_path,
            )
            return self._store_metadata(
                metadata,
                active_request.requested_at,
                active_request.request_id,
                None,
            )

        try:
            population = parse_population_response(response.body, place)
            status = "success"
        except ValueError as error:
            population = None
            if str(error) == "parse_error":
                status = "parse_error"
            elif str(error).startswith("api_error"):
                status = "api_error"
            else:
                status = "validation_error"

        metadata = self._metadata(
            request=active_request,
            received_at=received_at,
            http_status=response.status_code,
            status=status,
            raw_path=raw_path,
        )
        return self._store_metadata(
            metadata,
            active_request.requested_at,
            active_request.request_id,
            population,
        )
