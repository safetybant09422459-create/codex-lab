import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import codex_api
from .config import FRONTEND_DIR, ROOT_DIR, SKILLS_DIR, TOOLS_DIR
from .git_api import file_diff, git, git_changes
from .models import (
    AuditResponse,
    ChangesResponse,
    CommitRequest,
    DiffResponse,
    GitActionResponse,
    LogResponse,
    ProjectResponse,
    PushRequest,
    RuntimeDryRunResponse,
    RuntimeExecuteResponse,
    RuntimeRequest,
    RuntimeToolResponse,
    RuntimeValidateResponse,
    RunRequest,
    RunResponse,
    ServiceResponse,
    SkillResponse,
    ToolResponse,
    TravelTripDetailResponse,
    TravelTripsResponse,
)
from .photo_immich_adapter import ImmichAPIError, ImmichConfigurationError
from .photo_repository import PhotoRepository
from .runtime import InvalidToolDefinitionError, RuntimeService, ToolNotFoundError
from .service_api import schedule_restart, systemctl

app = FastAPI(title="Jarvis Dev v0.3")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")
runtime_service = RuntimeService()
photo_repository = PhotoRepository()

JARVIS_PRINCIPLE_CHECK = """\

Jarvis Principle Check:
この変更について、最後に以下を短く評価してください。

1. Web UIから利用できるか
2. API / Toolとして利用できるか
3. 将来MCP Tool化できるか
4. Jarvis Coreから呼び出せるか
5. UI依存のロジックになっていないか
6. 読み取り系か更新系か
7. 副作用・権限・プライバシー上の注意はあるか
"""


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/run", response_model=RunResponse)
async def run_codex(request: RunRequest) -> RunResponse:
    try:
        prompt = f"{request.prompt.rstrip()}{JARVIS_PRINCIPLE_CHECK}"
        await codex_api.start_codex(prompt)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RunResponse(status="started")


@app.get("/api/project", response_model=ProjectResponse)
async def get_project() -> ProjectResponse:
    status_text = await git("status", "--short", check=False)
    git_state = "clean" if not status_text.strip() else "changed"
    return ProjectResponse(
        name="Jarvis Developer",
        local_path=str(ROOT_DIR),
        branch="main",
        git_state=git_state,
    )


@app.get("/api/skills", response_model=list[SkillResponse])
async def get_skills() -> list[SkillResponse]:
    skills: list[SkillResponse] = []
    for skill_file in sorted(SKILLS_DIR.glob("*/skill.json")):
        try:
            data = json.loads(skill_file.read_text(encoding="utf-8"))
            skills.append(SkillResponse(**data))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid skill definition: {skill_file.relative_to(ROOT_DIR)}",
            ) from exc
    return skills


@app.get("/api/tools", response_model=list[ToolResponse])
async def get_tools(skill: str | None = None) -> list[ToolResponse]:
    tools: list[ToolResponse] = []
    tool_files = sorted(TOOLS_DIR.glob("*/*.json"))
    for tool_file in tool_files:
        try:
            data = json.loads(tool_file.read_text(encoding="utf-8"))
            tool = ToolResponse(**data)
            if skill is None or tool.skill_id == skill:
                tools.append(tool)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid tool definition: {tool_file.relative_to(ROOT_DIR)}",
            ) from exc
    return tools


