import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import codex_api
from .chat_router import handle_chat
from .config import FRONTEND_DIR, ROOT_DIR, SKILLS_DIR, TOOLS_DIR
from .git_api import file_diff, git, git_changes
from .git_workflow import GitWorkflow, redact_secrets
from .models import (
    AuditResponse,
    ChatRequest,
    ChatResponse,
    ChangesResponse,
    DiffResponse,
    GitCommitPushRequest,
    GitCommitPushResponse,
    GitPreflightResponse,
    LogResponse,
    ProjectResponse,
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
    TravelExperienceDetailResponse,
    TravelExperiencePhotoLinkRequest,
    TravelExperiencePhotoLinkWriteResponse,
    TravelExperiencePhotoLinksResponse,
    TravelExperiencePhotosResponse,
    TravelExperienceCreateRequest,
    TravelExperienceUpdateRequest,
    TravelExperienceWriteResponse,
    TravelSpotDetailResponse,
    TravelTripDetailResponse,
    TravelTripPhotosResponse,
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
git_workflow = GitWorkflow(git)
CHAT_SERVER_ROLE = "admin"

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


@app.post(
    "/api/chat",
    response_model=ChatResponse,
    response_model_exclude_none=True,
)
async def chat(request: ChatRequest) -> ChatResponse:
    result = handle_chat(
        request.message,
        # Authentication is not implemented yet. Keep this temporary role on
        # the trusted server side; request/Browser/LLM role values are ignored.
        role=CHAT_SERVER_ROLE,
        debug=request.debug,
        context=request.context,
        conversation_history=request.conversation_history,
    )
    return ChatResponse(**result)


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


@app.get(
    "/api/travel/trips/{trip_id}/photos",
    response_model=TravelTripPhotosResponse,
)
async def travel_get_trip_photos(
    trip_id: str, limit: int = 20, offset: int = 0
) -> TravelTripPhotosResponse:
    bounded_limit = min(max(limit, 1), 20)
    bounded_offset = max(offset, 0)

    try:
        response = runtime_service.execute_stub(
            "get_trip_photos",
            params={
                "trip_id": trip_id,
                "limit": bounded_limit,
                "offset": bounded_offset,
            },
            confirmed=False,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "trip not found":
            raise HTTPException(status_code=404, detail="Travel trip not found") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImmichConfigurationError as exc:
        raise HTTPException(
            status_code=503, detail="Immich connection is not configured"
        ) from exc
    except ImmichAPIError as exc:
        raise HTTPException(
            status_code=502, detail="Immich photo search request failed"
        ) from exc

    if not response.get("success"):
        if response.get("permission_denied"):
            raise HTTPException(
                status_code=403,
                detail=response.get("reason") or "Travel photos permission denied",
            )
        if response.get("blocked") and response.get("confirmation_required"):
            raise HTTPException(
                status_code=409,
                detail=response.get("reason") or "Travel photos confirmation required",
            )
        raise HTTPException(
            status_code=500,
            detail=response.get("reason") or "Travel photos request failed",
        )

    result = response.get("result") or {}
    return TravelTripPhotosResponse(
        trip_id=result.get("trip_id") or trip_id,
        photos=result.get("photos") or [],
        pagination=result.get("pagination") or {},
        source=result.get("source") or "photo_skill",
        execution_mode="local_travel_read",
    )


@app.get(
    "/api/travel/experiences/{experience_id}/photos",
    response_model=TravelExperiencePhotosResponse,
)
async def travel_get_experience_photos(
    experience_id: str, limit: int = 20, offset: int = 0
) -> TravelExperiencePhotosResponse:
    bounded_limit = min(max(limit, 1), 20)
    bounded_offset = max(offset, 0)

    try:
        response = runtime_service.execute_stub(
            "get_experience_photos",
            params={
                "experience_id": experience_id,
                "limit": bounded_limit,
                "offset": bounded_offset,
            },
            confirmed=False,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "timeline item not found":
            raise HTTPException(
                status_code=404, detail="Travel experience not found"
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImmichConfigurationError as exc:
        raise HTTPException(
            status_code=503, detail="Immich connection is not configured"
        ) from exc
    except ImmichAPIError as exc:
        raise HTTPException(
            status_code=502, detail="Immich photo search request failed"
        ) from exc

    if not response.get("success"):
        if response.get("permission_denied"):
            raise HTTPException(
                status_code=403,
                detail=response.get("reason") or "Travel photos permission denied",
            )
        if response.get("blocked") and response.get("confirmation_required"):
            raise HTTPException(
                status_code=409,
                detail=response.get("reason") or "Travel photos confirmation required",
            )
        raise HTTPException(
            status_code=500,
            detail=response.get("reason") or "Travel experience photos request failed",
        )

    result = response.get("result") or {}
    photos = result.get("photos") or []
    pagination = dict(result.get("pagination") or {})
    pagination_limit = pagination.get("limit") or bounded_limit
    pagination_offset = pagination.get("offset") or bounded_offset
    pagination_count = pagination.get("count")
    if pagination_count is None:
        pagination_count = len(photos)
    if "has_more" not in pagination:
        pagination["has_more"] = pagination_count == pagination_limit
    pagination["limit"] = pagination_limit
    pagination["offset"] = pagination_offset
    pagination["count"] = pagination_count
    return TravelExperiencePhotosResponse(
        experience_id=str(result.get("experience_id") or experience_id),
        experience_type=result.get("experience_type"),
        timeline_item_id=result.get("timeline_item_id") or result.get("experience_id"),
        trip_id=result.get("trip_id"),
        photos=photos,
        limit=pagination_limit,
        offset=pagination_offset,
        count=pagination_count,
        has_more=pagination.get("has_more"),
        pagination=pagination,
        source=result.get("source") or "photo_skill",
        execution_mode="local_travel_read",
    )


@app.get(
    "/api/travel/experiences/{experience_id}/photo-search",
    response_model=TravelExperiencePhotosResponse,
)
async def travel_search_experience_photos(
    experience_id: str,
    from_at: str = Query(alias="from"),
    to_at: str = Query(alias="to"),
    limit: int = 20,
    offset: int = 0,
) -> TravelExperiencePhotosResponse:
    bounded_limit = min(max(limit, 1), 20)
    bounded_offset = max(offset, 0)
    try:
        response = runtime_service.execute_stub(
            "get_experience_photo_search",
            params={
                "experience_id": experience_id,
                "from": from_at,
                "to": to_at,
                "limit": bounded_limit,
                "offset": bounded_offset,
            },
            confirmed=False,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "timeline item not found":
            raise HTTPException(
                status_code=404, detail="Travel experience not found"
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImmichConfigurationError as exc:
        raise HTTPException(
            status_code=503, detail="Immich connection is not configured"
        ) from exc
    except ImmichAPIError as exc:
        raise HTTPException(
            status_code=502, detail="Immich photo search request failed"
        ) from exc

    if not response.get("success"):
        if response.get("permission_denied"):
            raise HTTPException(
                status_code=403,
                detail=response.get("reason") or "Travel photos permission denied",
            )
        raise HTTPException(
            status_code=500,
            detail=response.get("reason") or "Travel photo search request failed",
        )

    result = response.get("result") or {}
    photos = result.get("photos") or []
    pagination = dict(result.get("pagination") or {})
    pagination_limit = pagination.get("limit") or bounded_limit
    pagination_offset = pagination.get("offset") or bounded_offset
    pagination_count = pagination.get("count")
    if pagination_count is None:
        pagination_count = len(photos)
    if "has_more" not in pagination:
        pagination["has_more"] = pagination_count == pagination_limit
    pagination.update(
        {
            "limit": pagination_limit,
            "offset": pagination_offset,
            "count": pagination_count,
        }
    )
    return TravelExperiencePhotosResponse(
        experience_id=str(result.get("experience_id") or experience_id),
        experience_type=result.get("experience_type"),
        timeline_item_id=result.get("timeline_item_id") or result.get("experience_id"),
        trip_id=result.get("trip_id"),
        photos=photos,
        limit=pagination_limit,
        offset=pagination_offset,
        count=pagination_count,
        has_more=pagination.get("has_more"),
        pagination=pagination,
        source=result.get("source") or "photo_skill",
        execution_mode="local_travel_read",
    )


@app.get(
    "/api/travel/experiences/{experience_id}/photo-links",
    response_model=TravelExperiencePhotoLinksResponse,
)
async def travel_get_experience_photo_links(
    experience_id: str,
) -> TravelExperiencePhotoLinksResponse:
    try:
        response = runtime_service.execute_stub(
            "get_experience_photo_links",
            params={"experience_id": experience_id},
            confirmed=False,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "experience not found":
            raise HTTPException(
                status_code=404, detail="Travel experience not found"
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not response.get("success"):
        if response.get("permission_denied"):
            raise HTTPException(
                status_code=403,
                detail=response.get("reason") or "Travel photo links permission denied",
            )
        raise HTTPException(
            status_code=500,
            detail=response.get("reason") or "Travel photo links request failed",
        )

    result = response.get("result") or {}
    links = result.get("links") or []
    return TravelExperiencePhotoLinksResponse(
        experience_id=str(result.get("experience_id") or experience_id),
        timeline_item_id=result.get("timeline_item_id") or result.get("experience_id"),
        trip_id=result.get("trip_id"),
        links=links,
        count=int(result.get("count") or len(links)),
        source=str(result.get("source") or "local_travel_read"),
        execution_mode="local_travel_read",
    )


@app.post(
    "/api/travel/experiences/{experience_id}/photo-links",
    response_model=TravelExperiencePhotoLinkWriteResponse,
)
async def travel_link_experience_photo(
    experience_id: str, request: TravelExperiencePhotoLinkRequest
) -> TravelExperiencePhotoLinkWriteResponse:
    try:
        response = runtime_service.execute_stub(
            "link_experience_photo",
            params={
                "experience_id": experience_id,
                "photo_asset_id": request.photo_asset_id,
                "link_type": request.link_type,
            },
            confirmed=True,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "experience not found":
            raise HTTPException(
                status_code=404, detail="Travel experience not found"
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _travel_photo_link_write_response(response, experience_id)


@app.post(
    "/api/travel/experiences/{experience_id}/photo-links/{link_id}/archive",
    response_model=TravelExperiencePhotoLinkWriteResponse,
)
async def travel_archive_experience_photo_link(
    experience_id: str, link_id: str
) -> TravelExperiencePhotoLinkWriteResponse:
    try:
        response = runtime_service.execute_stub(
            "archive_experience_photo_link",
            params={"experience_id": experience_id, "link_id": link_id},
            confirmed=True,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "experience not found":
            raise HTTPException(
                status_code=404, detail="Travel experience not found"
            ) from exc
        if str(exc) == "photo link not found":
            raise HTTPException(status_code=404, detail="Travel photo link not found") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _travel_photo_link_write_response(response, experience_id)


@app.get("/api/travel/spots/{spot_id}", response_model=TravelSpotDetailResponse)
async def travel_get_spot_detail(
    spot_id: str, limit: int = 20, offset: int = 0
) -> TravelSpotDetailResponse:
    bounded_limit = min(max(limit, 1), 20)
    bounded_offset = max(offset, 0)

    try:
        spot_response = runtime_service.execute_stub(
            "get_spot",
            params={"timeline_item_id": spot_id},
            confirmed=False,
            role="guest",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not spot_response.get("success"):
        raise HTTPException(
            status_code=500,
            detail=spot_response.get("reason") or "Travel spot request failed",
        )

    spot_result = spot_response.get("result") or {}
    spot = spot_result.get("spot")
    if spot is None:
        raise HTTPException(status_code=404, detail="Travel spot not found")

    photo_result: dict[str, object] = {}
    photo_source = "photo_skill"
    photo_error = False
    try:
        photo_response = runtime_service.execute_stub(
            "get_spot_photos",
            params={
                "timeline_item_id": spot_id,
                "limit": bounded_limit,
                "offset": bounded_offset,
            },
            confirmed=False,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "timeline item not found":
            raise HTTPException(status_code=404, detail="Travel spot not found") from exc
        photo_error = True
    except (ImmichConfigurationError, ImmichAPIError):
        photo_error = True

    if not photo_error:
        if not photo_response.get("success"):
            photo_error = True
        else:
            photo_result = photo_response.get("result") or {}
            photo_source = str(photo_result.get("source") or "photo_skill")

    return TravelSpotDetailResponse(
        experience=spot,
        experience_id=spot_result.get("experience_id") or spot.get("experience_id"),
        experience_type=spot_result.get("experience_type")
        or spot.get("experience_type"),
        timeline_item_id=spot_result.get("timeline_item_id")
        or spot.get("timeline_item_id")
        or spot.get("id"),
        spot=spot,
        photos=photo_result.get("photos") or [],
        pagination=photo_result.get("pagination") or {},
        photo_error=photo_error,
        source=spot_result.get("source") or "local_travel_read",
        photo_source=photo_source,
        execution_mode="local_travel_read",
    )


@app.get(
    "/api/travel/experiences/{experience_id}",
    response_model=TravelExperienceDetailResponse,
)
async def travel_get_experience_detail(
    experience_id: str, limit: int = 20, offset: int = 0
) -> TravelExperienceDetailResponse:
    bounded_limit = min(max(limit, 1), 20)
    bounded_offset = max(offset, 0)

    try:
        experience_response = runtime_service.execute_stub(
            "get_experience",
            params={"experience_id": experience_id},
            confirmed=False,
            role="guest",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not experience_response.get("success"):
        raise HTTPException(
            status_code=500,
            detail=experience_response.get("reason")
            or "Travel experience request failed",
        )

    experience_result = experience_response.get("result") or {}
    experience = experience_result.get("experience")
    if experience is None:
        raise HTTPException(status_code=404, detail="Travel experience not found")

    photo_result: dict[str, object] = {}
    photo_source = "photo_skill"
    photo_error = False
    try:
        photo_response = runtime_service.execute_stub(
            "get_experience_photos",
            params={
                "experience_id": experience_id,
                "limit": bounded_limit,
                "offset": bounded_offset,
            },
            confirmed=False,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "timeline item not found":
            raise HTTPException(
                status_code=404, detail="Travel experience not found"
            ) from exc
        photo_error = True
    except (ImmichConfigurationError, ImmichAPIError):
        photo_error = True

    if not photo_error:
        if not photo_response.get("success"):
            photo_error = True
        else:
            photo_result = photo_response.get("result") or {}
            photo_source = str(photo_result.get("source") or "photo_skill")

    return TravelExperienceDetailResponse(
        experience=experience,
        experience_id=str(
            experience_result.get("experience_id")
            or experience.get("experience_id")
            or experience.get("id")
        ),
        experience_type=experience_result.get("experience_type")
        or experience.get("experience_type"),
        timeline_item_id=experience_result.get("timeline_item_id")
        or experience.get("timeline_item_id")
        or experience.get("id"),
        spot=experience,
        photos=photo_result.get("photos") or [],
        pagination=photo_result.get("pagination") or {},
        photo_error=photo_error,
        source=experience_result.get("source") or "local_travel_read",
        photo_source=photo_source,
        execution_mode="local_travel_read",
    )


@app.patch(
    "/api/travel/experiences/{experience_id}",
    response_model=TravelExperienceWriteResponse,
)
async def travel_update_experience(
    experience_id: str, request: TravelExperienceUpdateRequest
) -> TravelExperienceWriteResponse:
    params = {"experience_id": experience_id, **_model_updates(request)}
    try:
        response = runtime_service.execute_stub(
            "update_experience",
            params=params,
            confirmed=True,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "experience not found":
            raise HTTPException(
                status_code=404, detail="Travel experience not found"
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _travel_experience_write_response(response)


@app.post(
    "/api/travel/trips/{trip_id}/experiences",
    response_model=TravelExperienceWriteResponse,
)
async def travel_create_experience(
    trip_id: str, request: TravelExperienceCreateRequest
) -> TravelExperienceWriteResponse:
    params = {"trip_id": trip_id, **_model_updates(request)}
    try:
        response = runtime_service.execute_stub(
            "create_experience",
            params=params,
            confirmed=True,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _travel_experience_write_response(response)


@app.post(
    "/api/travel/experiences/{experience_id}/archive",
    response_model=TravelExperienceWriteResponse,
)
async def travel_archive_experience(experience_id: str) -> TravelExperienceWriteResponse:
    try:
        response = runtime_service.execute_stub(
            "archive_experience",
            params={"experience_id": experience_id},
            confirmed=True,
            role="admin",
        )
    except ToolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidToolDefinitionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "experience not found":
            raise HTTPException(
                status_code=404, detail="Travel experience not found"
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _travel_experience_write_response(response)


def _model_updates(request: TravelExperienceUpdateRequest) -> dict[str, object]:
    if hasattr(request, "model_dump"):
        return request.model_dump(exclude_unset=True)
    return request.dict(exclude_unset=True)


def _travel_experience_write_response(
    response: dict[str, object],
) -> TravelExperienceWriteResponse:
    if not response.get("success"):
        if response.get("permission_denied"):
            raise HTTPException(
                status_code=403,
                detail=response.get("reason") or "Travel experience permission denied",
            )
        if response.get("blocked") and response.get("confirmation_required"):
            raise HTTPException(
                status_code=409,
                detail=response.get("reason")
                or "Travel experience confirmation required",
            )
        raise HTTPException(
            status_code=500,
            detail=response.get("reason") or "Travel experience write failed",
        )

    result = response.get("result") or {}
    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="Travel experience write failed")

    experience = result.get("experience")
    if not isinstance(experience, dict):
        raise HTTPException(status_code=500, detail="Travel experience write failed")

    return TravelExperienceWriteResponse(
        experience=experience,
        experience_id=str(
            result.get("experience_id")
            or experience.get("experience_id")
            or experience.get("id")
        ),
        experience_type=result.get("experience_type")
        or experience.get("experience_type"),
        timeline_item_id=result.get("timeline_item_id")
        or experience.get("timeline_item_id")
        or experience.get("id"),
        source=str(result.get("source") or "local_travel_write"),
        execution_mode="local_travel_write",
    )


def _travel_photo_link_write_response(
    response: dict[str, object], experience_id: str
) -> TravelExperiencePhotoLinkWriteResponse:
    if not response.get("success"):
        if response.get("permission_denied"):
            raise HTTPException(
                status_code=403,
                detail=response.get("reason") or "Travel photo link permission denied",
            )
        if response.get("blocked") and response.get("confirmation_required"):
            raise HTTPException(
                status_code=409,
                detail=response.get("reason")
                or "Travel photo link confirmation required",
            )
        raise HTTPException(
            status_code=500,
            detail=response.get("reason") or "Travel photo link write failed",
        )

    result = response.get("result") or {}
    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="Travel photo link write failed")

    link = result.get("link")
    if not isinstance(link, dict):
        raise HTTPException(status_code=500, detail="Travel photo link write failed")

    return TravelExperiencePhotoLinkWriteResponse(
        link=link,
        experience_id=str(link.get("experience_id") or experience_id),
        source=str(result.get("source") or "local_travel_write"),
        execution_mode="local_travel_write",
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
    return DiffResponse(path=path, diff=redact_secrets(await file_diff(path)))


@app.get("/api/git/preflight", response_model=GitPreflightResponse)
async def git_preflight() -> GitPreflightResponse:
    if codex_api.is_running():
        raise HTTPException(status_code=409, detail="Codex is still running.")
    report = await git_workflow.preflight()
    runtime_service.audit_logger.append(
        {
            "event": "developer.git_preflight",
            "success": report.ok,
            "file_count": len(report.files),
            "blockers": report.blockers,
        }
    )
    return GitPreflightResponse(**report.as_dict())


@app.post("/api/git/commit_push", response_model=GitCommitPushResponse)
async def git_commit_push(request: GitCommitPushRequest) -> GitCommitPushResponse:
    if codex_api.is_running():
        raise HTTPException(status_code=409, detail="Codex is still running.")
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Explicit UI confirmation is required.")
    result = await git_workflow.commit_push(
        request.expected_snapshot, request.ignored_finding_ids
    )
    runtime_service.audit_logger.append(
        {
            "event": "developer.git_commit_push",
            "success": bool(result["ok"]),
            "committed": bool(result["committed"]),
            "pushed": bool(result["pushed"]),
            "commit_hash": result.get("commit_hash", ""),
            "blockers": result["blockers"],
            "ignored_finding_ids": request.ignored_finding_ids,
        }
    )
    if not result["ok"]:
        raise HTTPException(status_code=409, detail="; ".join(result["blockers"]))
    return GitCommitPushResponse(**result)


@app.get("/api/service/status", response_model=ServiceResponse)
async def service_status() -> ServiceResponse:
    return await systemctl("status", "--no-pager")


@app.post("/api/service/restart", response_model=ServiceResponse)
async def service_restart() -> ServiceResponse:
    return await schedule_restart()
