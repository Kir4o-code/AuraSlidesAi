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
CHROME_CANDIDATES = (
    Path(os.getenv("CHROME_PATH", "")) if os.getenv("CHROME_PATH") else None,
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
)


def _inject_stylesheet(html: str, css_text: str) -> str:
    style_tag = f"<style>\n{css_text}\n</style>"
    if "</head>" in html:
        return html.replace("</head>", f"{style_tag}\n</head>", 1)
    return f"{style_tag}\n{html}"


def _find_browser_executable() -> Path | None:
    for candidate in CHROME_CANDIDATES:
        if candidate and candidate.exists():
            return candidate
    return None


def _export_with_browser(
    html: str,
    css_path: Path,
    output_path: Path,
    base_url: Path,
) -> None:
    browser = _find_browser_executable()
    if browser is None:
        raise PdfExportError(
            "Chrome or Edge was not found. Set CHROME_PATH or install a Chromium-based browser."
        )

    html_path = output_path.with_suffix(".browser.html")
    css_text = css_path.read_text(encoding="utf-8")
    html_with_css = _inject_stylesheet(html, css_text)
    html_path.write_text(html_with_css, encoding="utf-8")
    logger.info(
        "Browser export starting. browser=%s output=%s base_url=%s html_chars=%s timeout=%ss",
        browser,
        output_path,
        base_url,
        len(html_with_css),
        PDF_EXPORT_TIMEOUT_SECONDS,
    )
    command = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--disable-background-networking",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
        "--virtual-time-budget=500",
        f"--print-to-pdf={output_path}",
        html_path.resolve().as_uri(),
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
        logger.info("Browser stdout:\n%s", result.stdout.strip())
    if result.stderr.strip():
        logger.warning("Browser stderr:\n%s", result.stderr.strip())
    if result.returncode != 0:
        raise PdfExportError(f"Browser PDF export failed with exit code {result.returncode}.")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise PdfExportError("Browser PDF export finished without creating a PDF file.")


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
    base_url_uri = base_url.resolve().as_uri()
    command = [
        sys.executable,
        "-m",
        WORKER_MODULE,
        str(html_path),
        str(css_path),
        str(output_path),
        base_url_uri,
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
    if PDF_EXPORT_ENGINE == "chrome":
        engines = ["chrome"]
    elif PDF_EXPORT_ENGINE == "weasyprint":
        engines = ["weasyprint"]
    elif PDF_EXPORT_ENGINE == "xhtml2pdf":
        engines = ["xhtml2pdf"]
    else:
        engines = ["chrome", "weasyprint", "xhtml2pdf"]
    failures: list[str] = []
    try:
        started_at = perf_counter()
        for engine in engines:
            if output_path.exists():
                output_path.unlink()
            try:
                logger.info("Attempting PDF export with engine=%s", engine)
                if engine == "chrome":
                    _export_with_browser(html, css_path, output_path, base_url)
                elif engine == "weasyprint":
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
                    "This usually points to a local browser or renderer runtime issue."
                )
                failures.append(message)
                logger.exception("PDF export timeout with engine=%s", engine)
                raise PdfExportError(message) from exc
            except PdfExportError as exc:
                failures.append(f"{engine}: {exc}")
                logger.exception("PDF export failed with engine=%s", engine)
                if engine != engines[-1]:
                    continue
                raise PdfExportError("All PDF export engines failed: " + " | ".join(failures)) from exc
        logger.info(
            "PDF export finished in %.2fs. output=%s",
            perf_counter() - started_at,
            output_path,
        )
    except Exception as exc:
        if isinstance(exc, PdfExportError):
            raise
        raise PdfExportError(f"PDF export failed: {exc}") from exc
