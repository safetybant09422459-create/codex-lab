from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .domain_provider import DomainProvider, OperationContext, ProviderOperationSpec
from .executors import BaseExecutor


class JarvisProvider(DomainProvider):
    """Deterministic, read-only view of Jarvis runtime capabilities."""

    provider_id = "jarvis"

    def __init__(
        self,
        catalog_supplier: Callable[[], dict[str, Any]],
        capability_catalog_supplier: Callable[[], dict[str, Any]],
    ) -> None:
        self._catalog_supplier = catalog_supplier
        self._capability_catalog_supplier = capability_catalog_supplier

    def operation_specs(self) -> tuple[ProviderOperationSpec, ...]:
        return (
            ProviderOperationSpec(
                operation_id="get_capabilities",
                what_it_can_do=(
                    "Return structured facts about currently declared Jarvis "
                    "providers, operations, capabilities, planned features, and "
                    "limitations."
                ),
                what_it_cannot_do=(
                    "It cannot change state, enable features, interpret user "
                    "intent, or compose a conversational answer."
                ),
                examples=({"arguments": {}},),
                limitations=(
                    "The result reflects the current local Operation Catalog and "
                    "Capability Catalog.",
                    "The operation is read-only and has no side effects.",
                ),
            ),
            ProviderOperationSpec(
                operation_id="get_provider_status",
                what_it_can_do=(
                    "Return the declared Domain Provider areas and their current "
                    "active, partial, or planned status."
                ),
                what_it_cannot_do=(
                    "It cannot activate Providers, interpret user intent, select a "
                    "Provider, or change Provider state."
                ),
                examples=({"arguments": {}},),
                limitations=(
                    "The result reflects the current Capability Catalog.",
                    "Partial and planned areas are not executable unless they also "
                    "appear as implemented in the Operation Catalog.",
                    "The operation is read-only and has no side effects.",
                ),
            ),
            ProviderOperationSpec(
                operation_id="get_operation_catalog",
                what_it_can_do=(
                    "Return a deterministic structured summary of the Runtime "
                    "Operation Catalog."
                ),
                what_it_cannot_do=(
                    "It cannot interpret user intent or select, execute, rank, or "
                    "change Operations."
                ),
                examples=({"arguments": {}},),
                limitations=(
                    "Only operations registered in the local catalog are included.",
                    "The operation is read-only and has no side effects.",
                ),
            ),
        )

    def execute(
        self, operation: OperationContext, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if arguments:
            raise ValueError(f"{operation.operation_id} does not accept arguments")

        if operation.operation_id == "get_capabilities":
            catalog = self._catalog_supplier()
            capability_catalog = self._capability_catalog_supplier()
            operations = self._implemented_operations(catalog)
            return {
                "chat_status": "active_single_agent_loop_v0",
                "capability_catalog": capability_catalog,
                "available_providers": self._active_provider_ids(catalog),
                "available_operations": operations,
                "disabled_or_planned_features": [
                    "general multi-action iteration",
                    "conversation state persistence",
                    "Memory RAG / Memory Capability",
                    "Knowledge Enrichment Engine",
                    "general-user confirmation UI",
                    "external API-backed real tool execution",
                ],
                "limitations": [
                    "A turn can execute at most one Provider Operation.",
                    "The second LLM step must return a terminal action.",
                    "Only implemented catalog operations can be executed.",
                    "Partial or planned provider areas are not available through "
                    "the Provider Runtime path.",
                ],
                "source": "operation_catalog",
            }

        if operation.operation_id == "get_provider_status":
            return {
                "providers": self._capability_catalog_supplier().get("providers", []),
                "source": "capability_catalog",
            }

        if operation.operation_id == "get_operation_catalog":
            catalog = self._catalog_supplier()
            return {
                "contract_version": catalog.get("contract_version"),
                "providers": [
                    {
                        "provider_id": provider.get("provider_id"),
                        "operations": [
                            {
                                "operation_id": item.get("operation_id"),
                                "description": item.get("description"),
                                "availability": item.get("availability"),
                                "mode": item.get("mode"),
                                "risk_level": item.get("risk_level"),
                            }
                            for item in provider.get("operations", [])
                        ],
                    }
                    for provider in catalog.get("providers", [])
                ],
                "source": "operation_catalog",
            }

        raise ValueError(f"Unsupported jarvis operation: {operation.operation_id}")

    def get_execution_mode(self, operation: OperationContext) -> str:
        return "local_jarvis_status_read"

    def observation_details(
        self, operation: OperationContext, result: dict[str, Any]
    ) -> dict[str, Any]:
        facts: dict[str, Any] = {}
        counts: dict[str, int] = {}
        if operation.operation_id == "get_capabilities":
            providers = result.get("available_providers", [])
            operations = result.get("available_operations", [])
            capability_providers = result.get("capability_catalog", {}).get(
                "providers", []
            )
            capability_count = sum(
                len(item.get("capabilities", []))
                for item in capability_providers
                if isinstance(item, dict)
            )
            facts = {
                "provider_count": len(providers),
                "capability_count": capability_count,
                "operation_count": len(operations),
            }
            counts = dict(facts)
        elif operation.operation_id == "get_provider_status":
            providers = result.get("providers", [])
            facts = {"provider_count": len(providers)}
            counts = dict(facts)
        elif operation.operation_id == "get_operation_catalog":
            providers = result.get("providers", [])
            operation_count = sum(
                len(item.get("operations", []))
                for item in providers
                if isinstance(item, dict)
            )
            facts = {
                "provider_count": len(providers),
                "operation_count": operation_count,
            }
            counts = dict(facts)
        return {
            "facts": facts,
            "counts": counts,
            "limitations": list(result.get("limitations", [])),
            "visibility": "public",
            "related_capabilities": ["inspect_jarvis_status"],
        }

    @staticmethod
    def _active_provider_ids(catalog: dict[str, Any]) -> list[str]:
        return [
            str(provider["provider_id"])
            for provider in catalog.get("providers", [])
            if provider.get("provider_id")
        ]

    @staticmethod
    def _implemented_operations(catalog: dict[str, Any]) -> list[str]:
        return [
            f"{provider['provider_id']}.{operation['operation_id']}"
            for provider in catalog.get("providers", [])
            for operation in provider.get("operations", [])
            if operation.get("availability") == "implemented"
        ]

class JarvisExecutor(BaseExecutor):
    """Runtime adapter for the Jarvis Status Provider."""

    def __init__(self, provider: JarvisProvider) -> None:
        self.provider = provider

    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        return self.provider.execute(self._operation(tool), params)

    def get_execution_mode(self, tool: Any) -> str:
        return self.provider.get_execution_mode(self._operation(tool))

    @staticmethod
    def _operation(tool: Any) -> OperationContext:
        return OperationContext(
            operation_id=tool.id,
            skill_id=getattr(tool, "skill_id", "jarvis"),
            mode=getattr(tool, "mode", "read"),
            risk_level=getattr(tool, "risk_level", "low"),
        )
