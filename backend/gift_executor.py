from typing import Any

from .domain_provider import DomainProvider, OperationContext, ProviderOperationSpec
from .executors import BaseExecutor
from .gift_repository import GiftRepository


class GiftProvider(DomainProvider):
    provider_id = "gift"

    def __init__(self, repository: GiftRepository | None = None) -> None:
        self.repository = repository or GiftRepository()

    def operation_specs(self) -> tuple[ProviderOperationSpec, ...]:
        return (
            ProviderOperationSpec(
                operation_id="list_gifts",
                what_it_can_do="Read canonical gift candidates and given/received history.",
                what_it_cannot_do="It cannot infer relationships, occasions, or recommendations.",
                examples=({"arguments": {}}, {"arguments": {"person": "家族"}}),
                limitations=("Names are exact family-entered labels.",),
            ),
            ProviderOperationSpec(
                operation_id="create_gift",
                what_it_can_do="Create one confirmed gift candidate or history entry.",
                what_it_cannot_do="It cannot purchase, message, or create an entry without Runtime gates.",
                examples=({"arguments": {"entry_type": "candidate", "title": "本"}},),
                limitations=("Admin permission and explicit confirmation are required.",),
            ),
        )

    def execute(self, operation: OperationContext, params: dict[str, Any]) -> dict[str, Any]:
        if operation.operation_id == "list_gifts":
            entries = self.repository.list_entries(
                params.get("entry_type"), params.get("person"), params.get("year")
            )
            return {"tool_id": operation.operation_id, "entries": entries, "count": len(entries), "source": "local_gift_db"}
        if operation.operation_id == "create_gift":
            return {"tool_id": operation.operation_id, "entry": self.repository.create_entry(**params), "source": "local_gift_db"}
        raise ValueError(f"Unsupported gift operation: {operation.operation_id}")

    def get_execution_mode(self, operation: OperationContext) -> str:
        return "local_gift_read" if operation.mode == "read" else "local_gift_write"

    def observation_details(self, operation: OperationContext, result: dict[str, Any]) -> dict[str, Any]:
        if operation.operation_id != "list_gifts":
            return {"visibility": "family"}
        return {
            "facts": {"entries": result.get("entries", []), "count": result.get("count", 0), "source": result.get("source")},
            "visibility": "family",
            "freshness": "current local Gift DB snapshot",
            "limitations": ["Gift labels and people are family-entered facts; relationships are not inferred."],
            "provenance": {"provider_id": "gift", "operation_id": operation.operation_id},
        }


class GiftExecutor(BaseExecutor):
    def __init__(self, provider: GiftProvider | None = None) -> None:
        self.provider = provider or GiftProvider()

    def execute(self, tool: Any, params: dict[str, Any]) -> dict[str, Any]:
        return self.provider.execute(
            OperationContext(tool.id, tool.skill_id, tool.mode, tool.risk_level), params
        )

    def get_execution_mode(self, tool: Any) -> str:
        return self.provider.get_execution_mode(
            OperationContext(tool.id, tool.skill_id, tool.mode, tool.risk_level)
        )
