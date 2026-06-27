import os
import shlex
from pathlib import Path

ROOT_DIR = Path("/mnt/nas/projects/codex-lab")


def load_project_env() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.is_file():
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_project_env_without_dependency(env_path)
        return

    load_dotenv(env_path, override=False)


def _load_project_env_without_dependency(env_path: Path) -> None:
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue

        key = key.strip()
        if not key or not _is_valid_env_name(key):
            continue

        os.environ.setdefault(key, _parse_env_value(value))


def _is_valid_env_name(name: str) -> bool:
    return all(c.isalnum() or c == "_" for c in name) and not name[0].isdigit()


def _parse_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        quote = value[0]
        value = value[1:-1]
        if quote == '"':
            return value.encode("utf-8").decode("unicode_escape")
        return value

    return value.split(" #", 1)[0].strip()


load_project_env()

FRONTEND_DIR = ROOT_DIR / "frontend"
SKILLS_DIR = ROOT_DIR / "skills"
TOOLS_DIR = ROOT_DIR / "tools"
CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
CODEX_ARGS = shlex.split(os.environ.get("CODEX_ARGS", "exec"))
MAX_LOG_LINES = int(os.environ.get("JARVIS_DEV_MAX_LOG_LINES", "2000"))
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano").strip()

GUARD_PROMPT = """\
You are running from Jarvis Dev v0.3.

Safety rules:
- Work only in /mnt/nas/projects/codex-lab.
- Do not touch /mnt/nas/projects/project.
- Do not run git commit or git push.
- Do not run destructive commands unless the user explicitly asks and confirms.
- This prototype is intended for docs-change experiments first.

User prompt:
"""
