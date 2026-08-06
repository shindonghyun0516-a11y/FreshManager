from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apps.api.main import app


ROOT = Path(__file__).resolve().parents[3]
EXPORTER = ROOT / "scripts" / "export_web_openapi.py"
GENERATOR = ROOT / "scripts" / "generate_web_api_types.py"
COMPONENTS = (
    "HealthResponse",
    "ErrorDetail",
    "ErrorResponse",
    "AreaListItem",
    "AreasResponse",
    "PopulationRange",
    "AreaPilotData",
    "SpotOption",
    "AreaPilotResponse",
)


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class WebApiTypeGenerationTests(unittest.TestCase):
    def require_scripts(self) -> None:
        self.assertTrue(EXPORTER.is_file(), "OpenAPI exporter script is missing")
        self.assertTrue(GENERATOR.is_file(), "OpenAPI type generator script is missing")

    def generator(self):
        self.require_scripts()
        return load_script(GENERATOR, "web_api_type_generator_for_test")

    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_generated_types_are_deterministic_and_closed(self) -> None:
        generator = self.generator()
        document = app.openapi()
        first = generator.generate_types(document)
        second = generator.generate_types(document)

        self.assertEqual(first, second)  # 1. same input -> same bytes
        self.assertIn("Generated from FastAPI OpenAPI", first)  # 2. header
        self.assertIn("Do not edit manually", first)
        self.assertEqual(
            [line.removeprefix("export type ").removesuffix(" = {")
             for line in first.splitlines() if line.startswith("export type ")],
            list(COMPONENTS),
        )  # 3. exact nine components and order
        self.assertIn("export type ErrorDetail =", first)  # 4. errors
        self.assertIn("export type ErrorResponse =", first)
        self.assertIn(
            'prototype_data_status: "PROTOTYPE" | "SPOT_PROTOTYPE_DATA_UNAVAILABLE";',
            first,
        )  # 5. SpotOption literal union
        self.assertIn("area_auto_recommendation: false;", first)  # 6. boolean const
        self.assertIn("string | null", first)  # 7. nullable anyOf
        self.assertIn("source: string | null;", first)  # 8. required nullable field
        self.assertIn("area: AreaPilotData;", first)  # 9. ref
        self.assertIn("areas: AreaListItem[];", first)  # 10. array
        self.assertNotRegex(first, r"\b(?:any|unknown)\b")  # 15. no fallback types
        self.assertNotRegex(first, r"\d{4}-\d{2}-\d{2}")  # 13. no timestamp
        self.assertNotIn(str(ROOT), first)  # 14. no absolute path

        for mutation in ("extra", "missing"):
            with self.subTest(component_set=mutation):
                altered = json.loads(json.dumps(document))
                schemas = altered["components"]["schemas"]
                if mutation == "extra":
                    schemas["Unexpected"] = {"type": "string"}
                else:
                    del schemas["HealthResponse"]
                with self.assertRaises(generator.SchemaError):
                    generator.generate_types(altered)

    def test_supports_closed_objects_and_ignored_metadata(self) -> None:
        generator = self.generator()
        document = {
            "components": {
                "schemas": {
                    name: {
                        "type": "object",
                        "additionalProperties": False,
                        "title": name,
                        "description": "ignored",
                        "properties": {
                            "required_value": {
                                "type": "string",
                                "format": "date-time",
                                "minLength": 1,
                                "examples": ["value"],
                            },
                            "optional_value": {
                                "type": "integer",
                                "minimum": 0,
                                "default": 1,
                            },
                        },
                        "required": ["required_value"],
                    }
                    for name in COMPONENTS
                }
            }
        }

        generated = generator.generate_types(document)
        self.assertIn("required_value: string;", generated)
        self.assertIn("optional_value?: number;", generated)

    def test_write_check_and_drift_modes(self) -> None:
        self.require_scripts()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "generated" / "api-types.ts"
            write = self.run_script(GENERATOR, "--output", str(output))
            self.assertEqual(write.returncode, 0, write.stderr)
            self.assertEqual({path for path in root.rglob("*") if path.is_file()}, {output})
            expected = output.read_bytes()

            check = self.run_script(GENERATOR, "--output", str(output), "--check")
            self.assertEqual(check.returncode, 0, check.stderr)  # 11. check pass
            self.assertEqual(output.read_bytes(), expected)  # 12. check never writes

            output.write_bytes(expected + b"// drift\n")
            drifted = output.read_bytes()
            drift = self.run_script(GENERATOR, "--output", str(output), "--check")
            self.assertNotEqual(drift.returncode, 0)  # 12. drift fails
            self.assertEqual(output.read_bytes(), drifted)  # 12. still no write

    def test_rejects_every_unsupported_schema_form(self) -> None:
        generator = self.generator()
        base = {"components": {"schemas": {name: {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]} for name in COMPONENTS}}}
        cases = {
            "oneOf": {"oneOf": [{"type": "string"}, {"type": "number"}]},  # 16
            "complex anyOf": {"anyOf": [{"type": "string"}, {"type": "number"}]},  # 17
            "bad reference": {"$ref": "#/components/schemas/Missing"},  # 18
            "free form object": {"type": "object", "additionalProperties": True},  # 19
            "circular reference": {"$ref": "#/components/schemas/HealthResponse"},  # 20
        }
        for label, field_schema in cases.items():
            with self.subTest(label=label):
                document = json.loads(json.dumps(base))
                if label == "circular reference":
                    document["components"]["schemas"]["HealthResponse"] = field_schema
                else:
                    document["components"]["schemas"]["HealthResponse"]["properties"]["id"] = field_schema
                with self.assertRaises(generator.SchemaError):
                    generator.generate_types(document)

        for label, field_schema in {
            "allOf": {"allOf": [{"type": "string"}]},
            "discriminator": {"type": "string", "discriminator": {"propertyName": "kind"}},
            "pattern properties": {"type": "object", "properties": {"id": {"type": "string"}}, "patternProperties": {}},
            "object map": {"type": "object", "additionalProperties": {"type": "string"}},
            "unknown type": {"type": "date"},
            "unknown const type": {"type": "date", "const": "value"},
            "empty object": {"type": "object"},
            "unknown keyword": {"type": "string", "not": {}},
        }.items():
            with self.subTest(label=label):
                document = json.loads(json.dumps(base))
                document["components"]["schemas"]["HealthResponse"]["properties"]["id"] = field_schema
                with self.assertRaises(generator.SchemaError):
                    generator.generate_types(document)

    def test_export_and_generation_have_no_runtime_side_effects(self) -> None:
        self.require_scripts()
        exporter = load_script(EXPORTER, "web_openapi_exporter_for_test")
        generator = self.generator()
        original_service = getattr(app.state, "pilot_service", None)

        class ForbiddenProvider:
            def __getattr__(self, _name: str):
                raise AssertionError("runtime provider must not run")

        app.state.pilot_service = ForbiddenProvider()
        try:
            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")), mock.patch.object(socket, "socket", side_effect=AssertionError("network")), mock.patch.object(Path, "read_text", side_effect=AssertionError("artifact read")), mock.patch.object(Path, "read_bytes", side_effect=AssertionError("artifact read")):
                generated = generator.generate_types(app.openapi())
                self.assertIn("export type HealthResponse", generated)  # 22-24
                with tempfile.TemporaryDirectory() as directory:
                    exporter.export_openapi(Path(directory) / "openapi.json")
        finally:
            if original_service is None:
                del app.state.pilot_service
            else:
                app.state.pilot_service = original_service

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            export_output = root / "openapi.json"
            export = self.run_script(EXPORTER, "--output", str(export_output))
            self.assertEqual(export.returncode, 0, export.stderr)
            self.assertEqual(set(root.iterdir()), {export_output})  # 21. only output write
            document = json.loads(export_output.read_text(encoding="utf-8"))
            self.assertEqual(document, app.openapi())
            self.assertTrue(export_output.read_bytes().endswith(b"\n"))


if __name__ == "__main__":
    unittest.main()
