from typing import Literal

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
