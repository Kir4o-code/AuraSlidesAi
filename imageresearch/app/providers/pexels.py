import httpx

from app.providers.base import BaseImageProvider
from app.schemas import ImageCandidate


class PexelsProvider(BaseImageProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(
        self, query: str, per_page: int, orientation: str | None
    ) -> list[ImageCandidate]:
        params = {"query": query, "per_page": per_page}
        if orientation and orientation != "any":
            params["orientation"] = orientation
        headers = {"Authorization": self.api_key}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                "https://api.pexels.com/v1/search", params=params, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()

        out: list[ImageCandidate] = []
        for item in data.get("photos", []):
            src = item.get("src") or {}
            image_url = src.get("large2x") or src.get("large") or src.get("original")
            if not image_url:
                continue
            out.append(
                ImageCandidate(
                    id=f"pexels-{item.get('id')}",
                    source="pexels",
                    title=item.get("alt"),
                    image_url=image_url,
                    preview_url=src.get("medium") or src.get("small"),
                    source_url=item.get("url") or "",
                    author=item.get("photographer"),
                    license_name="Pexels License",
                    license_url="https://www.pexels.com/license/",
                    width=item.get("width"),
                    height=item.get("height"),
                    tags=[query],
                )
            )
        return out
