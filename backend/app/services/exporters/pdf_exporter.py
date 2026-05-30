import logging
import os
import subprocess
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.semantic.contracts import Alignment, LayoutElement, LayoutElementKind
from app.semantic.contracts import LayoutedPresentationDocument, ThemeDefinition
from app.services.exporters.base import BaseExporter

logger = logging.getLogger(__name__)

class PdfExporter(BaseExporter):
    """
    Exporter for PDF files.
    Prefers native conversion (e.g. PPTX to PDF via LibreOffice) for consistency,
    but can fall back to direct vector rendering.
    """
    
    def __init__(self):
        self.backend_dir = Path(__file__).resolve().parents[3]
        self.output_dir = self.backend_dir / "generated"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = int(os.getenv("PDF_EXPORT_TIMEOUT_SECONDS", "45"))
        self.libreoffice_path = os.getenv("LIBREOFFICE_PATH", r"C:\Program Files\LibreOffice\program\soffice.exe")
        self.page_width = 960
        self.page_height = 540

    def export_pptx(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str) -> str:
        raise NotImplementedError("Use PptxExporter for PPTX output.")

    def export_pdf(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str) -> str:
        pptx_name = f"{asset_id}.pptx"
        pptx_path = self.output_dir / pptx_name
        filename = f"{asset_id}.pdf"
        output_path = self.output_dir / filename
        
        if pptx_path.exists():
            try:
                self._convert_pptx_to_pdf(pptx_path, output_path)
                return filename
            except Exception as e:
                logger.warning("LibreOffice conversion failed: %s. Falling back to direct PDF rendering...", e)

        self._render_pdf(presentation, theme, output_path)
        return filename

    def _convert_pptx_to_pdf(self, pptx_path: Path, output_path: Path):
        command = [
            self.libreoffice_path,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(output_path.parent),
            str(pptx_path)
        ]
        subprocess.run(command, timeout=self.timeout, check=True, capture_output=True)
        # LibreOffice saves to [stem].pdf
        converted = output_path.parent / f"{pptx_path.stem}.pdf"
        if converted.exists() and converted != output_path:
            if output_path.exists(): output_path.unlink()
            converted.rename(output_path)
        if not output_path.exists():
            raise RuntimeError("LibreOffice did not create a PDF.")

    def _color(self, value: str | None, fallback: str = "#2563eb"):
        cleaned = (value or fallback).strip().lstrip("#")
        if len(cleaned) == 3:
            cleaned = "".join(char * 2 for char in cleaned)
        if len(cleaned) != 6:
            cleaned = fallback.lstrip("#")
        try:
            return colors.HexColor(f"#{cleaned}")
        except Exception:
            return colors.HexColor(fallback)

    def _component_style(self, theme: ThemeDefinition, component: str) -> dict:
        return theme.tokens.component_styles.get(component, {})

    def _pt(self, slide_width: int, slide_height: int, x: int, y: int, width: int, height: int) -> tuple[float, float, float, float]:
        sx = self.page_width / slide_width
        sy = self.page_height / slide_height
        w = width * sx
        h = height * sy
        return x * sx, self.page_height - ((y * sy) + h), w, h

    def _wrap(self, text: str, font: str, size: float, max_width: float) -> list[str]:
        lines: list[str] = []
        for raw in text.splitlines() or [""]:
            words = raw.split()
            line = ""
            for word in words:
                candidate = f"{line} {word}".strip()
                if line and stringWidth(candidate, font, size) > max_width:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            if line:
                lines.append(line)
        return lines

    def _draw_text(self, page: canvas.Canvas, element: LayoutElement, x: float, y: float, w: float, h: float, theme: ThemeDefinition) -> None:
        font = "Helvetica-Bold" if element.kind in {LayoutElementKind.STATISTIC, LayoutElementKind.QUOTE} or element.region == "title" else "Helvetica"
        size = max(7, (element.font_size or 18) * 0.75)
        text = element.text or ""
        if element.kind == LayoutElementKind.BULLET_ITEM:
            text = f"- {text}"
        page.setFillColor(self._color(theme.tokens.text_primary))
        page.setFont(font, size)
        line_height = size * (element.line_height or 1.18)
        lines = self._wrap(text, font, size, max(1, w - 8))
        total_height = len(lines) * line_height
        start_y = y + h - size
        if element.align == Alignment.CENTER:
            start_y = y + (h + total_height) / 2 - size
        for index, line in enumerate(lines):
            line_y = start_y - index * line_height
            if line_y < y:
                break
            if element.align == Alignment.CENTER:
                page.drawCentredString(x + w / 2, line_y, line)
            elif element.align == Alignment.END:
                page.drawRightString(x + w - 4, line_y, line)
            else:
                page.drawString(x + 4, line_y, line)

    def _draw_icon(self, page: canvas.Canvas, x: float, y: float, size: float, icon: str, theme: ThemeDefinition) -> None:
        page.setFillColor(self._color(theme.tokens.accent_secondary))
        page.setStrokeColor(self._color(theme.tokens.accent_primary))
        page.circle(x + size / 2, y + size / 2, size / 2, fill=1, stroke=1)
        page.setFillColor(self._color(theme.tokens.accent_primary))
        if icon == "chart":
            for index, height_scale in enumerate((0.28, 0.45, 0.62)):
                bw = size * 0.1
                bx = x + size * 0.32 + index * bw * 1.7
                bh = size * height_scale
                page.rect(bx, y + size * 0.24, bw, bh, fill=1, stroke=0)
        elif icon == "bolt":
            page.line(x + size * 0.58, y + size * 0.18, x + size * 0.38, y + size * 0.52)
            page.line(x + size * 0.38, y + size * 0.52, x + size * 0.58, y + size * 0.52)
            page.line(x + size * 0.58, y + size * 0.52, x + size * 0.42, y + size * 0.82)
        elif icon == "idea":
            page.circle(x + size * 0.5, y + size * 0.46, size * 0.18, fill=1, stroke=0)
            page.rect(x + size * 0.42, y + size * 0.24, size * 0.16, size * 0.12, fill=1, stroke=0)
        else:
            page.circle(x + size / 2, y + size / 2, size * 0.22, fill=0, stroke=1)
            page.circle(x + size / 2, y + size / 2, size * 0.06, fill=1, stroke=0)

    def _draw_bullet_card(self, page: canvas.Canvas, element: LayoutElement, x: float, y: float, w: float, h: float, theme: ThemeDefinition) -> None:
        bullet_style = self._component_style(theme, "bullet").get("style")
        page.setFillColor(self._color(theme.tokens.background_alt if bullet_style == "lines" else theme.tokens.surface))
        page.setStrokeColor(self._color(theme.tokens.border))
        radius = float(self._component_style(theme, "panel").get("radius") or 8) * 0.36
        page.roundRect(x, y, w, h, radius, fill=1, stroke=1)
        icon_size = min(34, h - 12)
        self._draw_icon(page, x + 10, y + h - icon_size - 10, icon_size, str(element.content.get("icon") or "target"), theme)
        self._draw_text(page, element, x + 52, y + 8, max(1, w - 60), max(1, h - 16), theme)

    def _draw_element(self, page: canvas.Canvas, element: LayoutElement, theme: ThemeDefinition, slide_width: int, slide_height: int, ox: int = 0, oy: int = 0) -> None:
        x, y, w, h = self._pt(slide_width, slide_height, ox + element.x, oy + element.y, element.width, element.height)
        if element.kind == LayoutElementKind.PANEL:
            page.setFillColor(self._color(theme.tokens.surface))
            page.setStrokeColor(self._color(theme.tokens.border))
            radius = float(self._component_style(theme, "panel").get("radius") or 8) * 0.36
            page.roundRect(x, y, w, h, radius, fill=1, stroke=1)
        elif element.kind == LayoutElementKind.IMAGE:
            local_path = element.content.get("local_path") if isinstance(element.content, dict) else None
            image_path = Path(local_path) if local_path else None
            inset = float(self._component_style(theme, "image").get("frame_inset") or 0) * (self.page_width / slide_width)
            page.setFillColor(self._color(theme.tokens.surface))
            page.setStrokeColor(self._color(theme.tokens.border))
            page.rect(x, y, w, h, fill=1, stroke=1)
            if image_path and image_path.exists():
                page.drawImage(ImageReader(str(image_path)), x + inset, y + inset, max(1, w - inset * 2), max(1, h - inset * 2), preserveAspectRatio=True, anchor="c")
            else:
                page.setFillColor(self._color(theme.tokens.background_alt))
                page.setStrokeColor(self._color(theme.tokens.border))
                page.rect(x + inset, y + inset, max(1, w - inset * 2), max(1, h - inset * 2), fill=1, stroke=1)
        elif element.kind == LayoutElementKind.BULLET_ITEM:
            self._draw_bullet_card(page, element, x, y, w, h, theme)
        elif isinstance(element.content, dict) and element.content.get("decorative_icon"):
            self._draw_icon(page, x, y, min(w, h), str(element.content.get("icon") or "target"), theme)
        else:
            self._draw_text(page, element, x, y, w, h, theme)

        for child in element.children:
            self._draw_element(page, child, theme, slide_width, slide_height, ox + element.x, oy + element.y)

    def _render_pdf(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, output_path: Path) -> None:
        doc = canvas.Canvas(str(output_path), pagesize=(self.page_width, self.page_height))
        for slide in presentation.slides:
            doc.setFillColor(self._color(theme.tokens.background))
            doc.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
            doc.setFillColor(self._color(theme.tokens.accent_primary))
            if self._component_style(theme, "background").get("accent_position") == "top":
                doc.rect(0, self.page_height - 9, self.page_width, 9, fill=1, stroke=0)
            else:
                doc.rect(0, 0, 9, self.page_height, fill=1, stroke=0)
            for element in sorted(slide.elements, key=lambda item: item.z_index):
                self._draw_element(doc, element, theme, slide.canvas_width, slide.canvas_height)
            doc.showPage()
        doc.save()
