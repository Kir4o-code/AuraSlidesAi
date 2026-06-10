import logging
import os
import shutil
import subprocess
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.semantic.contracts import (
    Alignment,
    LayoutedPresentationDocument,
    LayoutElement,
    LayoutElementKind,
    ThemeDefinition,
)
from app.services.exporters.base import BaseExporter

logger = logging.getLogger(__name__)


class PdfExporter(BaseExporter):
    """
    Exporter for PDF files.
    Prefers native conversion (e.g. PPTX to PDF via LibreOffice) for consistency,
    but falls back to direct vector rendering when LibreOffice is unavailable.
    """

    def __init__(self) -> None:
        self.backend_dir = Path(__file__).resolve().parents[3]
        self.output_dir = self.backend_dir / "generated"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = int(os.getenv("PDF_EXPORT_TIMEOUT_SECONDS", "45"))
        self.page_width = 960
        self.page_height = 540
        self.body_font, self.bold_font = self._register_fonts()

    def export_pptx(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str) -> str:
        raise NotImplementedError("Use PptxExporter for PPTX output.")

    def export_pdf(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str) -> str:
        pptx_name = f"{asset_id}.pptx"
        pptx_path = self.output_dir / pptx_name
        filename = f"{asset_id}.pdf"
        output_path = self.output_dir / filename

        if pptx_path.exists():
            libreoffice_path = self._find_libreoffice()
            if libreoffice_path is None:
                logger.warning("LibreOffice executable not found. PDF export via LibreOffice skipped.")
            else:
                try:
                    logger.info("Attempting PDF export via LibreOffice. executable=%s", libreoffice_path)
                    self._convert_pptx_to_pdf(libreoffice_path, pptx_path, output_path)
                    return filename
                except Exception as exc:
                    logger.warning("LibreOffice conversion failed: %s. Falling back to direct PDF rendering.", exc)

        logger.info("Attempting direct vector PDF rendering.")
        self._render_pdf(presentation, theme, output_path)
        logger.info("Direct vector PDF rendering complete. output=%s", output_path)
        return filename

    def _find_libreoffice(self) -> str | None:
        configured_path = os.getenv("LIBREOFFICE_PATH")
        candidates = (
            Path(configured_path) if configured_path else None,
            Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
            Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        )
        for candidate in candidates:
            if candidate and candidate.is_file():
                return str(candidate)
        for executable in ("soffice", "libreoffice"):
            resolved = shutil.which(executable)
            if resolved:
                return resolved
        return None

    def _convert_pptx_to_pdf(self, libreoffice_path: str, pptx_path: Path, output_path: Path) -> None:
        command = [
            libreoffice_path,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_path.parent),
            str(pptx_path),
        ]
        subprocess.run(command, timeout=self.timeout, check=True, capture_output=True)
        # LibreOffice saves to [stem].pdf
        converted = output_path.parent / f"{pptx_path.stem}.pdf"
        if converted.exists() and converted != output_path:
            if output_path.exists():
                output_path.unlink()
            converted.rename(output_path)
        if not output_path.exists():
            raise RuntimeError("LibreOffice did not create a PDF.")

    def _register_fonts(self) -> tuple[str, str]:
        candidates = (
            ("AuraSans", "AuraSans-Bold", Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")),
            (
                "AuraSans",
                "AuraSans-Bold",
                Path(r"C:\Windows\Fonts\segoeui.ttf"),
                Path(r"C:\Windows\Fonts\segoeuib.ttf"),
            ),
            (
                "AuraSans",
                "AuraSans-Bold",
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            ),
        )
        for regular_name, bold_name, regular_path, bold_path in candidates:
            if regular_path.is_file() and bold_path.is_file():
                if regular_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(regular_name, regular_path))
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                return regular_name, bold_name
        return "Helvetica", "Helvetica-Bold"

    def _color(self, value: str | None, fallback: str = "#2563eb") -> colors.Color:
        try:
            return colors.HexColor(value or fallback)
        except Exception:
            return colors.HexColor(fallback)

    def _component_style(self, theme: ThemeDefinition, component: str) -> dict:
        return theme.tokens.component_styles.get(component, {})

    def _pt(
        self, slide_width: int, slide_height: int, x: int, y: int, width: int, height: int
    ) -> tuple[float, float, float, float]:
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

    def _draw_text(
        self,
        page: canvas.Canvas,
        element: LayoutElement,
        x: float,
        y: float,
        w: float,
        h: float,
        theme: ThemeDefinition,
    ) -> None:
        bold = (
            element.kind in {LayoutElementKind.STATISTIC, LayoutElementKind.QUOTE}
            or "title" in element.region
            or "heading" in element.region
            or "value" in element.region
        )
        font = self.bold_font if bold else self.body_font
        size = max(7, (element.font_size or 18) * 0.75)
        lines = self._wrap(element.text or "", font, size, max(1, w - 8))
        line_height = size * (element.line_height or 1.18)
        start_y = y + h - size - 4
        if element.align == Alignment.CENTER:
            start_y = y + (h + len(lines) * line_height) / 2 - size
        page.setFillColor(
            self._color(
                theme.tokens.text_secondary
                if element.region in {"subtitle", "notes", "attribution"}
                else theme.tokens.text_primary
            )
        )
        page.setFont(font, size)
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

    def _draw_icon(
        self, page: canvas.Canvas, x: float, y: float, size: float, icon: str, theme: ThemeDefinition
    ) -> None:
        page.setFillColor(self._color(theme.tokens.accent_secondary))
        page.setStrokeColor(self._color(theme.tokens.accent_primary))
        page.circle(x + size / 2, y + size / 2, size / 2, fill=1, stroke=1)
        page.setStrokeColor(self._color(theme.tokens.accent_primary))
        page.setLineWidth(1.4)
        if icon == "chart":
            for index, height_scale in enumerate((0.28, 0.45, 0.62)):
                page.rect(
                    x + size * (0.27 + index * 0.18), y + size * 0.22, size * 0.1, size * height_scale, fill=0, stroke=1
                )
        elif icon == "bolt":
            page.line(x + size * 0.62, y + size * 0.78, x + size * 0.4, y + size * 0.5)
            page.line(x + size * 0.4, y + size * 0.5, x + size * 0.58, y + size * 0.5)
            page.line(x + size * 0.58, y + size * 0.5, x + size * 0.38, y + size * 0.2)
        elif icon in {"clock", "eye", "search", "target"}:
            page.circle(x + size / 2, y + size / 2, size * 0.22, fill=0, stroke=1)
            if icon == "clock":
                page.line(x + size / 2, y + size / 2, x + size / 2, y + size * 0.68)
                page.line(x + size / 2, y + size / 2, x + size * 0.66, y + size * 0.42)
            elif icon == "search":
                page.line(x + size * 0.65, y + size * 0.35, x + size * 0.82, y + size * 0.18)
        elif icon in {"person", "users"}:
            page.circle(x + size / 2, y + size * 0.66, size * 0.12, fill=1, stroke=1)
            page.ellipse(x + size * 0.32, y + size * 0.22, x + size * 0.68, y + size * 0.54, fill=0, stroke=1)
        elif icon in {"book", "film", "home", "shield", "star", "heart", "idea", "map"}:
            page.rect(x + size * 0.28, y + size * 0.28, size * 0.44, size * 0.44, fill=0, stroke=1)
        else:
            page.circle(x + size / 2, y + size / 2, size * 0.22, fill=0, stroke=1)

    def _draw_fitted_image(
        self, page: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float, fit: str
    ) -> None:
        image = ImageReader(str(path))
        source_width, source_height = image.getSize()
        source_ratio = source_width / max(source_height, 1)
        frame_ratio = w / max(h, 1)
        if fit == "contain":
            if source_ratio > frame_ratio:
                draw_w, draw_h = w, w / source_ratio
            else:
                draw_h, draw_w = h, h * source_ratio
        elif source_ratio > frame_ratio:
            draw_h, draw_w = h, h * source_ratio
        else:
            draw_w, draw_h = w, w / source_ratio
        page.saveState()
        clip = page.beginPath()
        clip.rect(x, y, w, h)
        page.clipPath(clip, stroke=0, fill=0)
        page.drawImage(image, x + ((w - draw_w) / 2), y + ((h - draw_h) / 2), draw_w, draw_h, mask="auto")
        page.restoreState()

    def _draw_element(
        self,
        page: canvas.Canvas,
        element: LayoutElement,
        theme: ThemeDefinition,
        slide_width: int,
        slide_height: int,
        ox: int = 0,
        oy: int = 0,
    ) -> None:
        x, y, w, h = self._pt(slide_width, slide_height, ox + element.x, oy + element.y, element.width, element.height)
        if element.kind == LayoutElementKind.PANEL:
            page.setFillColor(self._color(theme.tokens.surface))
            page.setStrokeColor(self._color(theme.tokens.border))
            if self._component_style(theme, "panel").get("style") == "square":
                page.rect(x, y, w, h, fill=1, stroke=1)
            else:
                page.roundRect(
                    x, y, w, h, float(self._component_style(theme, "panel").get("radius") or 8) * 0.36, fill=1, stroke=1
                )
        elif element.kind == LayoutElementKind.IMAGE:
            local_path = element.content.get("local_path")
            image_path = Path(local_path) if local_path else None
            page.setFillColor(self._color(theme.tokens.surface))
            page.setStrokeColor(self._color(theme.tokens.border))
            page.roundRect(x, y, w, h, 8, fill=1, stroke=1)
            if image_path and image_path.exists():
                inset = max(0, float(self._component_style(theme, "image").get("frame_inset") or 0) * 0.75)
                self._draw_fitted_image(
                    page,
                    image_path,
                    x + inset,
                    y + inset,
                    max(1, w - inset * 2),
                    max(1, h - inset * 2),
                    str(element.content.get("fit") or self._component_style(theme, "image").get("fit") or "cover"),
                )
        elif element.kind == LayoutElementKind.BULLET_ITEM:
            page.setStrokeColor(self._color(theme.tokens.border))
            if self._component_style(theme, "bullet").get("style") == "lines":
                page.setStrokeColor(self._color(theme.tokens.accent_primary))
                page.setLineWidth(2)
                page.line(x, y, x, y + h)
            else:
                page.setFillColor(self._color(theme.tokens.surface))
                page.roundRect(x, y, w, h, 8, fill=1, stroke=1)
            icon_size = min(24, h - 10)
            self._draw_icon(
                page, x + 8, y + h - icon_size - 5, icon_size, str(element.content.get("icon") or "target"), theme
            )
            self._draw_text(page, element, x + 38, y + 4, max(1, w - 44), max(1, h - 8), theme)
        elif element.kind != LayoutElementKind.BULLET_LIST:
            self._draw_text(page, element, x, y, w, h, theme)

        for child in element.children:
            self._draw_element(page, child, theme, slide_width, slide_height, ox + element.x, oy + element.y)

    def _render_pdf(
        self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, output_path: Path
    ) -> None:
        doc = canvas.Canvas(str(output_path), pagesize=(self.page_width, self.page_height))
        for slide in presentation.slides:
            doc.setFillColor(self._color(theme.tokens.background))
            doc.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
            doc.setFillColor(self._color(theme.tokens.accent_primary))
            if self._component_style(theme, "background").get("accent_position") == "top":
                doc.rect(0, self.page_height - 7, self.page_width, 7, fill=1, stroke=0)
            else:
                doc.rect(0, 0, 7, self.page_height, fill=1, stroke=0)
            for element in sorted(slide.elements, key=lambda item: item.z_index):
                self._draw_element(doc, element, theme, slide.canvas_width, slide.canvas_height)
            doc.showPage()
        doc.save()