@app.get("/api/runtime/tool/{tool_id}", response_model=RuntimeToolResponse)
async def runtime_get_tool(tool_id: str) -> RuntimeToolResponse:
    try:
        return RuntimeToolResponse(**runtime_service.get_tool(tool_id))
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/runtime/validate", response_model=RuntimeValidateResponse)
async def runtime_validate(request: RuntimeRequest) -> RuntimeValidateResponse:
    try:
        return RuntimeValidateResponse(
            **runtime_service.validate(request.tool_id, request.params)
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/runtime/dry-run", response_model=RuntimeDryRunResponse)
async def runtime_dry_run(request: RuntimeRequest) -> RuntimeDryRunResponse:
    try:
        return RuntimeDryRunResponse(
            **runtime_service.dry_run(request.tool_id, request.params)
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/runtime/execute", response_model=RuntimeExecuteResponse)
async def runtime_execute(request: RuntimeRequest) -> RuntimeExecuteResponse:
    try:
        return RuntimeExecuteResponse(
            **runtime_service.execute_stub(
                request.tool_id, request.params, request.confirmed, request.role
            )
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/travel/trips", response_model=TravelTripsResponse)
async def travel_get_trips() -> TravelTripsResponse:
    try:
        response = runtime_service.execute_stub(
            "get_trips", params={}, confirmed=False, role="guest"
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not response.get("success"):
        raise HTTPException(
            status_code=500,
            detail=response.get("reason") or "Travel trips request failed",
        )

    result = response.get("result") or {}
    return TravelTripsResponse(
        trips=result.get("trips") or [],
        source=result.get("source") or "local_travel_read",
        execution_mode="local_travel_read",
    )


@app.get("/api/travel/trips/{trip_id}", response_model=TravelTripDetailResponse)
async def travel_get_trip_detail(trip_id: str) -> TravelTripDetailResponse:
    try:
        trip_response = runtime_service.execute_stub(
            "get_trip",
            params={"trip_id": trip_id},
            confirmed=False,
            role="guest",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not trip_response.get("success"):
        raise HTTPException(
            status_code=500,
            detail=trip_response.get("reason") or "Travel trip request failed",
        )

    trip_result = trip_response.get("result") or {}
    trip = trip_result.get("trip")
    if trip is None:
        raise HTTPException(status_code=404, detail="Travel trip not found")

    try:
        timeline_response = runtime_service.execute_stub(
            "get_trip_timeline",
            params={"trip_id": trip_id},
            confirmed=False,
            role="guest",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not timeline_response.get("success"):
        raise HTTPException(
            status_code=500,
            detail=timeline_response.get("reason")
            or "Travel timeline request failed",
        )

    timeline_result = timeline_response.get("result") or {}
    return TravelTripDetailResponse(
        trip=trip,
        timeline=timeline_result.get("items") or [],
        source=trip_result.get("source") or "local_travel_read",
        execution_mode="local_travel_read",
    )


@app.get("/api/photo/assets/{asset_id}/thumbnail")
async def photo_asset_thumbnail(asset_id: str) -> Response:
    try:
        content, content_type = photo_repository.get_thumbnail(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImmichConfigurationError as exc:
        raise HTTPException(
            status_code=503, detail="Immich connection is not configured"
        ) from exc
    except ImmichAPIError as exc:
        raise HTTPException(
            status_code=502, detail="Immich thumbnail request failed"
        ) from exc
    return Response(content=content, media_type=content_type)


@app.get("/api/photo/assets/{asset_id}/preview")
async def photo_asset_preview(asset_id: str) -> Response:
    try:
        content, content_type = photo_repository.get_preview(asset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImmichConfigurationError as exc:
        raise HTTPException(
            status_code=503, detail="Immich connection is not configured"
        ) from exc
    except ImmichAPIError as exc:
        raise HTTPException(
            status_code=502, detail="Immich preview request failed"
        ) from exc
    return Response(content=content, media_type=content_type)


@app.get("/api/audit", response_model=AuditResponse)
async def get_audit(limit: int = 50) -> AuditResponse:
    bounded_limit = min(max(limit, 1), 500)
    return AuditResponse(items=runtime_service.audit_logger.list_recent(bounded_limit))


@app.get("/api/logs", response_model=LogResponse)
async def get_logs() -> LogResponse:
    log_lines = codex_api.logs()
    final_answer = codex_api.extract_final_answer(log_lines)
    if not final_answer and codex_api.returncode() not in (None, 0):
        final_answer = codex_api.failure_summary(log_lines)
    return LogResponse(
        running=codex_api.is_running(),
        returncode=codex_api.returncode(),
        status=codex_api.current_status(),
        lines=log_lines,
        final_answer=final_answer,
        tokens_used=codex_api.extract_tokens_used(log_lines),
    )


@app.get("/api/changes", response_model=ChangesResponse)
async def get_changes() -> ChangesResponse:
    return await git_changes()


@app.get("/api/diff", response_model=DiffResponse)
async def get_diff(path: str) -> DiffResponse:
    return DiffResponse(path=path, diff=await file_diff(path))


@app.post("/api/commit", response_model=GitActionResponse)
async def commit_changes(request: CommitRequest) -> GitActionResponse:
    if codex_api.is_running():
        raise HTTPException(status_code=409, detail="Codex is still running.")

    changes = await git_changes()
    if not changes.files:
        raise HTTPException(status_code=400, detail="No changes to commit.")

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Commit message is required.")

    await git("add", "-A")
    output = await git("commit", "-m", message)
    return GitActionResponse(ok=True, output=output)


@app.post("/api/push", response_model=GitActionResponse)
async def push_changes(request: PushRequest) -> GitActionResponse:
    if codex_api.is_running():
        raise HTTPException(status_code=409, detail="Codex is still running.")
    if not request.confirm or request.confirm_text != "PUSH":
        raise HTTPException(status_code=400, detail="Push requires two confirmations.")

    output = await git("push")
    return GitActionResponse(ok=True, output=output)


@app.get("/api/service/status", response_model=ServiceResponse)
async def service_status() -> ServiceResponse:
    return await systemctl("status", "--no-pager")


@app.post("/api/service/restart", response_model=ServiceResponse)
async def service_restart() -> ServiceResponse:
    return await schedule_restart()
