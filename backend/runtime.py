import json
from dataclasses import dataclass
from typing import Any

from .config import ROOT_DIR, TOOLS_DIR


class RuntimeError(Exception):
    pass


class ToolNotFoundError(RuntimeError):
    pass


class InvalidToolDefinitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeTool:
    id: str
    skill_id: str
    mode: str
    risk_level: str
    confirmation_required: bool
    audit_required: bool
    input_schema: dict[str, Any]
    raw: dict[str, Any]

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "skill_id": self.skill_id,
            "mode": self.mode,
            "risk_level": self.risk_level,
            "confirmation_required": self.confirmation_required,
            "audit_required": self.audit_required,
        }


class RuntimeService:
    def __init__(self, tools_dir=TOOLS_DIR) -> None:
        self.tools_dir = tools_dir

    def get_tool(self, tool_id: str) -> dict[str, Any]:
        return self._load_tool(tool_id).summary()

    def validate(self, tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
        tool = self._load_tool(tool_id)
        errors = self._validate_required_fields(tool.input_schema, params)
        return {"valid": not errors, "errors": errors}

    def dry_run(self, tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
        tool = self._load_tool(tool_id)
        validation = self.validate(tool_id, params)
        return {
            "success": validation["valid"],
            "tool_id": tool.id,
            "skill_id": tool.skill_id,
            "risk_level": tool.risk_level,
            "confirmation_required": tool.confirmation_required,
            "audit_required": tool.audit_required,
            "would_execute": validation["valid"],
            "errors": validation["errors"],
        }

    def execute_stub(self, tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
        validation = self.validate(tool_id, params)
        if not validation["valid"]:
            return {
                "success": False,
                "tool_id": tool_id,
                "execution_mode": "stub",
                "result": None,
                "errors": validation["errors"],
            }

        return {
            "success": True,
            "tool_id": tool_id,
            "execution_mode": "stub",
            "result": {"message": "stub execution"},
        }

    def _load_tool(self, tool_id: str) -> RuntimeTool:
        for tool_file in sorted(self.tools_dir.glob("*/*.json")):
            try:
                data = json.loads(tool_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise InvalidToolDefinitionError(
                    f"Invalid tool definition: {tool_file.relative_to(ROOT_DIR)}"
                ) from exc

            if data.get("id") != tool_id:
                continue

            try:
                return RuntimeTool(
                    id=data["id"],
                    skill_id=data["skill_id"],
                    mode=data["mode"],
                    risk_level=data["risk_level"],
                    confirmation_required=self._confirmation_required(data),
                    audit_required=self._audit_required(data),
                    input_schema=data.get("input_schema", {}),
                    raw=data,
                )
            except KeyError as exc:
                raise InvalidToolDefinitionError(
                    f"Invalid tool definition: {tool_file.relative_to(ROOT_DIR)}"
                ) from exc

        raise ToolNotFoundError(f"Tool not found: {tool_id}")

    def _validate_required_fields(
        self, input_schema: dict[str, Any], params: dict[str, Any]
    ) -> list[str]:
        errors: list[str] = []
        required = input_schema.get("required", [])
        if not isinstance(required, list):
            return ["input_schema.required must be a list"]

        for field in required:
            if not isinstance(field, str):
                errors.append("input_schema.required entries must be strings")
                continue
            if field not in params or params[field] in (None, ""):
                errors.append(f"{field} is required")

        return errors

    def _confirmation_required(self, data: dict[str, Any]) -> bool:
        if "confirmation_required" in data:
            return bool(data["confirmation_required"])
        return data.get("risk_level") == "high" or data.get("mode") in {"write", "mixed"}

    def _audit_required(self, data: dict[str, Any]) -> bool:
        if "audit_required" in data:
            return bool(data["audit_required"])
        return data.get("risk_level") in {"medium", "high"} or data.get("mode") in {
            "write",
            "mixed",
        }
