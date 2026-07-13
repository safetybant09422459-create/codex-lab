import asyncio
import os
import re
import shlex
from dataclasses import dataclass
from typing import Literal

from .config import CODEX_ARGS, CODEX_BIN, GUARD_PROMPT, MAX_LOG_LINES, ROOT_DIR

_lock = asyncio.Lock()
_process: asyncio.subprocess.Process | None = None
_logs: list[str] = []
_returncode: int | None = None

SESSION_ID_RE = re.compile(
    r"^\s*(?:session id|session_id)\s*:\s*([0-9a-f]{8}-[0-9a-f-]{27,})\s*$",
    re.IGNORECASE,
)


@dataclass
class CodexSessionManager:
    """Owns the process-local Codex conversation selected by Developer."""

    session_id: str | None = None

    def reset(self) -> None:
        self.session_id = None

    def capture(self, line: str) -> None:
        match = SESSION_ID_RE.match(_clean_line(line))
        if match:
            self.session_id = match.group(1)

    def command(self, prompt: str) -> tuple[list[str], bool]:
        if self.session_id is None:
            return [CODEX_BIN, *CODEX_ARGS, prompt], False
        return [CODEX_BIN, *CODEX_ARGS, "resume", self.session_id, prompt], True


_session_manager = CodexSessionManager()

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
FINAL_MARKER_RE = re.compile(
    r"^\s*(?:final answer|assistant final|final|回答|最終回答)\s*:?\s*$",
    re.IGNORECASE,
)
TOKENS_RE = re.compile(
    r"(?:tokens?\s+used|used\s+tokens?|total\s+tokens?)\s*[:=]?\s*([0-9][0-9,]*)",
    re.IGNORECASE,
)
TOKENS_USED_LINE_RE = re.compile(r"\btokens?\s+used\b", re.IGNORECASE)
CODEX_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TMPDIR",
    "XDG_CONFIG_HOME",
    "CODEX_HOME",
)


def codex_subprocess_env() -> dict[str, str]:
    """Keep CLI discovery, locale, terminal, and Codex config without app secrets."""
    return {name: os.environ[name] for name in CODEX_ENV_ALLOWLIST if name in os.environ}


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
        or TOKENS_USED_LINE_RE.search(stripped) is not None
    )


def extract_tokens_used(lines: list[str]) -> str | None:
    for line in reversed(lines):
        match = TOKENS_RE.search(_clean_line(line))
        if match:
            return match.group(1)
    return None


def extract_final_answer_from_tokens_used(lines: list[str]) -> str:
    cleaned = [_clean_line(line) for line in lines]
    for index in range(len(cleaned) - 1, -1, -1):
        if TOKENS_USED_LINE_RE.search(cleaned[index]):
            return "\n".join(cleaned[index:]).strip()
    return ""


def extract_final_answer(lines: list[str]) -> str:
    cleaned = [_clean_line(line) for line in lines]

    tokens_answer = extract_final_answer_from_tokens_used(lines)
    if tokens_answer:
        return tokens_answer

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


def failure_summary(lines: list[str]) -> str:
    cleaned = [_clean_line(line) for line in lines]
    errors = [
        line
        for line in cleaned
        if line.startswith("[error]") or "error" in line.lower() or "failed" in line.lower()
    ]
    if errors:
        return "\n".join(errors[-12:]).strip()
    useful = [line for line in cleaned if line.strip() and not TOKENS_RE.search(line)]
    return "\n".join(useful[-20:]).strip()


def current_status() -> Literal["idle", "running", "succeeded", "failed"]:
    if _lock.locked():
        return "running"
    if _returncode is None:
        return "idle"
    if _returncode == 0:
        return "succeeded"
    return "failed"


def is_running() -> bool:
    return _lock.locked()


def logs() -> list[str]:
    return _logs


def returncode() -> int | None:
    return _returncode


def reset_session() -> None:
    if _lock.locked():
        raise RuntimeError("Codex is already running.")
    _session_manager.reset()


async def start_codex(prompt: str) -> None:
    global _returncode

    if _lock.locked():
        raise RuntimeError("Codex is already running.")

    await _lock.acquire()
    _logs.clear()
    _returncode = None
    asyncio.create_task(_run_codex(prompt))


async def _run_codex(prompt: str) -> None:
    global _process, _returncode

    full_prompt = f"{GUARD_PROMPT}{prompt}"
    command, is_resume = _session_manager.command(full_prompt)

    _append_log(f"$ cd {ROOT_DIR}")
    _append_log("Resume Session" if is_resume else "New Session")
    display_command = [CODEX_BIN, *CODEX_ARGS]
    if is_resume:
        display_command.extend(["resume", "<session>"])
    _append_log(
        "$ "
        + " ".join(shlex.quote(part) for part in display_command)
        + " <prompt>"
    )

    try:
        _process = await asyncio.create_subprocess_exec(
            *command,
            cwd=ROOT_DIR,
            env=codex_subprocess_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        assert _process.stdout is not None
        while True:
            line = await _process.stdout.readline()
            if not line:
                break
            decoded_line = line.decode("utf-8", errors="replace")
            _session_manager.capture(decoded_line)
            _append_log(decoded_line)

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
