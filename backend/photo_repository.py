from typing import Any
from urllib.parse import quote

from .photo_immich_adapter import ImmichAdapter


class PhotoRepository:
    def __init__(self, adapter: ImmichAdapter | None = None) -> None:
        self.adapter = adapter

    def get_photos(
        self, from_at: str, to_at: str, limit: int
    ) -> list[dict[str, Any]]:
        adapter = self._adapter()
        return [
            self._photo_result(asset, adapter)
            for asset in adapter.search_photos(from_at, to_at, limit)
        ]

    def _photo_result(
        self, asset: dict[str, Any], adapter: ImmichAdapter
    ) -> dict[str, Any]:
        asset_id = self._asset_id(asset)
        return {
            "asset_id": asset_id,
            "taken_at": self._taken_at(asset),
            "thumbnail_url": self.thumbnail_url(asset_id),
            "source": "immich",
        }

    def get_thumbnail(self, asset_id: str) -> tuple[bytes, str]:
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError("asset_id is required")
        return self._adapter().get_thumbnail(asset_id.strip())

    def thumbnail_url(self, asset_id: str) -> str:
        encoded_id = quote(self._asset_id({"id": asset_id}), safe="")
        return f"/api/photo/assets/{encoded_id}/thumbnail"

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
