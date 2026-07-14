import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT_DIR


GIFT_DB_PATH = ROOT_DIR / "storage" / "gift.db"


class SQLiteGiftStorage:
    def __init__(self, db_path: Path = GIFT_DB_PATH, *, initialize: bool = True) -> None:
        self.db_path = db_path
        if initialize:
            self.initialize()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        migration = (ROOT_DIR / "migrations" / "gift" / "001_initial.sql").read_text(
            encoding="utf-8"
        )
        with self._connect() as conn:
            conn.executescript(migration)
            conn.execute(
                "INSERT OR IGNORE INTO gift_schema_migrations(version, applied_at) VALUES (?, ?)",
                (1, self._now()),
            )

    def list_entries(
        self, entry_type: str | None = None, person: str | None = None, year: int | None = None
    ) -> list[dict[str, Any]]:
        clauses = ["status = 'active'"]
        params: list[Any] = []
        if entry_type:
            clauses.append("entry_type = ?")
            params.append(entry_type)
        if person:
            clauses.append("(giver = ? OR recipient = ?)")
            params.extend((person, person))
        if year is not None:
            clauses.append("substr(gift_date, 1, 4) = ?")
            params.append(str(year))
        query = f"""
            SELECT id, entry_type, title, giver, recipient, gift_date, amount_yen,
                   memo, related_event, occasion_date, status, created_at, updated_at
            FROM gift_entries WHERE {' AND '.join(clauses)}
            ORDER BY gift_date IS NULL, gift_date DESC, created_at DESC
        """
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def create_entry(self, values: dict[str, Any]) -> dict[str, Any]:
        now = self._now()
        entry = {
            "id": str(uuid.uuid4()),
            "status": "active",
            "created_at": now,
            "updated_at": now,
            **values,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO gift_entries (
                    id, entry_type, title, giver, recipient, gift_date, amount_yen,
                    memo, related_event, occasion_date, status, created_at, updated_at
                ) VALUES (
                    :id, :entry_type, :title, :giver, :recipient, :gift_date, :amount_yen,
                    :memo, :related_event, :occasion_date, :status, :created_at, :updated_at
                )
                """,
                entry,
            )
        return entry

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
