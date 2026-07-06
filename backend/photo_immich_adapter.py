import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class ImmichConfigurationError(RuntimeError):
    pass


class ImmichAPIError(RuntimeError):
    pass


class ImmichAdapter:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("IMMICH_BASE_URL", "")).strip()
        self.api_key = (api_key or os.environ.get("IMMICH_API_KEY", "")).strip()
        try:
            self.timeout_seconds = timeout_seconds or float(
                os.environ.get("IMMICH_TIMEOUT_SECONDS", "10")
            )
        except ValueError as exc:
            raise ImmichConfigurationError(
                "IMMICH_TIMEOUT_SECONDS must be a number"
            ) from exc

        if not self.base_url:
            raise ImmichConfigurationError("IMMICH_BASE_URL is required")
        if not self.api_key:
            raise ImmichConfigurationError("IMMICH_API_KEY is required")

        self.base_url = self.base_url.rstrip("/")

    def search_photos(
        self, from_at: str, to_at: str, limit: int, offset: int = 0
    ) -> list[dict[str, Any]]:
        page_size = 100
        page = (offset // page_size) + 1
        skip = offset % page_size
        assets: list[dict[str, Any]] = []

        while len(assets) < limit:
            page_assets = self._search_photos_page(from_at, to_at, page_size, page)
            if not page_assets:
                break
            assets.extend(page_assets[skip:])
            if len(page_assets) < page_size:
                break
            page += 1
            skip = 0

        return assets[:limit]

    def _search_photos_page(
        self, from_at: str, to_at: str, size: int, page: int
    ) -> list[dict[str, Any]]:
        response = self._post_json(
            "/search/metadata",
            {
                "takenAfter": from_at,
                "takenBefore": to_at,
                "size": size,
                "page": page,
                "type": "IMAGE",
                "withExif": True,
            },
        )
        return self._extract_assets(response)

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        encoded_id = quote(asset_id, safe="")
        return self._get_json(f"/assets/{encoded_id}")

    def get_thumbnail(self, asset_id: str) -> tuple[bytes, str]:
        return self._get_thumbnail(asset_id, "thumbnail")

    def get_preview(self, asset_id: str) -> tuple[bytes, str]:
        return self._get_thumbnail(asset_id, "preview")

    def _get_thumbnail(self, asset_id: str, size: str) -> tuple[bytes, str]:
        encoded_id = quote(asset_id, safe="")
        request = Request(
            self._url(f"/assets/{encoded_id}/thumbnail?size={size}"),
            headers={
                "Accept": "image/*",
                "x-api-key": self.api_key,
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                content_type = response.headers.get_content_type()
                return response.read(), content_type
        except HTTPError as exc:
            raise ImmichAPIError(
                f"Immich API request failed with status {exc.code}"
            ) from exc
        except URLError as exc:
            raise ImmichAPIError(f"Immich API request failed: {exc.reason}") from exc

    def _get_json(self, path: str) -> dict[str, Any]:
        request = Request(
            self._url(path),
            headers={
                "Accept": "application/json",
                "x-api-key": self.api_key,
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ImmichAPIError(
                f"Immich API request failed with status {exc.code}"
            ) from exc
        except URLError as exc:
            raise ImmichAPIError(f"Immich API request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ImmichAPIError("Immich API returned invalid JSON") from exc

        if not isinstance(decoded, dict):
            raise ImmichAPIError("Immich API returned invalid JSON object")
        return decoded

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self._url(path),
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise ImmichAPIError(
                f"Immich API request failed with status {exc.code}"
            ) from exc
        except URLError as exc:
            raise ImmichAPIError(f"Immich API request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ImmichAPIError("Immich API returned invalid JSON") from exc

    def _extract_assets(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        assets = response.get("assets")
        if isinstance(assets, dict) and isinstance(assets.get("items"), list):
            return [item for item in assets["items"] if isinstance(item, dict)]
        if isinstance(assets, list):
            return [item for item in assets if isinstance(item, dict)]
        if isinstance(response.get("items"), list):
            return [item for item in response["items"] if isinstance(item, dict)]
        if isinstance(response, list):
            return [item for item in response if isinstance(item, dict)]
        return []

    def _url(self, path: str) -> str:
        return f"{self._api_base()}{path}"

    def _api_base(self) -> str:
        if self.base_url.endswith("/api"):
            return self.base_url
        return f"{self.base_url}/api"
