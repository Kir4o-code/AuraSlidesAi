from pathlib import Path

from dotenv import dotenv_values


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"
FALSE_VALUES = {"false", "0", "off", "no"}


def is_image_generation_enabled() -> bool:
    file_values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    raw_value = file_values.get("IMAGE_GEN_SWITCH", "true")
    value = str(raw_value).strip().lower()
    return value not in FALSE_VALUES
