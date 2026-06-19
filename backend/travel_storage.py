import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ROOT_DIR


TRAVEL_DB_PATH = ROOT_DIR / "storage" / "travel.db"


class SQLiteTravelStorage:
    def __init__(self, db_path: Path = TRAVEL_DB_PATH) -> None:
        self.db_path = db_path
        self.initialize()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS travel_trips (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    privacy_level TEXT NOT NULL,
                    start_date TEXT,
                    end_date TEXT,
                    prefectures TEXT,
                    outing_type TEXT,
                    cover_image_id TEXT,
                    memo TEXT,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS travel_timeline_items (
                    id TEXT PRIMARY KEY,
                    trip_id TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    display_title TEXT NOT NULL,
                    place_name TEXT,
                    place_id TEXT,
                    category TEXT,
                    start_at TEXT,
                    end_at TEXT,
                    time_kind TEXT,
                    cover_image_id TEXT,
                    memo TEXT,
                    order_no INTEGER,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(trip_id) REFERENCES travel_trips(id)
                );

                CREATE TABLE IF NOT EXISTS travel_cover_images (
                    id TEXT PRIMARY KEY,
                    owner_type TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    image_source TEXT NOT NULL,
                    image_ref TEXT NOT NULL,
                    source_provider TEXT,
                    attribution TEXT,
                    selected_by TEXT,
                    selected_at TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def get_trips(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, title, status, privacy_level, start_date, end_date,
                       prefectures, outing_type, cover_image_id, memo, created_by,
                       created_at, updated_at
                FROM travel_trips
                ORDER BY start_date IS NULL, start_date, created_at
                """
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_trip(self, trip_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, title, status, privacy_level, start_date, end_date,
                       prefectures, outing_type, cover_image_id, memo, created_by,
                       created_at, updated_at
                FROM travel_trips
                WHERE id = ?
                """,
                (trip_id,),
            ).fetchone()
        return self._row_to_dict(row) if row is not None else None

    def get_trip_timeline(self, trip_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, trip_id, item_type, display_title, place_name, place_id,
                       category, start_at, end_at, time_kind, cover_image_id, memo,
                       order_no, status, created_at, updated_at
                FROM travel_timeline_items
                WHERE trip_id = ?
                ORDER BY order_no IS NULL, order_no, start_at IS NULL, start_at, created_at
                """,
                (trip_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def create_trip(
        self,
        *,
        title: str,
        start_date: str | None = None,
        end_date: str | None = None,
        outing_type: str | None = None,
        prefectures: Any = None,
        memo: str | None = None,
        privacy_level: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        now = self._now()
        trip = {
            "id": f"trip_{uuid.uuid4().hex}",
            "title": title,
            "status": "planning",
            "privacy_level": privacy_level or "private",
            "start_date": start_date,
            "end_date": end_date,
            "prefectures": self._serialize_prefectures(prefectures),
            "outing_type": outing_type,
            "cover_image_id": None,
            "memo": memo,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO travel_trips (
                    id, title, status, privacy_level, start_date, end_date,
                    prefectures, outing_type, cover_image_id, memo, created_by,
                    created_at, updated_at
                )
                VALUES (
                    :id, :title, :status, :privacy_level, :start_date, :end_date,
                    :prefectures, :outing_type, :cover_image_id, :memo, :created_by,
                    :created_at, :updated_at
                )
                """,
                trip,
            )
        return trip

    def create_timeline_item(
        self,
        *,
        trip_id: str,
        item_type: str,
        display_title: str,
        place_name: str | None = None,
        place_id: str | None = None,
        category: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        time_kind: str | None = None,
        memo: str | None = None,
        order_no: int | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        now = self._now()
        item = {
            "id": f"item_{uuid.uuid4().hex}",
            "trip_id": trip_id,
            "item_type": item_type,
            "display_title": display_title,
            "place_name": place_name,
            "place_id": place_id,
            "category": category,
            "start_at": start_at,
            "end_at": end_at,
            "time_kind": time_kind,
            "cover_image_id": None,
            "memo": memo,
            "order_no": order_no,
            "status": status or "planned",
            "created_at": now,
            "updated_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO travel_timeline_items (
                    id, trip_id, item_type, display_title, place_name, place_id,
                    category, start_at, end_at, time_kind, cover_image_id, memo,
                    order_no, status, created_at, updated_at
                )
                VALUES (
                    :id, :trip_id, :item_type, :display_title, :place_name, :place_id,
                    :category, :start_at, :end_at, :time_kind, :cover_image_id, :memo,
                    :order_no, :status, :created_at, :updated_at
                )
                """,
                item,
            )
        return item

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def _now(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _serialize_prefectures(self, prefectures: Any) -> str | None:
        if prefectures is None or prefectures == "":
            return None
        if isinstance(prefectures, str):
            return prefectures
        return json.dumps(prefectures, ensure_ascii=False, separators=(",", ":"))
