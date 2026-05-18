import httpx

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
    async def search(
        self, query: str, per_page: int, orientation: str | None
    ) -> list[ImageCandidate]:
        params = {
            "q": query,
            "page_size": min(max(per_page, 5), 50),
            "license": "cc0,pdm,by,by-sa",
            "mature": "false",
        }
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            resp = await client.get(
                "https://api.openverse.engineering/v1/images/",
                params=params,
                headers={"User-Agent": "ImageResearcher/1.0 (local-image-research@example.invalid)"},
            )
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
                    tags=tags + [query, item.get("source") or ""],
                )
            )
        return out
