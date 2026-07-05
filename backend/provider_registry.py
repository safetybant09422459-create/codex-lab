from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import ROOT_DIR, SKILLS_DIR, TOOLS_DIR
from .domain_provider import DomainProvider, ProviderOperationSpec


class ProviderRegistryError(Exception):
    pass


class ProviderNotFoundError(ProviderRegistryError):
    pass


class OperationNotFoundError(ProviderRegistryError):
    pass


class OperationNotExecutableError(ProviderRegistryError):
    pass


@dataclass(frozen=True)
class OperationDefinition:
    provider_id: str
    operation_id: str
    description: str
    what_it_can_do: str
    what_it_cannot_do: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    mode: str
    risk_level: str
    confirmation_required: bool
    audit_required: bool
    examples: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...]
    availability: str
    tool_id: str | None

    def catalog_entry(self) -> dict[str, Any]:
        return asdict(self)


class ProviderRegistry:
    """Discovers providers and projects Tool JSON into an agent-facing catalog."""

    def __init__(
        self, tools_dir: Path = TOOLS_DIR, skills_dir: Path = SKILLS_DIR
    ) -> None:
        self.tools_dir = tools_dir
        self.skills_dir = skills_dir
        self._providers: dict[str, DomainProvider] = {}
        self._operations: dict[tuple[str, str], OperationDefinition] = {}

    def register(self, provider: DomainProvider) -> None:
        provider_id = provider.provider_id
        if not provider_id or provider_id in self._providers:
            raise ProviderRegistryError(f"Provider already registered: {provider_id}")
        definitions = self._build_definitions(provider)
        self._providers[provider_id] = provider
        for definition in definitions:
            self._operations[(provider_id, definition.operation_id)] = definition

    def get_provider(self, provider_id: str) -> DomainProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise ProviderNotFoundError(f"Provider not found: {provider_id}") from exc

    def get_operation(
        self, provider_id: str, operation_id: str, *, executable: bool = False
    ) -> OperationDefinition:
        self.get_provider(provider_id)
        try:
            operation = self._operations[(provider_id, operation_id)]
        except KeyError as exc:
            raise OperationNotFoundError(
                f"Operation not found: {provider_id}.{operation_id}"
            ) from exc
        if executable and operation.availability != "implemented":
            raise OperationNotExecutableError(
                f"Operation is not executable: {provider_id}.{operation_id} "
                f"({operation.availability})"
            )
        return operation

    def catalog(self) -> dict[str, Any]:
        return {
            "contract_version": "1",
            "providers": [
                {
                    "provider_id": provider_id,
                    "operations": [
                        operation.catalog_entry()
                        for operation in self._operations.values()
                        if operation.provider_id == provider_id
                    ],
                }
                for provider_id in sorted(self._providers)
            ],
        }

    def capability_catalog(self) -> dict[str, Any]:
        """Return provider-owned human-facing descriptions without selecting them."""
        providers: list[dict[str, Any]] = []
        for skill_file in sorted(self.skills_dir.glob("*/skill.json")):
            data = self._load_json(skill_file, "skill definition")
            provider_id = data.get("id")
            if not provider_id:
                continue
            capabilities = data.get("capabilities")
            if not isinstance(capabilities, list) or not capabilities:
                capabilities = [
                    {
                        "id": "description_unavailable",
                        "description": "User-facing capability descriptions are not declared.",
                    }
                ]
            providers.append(
                {
                    "provider_id": str(provider_id),
                    "name": data.get("name"),
                    "status": data.get("status"),
                    "registered": provider_id in self._providers,
                    "capabilities": capabilities,
                }
            )
        return {"contract_version": "1", "providers": providers}

    def _build_definitions(
        self, provider: DomainProvider
    ) -> tuple[OperationDefinition, ...]:
        tool_data = self._load_tools(provider.provider_id)
        definitions: list[OperationDefinition] = []
        seen: set[str] = set()
        for spec in provider.operation_specs():
            if spec.operation_id in seen:
                raise ProviderRegistryError(
                    f"Duplicate operation: {provider.provider_id}.{spec.operation_id}"
                )
            seen.add(spec.operation_id)
            tool = tool_data.get(spec.operation_id)
            definitions.append(self._definition(provider.provider_id, spec, tool))
        return tuple(definitions)

    def _definition(
        self,
        provider_id: str,
        spec: ProviderOperationSpec,
        tool: dict[str, Any] | None,
    ) -> OperationDefinition:
        if spec.availability == "implemented" and tool is None:
            raise ProviderRegistryError(
                f"Implemented operation has no Tool JSON: {provider_id}.{spec.operation_id}"
            )
        if tool is not None:
            input_schema = tool.get("input_schema") or {
                "type": "object",
                "properties": {},
            }
            output_schema = tool.get("output_schema") or spec.output_schema or {
                "type": "object"
            }
            mode = tool.get("mode")
            risk_level = tool.get("risk_level")
            confirmation_required = bool(
                tool.get("confirmation_required", risk_level == "high")
            )
            audit_required = bool(
                tool.get(
                    "audit_required",
                    risk_level in {"medium", "high"}
                    or mode in {"write", "mixed", "action"},
                )
            )
            description = tool.get("description") or spec.description
        else:
            input_schema = spec.input_schema or {"type": "object", "properties": {}}
            output_schema = spec.output_schema or {"type": "object"}
            mode = spec.mode
            risk_level = spec.risk_level
            confirmation_required = spec.confirmation_required
            audit_required = False
            description = spec.description
        if not all((description, mode, risk_level)) or confirmation_required is None:
            raise ProviderRegistryError(
                f"Incomplete operation metadata: {provider_id}.{spec.operation_id}"
            )
        return OperationDefinition(
            provider_id=provider_id,
            operation_id=spec.operation_id,
            description=str(description),
            what_it_can_do=spec.what_it_can_do,
            what_it_cannot_do=spec.what_it_cannot_do,
            input_schema=input_schema,
            output_schema=output_schema,
            mode=str(mode),
            risk_level=str(risk_level),
            confirmation_required=confirmation_required,
            audit_required=audit_required,
            examples=spec.examples,
            limitations=spec.limitations,
            availability=spec.availability,
            tool_id=spec.operation_id if tool is not None else None,
        )

    def _load_tools(self, provider_id: str) -> dict[str, dict[str, Any]]:
        tools: dict[str, dict[str, Any]] = {}
        for tool_file in sorted(self.tools_dir.glob("*/*.json")):
            data = self._load_json(tool_file, "tool definition")
            if data.get("skill_id") == provider_id:
                tools[data.get("id", "")] = data
        return tools

    @staticmethod
    def _load_json(path: Path, kind: str) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            try:
                relative_path = path.relative_to(ROOT_DIR)
            except ValueError:
                relative_path = path
            raise ProviderRegistryError(f"Invalid {kind}: {relative_path}") from exc
