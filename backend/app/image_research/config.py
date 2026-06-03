import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
APP_DIR = BACKEND_DIR / "app"
GENERATED_DIR = BACKEND_DIR / "generated"
IMAGE_RESEARCH_DIR = GENERATED_DIR / "image_research"
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(APP_DIR / ".env", override=True)


def env_value(name: str) -> str | None:
    value = (os.getenv(name) or "").strip()
    if not value or value.lower().startswith("your_"):
        return None
    return value


@dataclass(frozen=True)
class Settings:
    groq_api_key: str | None = env_value("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile"
    unsplash_access_key: str | None = env_value("UNSPLASH_ACCESS_KEY")
    clip_model: str = os.getenv("CLIP_MODEL") or "openai/clip-vit-base-patch32"


settings = Settings()


def get_unsplash_access_key() -> str | None:
    return env_value("UNSPLASH_ACCESS_KEY")

OUTPUT_DIR = IMAGE_RESEARCH_DIR
IMAGES_DIR = OUTPUT_DIR / "images"
TEMP_DIR = OUTPUT_DIR / "temp"
METADATA_DIR = OUTPUT_DIR / "metadata"
PUBLIC_IMAGES_PREFIX = "/generated/image_research/images"
