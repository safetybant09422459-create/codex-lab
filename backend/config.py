import os
import shlex
from pathlib import Path

ROOT_DIR = Path("/mnt/nas/projects/codex-lab")
FRONTEND_DIR = ROOT_DIR / "frontend"
CODEX_BIN = os.environ.get("CODEX_BIN", "codex")
CODEX_ARGS = shlex.split(os.environ.get("CODEX_ARGS", "exec"))
MAX_LOG_LINES = int(os.environ.get("JARVIS_DEV_MAX_LOG_LINES", "2000"))

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
