"""HTTP adapter for one Seoul population request without automatic execution."""

from __future__ import annotations

import socket
from contextlib import closing
from typing import BinaryIO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .collector import HttpResponse


BASE_URL = "http://openapi.seoul.go.kr:8088"
RESPONSE_FORMAT = "json"
SERVICE_NAME = "citydata_ppltn"
START_INDEX = 1
END_INDEX = 5
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024


class TransportResponse(Protocol):
    """Small response surface used by the adapter."""

    status: int

    def read(self, size: int = -1) -> bytes:
        """Read response bytes."""

    def close(self) -> None:
        """Release response resources."""


class Transport(Protocol):
    """Open one prepared request and return a readable response."""

    def open(self, request: Request, timeout_seconds: float) -> TransportResponse:
        """Execute a request without logging its URL or credentials."""


class RejectRedirectHandler(HTTPRedirectHandler):
    """Prevent authentication information from being forwarded by redirects."""

    def redirect_request(
        self,
        request: Request,
        file_pointer: BinaryIO,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


class UrllibTransport:
    """Network-capable transport. Constructing it does not perform a request."""

    def __init__(self) -> None:
        self._opener = build_opener(RejectRedirectHandler())

    def open(self, request: Request, timeout_seconds: float) -> TransportResponse:
        return self._opener.open(request, timeout=timeout_seconds)  # type: ignore[return-value]


def build_population_request(area_code: str, api_key: str) -> Request:
    """Build the approved GET request without printing the completed URL."""

    if not area_code:
        raise ValueError("validation_error: 장소코드 누락")
    if not api_key:
        raise ValueError("config_error: API Key 누락")
    path = "/".join(
        [
            quote(api_key, safe=""),
            RESPONSE_FORMAT,
            SERVICE_NAME,
            str(START_INDEX),
            str(END_INDEX),
            quote(area_code, safe=""),
        ]
    )
    return Request(f"{BASE_URL}/{path}", method="GET")


def _read_limited(response: BinaryIO, maximum_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        read_size = min(READ_CHUNK_BYTES, maximum_bytes - total + 1)
        try:
            chunk = response.read(read_size)
        except OSError:
            raise OSError("api_error: 응답 읽기 실패") from None
        if not isinstance(chunk, bytes):
            raise OSError("api_error: 응답 형식 오류") from None
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > maximum_bytes:
            raise OSError("api_error: 응답 크기 제한 초과") from None


class SeoulPopulationHttpClient:
    """Translate one injected transport call into the Collector HTTP contract."""

    def __init__(self, transport: Transport, *, maximum_response_bytes: int = MAX_RESPONSE_BYTES) -> None:
        if maximum_response_bytes <= 0:
            raise ValueError("validation_error: 응답 크기 제한 오류")
        self._transport = transport
        self._maximum_response_bytes = maximum_response_bytes

    def fetch_population(self, area_code: str, api_key: str, timeout_seconds: float) -> HttpResponse:
        request = build_population_request(area_code, api_key)
        try:
            response = self._transport.open(request, timeout_seconds)
        except HTTPError as error:
            if error.fp is None:
                body = b""
            else:
                with closing(error):
                    body = _read_limited(error, self._maximum_response_bytes)
            return HttpResponse(status_code=int(error.code), body=body)
        except (TimeoutError, socket.timeout):
            raise TimeoutError("timeout") from None
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise TimeoutError("timeout") from None
            raise OSError("api_error: 연결 실패") from None
        except OSError:
            raise OSError("api_error: 연결 실패") from None

        with closing(response):
            try:
                status_code = int(response.status)
            except (AttributeError, TypeError, ValueError):
                raise OSError("api_error: HTTP 상태 오류") from None
            body = _read_limited(response, self._maximum_response_bytes)
        return HttpResponse(status_code=status_code, body=body)
