from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any


class NativeToolSchemaError(ValueError):
    pass


class NativeToolArgumentsError(NativeToolSchemaError):
    pass


_SUPPORTED = {
    "type", "properties", "required", "enum", "const", "items",
    "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems",
    "description", "additionalProperties", "default", "format",
}
_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class NativeToolEntry:
    name: str
    provider_id: str
    operation_id: str
    canonical_schema: dict[str, Any]
    openai_schema: dict[str, Any]
    optional_paths: frozenset[tuple[str, ...]]
    nullable_paths: frozenset[tuple[str, ...]]


@dataclass(frozen=True)
class NativeToolRegistry:
    entries: dict[str, NativeToolEntry]

    def resolve(self, name: str) -> NativeToolEntry:
        try:
            return self.entries[name]
        except KeyError as exc:
            raise NativeToolSchemaError(f"Unknown native tool: {name}") from exc

    def resolve_operation(
        self, provider_id: str, operation_id: str
    ) -> NativeToolEntry:
        matches = [
            entry
            for entry in self.entries.values()
            if entry.provider_id == provider_id
            and entry.operation_id == operation_id
        ]
        if len(matches) != 1:
            raise NativeToolSchemaError(
                f"Unknown operation: {provider_id}.{operation_id}"
            )
        return matches[0]


def compile_registry(catalog: dict[str, Any]) -> NativeToolRegistry:
    entries: dict[str, NativeToolEntry] = {}
    for provider in catalog.get("providers", []):
        provider_id = provider.get("provider_id")
        for operation in provider.get("operations", []):
            if operation.get("availability") != "implemented":
                continue
            operation_id = operation.get("operation_id")
            schema = operation.get("input_schema")
            if not all(isinstance(value, str) and value for value in (provider_id, operation_id)):
                raise NativeToolSchemaError("Catalog operation identifiers must be strings")
            if not isinstance(schema, dict):
                raise NativeToolSchemaError(f"{provider_id}.{operation_id}: input_schema must be an object")
            optional: set[tuple[str, ...]] = set()
            nullable: set[tuple[str, ...]] = set()
            compiled = _compile_node(schema, provider_id, operation_id, ("$",), optional, nullable)
            name = _tool_name(provider_id, operation_id)
            if name in entries:
                raise NativeToolSchemaError(f"Native tool name collision: {name}")
            entries[name] = NativeToolEntry(
                name=name,
                provider_id=provider_id,
                operation_id=operation_id,
                canonical_schema=deepcopy(schema),
                openai_schema=compiled,
                optional_paths=frozenset(optional),
                nullable_paths=frozenset(nullable),
            )
    return NativeToolRegistry(entries)


def normalize_arguments(value: Any, entry: NativeToolEntry) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NativeToolArgumentsError("Operation arguments must be an object")
    normalized = deepcopy(value)
    _drop_optional_nulls(normalized, entry, ("$",))
    _validate_node(entry.canonical_schema, normalized, entry.provider_id, entry.operation_id, ("$",))
    return normalized


def _tool_name(provider_id: str, operation_id: str) -> str:
    raw = f"jarvis__{provider_id}__{operation_id}"
    name = re.sub(r"[^A-Za-z0-9_-]", "_", raw)
    if len(name) > 64:
        digest = hashlib.sha256(raw.encode()).hexdigest()[:10]
        name = f"{name[:53]}_{digest}"
    if not _NAME_RE.fullmatch(name):
        raise NativeToolSchemaError(f"Invalid generated tool name for {provider_id}.{operation_id}")
    return name


