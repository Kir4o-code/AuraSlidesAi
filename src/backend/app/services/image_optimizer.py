# Роля на модула: Граница между суров image asset и файл, подходящ за exporters. Тук се намаляват размерът и форматните рискове.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

# `OPTIMIZED_IMAGES_DIR` пази резултата от `Path(__file__).resolve`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
OPTIMIZED_IMAGES_DIR = Path(__file__).resolve().parents[2] / "generated" / "optimized_images"
OPTIMIZED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGE_SIZE = (1600, 900)
JPEG_QUALITY = 82


class ImageOptimizationError(Exception):
    # Роля на класа: Този custom exception маркира конкретен тип pipeline отказ, за да може горният слой да го преведе към правилен HTTP status или fallback.
    # Отделният exception тип позволява точно `except` правило без parsing на текстово съобщение.
    pass


@dataclass(frozen=True)
class OptimizedImage:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    path: Path
    width: int | None
    height: int | None
    has_transparency: bool


def _safe_key(value: str) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `safe_key` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.sub`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    # `cleaned` пази резултата от `re.sub('[^a-zA-Z0-9._-]+', '_', value).strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._-")
    return cleaned[:80] or "image"


def _detect_transparency(image: Image.Image) -> bool:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `detect_transparency` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `image` (Image.Image); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bool`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    # Това условие е decision point: `image.mode in {'RGBA', 'LA'}`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `True`, без да проверява по-слабите правила отдолу.
    if image.mode in {"RGBA", "LA"}:
        return True
    return image.mode == "P" and "transparency" in image.info


def _output_path(cache_key: str, digest: str, has_transparency: bool) -> Path:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `output_path` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `cache_key` (str), `digest` (str), `has_transparency` (bool); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_safe_key`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `Path`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    suffix = ".png" if has_transparency else ".jpg"
    return OPTIMIZED_IMAGES_DIR / f"{_safe_key(cache_key)}_{digest}{suffix}"


def _save_optimized_image(image: Image.Image, output_path: Path, has_transparency: bool) -> None:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: записва резултат от pipeline-а и връща стабилна референция към него.
    # Входът идва през `image` (Image.Image), `output_path` (Path), `has_transparency` (bool); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `ImageOps.exif_transpose`, `image.thumbnail`, `image.convert`, `rgb_image.save`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
    # `image` пази резултата от `ImageOps.exif_transpose`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    image = ImageOps.exif_transpose(image)
    image.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)

    # Това условие е decision point: `has_transparency`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`None`) и прескачаме ненужната останала работа.
    if has_transparency:
        # `rgba_image` пази резултата от `image.convert`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        rgba_image = image.convert("RGBA")
        rgba_image.save(
            output_path,
            format="PNG",
            optimize=True,
            compress_level=9,
        )
        return

    # `rgb_image` пази резултата от `image.convert`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    rgb_image = image.convert("RGB")
    rgb_image.save(
        output_path,
        format="JPEG",
        quality=JPEG_QUALITY,
        optimize=True,
        progressive=True,
    )


def optimize_image_bytes(image_bytes: bytes, cache_key: str) -> OptimizedImage:
    # Роля в pipeline-а: обработва стъпката `optimize_image_bytes` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `image_bytes` (bytes), `cache_key` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `OPTIMIZED_IMAGES_DIR.mkdir`, `hashlib.sha256(image_bytes).hexdigest`, `Image.open`, `_detect_transparency`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `OptimizedImage`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    OPTIMIZED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    # `digest` пази резултата от `hashlib.sha256(image_bytes).hexdigest`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    digest = hashlib.sha256(image_bytes).hexdigest()[:16]

    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (Exception) в предвидимо поведение за горния слой.
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            # `has_transparency` е boolean решение, което управлява кой branch от pipeline-а ще се изпълни.
            has_transparency = _detect_transparency(image)
            # `output_path` е крайното място във файловата система, което следващият слой може безопасно да използва.
            output_path = _output_path(cache_key, digest, has_transparency)
            # Това условие е decision point: `not output_path.exists()`.
            # При вярно условие се активира `_save_optimized_image`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if not output_path.exists():
                _save_optimized_image(image, output_path, has_transparency)

            with Image.open(output_path) as optimized:
                width, height = optimized.size

            return OptimizedImage(
                path=output_path,
                width=width,
                height=height,
                has_transparency=has_transparency,
            )
    except Exception as exc:
        raise ImageOptimizationError(f"Failed to optimize image: {exc}") from exc


def optimize_image_file(source_path: Path, cache_key: str | None = None) -> OptimizedImage:
    # Роля в pipeline-а: обработва стъпката `optimize_image_file` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `source_path` (Path), `cache_key` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `optimize_image_bytes`, `source_path.read_bytes`, `ImageOptimizationError`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `OptimizedImage`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (Exception) в предвидимо поведение за горния слой.
    try:
        # `image_bytes` е суровото binary съдържание на изображението преди оптимизация и запис.
        image_bytes = source_path.read_bytes()
    except Exception as exc:
        raise ImageOptimizationError(f"Failed to read image file {source_path}: {exc}") from exc

    return optimize_image_bytes(image_bytes, cache_key=cache_key or source_path.stem)
