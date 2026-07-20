from __future__ import annotations

import argparse
import io
import json
import socket
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from freshmanager import live
from freshmanager.collector import METADATA_FIELDS


SAMPLE_PATH = Path("data/samples/population_yeouido_sample.json")
DUMMY_KEY = "dummy-live-key-for-tests"
ENV_NAME = "SEOUL_OPEN" + "_API_KEY"


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.body) - self.offset
        chunk = self.body[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk

    def close(self) -> None:
        return None


class FakeTransport:
    def __init__(self, body: bytes, *, error: BaseException | None = None) -> None:
        self.body = body
        self.error = error
        self.calls: list[tuple[object, float]] = []

    def open(self, request: object, timeout_seconds: float) -> FakeResponse:
        self.calls.append((request, timeout_seconds))
        if self.error is not None:
            raise self.error
        return FakeResponse(self.body)


class LiveCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample = SAMPLE_PATH.read_bytes()

    @staticmethod
    def _write_env(directory: Path, value: str = DUMMY_KEY) -> Path:
        path = directory / "dummy.env"
        path.write_text(f"{ENV_NAME}={value}\n", encoding="utf-8")
        return path

    @staticmethod
    def _invoke(argv: list[str], **kwargs: object) -> tuple[int, str]:
        output = io.StringIO()
        errors = io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = live.run(argv, **kwargs)  # type: ignore[arg-type]
        return code, output.getvalue() + errors.getvalue()

    def test_missing_execute_live_has_no_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env_path = root / "must-not-be-read.env"
            output_root = root / "must-not-exist"
            transport_factory = mock.Mock(side_effect=AssertionError("transport factory called"))
            storage_factory = mock.Mock(side_effect=AssertionError("storage factory called"))
            with (
                mock.patch("freshmanager.live.load_api_key", side_effect=AssertionError("env read")) as loader,
                mock.patch.object(
                    live.Collector,
                    "prepare_request",
                    side_effect=AssertionError("request prepared"),
                ) as prepare_request,
                mock.patch(
                    "freshmanager.http_adapter.build_population_request",
                    side_effect=AssertionError("request created"),
                ) as request_builder,
            ):
                code, output = self._invoke(
                    ["--env-file", str(env_path), "--output-root", str(output_root)],
                    transport_factory=transport_factory,
                    storage_factory=storage_factory,
                )
            self.assertEqual(code, 2)
            self.assertEqual(output.strip(), "execution_not_approved: --execute-live 옵션이 필요합니다")
            self.assertNotIn(str(env_path), output)
            self.assertNotIn(str(output_root), output)
            loader.assert_not_called()
            prepare_request.assert_not_called()
            request_builder.assert_not_called()
            transport_factory.assert_not_called()
            storage_factory.assert_not_called()
            self.assertFalse(output_root.exists())

    def test_dummy_env_and_fake_transport_succeed_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env_path = self._write_env(root)
            output_root = root / "output"
            transport = FakeTransport(self.sample)
            code, output = self._invoke(
                [
                    "--env-file",
                    str(env_path),
                    "--output-root",
                    str(output_root),
                    "--execute-live",
                ],
                transport_factory=lambda: transport,
            )
            self.assertEqual(code, 0)
            self.assertIn("collection_status=success", output)
            self.assertEqual(len(transport.calls), 1)
            request, timeout = transport.calls[0]
            self.assertEqual(timeout, 10.0)
            full_url = str(getattr(request, "full_url", ""))
            self.assertTrue(full_url.endswith("/json/citydata_ppltn/1/5/POI072"), "endpoint mismatch")
            self.assertNotIn(DUMMY_KEY, output)
            self.assertNotIn("http://", output)
            self.assertNotIn("Request", output)

    def test_success_connects_raw_and_exact_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env_path = self._write_env(root)
            output_root = root / "output"
            code, _ = self._invoke(
                ["--env-file", str(env_path), "--output-root", str(output_root), "--execute-live"],
                transport_factory=lambda: FakeTransport(self.sample),
            )
            self.assertEqual(code, 0)
            raw_files = list((output_root / "data/raw/population").rglob("*.json"))
            metadata_files = list((output_root / "data/processed/collection_logs").rglob("*.metadata.json"))
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(len(metadata_files), 1)
            self.assertEqual(raw_files[0].read_bytes(), self.sample)
            metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
            self.assertEqual(tuple(metadata), METADATA_FIELDS)
            self.assertEqual(metadata["area_code"], "POI072")
            self.assertEqual(metadata["endpoint_name"], "citydata_ppltn")
            self.assertEqual(metadata["collection_status"], "success")
            self.assertEqual(Path(metadata["raw_file_path"]).resolve(), raw_files[0].resolve())

    def test_configuration_errors_store_safe_metadata_without_transport(self) -> None:
        cases = {
            "missing_file": None,
            "missing_key": "OTHER=value\n",
            "empty_key": f"{ENV_NAME}=   \n",
        }
        for name, contents in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                env_path = root / "dummy.env"
                if contents is not None:
                    env_path.write_text(contents, encoding="utf-8")
                output_root = root / "output"
                transport_factory = mock.Mock(side_effect=AssertionError("transport factory called"))
                code, output = self._invoke(
                    ["--env-file", str(env_path), "--output-root", str(output_root), "--execute-live"],
                    transport_factory=transport_factory,
                )
                self.assertEqual(code, 1)
                self.assertIn("collection_status=config_error", output)
                self.assertNotIn(str(env_path), output)
                transport_factory.assert_not_called()
                self.assertFalse((output_root / "data/raw/population").exists())
                metadata_files = list(
                    (output_root / "data/processed/collection_logs").rglob("*.metadata.json")
                )
                self.assertEqual(len(metadata_files), 1)
                metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
                self.assertEqual(tuple(metadata), METADATA_FIELDS)
                self.assertEqual(metadata["collection_status"], "config_error")
                self.assertIsNone(metadata["raw_file_path"])

    def test_timeout_default_and_upper_bound_are_forwarded(self) -> None:
        for value, expected in [(None, 10.0), ("60", 60.0)]:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                env_path = self._write_env(root)
                transport = FakeTransport(self.sample)
                argv = ["--env-file", str(env_path), "--output-root", str(root / "output"), "--execute-live"]
                if value is not None:
                    argv.extend(["--timeout", value])
                code, _ = self._invoke(argv, transport_factory=lambda: transport)
                self.assertEqual(code, 0)
                self.assertEqual(transport.calls[0][1], expected)

    def test_invalid_timeouts_are_input_errors_without_output(self) -> None:
        for value in ["0", "-1", "60.1", "nan", "inf", "invalid"]:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                output_root = root / "output"
                code, output = self._invoke(
                    [
                        "--env-file",
                        str(root / "unused.env"),
                        "--output-root",
                        str(output_root),
                        "--timeout",
                        value,
                        "--execute-live",
                    ]
                )
                self.assertEqual(code, 2)
                self.assertEqual(output.strip(), "input_error: 실행 옵션을 확인하세요")
                self.assertFalse(output_root.exists())

    def test_area_code_option_is_not_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_root = root / "output"
            code, output = self._invoke(
                [
                    "--env-file",
                    str(root / "unused.env"),
                    "--output-root",
                    str(output_root),
                    "--area-code",
                    "POI001",
                    "--execute-live",
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(output.strip(), "input_error: 실행 옵션을 확인하세요")
            self.assertFalse(output_root.exists())

    def test_protected_output_roots_are_rejected_without_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project_root = Path(temporary) / "project"
            candidates = [
                project_root / ".git",
                project_root / "work log" / "nested",
                project_root / "data/reference",
                project_root / "data/samples/nested",
                project_root / "tests/fixtures",
            ]
            with mock.patch("freshmanager.live.PROJECT_ROOT", project_root):
                for candidate in candidates:
                    with self.subTest(candidate=candidate.name):
                        code, output = self._invoke(
                            [
                                "--env-file",
                                str(project_root / "unused.env"),
                                "--output-root",
                                str(candidate),
                                "--execute-live",
                            ]
                        )
                        self.assertEqual(code, 2)
                        self.assertEqual(output.strip(), "input_error: 안전한 출력 경로를 지정해야 합니다")
                        self.assertFalse(candidate.exists())

    def test_existing_regular_file_is_rejected_as_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_file = root / "not-a-directory"
            output_file.write_text("unchanged", encoding="utf-8")
            code, output = self._invoke(
                [
                    "--env-file",
                    str(root / "unused.env"),
                    "--output-root",
                    str(output_file),
                    "--execute-live",
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(output.strip(), "input_error: 안전한 출력 경로를 지정해야 합니다")
            self.assertNotIn(str(output_file), output)
            self.assertEqual(output_file.read_text(encoding="utf-8"), "unchanged")

    def test_timeout_is_recorded_without_exception_details(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env_path = self._write_env(root)
            transport = FakeTransport(self.sample, error=TimeoutError("sensitive timeout detail"))
            code, output = self._invoke(
                ["--env-file", str(env_path), "--output-root", str(root / "output"), "--execute-live"],
                transport_factory=lambda: transport,
            )
            self.assertEqual(code, 1)
            self.assertIn("collection_status=timeout", output)
            self.assertNotIn("sensitive", output)
            self.assertEqual(len(transport.calls), 1)

    def test_unexpected_internal_error_is_fixed_and_non_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env_path = self._write_env(root)
            secret_detail = "do-not-print-this-detail"
            code, output = self._invoke(
                ["--env-file", str(env_path), "--output-root", str(root / "output"), "--execute-live"],
                transport_factory=mock.Mock(side_effect=RuntimeError(secret_detail)),
            )
            self.assertEqual(code, 3)
            self.assertEqual(output.strip(), "internal_error: 실행을 안전하게 완료하지 못했습니다")
            self.assertNotIn(secret_detail, output)
            self.assertNotIn(DUMMY_KEY, output)

    def test_fake_execution_never_uses_dns_socket_or_http(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env_path = self._write_env(root)
            transport = FakeTransport(self.sample)
            with (
                mock.patch("socket.create_connection", side_effect=AssertionError("network forbidden")) as create,
                mock.patch.object(
                    socket.socket,
                    "connect",
                    side_effect=AssertionError("network forbidden"),
                ) as connect,
                mock.patch("socket.getaddrinfo", side_effect=AssertionError("network forbidden")) as dns,
                mock.patch(
                    "freshmanager.http_adapter.UrllibTransport.open",
                    side_effect=AssertionError("http forbidden"),
                ) as http_open,
            ):
                code, _ = self._invoke(
                    ["--env-file", str(env_path), "--output-root", str(root / "output"), "--execute-live"],
                    transport_factory=lambda: transport,
                )
            self.assertEqual(code, 0)
            create.assert_not_called()
            connect.assert_not_called()
            dns.assert_not_called()
            http_open.assert_not_called()

    def test_imported_module_and_parser_creation_do_not_connect(self) -> None:
        with (
            mock.patch("socket.create_connection", side_effect=AssertionError("network forbidden")) as create,
            mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")) as connect,
            mock.patch("socket.getaddrinfo", side_effect=AssertionError("network forbidden")) as dns,
            mock.patch(
                "freshmanager.http_adapter.UrllibTransport.open",
                side_effect=AssertionError("http forbidden"),
            ) as http_open,
        ):
            parser = live.build_parser()
        self.assertIsInstance(parser, argparse.ArgumentParser)
        create.assert_not_called()
        connect.assert_not_called()
        dns.assert_not_called()
        http_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