def _compile_node(node: Any, provider_id: str, operation_id: str, path: tuple[str, ...], optional: set[tuple[str, ...]], nullable: set[tuple[str, ...]]) -> dict[str, Any]:
    if not isinstance(node, dict):
        _fail(provider_id, operation_id, path, "schema node must be an object")
    unsupported = sorted(set(node) - _SUPPORTED)
    if unsupported:
        _fail(provider_id, operation_id, path, f"unsupported keyword: {unsupported[0]}")
    result = deepcopy(node)
    result.pop("default", None)
    types = _types(node.get("type"), provider_id, operation_id, path)
    if "null" in types:
        nullable.add(path)
    if "object" in types:
        properties = node.get("properties", {})
        required = node.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            _fail(provider_id, operation_id, path, "invalid object schema")
        if set(required) - set(properties):
            _fail(provider_id, operation_id, path, "required property is undefined")
        compiled_properties = {}
        for name, child in properties.items():
            child_path = (*path, name)
            compiled = _compile_node(child, provider_id, operation_id, child_path, optional, nullable)
            if name not in required:
                optional.add(child_path)
                child_types = compiled["type"] if isinstance(compiled["type"], list) else [compiled["type"]]
                compiled["type"] = child_types if "null" in child_types else [*child_types, "null"]
                if "enum" in compiled and None not in compiled["enum"]:
                    compiled["enum"] = [*compiled["enum"], None]
                if "const" in compiled:
                    compiled["enum"] = [compiled.pop("const"), None]
            compiled_properties[name] = compiled
        result["properties"] = compiled_properties
        result["required"] = list(properties)
        result["additionalProperties"] = False
    elif "array" in types:
        if "items" not in node:
            _fail(provider_id, operation_id, path, "array requires items")
        result["items"] = _compile_node(node["items"], provider_id, operation_id, (*path, "[]"), optional, nullable)
    return result


def _drop_optional_nulls(value: Any, entry: NativeToolEntry, path: tuple[str, ...]) -> None:
    if isinstance(value, dict):
        for key in list(value):
            child = (*path, key)
            if value[key] is None and child in entry.optional_paths and child not in entry.nullable_paths:
                del value[key]
            else:
                _drop_optional_nulls(value[key], entry, child)
    elif isinstance(value, list):
        for item in value:
            _drop_optional_nulls(item, entry, (*path, "[]"))


def _validate_node(schema: dict[str, Any], value: Any, provider_id: str, operation_id: str, path: tuple[str, ...]) -> None:
    types = _types(schema.get("type"), provider_id, operation_id, path)
    if not _matches(value, types):
        _fail(provider_id, operation_id, path, "argument type does not match schema")
    if value is None:
        return
    if "enum" in schema and value not in schema["enum"]:
        _fail(provider_id, operation_id, path, "value is not in enum")
    if "const" in schema and value != schema["const"]:
        _fail(provider_id, operation_id, path, "value does not match const")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        unknown = set(value) - set(properties)
        if unknown:
            _fail(provider_id, operation_id, path, f"unknown property: {sorted(unknown)[0]}")
        for name in schema.get("required", []):
            if name not in value:
                _fail(provider_id, operation_id, (*path, name), "required property is missing")
        for name, child in value.items():
            _validate_node(properties[name], child, provider_id, operation_id, (*path, name))
    elif isinstance(value, list):
        _bounds(schema, len(value), "minItems", "maxItems", provider_id, operation_id, path)
        for item in value:
            _validate_node(schema["items"], item, provider_id, operation_id, (*path, "[]"))
    elif isinstance(value, str):
        _bounds(schema, len(value), "minLength", "maxLength", provider_id, operation_id, path)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        _bounds(schema, value, "minimum", "maximum", provider_id, operation_id, path)


def _bounds(schema: dict[str, Any], value: float, minimum: str, maximum: str, provider_id: str, operation_id: str, path: tuple[str, ...]) -> None:
    if minimum in schema and value < schema[minimum]:
        _fail(provider_id, operation_id, path, f"{minimum} constraint failed")
    if maximum in schema and value > schema[maximum]:
        _fail(provider_id, operation_id, path, f"{maximum} constraint failed")


def _types(value: Any, provider_id: str, operation_id: str, path: tuple[str, ...]) -> list[str]:
    values = value if isinstance(value, list) else [value]
    if not values or any(item not in _TYPES for item in values):
        _fail(provider_id, operation_id, path, "unsupported or missing type")
    return list(values)


def _matches(value: Any, types: list[str]) -> bool:
    return any({
        "null": value is None, "object": isinstance(value, dict),
        "array": isinstance(value, list), "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
    }[kind] for kind in types)


def _fail(provider_id: str, operation_id: str, path: tuple[str, ...], reason: str) -> None:
    raise NativeToolArgumentsError(f"{provider_id}.{operation_id} {'.'.join(path)}: {reason}")
