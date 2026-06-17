import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import codex_api
from .config import FRONTEND_DIR, ROOT_DIR, SKILLS_DIR
from .git_api import file_diff, git, git_changes
from .models import (
    ChangesResponse,
    CommitRequest,
    DiffResponse,
    GitActionResponse,
    LogResponse,
    ProjectResponse,
    PushRequest,
    RunRequest,
    RunResponse,
    ServiceResponse,
    SkillResponse,
)
from .service_api import systemctl

app = FastAPI(title="Jarvis Dev v0.3")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

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
    return await systemctl("restart")
