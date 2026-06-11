# Роля на модула: Export orchestration и избор на конкретна стратегия.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
import logging
import os
from typing import Literal

from app.schemas.presentation import Presentation
from app.semantic.contracts import LayoutedPresentationDocument, ThemeDefinition
from app.services.exporters.base import BaseExporter
from app.services.exporters.pdf_exporter import PdfExporter
from app.services.exporters.pptx_exporter import PptxExporter

ExporterType = Literal["native", "screenshot"]

logger = logging.getLogger(__name__)


def _legacy_screenshot_enabled() -> bool:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `legacy_screenshot_enabled` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Функцията няма входни параметри; тя чете конфигурация или създава общ ресурс.
    # Основните преходи навън са към `os.getenv`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bool`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
    return os.getenv("ENABLE_LEGACY_SCREENSHOT_EXPORT", "false").strip().lower() in {"1", "true", "yes", "on"}


def get_exporter(exporter_type: ExporterType) -> BaseExporter:
    # Роля в pipeline-а: осигурява достъп до общ ресурс или конфигурация, без caller-ът да знае как се създава.
    # Входът идва през `exporter_type` (ExporterType); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `ScreenshotExporter`, `UnifiedNativeExporter`, `_legacy_screenshot_enabled`, `RuntimeError`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `BaseExporter`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
    """Factory to get the requested exporter implementation."""
    # Това условие е decision point: `exporter_type == 'native'`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`UnifiedNativeExporter()`) и прескачаме ненужната останала работа.
    if exporter_type == "native":
        return UnifiedNativeExporter()
    # Това условие е decision point: `not _legacy_screenshot_enabled()`.
    # При вярно условие се активира `RuntimeError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if not _legacy_screenshot_enabled():
        raise RuntimeError(
            "Legacy screenshot export is disabled. Set ENABLE_LEGACY_SCREENSHOT_EXPORT=true to use it explicitly."
        )
    logger.warning("Using legacy screenshot export. This path is DOM-dependent and should only be used as a fallback.")
    from app.services.exporters.screenshot_exporter import ScreenshotExporter

    return ScreenshotExporter()


class UnifiedNativeExporter(BaseExporter):
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    """
    Combines PptxExporter and PdfExporter into a single interface.
    """

    def __init__(self) -> None:
        # Роля в pipeline-а: обработва стъпката `init` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `PptxExporter`, `PdfExporter`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        # `self.pptx` пази резултата от `PptxExporter`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        self.pptx = PptxExporter()
        # `self.pdf` пази резултата от `PdfExporter`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        self.pdf = PdfExporter()

    def export_pptx(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str) -> str:
        # Роля в pipeline-а: превръща готовия layout в краен файл за клиента.
        # Входът идва през `self` (неуточнен тип), `presentation` (LayoutedPresentationDocument), `theme` (ThemeDefinition), `asset_id` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self.pptx.export_pptx`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `str`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        return self.pptx.export_pptx(presentation, theme, asset_id)

    def export_pdf(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str) -> str:
        # Роля в pipeline-а: превръща готовия layout в краен файл за клиента.
        # Входът идва през `self` (неуточнен тип), `presentation` (LayoutedPresentationDocument), `theme` (ThemeDefinition), `asset_id` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self.pdf.export_pdf`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `str`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        return self.pdf.export_pdf(presentation, theme, asset_id)


def _export_pdf_with_browser(presentation: Presentation | None, theme: ThemeDefinition, asset_id: str) -> str | None:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: превръща готовия layout в краен файл за клиента.
    # Входът идва през `presentation` (Presentation | None), `theme` (ThemeDefinition), `asset_id` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_legacy_screenshot_enabled`, `ScreenshotExporter().export_pdf`, `ScreenshotExporter`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str | None`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
    # Това условие е decision point: `presentation is None`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
    if presentation is None:
        logger.warning("Browser PDF fallback unavailable: original presentation data was not provided.")
        return None
    # Това условие е decision point: `not _legacy_screenshot_enabled()`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
    if not _legacy_screenshot_enabled():
        logger.warning(
            "Browser PDF fallback unavailable: legacy screenshot export is disabled. "
            "Set ENABLE_LEGACY_SCREENSHOT_EXPORT=true to use it."
        )
        return None

    logger.info("Attempting PDF export via browser fallback.")
    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (Exception) в предвидимо поведение за горния слой.
    try:
        from app.services.exporters.screenshot_exporter import ScreenshotExporter

        return ScreenshotExporter().export_pdf(presentation, theme, asset_id)
    except Exception as exc:
        logger.warning("Browser PDF fallback unavailable: %s", exc)
        return None


def build_presentation_exports(
    presentation: LayoutedPresentationDocument,
    theme: ThemeDefinition,
    asset_id: str,
    exporter_type: ExporterType = "native",
    browser_fallback_presentation: Presentation | None = None,
) -> tuple[str, str | None]:
    # Роля в pipeline-а: Стартира крайната PPTX/PDF печатница и връща имената на файловете, които route-ът превръща в публични URL адреси.
    # Входът идва през `presentation` (LayoutedPresentationDocument), `theme` (ThemeDefinition), `asset_id` (str), `exporter_type` (ExporterType), `browser_fallback_presentation` (Presentation | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `get_exporter`, `exporter.export_pptx`, `RuntimeError`, `exporter.export_pdf`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `tuple[str, str | None]`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
    """Universal entry point for all presentation exports."""
    # `exporter` пази резултата от `get_exporter`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    exporter = get_exporter(exporter_type)
    export_presentation = browser_fallback_presentation if exporter_type == "screenshot" else presentation
    # Това условие е decision point: `export_presentation is None`.
    # При вярно условие се активира `RuntimeError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if export_presentation is None:
        raise RuntimeError("Screenshot export requires original presentation data.")

    # `pptx_name` пази резултата от `exporter.export_pptx`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    pptx_name = exporter.export_pptx(export_presentation, theme, asset_id)
    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (Exception) в предвидимо поведение за горния слой.
    try:
        # `pdf_name` пази резултата от `exporter.export_pdf`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        pdf_name = exporter.export_pdf(export_presentation, theme, asset_id)
    except Exception as exc:
        logger.warning("PDF export via %s failed: %s", exporter.__class__.__name__, exc)
        # `pdf_name` пази резултата от `_export_pdf_with_browser`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        pdf_name = (
            _export_pdf_with_browser(browser_fallback_presentation, theme, asset_id)
            if exporter_type == "native"
            else None
        )
    # Това условие е decision point: `pdf_name is None`.
    # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
    if pdf_name is None:
        logger.warning("PDF export unavailable. PPTX export completed successfully.")

    return pptx_name, pdf_name
