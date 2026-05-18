import httpx

from app.config import settings
from app.providers.base import BaseImageProvider
from app.schemas import ImageCandidate


def _license(value: str | None) -> str:
    key = (value or "").lower()
    return {
        "cc0": "CC0",
        "pdm": "Public Domain",
        "by": "CC BY",
        "by-sa": "CC BY-SA",
    }.get(key, value or "Unknown")


class OpenverseProvider(BaseImageProvider):
    def __init__(self) -> None:
        self._token: str | None = None

    async def _headers(self, client: httpx.AsyncClient) -> dict[str, str]:
        headers = {"User-Agent": "ImageResearcher/1.0 (local-image-research@example.invalid)"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
            return headers
        if not settings.openverse_client_id or not settings.openverse_client_secret:
            return headers
        resp = await client.post(
            "https://api.openverse.org/v1/auth_tokens/token/",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.openverse_client_id,
                "client_secret": settings.openverse_client_secret,
            },
            headers=headers,
        )
        resp.raise_for_status()
        self._token = resp.json().get("access_token")
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def search(
        self, query: str, per_page: int, orientation: str | None, image_type: str | None = None
    ) -> list[ImageCandidate]:
        params = {
            "q": query,
            "page_size": min(max(per_page, 5), 50),
            "license": "cc0,pdm,by,by-sa",
            "mature": "false",
        }
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            resp = await client.get(
                "https://api.openverse.org/v1/images/",
                params=params,
                headers=await self._headers(client),
            )
            if resp.status_code in {401, 403, 429}:
                return []
            resp.raise_for_status()
            data = resp.json()

        out: list[ImageCandidate] = []
        for item in data.get("results", []):
            image_url = item.get("url")
            if not image_url:
                continue
            if image_url.lower().split("?")[0].endswith(".svg"):
                continue
            tags = [
                tag.get("name", "")
                for tag in item.get("tags", [])
                if isinstance(tag, dict) and tag.get("name")
            ]
            out.append(
                ImageCandidate(
                    id=f"openverse-{item.get('id')}",
                    source="openverse",
                    title=item.get("title"),
                    image_url=image_url,
                    preview_url=item.get("thumbnail"),
                    source_url=item.get("foreign_landing_url") or item.get("url") or "",
                    author=item.get("creator"),
                    license_name=_license(item.get("license")),
                    license_url=item.get("license_url"),
                    width=item.get("width"),
                    height=item.get("height"),
                    tags=tags + [item.get("source") or ""],
                )
            )
        return out
