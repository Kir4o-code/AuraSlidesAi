import json
import re
import shutil
from pathlib import Path

from app.config import IMAGES_DIR, METADATA_DIR, TEMP_DIR


def slugify(value: str, fallback: str = "image_query") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return (slug[:70] or fallback).strip("_")


def ensure_output_dirs(prompt_slug: str | None = None) -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    if prompt_slug:
        (IMAGES_DIR / prompt_slug).mkdir(parents=True, exist_ok=True)
        (TEMP_DIR / prompt_slug).mkdir(parents=True, exist_ok=True)
        (METADATA_DIR / prompt_slug).mkdir(parents=True, exist_ok=True)


def save_metadata(request_id: str, data: dict, prompt_slug: str | None = None) -> Path:
    ensure_output_dirs(prompt_slug)
    base = METADATA_DIR / prompt_slug if prompt_slug else METADATA_DIR
    path = base / f"{request_id}_metadata.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def copy_best_image(temp_path: str, request_id: str, prompt_slug: str | None = None) -> Path:
    ensure_output_dirs(prompt_slug)
    base = IMAGES_DIR / prompt_slug if prompt_slug else IMAGES_DIR
    dest = base / f"{request_id}_best.jpg"
    shutil.copyfile(temp_path, dest)
    return dest
