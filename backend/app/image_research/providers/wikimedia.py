import re

import httpx

from app.image_research.providers.base import BaseImageProvider
from app.image_research.schemas import ImageCandidate


def _plain(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"<[^>]+>", "", value).strip() or None


def _license(value: str | None) -> str:
    text = (value or "").upper()
    if "PUBLIC DOMAIN" in text:
        return "Public Domain"
    if "CC0" in text:
        return "CC0"
    if "CC BY-SA" in text:
        return "CC BY-SA"
    if "CC BY" in text:
        return "CC BY"
    return value or "Unknown"


class WikimediaProvider(BaseImageProvider):
    async def search(
        self, query: str, per_page: int, orientation: str | None, image_type: str | None = None
    ) -> list[ImageCandidate]:
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": min(max(per_page, 5), 50),
            "prop": "imageinfo|info|categories",
            "inprop": "url",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1024,
            "cllimit": 20,
            "origin": "*",
        }
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.get(
                "https://commons.wikimedia.org/w/api.php",
                params=params,
                headers={"User-Agent": "ImageResearcher/1.0 (local-image-research@example.invalid)"},
            )
            resp.raise_for_status()
            data = resp.json()

        out: list[ImageCandidate] = []
        for page in (data.get("query") or {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [{}])[0]
            mime = info.get("mime") or ""
            if not mime.startswith("image/") or mime == "image/svg+xml":
                continue
            meta = info.get("extmetadata") or {}
            image_url = info.get("thumburl") or info.get("url")
            if not image_url:
                continue
            title = page.get("title", "").replace("File:", "")
            description = _plain((meta.get("ImageDescription") or {}).get("value"))
            author = _plain((meta.get("Artist") or {}).get("value"))
            license_name = _license((meta.get("LicenseShortName") or {}).get("value"))
            # Wikimedia specialization: categories/titles boost factual educational assets.
            categories = [
                str(category.get("title", "")).replace("Category:", "")
                for category in page.get("categories") or []
                if category.get("title")
            ]
            factual_text = " ".join([title, description or "", *categories]).lower()
            factual_score = 0.0
            if any(term in factual_text for term in ("diagrams", "svg diagrams", "maps", "anatomy", "scientific")):
                factual_score += 0.25
            if any(term in factual_text for term in ("photographs", "historical images", "public domain")):
                factual_score += 0.2
            if any(term in factual_text for term in ("reenactment", "replica", "fictional", "cosplay", "memorial")):
                factual_score -= 0.35
            out.append(
                ImageCandidate(
                    id=f"wikimedia-{page.get('pageid')}",
                    source="wikimedia",
                    title=description or title,
                    image_url=image_url,
                    preview_url=info.get("thumburl"),
                    source_url=info.get("descriptionurl") or page.get("fullurl") or "",
                    author=author,
                    license_name=license_name,
                    license_url=(meta.get("LicenseUrl") or {}).get("value"),
                    width=info.get("thumbwidth") or info.get("width"),
                    height=info.get("thumbheight") or info.get("height"),
                    tags=[title, description or "", *categories],
                    categories=categories,
                    page_title=title,
                    factual_score=factual_score,
                )
            )
        return out
