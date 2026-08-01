from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
METADATA = {
    "title",
    "description",
    "default",
    "examples",
    "example",
    "format",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
}
IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


class SchemaError(ValueError):
    pass


def openapi_document() -> Mapping[str, Any]:
    from apps.api.main import app

    return app.openapi()


def _mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{context} must be an object")
    return value


def _check_keys(schema: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unexpected = set(schema) - allowed - METADATA
    if unexpected:
        raise SchemaError(f"{context} has unsupported keyword: {sorted(unexpected)[0]}")


def _literal(value: object, context: str) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            raise SchemaError(f"{context} contains a non-finite literal")
        return json.dumps(value, ensure_ascii=False)
    raise SchemaError(f"{context} contains an unsupported literal")


def _literal_matches_type(value: object, schema_type: object) -> bool:
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "boolean":
        return type(value) is bool
    if schema_type == "integer":
        return type(value) is int
    if schema_type == "number":
        return type(value) in {int, float}
    if schema_type == "null":
        return value is None
    return False


def _property_name(name: object, context: str) -> str:
    if not isinstance(name, str):
        raise SchemaError(f"{context} property name must be a string")
    return name if IDENTIFIER.fullmatch(name) else json.dumps(name, ensure_ascii=False)


def _object_type(
    schema: Mapping[str, Any],
    components: Mapping[str, Any],
    resolving: set[str],
    context: str,
    multiline: bool,
) -> str:
    _check_keys(schema, {"type", "properties", "required", "additionalProperties"}, context)
    properties = _mapping(schema.get("properties"), f"{context}.properties")
    if not properties:
        raise SchemaError(f"{context} is a free-form object")
    additional = schema.get("additionalProperties", False)
    if additional is not False:
        raise SchemaError(f"{context} has unsupported additionalProperties")
    required = schema.get("required", [])
    if not isinstance(required, list) or not all(isinstance(name, str) for name in required):
        raise SchemaError(f"{context}.required must be a string array")
    required_set = set(required)
    if not required_set <= set(properties):
        raise SchemaError(f"{context}.required names an unknown property")

    fields = []
    for name in sorted(properties):
        value = _mapping(properties[name], f"{context}.{name}")
        optional = "" if name in required_set else "?"
        fields.append(
            f"{_property_name(name, context)}{optional}: "
            f"{_type(value, components, resolving, f'{context}.{name}')};"
        )
    if multiline:
        return "{\n" + "\n".join(f"  {field}" for field in fields) + "\n}"
    return "{ " + " ".join(fields) + " }"


def _type(
    schema: Mapping[str, Any],
    components: Mapping[str, Any],
    resolving: set[str],
    context: str,
) -> str:
    if "$ref" in schema:
        _check_keys(schema, {"$ref"}, context)
        reference = schema["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/components/schemas/"):
            raise SchemaError(f"{context} has an unsupported reference")
        name = reference.removeprefix("#/components/schemas/")
        if not name or "/" in name or name not in components:
            raise SchemaError(f"{context} has an unresolved reference")
        if name in resolving:
            raise SchemaError(f"{context} has a circular reference")
        _type(_mapping(components[name], f"component {name}"), components, resolving | {name}, f"component {name}")
        return name

    if "oneOf" in schema or "allOf" in schema or "discriminator" in schema or "patternProperties" in schema:
        raise SchemaError(f"{context} has an unsupported composition")
    if "anyOf" in schema:
        _check_keys(schema, {"anyOf"}, context)
        choices = schema["anyOf"]
        if not isinstance(choices, list) or len(choices) != 2:
            raise SchemaError(f"{context} has an unsupported anyOf")
        rendered = []
        null_count = 0
        for index, choice in enumerate(choices):
            value = _mapping(choice, f"{context}.anyOf[{index}]")
            if value.get("type") == "null":
                _check_keys(value, {"type"}, f"{context}.anyOf[{index}]")
                null_count += 1
                rendered.append("null")
            else:
                rendered.append(_type(value, components, resolving, f"{context}.anyOf[{index}]"))
        if null_count != 1:
            raise SchemaError(f"{context} has an unsupported anyOf")
        return " | ".join(rendered)

    if "enum" in schema:
        _check_keys(schema, {"type", "enum"}, context)
        values = schema["enum"]
        if not isinstance(values, list) or not values:
            raise SchemaError(f"{context} has an invalid enum")
        if not all(_literal_matches_type(value, schema.get("type")) for value in values):
            raise SchemaError(f"{context} enum does not match its type")
        return " | ".join(_literal(value, context) for value in values)
    if "const" in schema:
        _check_keys(schema, {"type", "const"}, context)
        if not _literal_matches_type(schema["const"], schema.get("type")):
            raise SchemaError(f"{context} const does not match its type")
        return _literal(schema["const"], context)

    schema_type = schema.get("type")
    if schema_type == "object":
        return _object_type(schema, components, resolving, context, multiline=False)
    if schema_type == "array":
        _check_keys(schema, {"type", "items"}, context)
        item = _mapping(schema.get("items"), f"{context}.items")
        rendered = _type(item, components, resolving, f"{context}.items")
        return f"({rendered})[]" if " | " in rendered else f"{rendered}[]"
    if schema_type in {"string", "integer", "number"}:
        _check_keys(schema, {"type"}, context)
        return "string" if schema_type == "string" else "number"
    if schema_type == "boolean":
        _check_keys(schema, {"type"}, context)
        return "boolean"
    if schema_type == "null":
        _check_keys(schema, {"type"}, context)
        return "null"
    raise SchemaError(f"{context} has an unknown or missing type")


def generate_types(document: Mapping[str, Any]) -> str:
    components = _mapping(_mapping(document.get("components"), "components").get("schemas"), "components.schemas")
    if set(components) != set(COMPONENTS):
        raise SchemaError("components.schemas does not match the approved component set")

    blocks = ["// Generated from FastAPI OpenAPI. Do not edit manually."]
    for name in COMPONENTS:
        schema = _mapping(components[name], f"component {name}")
        if schema.get("type") != "object":
            raise SchemaError(f"component {name} must be an object")
        body = _object_type(schema, components, {name}, f"component {name}", multiline=True)
        blocks.append(f"export type {name} = {body};")
    return "\n\n".join(blocks) + "\n"


def write_or_check(output: Path, check: bool) -> bool:
    generated = generate_types(openapi_document()).encode("utf-8")
    if check:
        try:
            return output.read_bytes() == generated
        except FileNotFoundError:
            return False
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(generated)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        matches = write_or_check(args.output, args.check)
    except (OSError, SchemaError, TypeError, ValueError) as error:
        print(f"OpenAPI type generation failed: {error}", file=sys.stderr)
        return 1
    if args.check and not matches:
        print("Generated API types are missing or out of date.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
