from __future__ import annotations

import contextlib
import io
import socket
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from freshmanager import http_adapter
from freshmanager.collector import Collector, HttpResponse
from freshmanager.storage import FileStorage


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data/reference/seoul_121_places.csv"
SAMPLE_PATH = ROOT / "data/samples/population_yeouido_sample.json"
DUMMY_KEY = "dummy-key-for-http-adapter-test"
FIXED_TIME = datetime(2026, 7, 20, 10, 11, 12, tzinfo=ZoneInfo("Asia/Seoul"))
FIXED_ID = uuid.UUID("abcdefab-cdef-4abc-8def-abcdefabcdef")


class FakeResponse:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = io.BytesIO(body)
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def close(self) -> None:
        self.closed = True
        self._body.close()


class FakeTransport:
    def __init__(self, response: FakeResponse | None = None, error: BaseException | None = None) -> None:
        self.response = response or FakeResponse(200, b"ok")
        self.error = error
        self.calls: list[tuple[object, float]] = []

    def open(self, request: object, timeout_seconds: float) -> FakeResponse:
        self.calls.append((request, timeout_seconds))
        if self.error is not None:
            raise self.error
        return self.response


class HttpAdapterTests(unittest.TestCase):
    def client(self, transport: FakeTransport, *, maximum: int = http_adapter.MAX_RESPONSE_BYTES) -> http_adapter.SeoulPopulationHttpClient:
        return http_adapter.SeoulPopulationHttpClient(transport, maximum_response_bytes=maximum)

    def test_builds_get_request(self) -> None:
        request = http_adapter.build_population_request("POI072", DUMMY_KEY)
        self.assertEqual(request.get_method(), "GET")

    def test_builds_approved_poi072_path(self) -> None:
        request = http_adapter.build_population_request("POI072", DUMMY_KEY)
        segments = request.selector.split("/")
        self.assertTrue(
            segments[-5:] == ["json", "citydata_ppltn", "1", "5", "POI072"],
            "승인된 Endpoint 경로 불일치",
        )

    def test_passes_timeout_to_transport(self) -> None:
        transport = FakeTransport()
        self.client(transport).fetch_population("POI072", DUMMY_KEY, 7.5)
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(transport.calls[0][1], 7.5)

    def test_returns_200_body_without_changes(self) -> None:
        body = b' {"value":"001"}\n'
        result = self.client(FakeTransport(FakeResponse(200, body))).fetch_population("POI072", DUMMY_KEY, 10)
        self.assertEqual(result, HttpResponse(200, body))

    def test_returns_empty_body_without_changes(self) -> None:
        result = self.client(FakeTransport(FakeResponse(200, b""))).fetch_population("POI072", DUMMY_KEY, 10)
        self.assertEqual(result, HttpResponse(200, b""))

    def test_returns_4xx_status_and_body(self) -> None:
        body = b'{"error":"bad request"}'
        result = self.client(FakeTransport(FakeResponse(400, body))).fetch_population("POI072", DUMMY_KEY, 10)
        self.assertEqual(result, HttpResponse(400, body))

    def test_returns_5xx_status_and_body(self) -> None:
        body = b'{"error":"server"}'
        result = self.client(FakeTransport(FakeResponse(503, body))).fetch_population("POI072", DUMMY_KEY, 10)
        self.assertEqual(result, HttpResponse(503, body))

    def test_redirect_is_not_followed(self) -> None:
        error = http_adapter.HTTPError("redacted", 302, "redirect", {}, io.BytesIO(b"redirect"))
        transport = FakeTransport(error=error)
        result = self.client(transport).fetch_population("POI072", DUMMY_KEY, 10)
        self.assertEqual(result, HttpResponse(302, b"redirect"))
        handler = http_adapter.RejectRedirectHandler()
        self.assertIsNone(handler.redirect_request(mock.Mock(), io.BytesIO(), 302, "redirect", {}, "redacted"))

    def test_exactly_five_mib_is_allowed(self) -> None:
        body = b"x" * http_adapter.MAX_RESPONSE_BYTES
        result = self.client(FakeTransport(FakeResponse(200, body))).fetch_population("POI072", DUMMY_KEY, 10)
        self.assertEqual(len(result.body), http_adapter.MAX_RESPONSE_BYTES)

    def test_more_than_five_mib_is_rejected(self) -> None:
        body = b"x" * (http_adapter.MAX_RESPONSE_BYTES + 1)
        with self.assertRaisesRegex(OSError, "응답 크기 제한 초과"):
            self.client(FakeTransport(FakeResponse(200, body))).fetch_population("POI072", DUMMY_KEY, 10)

    def test_error_responses_share_five_mib_limit(self) -> None:
        for status in [302, 400, 500]:
            with self.subTest(status=status):
                body = io.BytesIO(b"x" * (http_adapter.MAX_RESPONSE_BYTES + 1))
                error = http_adapter.HTTPError("redacted", status, "error", {}, body)
                with self.assertRaisesRegex(OSError, "응답 크기 제한 초과"):
                    self.client(FakeTransport(error=error)).fetch_population("POI072", DUMMY_KEY, 10)

    def test_timeout_is_safely_converted(self) -> None:
        with self.assertRaisesRegex(TimeoutError, "^timeout$"):
            self.client(FakeTransport(error=TimeoutError("unsafe detail"))).fetch_population("POI072", DUMMY_KEY, 10)

    def test_dns_error_is_safely_converted(self) -> None:
        error = http_adapter.URLError(OSError("unsafe dns detail"))
        with self.assertRaisesRegex(OSError, "^api_error: 연결 실패$"):
            self.client(FakeTransport(error=error)).fetch_population("POI072", DUMMY_KEY, 10)

    def test_connection_error_is_safely_converted(self) -> None:
        with self.assertRaisesRegex(OSError, "^api_error: 연결 실패$"):
            self.client(FakeTransport(error=OSError("unsafe connection detail"))).fetch_population("POI072", DUMMY_KEY, 10)

    def test_fake_transport_is_called_once(self) -> None:
        transport = FakeTransport()
        self.client(transport).fetch_population("POI072", DUMMY_KEY, 10)
        self.assertEqual(len(transport.calls), 1)

    def test_key_and_completed_url_are_not_exposed(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                self.client(FakeTransport(error=OSError("unsafe"))).fetch_population("POI072", DUMMY_KEY, 10)
            except OSError as error:
                rendered = str(error)
        combined = stdout.getvalue() + stderr.getvalue() + rendered
        self.assertNotIn(DUMMY_KEY, combined)
        self.assertNotIn(http_adapter.BASE_URL, combined)

    def test_fake_path_uses_no_network_and_no_env_loader(self) -> None:
        transport = FakeTransport()
        with (
            mock.patch("socket.create_connection", side_effect=AssertionError("network forbidden")) as create_connection,
            mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")) as connect,
            mock.patch("socket.getaddrinfo", side_effect=AssertionError("network forbidden")) as getaddrinfo,
            mock.patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("HTTP forbidden")) as opener,
            mock.patch("freshmanager.config.load_api_key", side_effect=AssertionError(".env forbidden")) as load_api_key,
        ):
            result = self.client(transport).fetch_population("POI072", DUMMY_KEY, 10)
        self.assertEqual(result.status_code, 200)
        create_connection.assert_not_called()
        connect.assert_not_called()
        getaddrinfo.assert_not_called()
        opener.assert_not_called()
        load_api_key.assert_not_called()

    def test_adapter_integrates_with_collector(self) -> None:
        with tempfile.TemporaryDirectory(prefix="freshmanager-http-adapter-") as temporary:
            root = Path(temporary)
            transport = FakeTransport(FakeResponse(200, SAMPLE_PATH.read_bytes()))
            collector = Collector(
                CSV_PATH,
                self.client(transport),
                FileStorage(root / "raw", root / "metadata"),
                clock=lambda: FIXED_TIME,
                request_id_factory=lambda: FIXED_ID,
            )
            result = collector.collect(DUMMY_KEY)
        self.assertEqual(result.status, "success")
        self.assertEqual(len(transport.calls), 1)


if __name__ == "__main__":
    unittest.main()
