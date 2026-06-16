import asyncio
import os
import re
import shlex
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT_DIR = Path("/mnt/nas/projects/codex-lab")
FRONTEND_DIR = ROOT_DIR / "frontend"
CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
CODEX_ARGS = shlex.split(os.environ.get("CODEX_ARGS", "exec"))
MAX_LOG_LINES = int(os.environ.get("JARVIS_DEV_MAX_LOG_LINES", "2000"))

GUARD_PROMPT = """\
You are running from Jarvis Dev v0.2.

Safety rules:
- Work only in /mnt/nas/projects/codex-lab.
- Do not touch /mnt/nas/projects/project.
- Do not run git commit or git push.
- Do not run destructive commands unless the user explicitly asks and confirms.
- This prototype is intended for docs-change experiments first.

User prompt:
"""


class RunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)


class RunResponse(BaseModel):
    status: Literal["started"]


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
    rejected: bool


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


app = FastAPI(title="Jarvis Dev v0.2")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

_lock = asyncio.Lock()
_process: asyncio.subprocess.Process | None = None
_logs: list[str] = []
_returncode: int | None = None
_rejected = False

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
FINAL_MARKER_RE = re.compile(
    r"^\s*(?:final answer|assistant final|final|回答|最終回答)\s*:?\s*$",
    re.IGNORECASE,
)
TOKENS_RE = re.compile(
    r"(?:tokens?\s+used|used\s+tokens?|total\s+tokens?)\s*[:=]?\s*([0-9][0-9,]*)",
    re.IGNORECASE,
)


def _append_log(line: str) -> None:
    _logs.append(line.rstrip("\n"))
    if len(_logs) > MAX_LOG_LINES:
        del _logs[: len(_logs) - MAX_LOG_LINES]


def _clean_line(line: str) -> str:
    return ANSI_RE.sub("", line).rstrip()


def _is_runtime_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return (
        stripped.startswith("$ ")
        or stripped.startswith("[process exited:")
        or stripped.startswith("[error]")
        or "tokens used" in stripped.lower()
    )


def _extract_tokens_used(lines: list[str]) -> str | None:
    for line in reversed(lines):
        match = TOKENS_RE.search(_clean_line(line))
        if match:
            return match.group(1)
    return None


def _extract_final_answer(lines: list[str]) -> str:
    cleaned = [_clean_line(line) for line in lines]

    for index in range(len(cleaned) - 1, -1, -1):
        if FINAL_MARKER_RE.match(cleaned[index]):
            answer_lines: list[str] = []
            for line in cleaned[index + 1 :]:
                if line.startswith("[process exited:"):
                    break
                if TOKENS_RE.search(line):
                    continue
                answer_lines.append(line)
            return "\n".join(answer_lines).strip()

    block: list[str] = []
    for line in reversed(cleaned):
        if not line.strip() or _is_runtime_line(line):
            if block:
                break
            continue
        block.append(line)
    return "\n".join(reversed(block)).strip()


def _current_status() -> Literal["idle", "running", "succeeded", "failed"]:
    if _lock.locked():
        return "running"
    if _returncode is None:
        return "idle"
    if _returncode == 0:
        return "succeeded"
    return "failed"


async def _git(*args: str, check: bool = True) -> str:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=ROOT_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    output = stdout.decode("utf-8", errors="replace")
    if check and process.returncode != 0:
        raise HTTPException(status_code=400, detail=output.strip() or "git command failed")
    return output


def _status_kind(code: str) -> Literal["new", "modified", "deleted"]:
    if code == "??" or "A" in code:
        return "new"
    if "D" in code:
        return "deleted"
    return "modified"


def _status_path(raw_path: str) -> str:
    if " -> " in raw_path:
        return raw_path.rsplit(" -> ", 1)[1]
    return raw_path


async def _git_changes() -> ChangesResponse:
    status_text = await _git("status", "--short")
    files: list[ChangedFile] = []
    for line in status_text.splitlines():
        if len(line) < 4:
            continue
        code = line[:2]
        raw_path = line[3:].strip()
        files.append(
            ChangedFile(
                path=_status_path(raw_path),
                status=_status_kind(code),
                raw=line,
            )
        )
    return ChangesResponse(status_text=status_text, files=files, rejected=_rejected)


