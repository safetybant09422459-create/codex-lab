from typing import Any, Literal

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)


class RunResponse(BaseModel):
    status: Literal["started"]


class ProjectResponse(BaseModel):
    name: str
    local_path: str
    branch: str
    git_state: str


class LogResponse(BaseModel):
    running: bool
    returncode: int | None
    status: Literal["idle", "running", "succeeded", "failed"]
    lines: list[str]
    final_answer: str
    tokens_used: str | None


class ChangedFile(BaseModel):
    path: str
    status: Literal["new", "modified", "deleted"]
    raw: str


class ChangesResponse(BaseModel):
    status_text: str
    files: list[ChangedFile]


class DiffResponse(BaseModel):
    path: str
    diff: str


class CommitRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class GitActionResponse(BaseModel):
    ok: bool
    output: str


class PushRequest(BaseModel):
    confirm: bool
    confirm_text: str = Field(max_length=80)


class ServiceResponse(BaseModel):
    ok: bool
    output: str
    stderr: str = ""
    command: str = ""
    returncode: int | None = None


class SkillResponse(BaseModel):
    id: str
    name: str
    description: str
    status: Literal["idea", "planned", "active", "deprecated"]
    type: Literal["module", "tool", "mcp"]
    version: str
    mode: Literal["read", "write", "mixed"]
    risk_level: Literal["low", "medium", "high"]
    confirmation_required: bool
    audit_required: bool
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    invocation_examples: list[str]


class ToolResponse(BaseModel):
    id: str
    skill_id: str
    name: str
    description: str
    status: Literal["idea", "planned", "active", "implemented", "deprecated"]
    mode: Literal["read", "write", "mixed"]
    risk_level: Literal["low", "medium", "high"]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class RuntimeToolResponse(BaseModel):
    id: str
    skill_id: str
    mode: Literal["read", "write", "mixed"]
    risk_level: Literal["low", "medium", "high"]
    confirmation_required: bool
    audit_required: bool


class RuntimeRequest(BaseModel):
    tool_id: str = Field(min_length=1, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    role: Literal["admin", "family", "guest"] = "guest"


class RuntimeValidateResponse(BaseModel):
    valid: bool
    errors: list[str]


class RuntimeDryRunResponse(BaseModel):
    success: bool
    tool_id: str
    skill_id: str
    risk_level: Literal["low", "medium", "high"]
    confirmation_required: bool
    audit_required: bool
    would_execute: bool
    errors: list[str] = Field(default_factory=list)


class RuntimeExecuteResponse(BaseModel):
    success: bool
    tool_id: str
    execution_mode: (
        Literal[
            "stub",
            "local_weather_stub",
            "local_travel_read",
            "local_travel_write",
        ]
        | None
    ) = None
    result: dict[str, Any] | None
    blocked: bool = False
    permission_denied: bool = False
    role: Literal["admin", "family", "guest"] = "guest"
    permission_allowed: bool | None = None
    confirmation_required: bool | None = None
    confirmed: bool = False
    reason: str | None = None
    errors: list[str] = Field(default_factory=list)


class AuditResponse(BaseModel):
    items: list[dict[str, Any]]
