# Роля на модула: Свързва domain Presentation модела със semantic layout и крайните exporters.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
import logging
import os
import re
import unicodedata
from pathlib import Path
from uuid import uuid4

from app.schemas.presentation import Presentation
from app.semantic.adapters import (
    build_layout_specs,
    build_renderer_context,
    build_theme_definition,
    presentation_to_document,
)
from app.semantic.contracts import LayoutedPresentationDocument, RendererTarget, ThemeDefinition
from app.semantic.layout_engine import build_layouted_presentation
from app.semantic.validators import (
    validate_layout_spec,
    validate_presentation_document,
    validate_renderer_context,
    validate_theme_definition,
)
from app.services.exporters import build_presentation_exports as run_exporters

# `APP_DIR` е абсолютната директория на app package-а, използвана като котва за generated assets.
APP_DIR = Path(__file__).resolve().parent.parent
# `OUTPUT_DIR` е общата директория за крайни PPTX/PDF файлове, която едновременно се използва от exporters и се публикува като static route.
OUTPUT_DIR = APP_DIR.parent / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)


def prepare_export_bundle(presentation: Presentation) -> tuple[LayoutedPresentationDocument, ThemeDefinition]:
    # Роля в pipeline-а: Подготвя semantic document, theme и layout веднъж, преди конкретните exporters да започнат файловата работа.
    # Входът идва през `presentation` (Presentation); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `os.getenv`, `presentation_to_document`, `build_theme_definition`, `build_renderer_context`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `tuple[LayoutedPresentationDocument, ThemeDefinition]`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    # `exporter_type` е избраната export стратегия от environment; тя решава дали pipeline-ът използва native renderer или screenshot fallback.
    exporter_type = os.getenv("EXPORTER_TYPE", "native")
    # Renderer target-ът не избира само exporter. Той описва capabilities, срещу които semantic context-ът
    # ще бъде проверен, така че несъвместима функция да се спре преди създаването на файл.
    # `renderer_target` е semantic описание на крайния renderer, чрез което capability проверките се правят преди export.
    renderer_target = RendererTarget.SCREENSHOT if exporter_type == "screenshot" else RendererTarget.PPTX

    # Тези три adapter стъпки са като превод на общ технически чертеж:
    # съдържанието, визуалните tokens и renderer възможностите се отделят в независими договори.
    # `semantic_document` е renderer-neutral копието на презентацията; от този момент layout кодът не зависи от API schema детайли.
    semantic_document = presentation_to_document(presentation)
    # `semantic_theme` е renderer-neutral визуалният договор, споделен от layout engine и exporters.
    semantic_theme = build_theme_definition(presentation.theme)
    # `semantic_context` е capability договорът на избрания renderer, използван за ранна проверка на несъвместими операции.
    semantic_context = build_renderer_context(renderer_target)
    # Layout engine-ът е "чертожникът": тук abstract regions стават конкретни координати и размери.
    # Exporter-ът след това само материализира този чертеж като PPTX/PDF.
    # `layouted_document` е готовият semantic документ с изчислени позиции и размери за всеки визуален елемент.
    layouted_document = build_layouted_presentation(
        semantic_document,
        debug_mode=os.getenv("LAYOUT_DEBUG", "false").lower() in {"1", "true", "yes", "on"},
        spacing_scale=semantic_theme.tokens.spacing_scale,
        typography_scale=semantic_theme.tokens.typography_scale,
    )

    # Валидираме преди export boundary-а. Това държи грешката близо до semantic причината,
    # вместо тя да се прояви по-късно като неясна PowerPoint или PDF rendering грешка.
    validate_presentation_document(semantic_document)
    validate_theme_definition(semantic_theme)
    validate_renderer_context(semantic_context)
    # Обхождаме `build_layout_specs(semantic_document)` като `layout_spec`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for layout_spec in build_layout_specs(semantic_document):
        validate_layout_spec(layout_spec)

    return layouted_document, semantic_theme


def _build_asset_id(title: str) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: сглобява по-ниско ниво данни в обект, който следващият pipeline етап разбира директно.
    # Входът идва през `title` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.findall`, `unicodedata.normalize`, `uuid4`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    # `words` е думите от заглавието след Unicode нормализация; те са суровината за безопасния slug.
    words = re.findall(r"\w+", unicodedata.normalize("NFKD", title), flags=re.UNICODE)
    # `slug` е четимата част на файловия идентификатор, получена от заглавието след нормализация.
    slug = "-".join(words).strip("-_").lower()[:64].strip("-_")
    return f"{slug or 'presentation'}-{uuid4().hex[:8]}"


def build_presentation_exports(presentation: Presentation) -> tuple[str, str | None]:
    # Роля в pipeline-а: Стартира крайната PPTX/PDF печатница и връща имената на файловете, които route-ът превръща в публични URL адреси.
    # Входът идва през `presentation` (Presentation); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_build_asset_id`, `os.getenv`, `prepare_export_bundle`, `run_exporters`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `tuple[str, str | None]`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    # `asset_id` е безопасният и уникален файлов идентификатор, използван едновременно за PPTX и PDF на една презентация.
    asset_id = _build_asset_id(presentation.title)
    # `exporter_type` е избраната export стратегия от environment; тя решава дали pipeline-ът използва native renderer или screenshot fallback.
    exporter_type = os.getenv("EXPORTER_TYPE", "native")
    # Bundle-ът се създава веднъж и се подава на конкретния exporter като готов договор.
    # Така PPTX и PDF не взимат различни layout решения за една и съща презентация.
    layouted_document, semantic_theme = prepare_export_bundle(presentation)

    logger.info("Starting presentation export. asset_id=%s exporter=%s", asset_id, exporter_type)
    return run_exporters(
        layouted_document,
        semantic_theme,
        asset_id,
        exporter_type=exporter_type,
        browser_fallback_presentation=presentation,
    )
