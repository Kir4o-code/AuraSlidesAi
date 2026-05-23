import logging
import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from time import perf_counter


class PdfExportError(Exception):
    pass


logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[2]
WORKER_MODULE = "app.services.weasyprint_worker"
PDF_EXPORT_TIMEOUT_SECONDS = int(os.getenv("PDF_EXPORT_TIMEOUT_SECONDS", "45"))
PDF_EXPORT_ENGINE = os.getenv("PDF_EXPORT_ENGINE", "auto").lower()


def _inject_stylesheet(html: str, css_text: str) -> str:
    style_tag = f"<style>\n{css_text}\n</style>"
    if "</head>" in html:
        return html.replace("</head>", f"{style_tag}\n</head>", 1)
    return f"{style_tag}\n{html}"


def _export_with_weasyprint(
    html: str,
    css_path: Path,
    output_path: Path,
    base_url: Path,
) -> None:
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    logger.info(
        "WeasyPrint export starting. output=%s css=%s base_url=%s html_chars=%s timeout=%ss",
        output_path,
        css_path,
        base_url,
        len(html),
        PDF_EXPORT_TIMEOUT_SECONDS,
    )
    command = [
        sys.executable,
        "-m",
        WORKER_MODULE,
        str(html_path),
        str(css_path),
        str(output_path),
        str(base_url),
    ]
    result = subprocess.run(
        command,
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=PDF_EXPORT_TIMEOUT_SECONDS,
        check=False,
    )
    if result.stdout.strip():
        logger.info("WeasyPrint worker stdout:\n%s", result.stdout.strip())
    if result.stderr.strip():
        logger.warning("WeasyPrint worker stderr:\n%s", result.stderr.strip())
    if result.returncode != 0:
        raise PdfExportError(
            f"WeasyPrint worker failed with exit code {result.returncode}."
        )
    if not output_path.exists():
        raise PdfExportError("WeasyPrint worker finished without creating a PDF file.")


def _export_with_xhtml2pdf(
    html: str,
    css_path: Path,
    output_path: Path,
    base_url: Path,
) -> None:
    try:
        from xhtml2pdf import pisa
    except ImportError as exc:
        raise PdfExportError(
            "xhtml2pdf is not installed. Run `pip install -r backend/requirements.txt`."
        ) from exc

    css_text = css_path.read_text(encoding="utf-8")
    html_with_css = _inject_stylesheet(html, css_text)
    logger.info(
        "xhtml2pdf export starting. output=%s css=%s base_url=%s html_chars=%s",
        output_path,
        css_path,
        base_url,
        len(html_with_css),
    )
    output_buffer = BytesIO()
    result = pisa.CreatePDF(
        src=html_with_css,
        dest=output_buffer,
        path=str(base_url),
        encoding="utf-8",
    )
    if result.err:
        raise PdfExportError("xhtml2pdf reported errors while building the PDF.")
    output_path.write_bytes(output_buffer.getvalue())
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise PdfExportError("xhtml2pdf finished without creating a PDF file.")
    logger.info("xhtml2pdf export finished. output=%s bytes=%s", output_path, output_path.stat().st_size)


def export_pdf(html: str, css_path: Path, output_path: Path, base_url: Path) -> None:
    engines = ["weasyprint", "xhtml2pdf"] if PDF_EXPORT_ENGINE == "auto" else [PDF_EXPORT_ENGINE]
    failures: list[str] = []
    try:
        started_at = perf_counter()
        for engine in engines:
            if output_path.exists():
                output_path.unlink()
            try:
                logger.info("Attempting PDF export with engine=%s", engine)
                if engine == "weasyprint":
                    _export_with_weasyprint(html, css_path, output_path, base_url)
                elif engine == "xhtml2pdf":
                    _export_with_xhtml2pdf(html, css_path, output_path, base_url)
                else:
                    raise PdfExportError(f"Unsupported PDF export engine: {engine}")
                logger.info("PDF export succeeded with engine=%s", engine)
                break
            except subprocess.TimeoutExpired as exc:
                message = (
                    f"{engine}: timed out after {PDF_EXPORT_TIMEOUT_SECONDS} seconds. "
                    "This usually points to a local WeasyPrint/Windows runtime issue."
                )
                failures.append(message)
                logger.exception("PDF export timeout with engine=%s", engine)
                if engine != engines[-1]:
                    logger.info("Falling back to next PDF engine after timeout.")
                    continue
                raise PdfExportError(message) from exc
            except PdfExportError as exc:
                failures.append(f"{engine}: {exc}")
                logger.exception("PDF export failed with engine=%s", engine)
                if engine != engines[-1]:
                    logger.info("Falling back to next PDF engine.")
                    continue
                raise PdfExportError("All PDF export engines failed: " + " | ".join(failures)) from exc
        logger.info(
            "WeasyPrint export finished in %.2fs. output=%s",
            perf_counter() - started_at,
            output_path,
        )
    except Exception as exc:
        if isinstance(exc, PdfExportError):
            raise
        raise PdfExportError(f"PDF export failed: {exc}") from exc
