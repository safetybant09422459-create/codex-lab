from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConfirmationDecision:
    required: bool
    allowed: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "allowed": self.allowed,
            "reason": self.reason,
        }


class ConfirmationEngine:
    def decide(self, tool: Any, confirmed: bool = False) -> ConfirmationDecision:
        required = bool(
            getattr(tool, "confirmation_required", False)
            or getattr(tool, "risk_level", None) == "high"
        )

        if not required:
            return ConfirmationDecision(
                required=False,
                allowed=True,
                reason="confirmation not required",
            )

        if confirmed:
            return ConfirmationDecision(
                required=True,
                allowed=True,
                reason="confirmation provided",
            )

        return ConfirmationDecision(
            required=True,
            allowed=False,
            reason="confirmation required before execution",
        )
