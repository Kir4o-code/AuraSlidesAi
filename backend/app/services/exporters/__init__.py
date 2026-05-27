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

def build_presentation_exports(presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str, exporter_type: ExporterType = "native") -> tuple[str, str]:
    """Universal entry point for all presentation exports."""
    exporter = get_exporter(exporter_type)

    pptx_name = exporter.export_pptx(presentation, theme, asset_id)
    pdf_name = exporter.export_pdf(presentation, theme, asset_id)
    
    return pptx_name, pdf_name
