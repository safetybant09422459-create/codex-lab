import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ROOT_DIR


AUDIT_LOG_PATH = ROOT_DIR / "logs" / "audit.log"


class AuditLogger:
    def __init__(self, log_path: Path = AUDIT_LOG_PATH) -> None:
        self.log_path = log_path

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        item = {"timestamp": self._timestamp(), **event}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as audit_file:
            audit_file.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
            audit_file.write("\n")
        return item

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if limit < 1:
            return []
        if not self.log_path.exists():
            return []

        items: list[dict[str, Any]] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                items.append(data)

        return list(reversed(items[-limit:]))

    def _timestamp(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")
