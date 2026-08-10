import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app


class HealthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app, raise_server_exceptions=False)

    def test_app_imports_without_business_modules(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; from apps.api.main import app; "
                    "assert not any(name == 'freshmanager' or "
                    "name.startswith('freshmanager.') for name in sys.modules)"
                ),
            ],
            cwd=Path(__file__).resolve().parents[3],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_health_returns_stable_schema(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "service": "freshmanager-api"},
        )
        self.assertTrue(response.headers["content-type"].startswith("application/json"))

        schema = self.client.get("/openapi.json").json()
        response_schema = schema["paths"]["/api/v1/health"]["get"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]
        self.assertEqual(
            response_schema,
            {"$ref": "#/components/schemas/HealthResponse"},
        )

    def test_health_request_writes_no_files(self) -> None:
        previous_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            temporary_directory = Path(directory)
            os.chdir(temporary_directory)
            try:
                before = set(temporary_directory.rglob("*"))
                response = self.client.get("/api/v1/health")
                after = set(temporary_directory.rglob("*"))
            finally:
                os.chdir(previous_directory)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(after, before)

    def test_unknown_route_uses_bounded_error(self) -> None:
        response = self.client.get("/api/v1/not-found")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "요청한 API 경로를 찾을 수 없습니다.",
                }
            },
        )
        serialized = json.dumps(response.json(), ensure_ascii=False).lower()
        for forbidden in ("traceback", ".env", "secret", "/users/", "\\users\\"):
            self.assertNotIn(forbidden, serialized)

    def test_unexpected_error_hides_exception_text(self) -> None:
        path = "/api/v1/test-only-error"

        def raise_test_error() -> None:
            raise RuntimeError("sensitive exception detail")

        app.add_api_route(path, raise_test_error, include_in_schema=False)
        try:
            response = self.client.get(path)
        finally:
            app.router.routes = [
                route for route in app.router.routes if getattr(route, "path", None) != path
            ]

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "요청을 처리할 수 없습니다.",
                }
            },
        )
        self.assertNotIn("sensitive exception detail", response.text)


if __name__ == "__main__":
    unittest.main()
