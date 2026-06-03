from __future__ import annotations

from urllib.parse import quote

import httpx

from app.image_research.providers.base import BaseImageProvider
from app.image_research.schemas import ImageCandidate


USER_AGENT = "AuraSlidesAI/1.0 (https://example.com; contact@auraslidesai.local)"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json; charset=utf-8",
}


class WikipediaProvider(BaseImageProvider):
    async def search(
        self, query: str, per_page: int, orientation: str | None, image_type: str | None = None
    ) -> list[ImageCandidate]:
        titles = self._title_candidates(query)
        api_titles = await self._candidate_titles(query, per_page=min(per_page, 5))
        for title in api_titles:
            if title not in titles:
                titles.append(title)

        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=DEFAULT_HEADERS) as client:
            for title in titles:
                summary = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe=':_()/')}")
                if summary.status_code == 404:
                    continue
                if summary.status_code == 403:
                    continue
                summary.raise_for_status()
                data = summary.json()
                thumbnail = data.get("originalimage") or data.get("thumbnail") or {}
                image_url = thumbnail.get("source")
                source_url = data.get("content_urls", {}).get("desktop", {}).get("page")
                if not image_url or not source_url:
                    continue
                description = data.get("description") or data.get("extract")
                return [
                    ImageCandidate(
                        id=f"wikipedia-{data.get('title', title)}",
                        source="wikipedia",
                        title=data.get("title") or title,
                        image_url=image_url,
                        preview_url=(data.get("thumbnail") or {}).get("source") or image_url,
                        source_url=source_url,
                        author="Wikipedia",
                        license_name="CC BY-SA",
                        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
                        width=thumbnail.get("width"),
                        height=thumbnail.get("height"),
                        tags=[description] if description else [],
                        categories=[data.get("type") or ""],
                        page_title=data.get("title") or title,
                    )
                ]
        return []

    def _title_candidates(self, query: str) -> list[str]:
        clean = " ".join(query.split()).strip(" .,:;")
        variants = [clean]
        if ":" in clean:
            variants.append(clean.split(":", 1)[0].strip())
        if " - " in clean:
            variants.append(clean.split(" - ", 1)[0].strip())
        if "," in clean:
            variants.append(clean.split(",", 1)[0].strip())
        return [value for index, value in enumerate(variants) if value and value not in variants[:index]]

    async def _candidate_titles(self, query: str, per_page: int) -> list[str]:
        async with httpx.AsyncClient(timeout=20, headers=DEFAULT_HEADERS) as client:
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "format": "json",
                    "srsearch": query,
                    "srlimit": min(max(per_page, 1), 5),
                    "srnamespace": 0,
                },
            )
            if resp.status_code == 403:
                return []
            resp.raise_for_status()
            results = resp.json().get("query", {}).get("search", [])
        return [item.get("title", "") for item in results if item.get("title")]
