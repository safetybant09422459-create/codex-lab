import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ROOT_DIR


TRAVEL_DB_PATH = ROOT_DIR / "storage" / "travel.db"


class SQLiteTravelStorage:
    def __init__(
        self,
        db_path: Path = TRAVEL_DB_PATH,
        *,
        initialize: bool = True,
    ) -> None:
        self.db_path = db_path
        if initialize:
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

                CREATE TABLE IF NOT EXISTS travel_experience_photo_links (
                    id TEXT PRIMARY KEY,
                    experience_id TEXT NOT NULL,
                    photo_asset_id TEXT NOT NULL,
                    link_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(experience_id) REFERENCES travel_timeline_items(id)
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
                SELECT
                    t.id,
                    t.title,
                    t.status,
                    t.privacy_level,
                    t.start_date,
                    t.end_date,
                    t.prefectures,
                    t.outing_type,
                    t.cover_image_id,
                    t.memo,
                    t.created_by,
                    t.created_at,
                    t.updated_at,
                    c.id AS cover_id,
                    c.image_source AS cover_image_source,
                    c.image_ref AS cover_image_ref,
                    c.source_provider AS cover_source_provider,
                    c.attribution AS cover_attribution,
                    c.selected_by AS cover_selected_by,
                    c.selected_at AS cover_selected_at,
                    c.status AS cover_status,
                    c.created_at AS cover_created_at
                FROM travel_trips t
                LEFT JOIN travel_cover_images c
                  ON c.id = t.cover_image_id
                 AND c.owner_type = 'trip'
                 AND c.owner_id = t.id
                 AND c.status = 'active'
                WHERE t.id = ?
                """,
                (trip_id,),
            ).fetchone()
        return self._trip_row_to_dict(row) if row is not None else None

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

    def get_timeline_item(self, timeline_item_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, trip_id, item_type, display_title, place_name, place_id,
                       category, start_at, end_at, time_kind, cover_image_id, memo,
                       order_no, status, created_at, updated_at
                FROM travel_timeline_items
                WHERE id = ?
                """,
                (timeline_item_id,),
            ).fetchone()
        return self._row_to_dict(row) if row is not None else None

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

    def update_timeline_item(
        self, timeline_item_id: str, **kwargs: Any
    ) -> dict[str, Any] | None:
        allowed_columns = {
            "item_type",
            "display_title",
            "place_name",
            "place_id",
            "category",
            "start_at",
            "end_at",
            "time_kind",
            "memo",
            "order_no",
            "status",
            "cover_image_id",
        }
        updates = {
            key: value for key, value in kwargs.items() if key in allowed_columns
        }
        if not updates:
            return self.get_timeline_item(timeline_item_id)

        now = self._now()
        assignments = [f"{column} = :{column}" for column in updates]
        assignments.append("updated_at = :updated_at")
        values = dict(updates)
        values["updated_at"] = now
        values["id"] = timeline_item_id

        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                UPDATE travel_timeline_items
                SET {", ".join(assignments)}
                WHERE id = :id
                """,
                values,
            )
            if cursor.rowcount == 0:
                return None

        return self.get_timeline_item(timeline_item_id)

    def set_trip_cover_image(
        self,
        *,
        trip_id: str,
        asset_id: str,
        selected_by: str = "admin",
    ) -> dict[str, Any]:
        now = self._now()
        cover_image = {
            "id": f"cover_{uuid.uuid4().hex}",
            "owner_type": "trip",
            "owner_id": trip_id,
            "image_source": "photo_asset",
            "image_ref": asset_id,
            "source_provider": "immich",
            "attribution": None,
            "selected_by": selected_by,
            "selected_at": now,
            "status": "active",
            "created_at": now,
        }
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE travel_cover_images
                SET status = 'inactive'
                WHERE owner_type = 'trip'
                  AND owner_id = ?
                  AND status = 'active'
                """,
                (trip_id,),
            )
            conn.execute(
                """
                INSERT INTO travel_cover_images (
                    id, owner_type, owner_id, image_source, image_ref,
                    source_provider, attribution, selected_by, selected_at,
                    status, created_at
                )
                VALUES (
                    :id, :owner_type, :owner_id, :image_source, :image_ref,
                    :source_provider, :attribution, :selected_by, :selected_at,
                    :status, :created_at
                )
                """,
                cover_image,
            )
            conn.execute(
                """
                UPDATE travel_trips
                SET cover_image_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (cover_image["id"], now, trip_id),
            )
        return cover_image

    def set_spot_cover_image(
        self,
        *,
        timeline_item_id: str,
        asset_id: str,
        selected_by: str = "admin",
    ) -> dict[str, Any]:
        now = self._now()
        cover_image = {
            "id": f"cover_{uuid.uuid4().hex}",
            "owner_type": "timeline_item",
            "owner_id": timeline_item_id,
            "image_source": "photo_asset",
            "image_ref": asset_id,
            "source_provider": "immich",
            "attribution": None,
            "selected_by": selected_by,
            "selected_at": now,
            "status": "active",
            "created_at": now,
        }
        with self._connect() as conn:
            item = conn.execute(
                """
                SELECT id
                FROM travel_timeline_items
                WHERE id = ?
                """,
                (timeline_item_id,),
            ).fetchone()
            if item is None:
                raise ValueError("timeline item not found")

            conn.execute(
                """
                UPDATE travel_cover_images
                SET status = 'inactive'
                WHERE owner_type = 'timeline_item'
                  AND owner_id = ?
                  AND status = 'active'
                """,
                (timeline_item_id,),
            )
            conn.execute(
                """
                INSERT INTO travel_cover_images (
                    id, owner_type, owner_id, image_source, image_ref,
                    source_provider, attribution, selected_by, selected_at,
                    status, created_at
                )
                VALUES (
                    :id, :owner_type, :owner_id, :image_source, :image_ref,
                    :source_provider, :attribution, :selected_by, :selected_at,
                    :status, :created_at
                )
                """,
                cover_image,
            )
            conn.execute(
                """
                UPDATE travel_timeline_items
                SET cover_image_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (cover_image["id"], now, timeline_item_id),
            )
        return cover_image

    def link_experience_photo(
        self,
        *,
        experience_id: str,
        photo_asset_id: str,
        link_type: str,
        created_by: str = "admin",
    ) -> dict[str, Any]:
        now = self._now()
        with self._connect() as conn:
            item = conn.execute(
                """
                SELECT id
                FROM travel_timeline_items
                WHERE id = ?
                """,
                (experience_id,),
            ).fetchone()
            if item is None:
                raise ValueError("experience not found")

            if link_type == "cover":
                conn.execute(
                    """
                    UPDATE travel_experience_photo_links
                    SET status = 'archived', updated_at = ?
                    WHERE experience_id = ?
                      AND link_type = 'cover'
                      AND status = 'active'
                    """,
                    (now, experience_id),
                )

            existing = conn.execute(
                """
                SELECT id, experience_id, photo_asset_id, link_type, status,
                       created_by, created_at, updated_at
                FROM travel_experience_photo_links
                WHERE experience_id = ?
                  AND photo_asset_id = ?
                  AND link_type = ?
                  AND status = 'active'
                """,
                (experience_id, photo_asset_id, link_type),
            ).fetchone()
            if existing is not None:
                return self._row_to_dict(existing)

            link = {
                "id": f"explink_{uuid.uuid4().hex}",
                "experience_id": experience_id,
                "photo_asset_id": photo_asset_id,
                "link_type": link_type,
                "status": "active",
                "created_by": created_by,
                "created_at": now,
                "updated_at": now,
            }
            conn.execute(
                """
                INSERT INTO travel_experience_photo_links (
                    id, experience_id, photo_asset_id, link_type, status,
                    created_by, created_at, updated_at
                )
                VALUES (
                    :id, :experience_id, :photo_asset_id, :link_type, :status,
                    :created_by, :created_at, :updated_at
                )
                """,
                link,
            )
        return link

    def get_experience_photo_links(
        self, experience_id: str, status: str = "active"
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, experience_id, photo_asset_id, link_type, status,
                       created_by, created_at, updated_at
                FROM travel_experience_photo_links
                WHERE experience_id = ?
                  AND status = ?
                ORDER BY link_type = 'cover' DESC, created_at, id
                """,
                (experience_id, status),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def archive_experience_photo_link(
        self, *, experience_id: str, link_id: str
    ) -> dict[str, Any] | None:
        now = self._now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE travel_experience_photo_links
                SET status = 'archived', updated_at = ?
                WHERE id = ?
                  AND experience_id = ?
                """,
                (now, link_id, experience_id),
            )
            if cursor.rowcount == 0:
                return None
            row = conn.execute(
                """
                SELECT id, experience_id, photo_asset_id, link_type, status,
                       created_by, created_at, updated_at
                FROM travel_experience_photo_links
                WHERE id = ?
                  AND experience_id = ?
                """,
                (link_id, experience_id),
            ).fetchone()
        return self._row_to_dict(row) if row is not None else None

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def _trip_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        trip = {
            key: data.get(key)
            for key in (
                "id",
                "title",
                "status",
                "privacy_level",
                "start_date",
                "end_date",
                "prefectures",
                "outing_type",
                "cover_image_id",
                "memo",
                "created_by",
                "created_at",
                "updated_at",
            )
        }
        if data.get("cover_id"):
            trip["cover_image"] = {
                "id": data.get("cover_id"),
                "owner_type": "trip",
                "owner_id": data.get("id"),
                "image_source": data.get("cover_image_source"),
                "image_ref": data.get("cover_image_ref"),
                "source_provider": data.get("cover_source_provider"),
                "attribution": data.get("cover_attribution"),
                "selected_by": data.get("cover_selected_by"),
                "selected_at": data.get("cover_selected_at"),
                "status": data.get("cover_status"),
                "created_at": data.get("cover_created_at"),
            }
        return trip

    def _now(self) -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    def _serialize_prefectures(self, prefectures: Any) -> str | None:
        if prefectures is None or prefectures == "":
            return None
        if isinstance(prefectures, str):
            return prefectures
        return json.dumps(prefectures, ensure_ascii=False, separators=(",", ":"))
