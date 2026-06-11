# Роля на модула: Домейн правилата за photo, diagram, icon и illustration.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ImageClass(str, Enum):
    # Роля на класа: Този Enum ограничава позволените стойности, за да не се разнасят свободни string-ове и различни изписвания през pipeline-а.
    # Наследяването от `str` и `Enum` позволява стойността да се сериализира като текст, но да остане строго ограничена.
    ICON = "icon"
    DIAGRAM = "diagram"
    ILLUSTRATION = "illustration"
    PHOTO = "photo"


@dataclass(frozen=True)
class ImageClassProfile:
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    image_class: ImageClass
    allowed_providers: tuple[str, ...]
    query_terms: tuple[str, ...]
    clip_context: tuple[str, ...]
    preferred_sources: dict[str, float]
    bad_terms: tuple[str, ...]
    metadata_weight: float
    clip_weight: float
    license_weight: float
    source_weight: float
    resolution_weight: float
    aspect_weight: float


# Class profiles centralize provider routing, expansion terms, and scoring weights.
# `CLASS_PROFILES` пази резултата от `ImageClassProfile`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
CLASS_PROFILES: dict[ImageClass, ImageClassProfile] = {
    ImageClass.ICON: ImageClassProfile(
        image_class=ImageClass.ICON,
        allowed_providers=("unsplash", "wikipedia", "wikimedia_commons"),
        query_terms=("icon", "symbol", "pictogram", "simple vector", "flat icon"),
        clip_context=("simple icon", "minimal symbol", "flat vector mark"),
        preferred_sources={"wikipedia": 1.0, "wikimedia_commons": 0.95, "unsplash": 0.7},
        bad_terms=("photo", "portrait", "people", "mockup", "wallpaper", "logo mockup"),
        metadata_weight=0.44,
        clip_weight=0.24,
        license_weight=0.10,
        source_weight=0.12,
        resolution_weight=0.04,
        aspect_weight=0.06,
    ),
    ImageClass.DIAGRAM: ImageClassProfile(
        image_class=ImageClass.DIAGRAM,
        allowed_providers=("unsplash", "wikipedia", "wikimedia_commons"),
        query_terms=("diagram", "labeled diagram", "educational illustration", "schema", "cross section"),
        clip_context=("educational labeled diagram", "clean explanatory chart", "technical schema"),
        preferred_sources={"wikipedia": 1.0, "wikimedia_commons": 0.95, "unsplash": 0.65},
        bad_terms=("stock photo", "portrait", "reenactment", "replica", "fictional", "costume"),
        metadata_weight=0.48,
        clip_weight=0.22,
        license_weight=0.10,
        source_weight=0.10,
        resolution_weight=0.05,
        aspect_weight=0.05,
    ),
    ImageClass.ILLUSTRATION: ImageClassProfile(
        image_class=ImageClass.ILLUSTRATION,
        allowed_providers=("unsplash", "wikipedia", "wikimedia_commons"),
        query_terms=("illustration", "vector", "drawing", "educational illustration"),
        clip_context=("clear illustration", "vector drawing", "educational visual"),
        preferred_sources={"wikipedia": 1.0, "wikimedia_commons": 0.95, "unsplash": 0.65},
        bad_terms=("stock photo", "portrait", "reenactment", "replica", "fictional"),
        metadata_weight=0.43,
        clip_weight=0.27,
        license_weight=0.10,
        source_weight=0.10,
        resolution_weight=0.05,
        aspect_weight=0.05,
    ),
    ImageClass.PHOTO: ImageClassProfile(
        image_class=ImageClass.PHOTO,
        allowed_providers=("unsplash", "wikipedia", "wikimedia_commons"),
        query_terms=("photograph", "photo", "documentary image", "real image"),
        clip_context=("real photograph", "documentary photo", "high quality photo"),
        preferred_sources={"wikipedia": 1.0, "wikimedia_commons": 0.95, "unsplash": 0.6},
        bad_terms=("illustration", "cartoon", "render", "ai generated", "replica", "reenactment"),
        metadata_weight=0.40,
        clip_weight=0.29,
        license_weight=0.10,
        source_weight=0.09,
        resolution_weight=0.07,
        aspect_weight=0.05,
    ),
}


TYPE_TO_CLASS = {
    "icon": ImageClass.ICON,
    "diagram": ImageClass.DIAGRAM,
    "chart": ImageClass.DIAGRAM,
    "graph": ImageClass.DIAGRAM,
    "schema": ImageClass.DIAGRAM,
    "illustration": ImageClass.ILLUSTRATION,
    "vector": ImageClass.ILLUSTRATION,
    "drawing": ImageClass.ILLUSTRATION,
    "photo": ImageClass.PHOTO,
    "photograph": ImageClass.PHOTO,
    "any": ImageClass.PHOTO,
}


CLASS_KEYWORDS: dict[ImageClass, tuple[str, ...]] = {
    ImageClass.ICON: ("icon", "symbol", "logo", "pictogram", "glyph"),
    ImageClass.DIAGRAM: ("diagram", "chart", "schema", "flow", "map", "timeline", "anatomy", "cross section"),
    ImageClass.ILLUSTRATION: ("illustration", "vector", "drawing", "sketch", "artwork"),
    ImageClass.PHOTO: ("photo", "photograph", "real", "documentary", "portrait", "landscape"),
}


def canonical_image_class(value: str | None) -> ImageClass:
    # Роля в pipeline-а: уеднаквява външна стойност към вътрешния речник на приложението.
    # Входът идва през `value` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `ImageClass`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    return TYPE_TO_CLASS.get((value or "any").strip().lower(), ImageClass.PHOTO)


def infer_image_class(prompt: str, image_type: str | None = None) -> ImageClass:
    # Роля в pipeline-а: извежда липсваща класификация от наличните текстови сигнали.
    # Входът идва през `prompt` (str), `image_type` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `canonical_image_class`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `ImageClass`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `requested` пази резултата от `canonical_image_class`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    requested = canonical_image_class(image_type)
    # Това условие е decision point: `image_type and image_type.strip().lower() != 'any'`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`requested`) и прескачаме ненужната останала работа.
    if image_type and image_type.strip().lower() != "any":
        return requested
    # `text` е нормализирано работно копие на текста; оригиналът остава непокътнат, а проверките стават върху предвидим формат.
    text = prompt.lower()
    # Обхождаме `(ImageClass.DIAGRAM, ImageClass.ICON, ImageClass.ILLUSTRATION, ImageClass.PHOTO)` като `image_class`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for image_class in (ImageClass.DIAGRAM, ImageClass.ICON, ImageClass.ILLUSTRATION, ImageClass.PHOTO):
        # Това условие е decision point: `any((term in text for term in CLASS_KEYWORDS[image_class]))`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`image_class`) и прескачаме ненужната останала работа.
        if any(term in text for term in CLASS_KEYWORDS[image_class]):
            return image_class
    return ImageClass.PHOTO


def get_class_profile(value: str | ImageClass | None) -> ImageClassProfile:
    # Роля в pipeline-а: осигурява достъп до общ ресурс или конфигурация, без caller-ът да знае как се създава.
    # Входът идва през `value` (str | ImageClass | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `canonical_image_class`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `ImageClassProfile`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `image_class` пази резултата от `isinstance`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    image_class = value if isinstance(value, ImageClass) else canonical_image_class(value)
    return CLASS_PROFILES[image_class]
