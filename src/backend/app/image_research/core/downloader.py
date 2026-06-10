import re
import uuid

import httpx
from PIL import Image

from app.image_research.config import TEMP_DIR, get_unsplash_access_key


class DownloadError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value)[:80]


async def download_image(image_url: str, prefix: str) -> str:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{_safe_name(prefix)}_{uuid.uuid4().hex[:10]}.jpg"
    path = TEMP_DIR / name
    async with httpx.AsyncClient(timeout=40, follow_redirects=True) as client:
        resp = await client.get(
            image_url,
            headers={"User-Agent": "AuraSlidesAI/1.0 (https://example.com; contact@auraslidesai.local)"},
        )
        if resp.status_code >= 400:
            raise DownloadError(f"HTTP {resp.status_code}", resp.status_code)
        if not (resp.headers.get("content-type") or "").lower().startswith("image/"):
            raise ValueError("Downloaded content is not an image")
        path.write_bytes(resp.content)

    try:
        with Image.open(path) as img:
            img.verify()
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise ValueError("Downloaded image is invalid") from exc
    return str(path)


async def track_remote_download(download_tracking_url: str | None) -> None:
    if not download_tracking_url:
        return
    headers = {"User-Agent": "AuraSlidesAI/1.0 (https://example.com; contact@auraslidesai.local)"}
    access_key = get_unsplash_access_key()
    if "api.unsplash.com" in download_tracking_url and access_key:
        headers["Accept-Version"] = "v1"
        headers["Authorization"] = f"Client-ID {access_key}"
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        await client.get(download_tracking_url, headers=headers)
