# Роля на модула: Помощен модул в backend pipeline-а; коментарите по-долу обясняват конкретните му граници и решения.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# `BACKEND_DIR` пази резултата от `Path(__file__).resolve`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
BACKEND_DIR = Path(__file__).resolve().parents[2]
# `APP_DIR` е абсолютната директория на app package-а, използвана като котва за generated assets.
APP_DIR = BACKEND_DIR / "app"
GENERATED_DIR = BACKEND_DIR / "generated"
IMAGE_RESEARCH_DIR = GENERATED_DIR / "image_research"
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(APP_DIR / ".env", override=True)


def env_value(name: str) -> str | None:
    # Роля в pipeline-а: обработва стъпката `env_value` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `name` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `value.lower().startswith`, `os.getenv`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str | None`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `value` пази резултата от `(os.getenv(name) or '').strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    value = (os.getenv(name) or "").strip()
    # Това условие е decision point: `not value or value.lower().startswith('your_')`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
    if not value or value.lower().startswith("your_"):
        return None
    return value


@dataclass(frozen=True)
class Settings:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    groq_api_key: str | None = env_value("GROQ_API_KEY")
    groq_model: str = os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile"
    unsplash_access_key: str | None = env_value("UNSPLASH_ACCESS_KEY")
    clip_model: str = os.getenv("CLIP_MODEL") or "openai/clip-vit-base-patch32"


# `settings` е конфигурацията от environment, която включва или изключва външни услуги и избира модели.
settings = Settings()


def get_unsplash_access_key() -> str | None:
    # Роля в pipeline-а: осигурява достъп до общ ресурс или конфигурация, без caller-ът да знае как се създава.
    # Функцията няма входни параметри; тя чете конфигурация или създава общ ресурс.
    # Основните преходи навън са към `env_value`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str | None`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    return env_value("UNSPLASH_ACCESS_KEY")


# `OUTPUT_DIR` е общата директория за крайни PPTX/PDF файлове, която едновременно се използва от exporters и се публикува като static route.
OUTPUT_DIR = IMAGE_RESEARCH_DIR
IMAGES_DIR = OUTPUT_DIR / "images"
TEMP_DIR = OUTPUT_DIR / "temp"
METADATA_DIR = OUTPUT_DIR / "metadata"
PUBLIC_IMAGES_PREFIX = "/generated/image_research/images"
