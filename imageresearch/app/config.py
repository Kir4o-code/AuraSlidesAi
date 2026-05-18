import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BASE_DIR / "app"
load_dotenv(BASE_DIR / ".env")
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
    pexels_api_key: str | None = env_value("PEXELS_API_KEY")
    pixabay_api_key: str | None = env_value("PIXABAY_API_KEY")
    openverse_client_id: str | None = env_value("OPENVERSE_CLIENT_ID")
    openverse_client_secret: str | None = env_value("OPENVERSE_CLIENT_SECRET")
    clip_model: str = os.getenv("CLIP_MODEL") or "openai/clip-vit-base-patch32"


settings = Settings()

FRONTEND_DIR = BASE_DIR / "frontend"
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
TEMP_DIR = OUTPUT_DIR / "temp"
METADATA_DIR = OUTPUT_DIR / "metadata"
