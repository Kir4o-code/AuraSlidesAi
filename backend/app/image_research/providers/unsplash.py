import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.image_research.config import get_unsplash_access_key
from app.image_research.providers.base import BaseImageProvider
from app.image_research.schemas import ImageCandidate

logger = logging.getLogger(__name__)


def _with_resize_params(url: str, orientation: str | None) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["fm"] = "jpg"
    query["q"] = "80"
    if orientation == "portrait":
        query["h"] = "1400"
    else:
        query["w"] = "1600"
    return urlunparse(parsed._replace(query=urlencode(query)))


def _with_referral(url: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["utm_source"] = "AuraSlidesAI"
    query["utm_medium"] = "referral"
    return urlunparse(parsed._replace(query=urlencode(query)))


class UnsplashProvider(BaseImageProvider):
    async def search(
        self, query: str, per_page: int, orientation: str | None, image_type: str | None = None
    ) -> list[ImageCandidate]:
        access_key = get_unsplash_access_key()
        if not access_key:
            raise RuntimeError("UNSPLASH_ACCESS_KEY is not configured.")

        params = {
            "query": query,
            "page": 1,
            "per_page": min(max(per_page, 5), 30),
            "order_by": "relevant",
            "content_filter": "high",
        }
        orientation_value = {"square": "squarish"}.get(orientation or "", orientation)
        if orientation_value in {"landscape", "portrait", "squarish"}:
            params["orientation"] = orientation_value

        headers = {
            "Accept-Version": "v1",
            "Authorization": f"Client-ID {access_key}",
            "User-Agent": "AuraSlidesAI/1.0",
        }
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            resp = await client.get("https://api.unsplash.com/search/photos", params=params, headers=headers)
            if resp.status_code in {401, 403, 429}:
                body = resp.text.strip()
                logger.warning(
                    "Unsplash search rejected. status=%s query=%r remaining=%s limit=%s body=%s",
                    resp.status_code,
                    query,
                    resp.headers.get("X-Ratelimit-Remaining"),
                    resp.headers.get("X-Ratelimit-Limit"),
                    body[:600],
                )
                return []
            resp.raise_for_status()
            data = resp.json()

        out: list[ImageCandidate] = []
        for item in data.get("results", []):
            urls = item.get("urls") or {}
            links = item.get("links") or {}
            user = item.get("user") or {}
            user_links = user.get("links") or {}
            image_url = urls.get("raw") or urls.get("full") or urls.get("regular")
            source_url = links.get("html")
            if not image_url or not source_url:
                continue

            tags = [tag.get("title", "") for tag in item.get("tags", []) if isinstance(tag, dict) and tag.get("title")]
            page_title = item.get("description") or item.get("alt_description") or item.get("slug")
            author_name = user.get("name") or user.get("username")

            out.append(
                ImageCandidate(
                    id=f"unsplash-{item.get('id')}",
                    source="unsplash",
                    title=page_title,
                    image_url=_with_resize_params(image_url, orientation),
                    preview_url=urls.get("small") or urls.get("thumb") or urls.get("regular"),
                    source_url=_with_referral(source_url),
                    author=author_name,
                    license_name="Unsplash License",
                    license_url="https://unsplash.com/license",
                    download_tracking_url=links.get("download_location"),
                    width=item.get("width"),
                    height=item.get("height"),
                    tags=tags,
                    categories=[item.get("color") or ""],
                    page_title=page_title,
                )
            )
        return out
