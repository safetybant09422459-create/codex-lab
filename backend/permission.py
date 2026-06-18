from dataclasses import dataclass
from typing import Any


VALID_ROLES = {"admin", "family", "guest"}


@dataclass(frozen=True)
class PermissionDecision:
    role: str
    allowed: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "allowed": self.allowed,
            "reason": self.reason,
        }


class PermissionEngine:
    def decide(self, tool: Any, role: str | None = None) -> PermissionDecision:
        normalized_role = role if role in VALID_ROLES else "guest"

        if normalized_role == "admin":
            return PermissionDecision(
                role=normalized_role,
                allowed=True,
                reason="admin is allowed to execute all tools",
            )

        skill_id = getattr(tool, "skill_id", None)
        mode = getattr(tool, "mode", None)
        risk_level = getattr(tool, "risk_level", None)

        if normalized_role == "guest" and skill_id == "developer":
            return PermissionDecision(
                role=normalized_role,
                allowed=False,
                reason="guest is not allowed to execute developer tools",
            )

        if mode == "read" and risk_level == "low":
            return PermissionDecision(
                role=normalized_role,
                allowed=True,
                reason=f"{normalized_role} is allowed to execute read low risk tools",
            )

        return PermissionDecision(
            role=normalized_role,
            allowed=False,
            reason=(
                f"{normalized_role} is only allowed to execute read low risk tools"
            ),
        )
