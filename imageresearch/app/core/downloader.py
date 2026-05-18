import re
import uuid
from pathlib import Path

import httpx
from PIL import Image

from app.config import TEMP_DIR


class DownloadError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
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
            headers={"User-Agent": "ImageResearcher/1.0 (local-image-research@example.invalid)"},
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
