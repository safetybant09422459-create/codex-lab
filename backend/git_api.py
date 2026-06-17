import asyncio
from typing import Literal

from fastapi import HTTPException

from .config import ROOT_DIR
from .models import ChangedFile, ChangesResponse


async def git(*args: str, check: bool = True) -> str:
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


async def git_changes() -> ChangesResponse:
    status_text = await git("status", "--short")
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
    return ChangesResponse(status_text=status_text, files=files)


def _assert_relative_repo_path(path: str) -> None:
    candidate = (ROOT_DIR / path).resolve()
    if ROOT_DIR not in candidate.parents and candidate != ROOT_DIR:
        raise HTTPException(status_code=400, detail="Path is outside target repository.")


async def file_diff(path: str) -> str:
    _assert_relative_repo_path(path)
    changes = await git_changes()
    changed = {item.path: item.status for item in changes.files}
    if path not in changed:
        raise HTTPException(status_code=404, detail="File is not changed.")

    if changed[path] == "new":
        output = await git("diff", "--no-index", "--", "/dev/null", path, check=False)
        return output or f"New file has no diff output: {path}\n"
    return await git("diff", "--", path, check=False)
