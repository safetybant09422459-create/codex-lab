from typing import Any, Literal

from pydantic import BaseModel, Field

from .chat_core import ConversationTurn


class RunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)


class RunResponse(BaseModel):
    status: Literal["started"]


class ChatRequest(BaseModel):
    message: str
    conversation_history: list[ConversationTurn] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "Recent user/assistant messages used only as ephemeral Planner "
            "working context; not persisted as Memory."
        ),
    )
    role: str | None = Field(
        default=None,
        deprecated=True,
        description=(
            "Ignored compatibility input. Chat authorization is server-owned; "
            "Browser and LLM values never select the Runtime role."
        ),
    )
    debug: bool = False
    context: dict[str, Any] | None = None


class ChatClarificationResponse(BaseModel):
    status: Literal["not_required", "clarification_required", "candidates"]
    clarification: str | None = None
    candidate_list: list[dict[str, Any]] = Field(default_factory=list)
    reason: Literal[
        "query_too_broad",
        "multiple_candidates",
        "low_confidence",
        "missing_context",
    ] | None = None
    recommended_action: Literal[
        "continue",
        "select_candidate",
        "provide_context",
    ]


class ChatResponse(BaseModel):
    action: str
    reply: str
    tool_id: str | None = None
    arguments: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    candidates: list[dict[str, Any]] | None = None
    clarification: ChatClarificationResponse | None = None
    navigation: dict[str, Any] | None = None
    updated_context: dict[str, Any] | None = None
    debug: dict[str, Any] | None = None


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


class GitCommitPushRequest(BaseModel):
    confirm: bool
    expected_snapshot: str = Field(min_length=64, max_length=64)
    ignored_finding_ids: list[str] = Field(default_factory=list)


class GitPreflightFinding(BaseModel):
    id: str
    rule: str
    file: str
    line: int
    detected_text: str
    remediation: str
    ignorable: bool


class GitPreflightResponse(BaseModel):
    ok: bool
    blockers: list[str]
    files: list[str]
    summary: str
    commit_message: str
    head: str
    branch: str
    upstream: str
    snapshot: str
    findings: list[GitPreflightFinding]


class GitCommitPushResponse(GitPreflightResponse):
    committed: bool
    pushed: bool
    commit_hash: str = ""
    push_output: str = ""


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
            "local_photo_read",
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


class TravelTripsResponse(BaseModel):
    trips: list[dict[str, Any]]
    source: str
    execution_mode: Literal["local_travel_read"]


class TravelTripDetailResponse(BaseModel):
    trip: dict[str, Any]
    timeline: list[dict[str, Any]]
    source: str
    execution_mode: Literal["local_travel_read"]


class TravelTripPhotosResponse(BaseModel):
    trip_id: str
    photos: list[dict[str, Any]]
    pagination: dict[str, Any]
    source: str
    execution_mode: Literal["local_travel_read"]


class TravelExperiencePhotosResponse(BaseModel):
    experience_id: str
    experience_type: str | None = None
    timeline_item_id: str | None = None
    trip_id: str | None = None
    photos: list[dict[str, Any]]
    limit: int | None = None
    offset: int | None = None
    count: int | None = None
    has_more: bool | None = None
    pagination: dict[str, Any]
    source: str
    execution_mode: Literal["local_travel_read"]


class TravelExperiencePhotoLinksResponse(BaseModel):
    experience_id: str
    timeline_item_id: str | None = None
    trip_id: str | None = None
    links: list[dict[str, Any]]
    count: int
    source: str
    execution_mode: Literal["local_travel_read"]


class TravelExperiencePhotoLinkRequest(BaseModel):
    photo_asset_id: str
    link_type: Literal["linked", "cover", "hidden", "excluded"] = "linked"


class TravelExperiencePhotoLinkWriteResponse(BaseModel):
    link: dict[str, Any]
    experience_id: str
    source: str
    execution_mode: Literal["local_travel_write"]


class TravelSpotDetailResponse(BaseModel):
    experience: dict[str, Any] | None = None
    experience_id: str | None = None
    experience_type: str | None = None
    timeline_item_id: str | None = None
    spot: dict[str, Any]
    photos: list[dict[str, Any]]
    pagination: dict[str, Any]
    photo_error: bool = False
    source: str
    photo_source: str
    execution_mode: Literal["local_travel_read"]


class TravelExperienceDetailResponse(BaseModel):
    experience: dict[str, Any]
    experience_id: str
    experience_type: str | None = None
    timeline_item_id: str | None = None
    spot: dict[str, Any] | None = None
    photos: list[dict[str, Any]]
    pagination: dict[str, Any]
    photo_error: bool = False
    source: str
    photo_source: str
    execution_mode: Literal["local_travel_read"]


class TravelExperienceUpdateRequest(BaseModel):
    experience_type: str | None = None
    display_title: str | None = None
    place_name: str | None = None
    place_id: str | None = None
    category: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    time_kind: str | None = None
    memo: str | None = None
    order_no: int | None = None
    status: str | None = None
    cover_image_id: str | None = None


class TravelExperienceCreateRequest(BaseModel):
    experience_type: str
    display_title: str
    memo: str | None = None
    status: str | None = None
    place_name: str | None = None
    category: str | None = None
    start_at: str | None = None
    end_at: str | None = None


class TravelExperienceWriteResponse(BaseModel):
    experience: dict[str, Any]
    experience_id: str
    experience_type: str | None = None
    timeline_item_id: str | None = None
    source: str
    execution_mode: Literal["local_travel_write"]
