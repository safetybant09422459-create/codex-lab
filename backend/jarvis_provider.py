from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .domain_provider import DomainProvider, OperationContext, ProviderOperationSpec
from .executors import BaseExecutor


class JarvisProvider(DomainProvider):
    """Deterministic, read-only view of Jarvis runtime capabilities."""

    provider_id = "jarvis"

    def __init__(self, catalog_supplier: Callable[[], dict[str, Any]]) -> None:
        self._catalog_supplier = catalog_supplier

    def operation_specs(self) -> tuple[ProviderOperationSpec, ...]:
        return (
            ProviderOperationSpec(
                operation_id="get_capabilities",
                what_it_can_do=(
                    "Return structured facts about currently available Jarvis "
                    "providers, operations, planned features, and limitations."
                ),
                what_it_cannot_do=(
                    "It cannot interpret user intent, enable features, or compose "
                    "a conversational answer."
                ),
                examples=({"arguments": {}},),
                limitations=(
                    "Availability reflects the current local Operation Catalog.",
                ),
            ),
            ProviderOperationSpec(
                operation_id="get_provider_status",
                what_it_can_do=(
                    "Return the known Domain Provider areas and their current "
                    "active, partial, or planned status."
                ),
                what_it_cannot_do=(
                    "It cannot activate providers or infer which provider a user "
                    "intended to use."
                ),
                examples=({"arguments": {}},),
                limitations=(
                    "Partial and planned areas are not executable unless they also "
                    "appear in the Operation Catalog.",
                ),
            ),
            ProviderOperationSpec(
                operation_id="get_operation_catalog",
                what_it_can_do=(
                    "Return a deterministic summary of the Runtime Operation "
                    "Catalog for explanation by the LLM."
                ),
                what_it_cannot_do=(
                    "It cannot select, execute, rank, or describe operations based "
                    "on user intent."
                ),
                examples=({"arguments": {}},),
                limitations=(
                    "Only operations registered in the local catalog are included.",
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
            operations = self._implemented_operations(catalog)
            return {
                "chat_status": "active_single_agent_loop_v0",
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
            active = set(self._active_provider_ids(self._catalog_supplier()))
            status = [
                self._provider_status("jarvis", "active", active),
                self._provider_status("travel", "active", active),
                {
                    "provider_id": "photo",
                    "status": "partial",
                    "detail": "Photo API and executor exist; Domain Provider is not registered.",
                },
                {
                    "provider_id": "weather",
                    "status": "partial",
                    "detail": "Local Runtime executor exists; Domain Provider is not registered.",
                },
                {
                    "provider_id": "developer",
                    "status": "partial",
                    "detail": "Developer UI exists; Domain Provider is not registered.",
                },
                *(
                    {
                        "provider_id": provider_id,
                        "status": "planned",
                        "detail": "Domain Provider is not registered.",
                    }
                    for provider_id in ("calendar", "garden", "home")
                ),
            ]
            return {"providers": status, "source": "jarvis_status"}

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

    @staticmethod
    def _provider_status(
        provider_id: str, registered_status: str, active: set[str]
    ) -> dict[str, str]:
        if provider_id in active:
            return {
                "provider_id": provider_id,
                "status": registered_status,
                "detail": "Registered in the current Operation Catalog.",
            }
        return {
            "provider_id": provider_id,
            "status": "unavailable",
            "detail": "Expected provider is not registered in the current Operation Catalog.",
        }


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
