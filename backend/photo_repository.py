from typing import Any
from urllib.parse import quote

from .photo_immich_adapter import ImmichAdapter


class PhotoRepository:
    def __init__(self, adapter: ImmichAdapter | None = None) -> None:
        self.adapter = adapter

    def get_photos(
        self, from_at: str, to_at: str, limit: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        adapter = self._adapter()
        return [
            self._photo_result(asset)
            for asset in adapter.search_photos(from_at, to_at, limit, offset)
        ]

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError("asset_id is required")
        return self._asset_result(self._adapter().get_asset(asset_id.strip()))

    def _photo_result(self, asset: dict[str, Any]) -> dict[str, Any]:
        asset_id = self._asset_id(asset)
        return {
            "asset_id": asset_id,
            "taken_at": self._taken_at(asset),
            "has_location": self._has_location(asset),
            "has_faces": self._has_faces(asset),
            "camera_make": self._exif_text(asset, "make"),
            "camera_model": self._exif_text(asset, "model"),
            "timezone": self._exif_text(asset, "timeZone"),
            "thumbnail_url": self.thumbnail_url(asset_id),
            "preview_url": self.preview_url(asset_id),
            "source": "immich",
        }

    def _asset_result(self, asset: dict[str, Any]) -> dict[str, Any]:
        asset_id = self._asset_id(asset)
        return {
            "asset_id": asset_id,
            "taken_at": self._taken_at(asset),
            "thumbnail_url": self.thumbnail_url(asset_id),
            "preview_url": self.preview_url(asset_id),
            "source": "immich",
            "filename": self._filename(asset),
            "width": self._dimension(asset, "exifImageWidth"),
            "height": self._dimension(asset, "exifImageHeight"),
        }

    def get_thumbnail(self, asset_id: str) -> tuple[bytes, str]:
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError("asset_id is required")
        return self._adapter().get_thumbnail(asset_id.strip())

    def get_preview(self, asset_id: str) -> tuple[bytes, str]:
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError("asset_id is required")
        return self._adapter().get_preview(asset_id.strip())

    def thumbnail_url(self, asset_id: str) -> str:
        encoded_id = quote(self._asset_id({"id": asset_id}), safe="")
        return f"/api/photo/assets/{encoded_id}/thumbnail"

    def preview_url(self, asset_id: str) -> str:
        encoded_id = quote(self._asset_id({"id": asset_id}), safe="")
        return f"/api/photo/assets/{encoded_id}/preview"

    def _adapter(self) -> ImmichAdapter:
        if self.adapter is None:
            self.adapter = ImmichAdapter()
        return self.adapter

    def _asset_id(self, asset: dict[str, Any]) -> str:
        asset_id = asset.get("id")
        if isinstance(asset_id, str) and asset_id.strip():
            return asset_id.strip()
        raise ValueError("Immich asset is missing id")

    def _taken_at(self, asset: dict[str, Any]) -> str | None:
        for field in ("fileCreatedAt", "localDateTime", "createdAt"):
            value = asset.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _filename(self, asset: dict[str, Any]) -> str | None:
        for field in ("originalFileName", "originalPath", "fileName"):
            value = asset.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip().rsplit("/", 1)[-1]
        return None

    @staticmethod
    def _has_location(asset: dict[str, Any]) -> bool:
        exif = asset.get("exifInfo")
        if not isinstance(exif, dict):
            return False
        return exif.get("latitude") is not None and exif.get("longitude") is not None

    @staticmethod
    def _has_faces(asset: dict[str, Any]) -> bool:
        people = asset.get("people")
        return isinstance(people, list) and bool(people)

    @staticmethod
    def _exif_text(asset: dict[str, Any], field_name: str) -> str | None:
        exif = asset.get("exifInfo")
        if not isinstance(exif, dict):
            return None
        value = exif.get(field_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _dimension(self, asset: dict[str, Any], field_name: str) -> int | None:
        exif = asset.get("exifInfo")
        if isinstance(exif, dict):
            value = exif.get(field_name)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
        value = asset.get(field_name)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return None
