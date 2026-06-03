from __future__ import annotations

import html

import httpx

from app.image_research.core.license_checker import canonical_license
from app.image_research.providers.base import BaseImageProvider
from app.image_research.schemas import ImageCandidate


USER_AGENT = "AuraSlidesAI/1.0 (https://example.com; contact@auraslidesai.local)"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json; charset=utf-8",
}


class WikimediaCommonsProvider(BaseImageProvider):
    async def search(
        self, query: str, per_page: int, orientation: str | None, image_type: str | None = None
    ) -> list[ImageCandidate]:
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": min(max(per_page, 3), 12),
            "prop": "imageinfo|categories",
            "iiprop": "url|size|extmetadata",
            "iiurlwidth": 1600,
            "cllimit": 10,
        }
        async with httpx.AsyncClient(timeout=25, headers=DEFAULT_HEADERS) as client:
            resp = await client.get("https://commons.wikimedia.org/w/api.php", params=params)
            if resp.status_code == 403:
                return []
            resp.raise_for_status()
            pages = (resp.json().get("query") or {}).get("pages") or {}

        candidates: list[ImageCandidate] = []
        for page_id, page in pages.items():
            image_info = (page.get("imageinfo") or [{}])[0]
            image_url = image_info.get("thumburl") or image_info.get("url")
            source_url = page.get("canonicalurl") or f"https://commons.wikimedia.org/?curid={page_id}"
            if not image_url or not source_url:
                continue
            original_url = image_info.get("url") or ""
            if not image_info.get("thumburl") and original_url.lower().split("?", 1)[0].endswith((".ogv", ".webm", ".mp4", ".mp3", ".ogg", ".wav")):
                continue
            metadata = image_info.get("extmetadata") or {}
            license_name = canonical_license((metadata.get("LicenseShortName") or {}).get("value")) or "CC BY-SA"
            categories = [
                str(category.get("title", "")).replace("Category:", "")
                for category in (page.get("categories") or [])
                if category.get("title")
            ]
            author = html.unescape((metadata.get("Artist") or {}).get("value") or "").strip() or None
            title = page.get("title", "").replace("File:", "")
            candidates.append(
                ImageCandidate(
                    id=f"commons-{page_id}",
                    source="wikimedia_commons",
                    title=title,
                    image_url=image_url,
                    preview_url=image_url,
                    source_url=source_url,
                    author=author,
                    license_name=license_name,
                    license_url=(metadata.get("LicenseUrl") or {}).get("value"),
                    width=image_info.get("width"),
                    height=image_info.get("height"),
                    tags=categories[:6],
                    categories=categories,
                    page_title=page.get("title"),
                )
            )
        return candidates
