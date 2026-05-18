import httpx

from app.providers.base import BaseImageProvider
from app.schemas import ImageCandidate


class PixabayProvider(BaseImageProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(
        self, query: str, per_page: int, orientation: str | None, image_type: str | None = None
    ) -> list[ImageCandidate]:
        pixabay_type = "photo"
        if image_type in {"illustration", "icon", "diagram"}:
            pixabay_type = "illustration"
        params = {
            "key": self.api_key,
            "q": query,
            "per_page": min(max(per_page, 3), 200),
            "safesearch": "true",
            "image_type": pixabay_type,
        }
        if orientation and orientation in {"horizontal", "vertical"}:
            params["orientation"] = orientation
        elif orientation == "landscape":
            params["orientation"] = "horizontal"
        elif orientation == "portrait":
            params["orientation"] = "vertical"

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get("https://pixabay.com/api/", params=params)
            resp.raise_for_status()
            data = resp.json()

        out: list[ImageCandidate] = []
        for item in data.get("hits", []):
            image_url = item.get("largeImageURL") or item.get("webformatURL")
            if not image_url:
                continue
            tags = [tag.strip() for tag in (item.get("tags") or "").split(",") if tag.strip()]
            out.append(
                ImageCandidate(
                    id=f"pixabay-{item.get('id')}",
                    source="pixabay",
                    title=item.get("tags"),
                    image_url=image_url,
                    preview_url=item.get("previewURL") or item.get("webformatURL"),
                    source_url=item.get("pageURL") or "",
                    author=item.get("user"),
                    license_name="Pixabay Content License",
                    license_url="https://pixabay.com/service/license-summary/",
                    width=item.get("imageWidth") or item.get("webformatWidth"),
                    height=item.get("imageHeight") or item.get("webformatHeight"),
                    tags=tags,
                )
            )
        return out
