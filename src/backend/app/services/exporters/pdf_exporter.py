# Роля на модула: PDF renderer/converter с fallback стратегии.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
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
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    """
    Exporter for PDF files.
    Prefers native conversion (e.g. PPTX to PDF via LibreOffice) for consistency,
    but falls back to direct vector rendering when LibreOffice is unavailable.
    """

    def __init__(self) -> None:
        # Роля в pipeline-а: обработва стъпката `init` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self.output_dir.mkdir`, `self._register_fonts`, `os.getenv`, `Path(__file__).resolve`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        # `self.backend_dir` пази резултата от `Path(__file__).resolve`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        self.backend_dir = Path(__file__).resolve().parents[3]
        self.output_dir = self.backend_dir / "generated"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # `self.timeout` пази резултата от `os.getenv`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        self.timeout = int(os.getenv("PDF_EXPORT_TIMEOUT_SECONDS", "45"))
        self.page_width = 960
        self.page_height = 540
        self.body_font, self.bold_font = self._register_fonts()

    def export_pptx(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str) -> str:
        # Роля в pipeline-а: превръща готовия layout в краен файл за клиента.
        # Входът идва през `self` (неуточнен тип), `presentation` (LayoutedPresentationDocument), `theme` (ThemeDefinition), `asset_id` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `NotImplementedError`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `str`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        raise NotImplementedError("Use PptxExporter for PPTX output.")

    def export_pdf(self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, asset_id: str) -> str:
        # Роля в pipeline-а: превръща готовия layout в краен файл за клиента.
        # Входът идва през `self` (неуточнен тип), `presentation` (LayoutedPresentationDocument), `theme` (ThemeDefinition), `asset_id` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `pptx_path.exists`, `self._render_pdf`, `self._find_libreoffice`, `self._convert_pptx_to_pdf`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `str`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        pptx_name = f"{asset_id}.pptx"
        # `pptx_path` материализира резултата като локална файлова референция, която renderer-ът може да използва без нова мрежова заявка.
        pptx_path = self.output_dir / pptx_name
        filename = f"{asset_id}.pdf"
        # `output_path` е крайното място във файловата система, което следващият слой може безопасно да използва.
        output_path = self.output_dir / filename

        # Това условие е decision point: `pptx_path.exists()`.
        # При вярно условие се активира `self._find_libreoffice`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if pptx_path.exists():
            # `libreoffice_path` материализира резултата като локална файлова референция, която renderer-ът може да използва без нова мрежова заявка.
            libreoffice_path = self._find_libreoffice()
            # Това условие е decision point: `libreoffice_path is None`.
            # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
            if libreoffice_path is None:
                logger.warning("LibreOffice executable not found. PDF export via LibreOffice skipped.")
            else:
                # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
                # `try/except` превръща техническите грешки (Exception) в предвидимо поведение за горния слой.
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
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `find_libreoffice` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `os.getenv`, `Path`, `shutil.which`, `candidate.is_file`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `str | None`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        # `configured_path` материализира резултата като локална файлова референция, която renderer-ът може да използва без нова мрежова заявка.
        configured_path = os.getenv("LIBREOFFICE_PATH")
        # `candidates` е работният списък с image резултати, който pipeline-ът филтрира и подрежда.
        candidates = (
            Path(configured_path) if configured_path else None,
            Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
            Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        )
        # Обхождаме `candidates` като `candidate`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for candidate in candidates:
            # Това условие е decision point: `candidate and candidate.is_file()`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`str(candidate)`) и прескачаме ненужната останала работа.
            if candidate and candidate.is_file():
                return str(candidate)
        # Обхождаме `('soffice', 'libreoffice')` като `executable`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for executable in ("soffice", "libreoffice"):
            # `resolved` пази резултата от `shutil.which`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            resolved = shutil.which(executable)
            # Това условие е decision point: `resolved`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`resolved`) и прескачаме ненужната останала работа.
            if resolved:
                return resolved
        return None

    def _convert_pptx_to_pdf(self, libreoffice_path: str, pptx_path: Path, output_path: Path) -> None:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `convert_pptx_to_pdf` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `libreoffice_path` (str), `pptx_path` (Path), `output_path` (Path); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `subprocess.run`, `converted.exists`, `output_path.exists`, `converted.rename`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
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
        # Това условие е decision point: `converted.exists() and converted != output_path`.
        # При вярно условие се активира `output_path.exists`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if converted.exists() and converted != output_path:
            # Това условие е decision point: `output_path.exists()`.
            # При вярно условие се активира `output_path.unlink`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if output_path.exists():
                output_path.unlink()
            converted.rename(output_path)
        # Това условие е decision point: `not output_path.exists()`.
        # При вярно условие се активира `RuntimeError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if not output_path.exists():
            raise RuntimeError("LibreOffice did not create a PDF.")

    def _register_fonts(self) -> tuple[str, str]:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `register_fonts` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `Path`, `regular_path.is_file`, `bold_path.is_file`, `pdfmetrics.getRegisteredFontNames`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `tuple[str, str]`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        # `candidates` е работният списък с image резултати, който pipeline-ът филтрира и подрежда.
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
        # Обхождаме `candidates` като `(regular_name, bold_name, regular_path, bold_path)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for regular_name, bold_name, regular_path, bold_path in candidates:
            # Това условие е decision point: `regular_path.is_file() and bold_path.is_file()`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`(regular_name, bold_name)`) и прескачаме ненужната останала работа.
            if regular_path.is_file() and bold_path.is_file():
                # Това условие е decision point: `regular_name not in pdfmetrics.getRegisteredFontNames()`.
                # При вярно условие се активира `pdfmetrics.registerFont`; така този branch избира конкретна стратегия, а не просто проверява стойност.
                if regular_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(regular_name, regular_path))
                    pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                return regular_name, bold_name
        return "Helvetica", "Helvetica-Bold"

    def _color(self, value: str | None, fallback: str = "#2563eb") -> colors.Color:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `color` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `value` (str | None), `fallback` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `colors.HexColor`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `colors.Color`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
        # `try/except` превръща техническите грешки (Exception) в предвидимо поведение за горния слой.
        try:
            return colors.HexColor(value or fallback)
        except Exception:
            return colors.HexColor(fallback)

    def _component_style(self, theme: ThemeDefinition, component: str) -> dict:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `component_style` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `theme` (ThemeDefinition), `component` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `dict`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        return theme.tokens.component_styles.get(component, {})

    def _pt(
        self, slide_width: int, slide_height: int, x: int, y: int, width: int, height: int
    ) -> tuple[float, float, float, float]:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `pt` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `slide_width` (int), `slide_height` (int), `x` (int), `y` (int), `width` (int) и още параметри; имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `tuple[float, float, float, float]`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        sx = self.page_width / slide_width
        sy = self.page_height / slide_height
        w = width * sx
        h = height * sy
        return x * sx, self.page_height - ((y * sy) + h), w, h

    def _wrap(self, text: str, font: str, size: float, max_width: float) -> list[str]:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `wrap` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `text` (str), `font` (str), `size` (float), `max_width` (float); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `text.splitlines`, `stringWidth`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `list[str]`. Резултатът е част от последния rendering/export етап и вече е близо до крайния PPTX/PDF файл.
        lines: list[str] = []
        # Обхождаме `text.splitlines() or ['']` като `raw`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for raw in text.splitlines() or [""]:
            # `words` е думите от заглавието след Unicode нормализация; те са суровината за безопасния slug.
            words = raw.split()
            line = ""
            # Обхождаме `words` като `word`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
            # Цикълът държи обработката еднаква за всеки елемент.
            for word in words:
                # `candidate` е един възможен image резултат, който още не е минал всички проверки и scoring.
                candidate = f"{line} {word}".strip()
                # Това условие е decision point: `line and stringWidth(candidate, font, size) > max_width`.
                # При вярно условие се активира `lines.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
                if line and stringWidth(candidate, font, size) > max_width:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            # Това условие е decision point: `line`.
            # При вярно условие се активира `lines.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
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
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `draw_text` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `page` (canvas.Canvas), `element` (LayoutElement), `x` (float), `y` (float), `w` (float) и още параметри; имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self._wrap`, `page.setFillColor`, `page.setFont`, `self._color`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        bold = (
            element.kind in {LayoutElementKind.STATISTIC, LayoutElementKind.QUOTE}
            or "title" in element.region
            or "heading" in element.region
            or "value" in element.region
        )
        font = self.bold_font if bold else self.body_font
        size = max(7, (element.font_size or 18) * 0.75)
        # `lines` пази резултата от `self._wrap`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        lines = self._wrap(element.text or "", font, size, max(1, w - 8))
        line_height = size * (element.line_height or 1.18)
        start_y = y + h - size - 4
        # Това условие е decision point: `element.align == Alignment.CENTER`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
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
        # Обхождаме `enumerate(lines)` като `(index, line)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for index, line in enumerate(lines):
            line_y = start_y - index * line_height
            # Това условие е decision point: `line_y < y`.
            # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
            if line_y < y:
                break
            # Това условие е decision point: `element.align == Alignment.CENTER`.
            # При вярно условие се активира `page.drawCentredString`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if element.align == Alignment.CENTER:
                page.drawCentredString(x + w / 2, line_y, line)
            # Това условие е decision point: `element.align == Alignment.END`.
            # При вярно условие се активира `page.drawRightString`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            elif element.align == Alignment.END:
                page.drawRightString(x + w - 4, line_y, line)
            else:
                page.drawString(x + 4, line_y, line)

    def _draw_icon(
        self, page: canvas.Canvas, x: float, y: float, size: float, icon: str, theme: ThemeDefinition
    ) -> None:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `draw_icon` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `page` (canvas.Canvas), `x` (float), `y` (float), `size` (float), `icon` (str) и още параметри; имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `page.setFillColor`, `page.setStrokeColor`, `page.circle`, `page.setLineWidth`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        page.setFillColor(self._color(theme.tokens.accent_secondary))
        page.setStrokeColor(self._color(theme.tokens.accent_primary))
        page.circle(x + size / 2, y + size / 2, size / 2, fill=1, stroke=1)
        page.setStrokeColor(self._color(theme.tokens.accent_primary))
        page.setLineWidth(1.4)
        # Това условие е decision point: `icon == 'chart'`.
        # При вярно условие се активира `enumerate`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if icon == "chart":
            # Обхождаме `enumerate((0.28, 0.45, 0.62))` като `(index, height_scale)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
            # Цикълът държи обработката еднаква за всеки елемент.
            for index, height_scale in enumerate((0.28, 0.45, 0.62)):
                page.rect(
                    x + size * (0.27 + index * 0.18), y + size * 0.22, size * 0.1, size * height_scale, fill=0, stroke=1
                )
        # Това условие е decision point: `icon == 'bolt'`.
        # При вярно условие се активира `page.line`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        elif icon == "bolt":
            page.line(x + size * 0.62, y + size * 0.78, x + size * 0.4, y + size * 0.5)
            page.line(x + size * 0.4, y + size * 0.5, x + size * 0.58, y + size * 0.5)
            page.line(x + size * 0.58, y + size * 0.5, x + size * 0.38, y + size * 0.2)
        # Това условие е decision point: `icon in {'clock', 'eye', 'search', 'target'}`.
        # При вярно условие се активира `page.circle`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        elif icon in {"clock", "eye", "search", "target"}:
            page.circle(x + size / 2, y + size / 2, size * 0.22, fill=0, stroke=1)
            # Това условие е decision point: `icon == 'clock'`.
            # При вярно условие се активира `page.line`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if icon == "clock":
                page.line(x + size / 2, y + size / 2, x + size / 2, y + size * 0.68)
                page.line(x + size / 2, y + size / 2, x + size * 0.66, y + size * 0.42)
            # Това условие е decision point: `icon == 'search'`.
            # При вярно условие се активира `page.line`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            elif icon == "search":
                page.line(x + size * 0.65, y + size * 0.35, x + size * 0.82, y + size * 0.18)
        # Това условие е decision point: `icon in {'person', 'users'}`.
        # При вярно условие се активира `page.circle`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        elif icon in {"person", "users"}:
            page.circle(x + size / 2, y + size * 0.66, size * 0.12, fill=1, stroke=1)
            page.ellipse(x + size * 0.32, y + size * 0.22, x + size * 0.68, y + size * 0.54, fill=0, stroke=1)
        # Това условие е decision point: `icon in {'book', 'film', 'home', 'shield', 'star', 'heart', 'idea', 'map'}`.
        # При вярно условие се активира `page.rect`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        elif icon in {"book", "film", "home", "shield", "star", "heart", "idea", "map"}:
            page.rect(x + size * 0.28, y + size * 0.28, size * 0.44, size * 0.44, fill=0, stroke=1)
        else:
            page.circle(x + size / 2, y + size / 2, size * 0.22, fill=0, stroke=1)

    def _draw_fitted_image(
        self, page: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float, fit: str
    ) -> None:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `draw_fitted_image` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `page` (canvas.Canvas), `path` (Path), `x` (float), `y` (float), `w` (float) и още параметри; имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `ImageReader`, `image.getSize`, `page.saveState`, `page.beginPath`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        # `image` пази резултата от `ImageReader`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        image = ImageReader(str(path))
        source_width, source_height = image.getSize()
        source_ratio = source_width / max(source_height, 1)
        frame_ratio = w / max(h, 1)
        # Това условие е decision point: `fit == 'contain'`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if fit == "contain":
            # Това условие е decision point: `source_ratio > frame_ratio`.
            # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
            if source_ratio > frame_ratio:
                draw_w, draw_h = w, w / source_ratio
            else:
                draw_h, draw_w = h, h * source_ratio
        # Това условие е decision point: `source_ratio > frame_ratio`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        elif source_ratio > frame_ratio:
            draw_h, draw_w = h, h * source_ratio
        else:
            draw_w, draw_h = w, w / source_ratio
        page.saveState()
        # `clip` пази резултата от `page.beginPath`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
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
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `draw_element` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `page` (canvas.Canvas), `element` (LayoutElement), `theme` (ThemeDefinition), `slide_width` (int), `slide_height` (int) и още параметри; имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self._pt`, `page.setFillColor`, `page.setStrokeColor`, `self._draw_element`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        x, y, w, h = self._pt(slide_width, slide_height, ox + element.x, oy + element.y, element.width, element.height)
        # Това условие е decision point: `element.kind == LayoutElementKind.PANEL`.
        # При вярно условие се активира `page.setFillColor`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if element.kind == LayoutElementKind.PANEL:
            page.setFillColor(self._color(theme.tokens.surface))
            page.setStrokeColor(self._color(theme.tokens.border))
            # Това условие е decision point: `self._component_style(theme, 'panel').get('style') == 'square'`.
            # При вярно условие се активира `page.rect`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if self._component_style(theme, "panel").get("style") == "square":
                page.rect(x, y, w, h, fill=1, stroke=1)
            else:
                page.roundRect(
                    x, y, w, h, float(self._component_style(theme, "panel").get("radius") or 8) * 0.36, fill=1, stroke=1
                )
        # Това условие е decision point: `element.kind == LayoutElementKind.IMAGE`.
        # При вярно условие се активира `element.content.get`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        elif element.kind == LayoutElementKind.IMAGE:
            # `local_path` материализира резултата като локална файлова референция, която renderer-ът може да използва без нова мрежова заявка.
            local_path = element.content.get("local_path")
            # `image_path` е локалният asset път, който renderer/exporter може да отвори без мрежова зависимост.
            image_path = Path(local_path) if local_path else None
            page.setFillColor(self._color(theme.tokens.surface))
            page.setStrokeColor(self._color(theme.tokens.border))
            page.roundRect(x, y, w, h, 8, fill=1, stroke=1)
            # Това условие е decision point: `image_path and image_path.exists()`.
            # При вярно условие се активира `max`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if image_path and image_path.exists():
                # `inset` пази резултата от `self._component_style(theme, 'image').get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
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
        # Това условие е decision point: `element.kind == LayoutElementKind.BULLET_ITEM`.
        # При вярно условие се активира `page.setStrokeColor`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        elif element.kind == LayoutElementKind.BULLET_ITEM:
            page.setStrokeColor(self._color(theme.tokens.border))
            # Това условие е decision point: `self._component_style(theme, 'bullet').get('style') == 'lines'`.
            # При вярно условие се активира `page.setStrokeColor`; така този branch избира конкретна стратегия, а не просто проверява стойност.
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
        # Това условие е decision point: `element.kind != LayoutElementKind.BULLET_LIST`.
        # При вярно условие се активира `self._draw_text`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        elif element.kind != LayoutElementKind.BULLET_LIST:
            self._draw_text(page, element, x, y, w, h, theme)

        # Обхождаме `element.children` като `child`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for child in element.children:
            self._draw_element(page, child, theme, slide_width, slide_height, ox + element.x, oy + element.y)

    def _render_pdf(
        self, presentation: LayoutedPresentationDocument, theme: ThemeDefinition, output_path: Path
    ) -> None:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: превежда semantic/layout информация към конкретни визуални обекти.
        # Входът идва през `self` (неуточнен тип), `presentation` (LayoutedPresentationDocument), `theme` (ThemeDefinition), `output_path` (Path); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `canvas.Canvas`, `doc.save`, `doc.setFillColor`, `doc.rect`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        # `doc` пази резултата от `canvas.Canvas`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        doc = canvas.Canvas(str(output_path), pagesize=(self.page_width, self.page_height))
        # Обхождаме `presentation.slides` като `slide`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for slide in presentation.slides:
            doc.setFillColor(self._color(theme.tokens.background))
            doc.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
            doc.setFillColor(self._color(theme.tokens.accent_primary))
            # Това условие е decision point: `self._component_style(theme, 'background').get('accent_position') == 'top'`.
            # При вярно условие се активира `doc.rect`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if self._component_style(theme, "background").get("accent_position") == "top":
                doc.rect(0, self.page_height - 7, self.page_width, 7, fill=1, stroke=0)
            else:
                doc.rect(0, 0, 7, self.page_height, fill=1, stroke=0)
            # Обхождаме `sorted(slide.elements, key=lambda item: item.z_index)` като `element`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
            # Цикълът държи обработката еднаква за всеки елемент.
            for element in sorted(slide.elements, key=lambda item: item.z_index):
                self._draw_element(doc, element, theme, slide.canvas_width, slide.canvas_height)
            doc.showPage()
        doc.save()