def _assert_relative_repo_path(path: str) -> None:
    candidate = (ROOT_DIR / path).resolve()
    if ROOT_DIR not in candidate.parents and candidate != ROOT_DIR:
        raise HTTPException(status_code=400, detail="Path is outside target repository.")


async def _file_diff(path: str) -> str:
    _assert_relative_repo_path(path)
    changes = await _git_changes()
    changed = {item.path: item.status for item in changes.files}
    if path not in changed:
        raise HTTPException(status_code=404, detail="File is not changed.")

    if changed[path] == "new":
        output = await _git("diff", "--no-index", "--", "/dev/null", path, check=False)
        return output or f"New file has no diff output: {path}\n"
    return await _git("diff", "--", path, check=False)


async def _run_codex(prompt: str) -> None:
    global _process, _returncode

    full_prompt = f"{GUARD_PROMPT}{prompt}"
    command = [CODEX_BIN, *CODEX_ARGS, full_prompt]

    _append_log(f"$ cd {ROOT_DIR}")
    _append_log("$ " + " ".join(shlex.quote(part) for part in command[:-1]) + " <prompt>")

    try:
        _process = await asyncio.create_subprocess_exec(
            *command,
            cwd=ROOT_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        assert _process.stdout is not None
        while True:
            line = await _process.stdout.readline()
            if not line:
                break
            _append_log(line.decode("utf-8", errors="replace"))

        _returncode = await _process.wait()
        _append_log(f"[process exited: {_returncode}]")
    except FileNotFoundError:
        _returncode = 127
        _append_log(
            f"[error] Codex CLI not found: {CODEX_BIN}. "
            "Set CODEX_BIN or install codex CLI on this machine."
        )
    except Exception as exc:
        _returncode = 1
        _append_log(f"[error] {type(exc).__name__}: {exc}")
    finally:
        _process = None
        if _lock.locked():
            _lock.release()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.post("/api/run", response_model=RunResponse)
async def run_codex(request: RunRequest) -> RunResponse:
    global _rejected, _returncode

    if _lock.locked():
        raise HTTPException(status_code=409, detail="Codex is already running.")

    await _lock.acquire()
    _logs.clear()
    _rejected = False
    _returncode = None
    asyncio.create_task(_run_codex(request.prompt))
    return RunResponse(status="started")


@app.get("/api/logs", response_model=LogResponse)
async def get_logs() -> LogResponse:
    return LogResponse(
        running=_lock.locked(),
        returncode=_returncode,
        status=_current_status(),
        lines=_logs,
        final_answer=_extract_final_answer(_logs),
        tokens_used=_extract_tokens_used(_logs),
    )


@app.get("/api/changes", response_model=ChangesResponse)
async def get_changes() -> ChangesResponse:
    return await _git_changes()


@app.get("/api/diff", response_model=DiffResponse)
async def get_diff(path: str) -> DiffResponse:
    return DiffResponse(path=path, diff=await _file_diff(path))


@app.post("/api/reject", response_model=GitActionResponse)
async def reject_changes() -> GitActionResponse:
    global _rejected

    _rejected = True
    return GitActionResponse(
        ok=True,
        output="Rejected in Jarvis Dev. No files were reverted and no Git command was run.",
    )


@app.post("/api/commit", response_model=GitActionResponse)
async def commit_changes(request: CommitRequest) -> GitActionResponse:
    if _lock.locked():
        raise HTTPException(status_code=409, detail="Codex is still running.")

    changes = await _git_changes()
    if not changes.files:
        raise HTTPException(status_code=400, detail="No changes to commit.")

    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Commit message is required.")

    await _git("add", "-A")
    output = await _git("commit", "-m", message)
    return GitActionResponse(ok=True, output=output)


@app.post("/api/push", response_model=GitActionResponse)
async def push_changes(request: PushRequest) -> GitActionResponse:
    if _lock.locked():
        raise HTTPException(status_code=409, detail="Codex is still running.")
    if not request.confirm or request.confirm_text != "PUSH":
        raise HTTPException(status_code=400, detail="Push requires two confirmations.")

    output = await _git("push")
    return GitActionResponse(ok=True, output=output)
