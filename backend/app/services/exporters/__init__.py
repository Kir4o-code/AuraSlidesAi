import logging
import os
from typing import Literal

from app.schemas.presentation import Presentation
from app.semantic.contracts import LayoutedPresentationDocument, ThemeDefinition
from app.services.exporters.base import BaseExporter
from app.services.exporters.pptx_exporter import PptxExporter
from app.services.exporters.pdf_exporter import PdfExporter

ExporterType = Literal["native", "screenshot"]

logger = logging.getLogger(__name__)


def _legacy_screenshot_enabled() -> bool:
    return os.getenv("ENABLE_LEGACY_SCREENSHOT_EXPORT", "false").strip().lower() in {"1", "true", "yes", "on"}

def get_exporter(exporter_type: ExporterType) -> BaseExporter:
    """Factory to get the requested exporter implementation."""
    if exporter_type == "native":
        return UnifiedNativeExporter()
    if not _legacy_screenshot_enabled():
        raise RuntimeError(
            "Legacy screenshot export is disabled. Set ENABLE_LEGACY_SCREENSHOT_EXPORT=true to use it explicitly."
        )
    logger.warning("Using legacy screenshot export. This path is DOM-dependent and should only be used as a fallback.")
    from app.services.exporters.screenshot_exporter import ScreenshotExporter

    return ScreenshotExporter()

class UnifiedNativeExporter(BaseExporter):
    """
    Combines PptxExporter and PdfExporter into a single interface.
    """
    def __init__(self):
        self.pptx = PptxExporter()
        self.pdf = PdfExporter()
        
    def export_pptx(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str) -> str:
        return self.pptx.export_pptx(presentation, theme, asset_id)
        
    def export_pdf(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str) -> str:
        return self.pdf.export_pdf(presentation, theme, asset_id)

def _export_pdf_with_browser(presentation: Presentation | None, theme: ThemeDefinition, asset_id: str) -> str | None:
    if presentation is None:
        logger.warning("Browser PDF fallback unavailable: original presentation data was not provided.")
        return None
    if not _legacy_screenshot_enabled():
        logger.warning(
            "Browser PDF fallback unavailable: legacy screenshot export is disabled. "
            "Set ENABLE_LEGACY_SCREENSHOT_EXPORT=true to use it."
        )
        return None

    logger.info("Attempting PDF export via browser fallback.")
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
    """Universal entry point for all presentation exports."""
    exporter = get_exporter(exporter_type)
    export_presentation = browser_fallback_presentation if exporter_type == "screenshot" else presentation
    if export_presentation is None:
        raise RuntimeError("Screenshot export requires original presentation data.")

    pptx_name = exporter.export_pptx(export_presentation, theme, asset_id)
    try:
        pdf_name = exporter.export_pdf(export_presentation, theme, asset_id)
    except Exception as exc:
        logger.warning("PDF export via %s failed: %s", exporter.__class__.__name__, exc)
        pdf_name = (
            _export_pdf_with_browser(browser_fallback_presentation, theme, asset_id)
            if exporter_type == "native"
            else None
        )
    if pdf_name is None:
        logger.warning("PDF export unavailable. PPTX export completed successfully.")
    
    return pptx_name, pdf_name
