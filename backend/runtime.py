import json
from dataclasses import dataclass
from typing import Any

from .audit import AuditLogger
from .confirmation import ConfirmationEngine
from .config import ROOT_DIR, TOOLS_DIR
from .domain_provider import OperationContext
from .executors import ExecutorRegistry
from .permission import PermissionEngine
from .provider_registry import ProviderRegistry


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
    def __init__(
        self,
        tools_dir=TOOLS_DIR,
        audit_logger: AuditLogger | None = None,
        confirmation_engine: ConfirmationEngine | None = None,
        executor_registry: ExecutorRegistry | None = None,
        permission_engine: PermissionEngine | None = None,
        provider_registry: ProviderRegistry | None = None,
    ) -> None:
        self.tools_dir = tools_dir
        self.audit_logger = audit_logger or AuditLogger()
        self.confirmation_engine = confirmation_engine or ConfirmationEngine()
        if provider_registry is None:
            from .jarvis_provider import JarvisProvider
            from .travel_executor import TravelProvider

            provider_registry = ProviderRegistry(tools_dir=tools_dir)
            if (tools_dir / "travel").is_dir():
                provider_registry.register(TravelProvider())
            if (tools_dir / "jarvis").is_dir():
                provider_registry.register(
                    JarvisProvider(
                        provider_registry.catalog,
                        provider_registry.capability_catalog,
                    )
                )
        self.provider_registry = provider_registry
        self.executor_registry = executor_registry or ExecutorRegistry()
        if executor_registry is None and (tools_dir / "travel").is_dir():
            from .travel_executor import TravelExecutor

            self.executor_registry.register_skill(
                "travel",
                TravelExecutor(provider=self.provider_registry.get_provider("travel")),
            )
        if executor_registry is None and (tools_dir / "jarvis").is_dir():
            from .jarvis_provider import JarvisExecutor

            self.executor_registry.register_skill(
                "jarvis",
                JarvisExecutor(provider=self.provider_registry.get_provider("jarvis")),
            )
        self.permission_engine = permission_engine or PermissionEngine()

    def get_tool(self, tool_id: str) -> dict[str, Any]:
        return self._load_tool(tool_id).summary()

    def get_operation_catalog(self) -> dict[str, Any]:
        return self.provider_registry.catalog()

    def get_capability_catalog(self) -> dict[str, Any]:
        return self.provider_registry.capability_catalog()

    def get_observation_details(
        self, provider_id: str, operation_id: str, result: dict[str, Any]
    ) -> dict[str, Any]:
        operation = self.provider_registry.get_operation(
            provider_id, operation_id, executable=True
        )
        if operation.mode != "read" or not result.get("success"):
            return {}
        provider_result = result.get("result")
        if not isinstance(provider_result, dict):
            return {}
        provider = self.provider_registry.get_provider(provider_id)
        return provider.observation_details(
            OperationContext(
                operation_id=operation.operation_id,
                skill_id=provider_id,
                mode=operation.mode,
                risk_level=operation.risk_level,
            ),
            provider_result,
        )

    def execute_provider_operation(
        self,
        provider_id: str,
        operation_id: str,
        arguments: dict[str, Any],
        confirmed: bool = False,
        role: str | None = None,
    ) -> dict[str, Any]:
        operation = self.provider_registry.get_operation(
            provider_id, operation_id, executable=True
        )
        if operation.tool_id is None:
            raise InvalidToolDefinitionError(
                f"Executable operation has no Runtime Tool: {provider_id}.{operation_id}"
            )
        runtime_tool = self._load_tool(operation.tool_id)
        if runtime_tool.skill_id != provider_id:
            raise InvalidToolDefinitionError(
                f"Operation Tool belongs to another provider: "
                f"{provider_id}.{operation_id}"
            )
        return self.execute_stub(
            operation.tool_id, arguments, confirmed=confirmed, role=role
        )

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

    def execute_stub(
        self,
        tool_id: str,
        params: dict[str, Any],
        confirmed: bool = False,
        role: str | None = None,
    ) -> dict[str, Any]:
        effective_role = role or "guest"
        try:
            tool = self._load_tool(tool_id)
        except RuntimeError as exc:
            self._append_execute_stub_audit(
                tool_id=tool_id,
                skill_id=None,
                risk_level=None,
                confirmation_required=None,
                confirmed=confirmed,
                audit_required=None,
                status="failed",
                role=effective_role,
                permission_allowed=None,
                error=str(exc),
            )
            raise

        errors = self._validate_required_fields(tool.input_schema, params)
        validation = {"valid": not errors, "errors": errors}
        if not validation["valid"]:
            self._append_execute_stub_audit(
                tool_id=tool.id,
                skill_id=tool.skill_id,
                risk_level=tool.risk_level,
                confirmation_required=tool.confirmation_required,
                confirmed=confirmed,
                audit_required=tool.audit_required,
                status="failed",
                role=effective_role,
                permission_allowed=None,
                error="; ".join(validation["errors"]),
            )
            return {
                "success": False,
                "tool_id": tool_id,
                "execution_mode": "stub",
                "result": None,
                "blocked": False,
                "confirmation_required": tool.confirmation_required,
                "confirmed": confirmed,
                "role": effective_role,
                "permission_allowed": None,
                "permission_denied": False,
                "reason": None,
                "errors": validation["errors"],
            }

        permission = self.permission_engine.decide(tool, effective_role)
        if not permission.allowed:
            self._append_permission_denied_audit(
                tool_id=tool.id,
                skill_id=tool.skill_id,
                risk_level=tool.risk_level,
                confirmation_required=tool.confirmation_required,
                confirmed=confirmed,
                audit_required=tool.audit_required,
                role=permission.role,
                reason=permission.reason,
            )
            return {
                "success": False,
                "tool_id": tool_id,
                "execution_mode": None,
                "result": None,
                "blocked": True,
                "permission_denied": True,
                "role": permission.role,
                "permission_allowed": False,
                "confirmation_required": None,
                "confirmed": confirmed,
                "reason": permission.reason,
                "errors": [],
            }

        confirmation = self.confirmation_engine.decide(tool, confirmed)
        if not confirmation.allowed:
            self._append_confirmation_blocked_audit(
                tool_id=tool.id,
                skill_id=tool.skill_id,
                risk_level=tool.risk_level,
                confirmation_required=confirmation.required,
                confirmed=confirmed,
                audit_required=tool.audit_required,
                role=permission.role,
                permission_allowed=permission.allowed,
                reason=confirmation.reason,
            )
            return {
                "success": False,
                "tool_id": tool_id,
                "execution_mode": None,
                "result": None,
                "blocked": True,
                "permission_denied": False,
                "role": permission.role,
                "permission_allowed": True,
                "confirmation_required": confirmation.required,
                "confirmed": confirmed,
                "reason": confirmation.reason,
                "errors": [],
            }

        executor = self.executor_registry.get_executor(tool.id, tool.skill_id)
        if hasattr(executor, "get_execution_mode"):
            execution_mode = executor.get_execution_mode(tool)
        else:
            execution_mode = getattr(executor, "execution_mode", "stub")
        try:
            result = executor.execute(tool, params)
        except Exception as exc:
            self._append_execute_stub_audit(
                tool_id=tool.id,
                skill_id=tool.skill_id,
                risk_level=tool.risk_level,
                confirmation_required=tool.confirmation_required,
                confirmed=confirmed,
                audit_required=tool.audit_required,
                status="failed",
                role=permission.role,
                permission_allowed=permission.allowed,
                execution_mode=execution_mode,
                error=str(exc),
            )
            raise

        self._append_execute_stub_audit(
            tool_id=tool.id,
            skill_id=tool.skill_id,
            risk_level=tool.risk_level,
            confirmation_required=tool.confirmation_required,
            confirmed=confirmed,
            audit_required=tool.audit_required,
            status="success",
            role=permission.role,
            permission_allowed=permission.allowed,
            execution_mode=execution_mode,
        )
        return {
            "success": True,
            "tool_id": tool_id,
            "execution_mode": execution_mode,
            "result": result,
            "blocked": False,
            "permission_denied": False,
            "role": permission.role,
            "permission_allowed": True,
            "confirmation_required": confirmation.required,
            "confirmed": confirmed,
            "reason": None,
            "errors": [],
        }

    def _append_execute_stub_audit(
        self,
        *,
        tool_id: str,
        skill_id: str | None,
        risk_level: str | None,
        confirmation_required: bool | None,
        confirmed: bool,
        audit_required: bool | None,
        status: str,
        role: str,
        permission_allowed: bool | None,
        execution_mode: str = "stub",
        error: str | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "event_type": "runtime.execute_stub",
            "tool_id": tool_id,
            "skill_id": skill_id,
            "execution_mode": execution_mode,
            "status": status,
            "risk_level": risk_level,
            "confirmation_required": confirmation_required,
            "confirmed": confirmed,
            "audit_required": audit_required,
            "role": role,
            "permission_allowed": permission_allowed,
        }
        if error:
            event["error"] = error
        self.audit_logger.append(event)

    def _append_confirmation_blocked_audit(
        self,
        *,
        tool_id: str,
        skill_id: str,
        risk_level: str,
        confirmation_required: bool,
        confirmed: bool,
        audit_required: bool,
        role: str,
        permission_allowed: bool,
        reason: str,
    ) -> None:
        self.audit_logger.append(
            {
                "event_type": "runtime.confirmation_blocked",
                "tool_id": tool_id,
                "skill_id": skill_id,
                "execution_mode": "stub",
                "status": "blocked",
                "risk_level": risk_level,
                "confirmation_required": confirmation_required,
                "confirmed": confirmed,
                "audit_required": audit_required,
                "role": role,
                "permission_allowed": permission_allowed,
                "reason": reason,
            }
        )

    def _append_permission_denied_audit(
        self,
        *,
        tool_id: str,
        skill_id: str,
        risk_level: str,
        confirmation_required: bool,
        confirmed: bool,
        audit_required: bool,
        role: str,
        reason: str,
    ) -> None:
        self.audit_logger.append(
            {
                "event_type": "runtime.permission_denied",
                "tool_id": tool_id,
                "skill_id": skill_id,
                "execution_mode": None,
                "status": "blocked",
                "risk_level": risk_level,
                "confirmation_required": confirmation_required,
                "confirmed": confirmed,
                "audit_required": audit_required,
                "role": role,
                "permission_allowed": False,
                "reason": reason,
            }
        )

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
        return data.get("risk_level") == "high"

    def _audit_required(self, data: dict[str, Any]) -> bool:
        if "audit_required" in data:
            return bool(data["audit_required"])
        return data.get("risk_level") in {"medium", "high"} or data.get("mode") in {
            "write",
            "mixed",
        }
