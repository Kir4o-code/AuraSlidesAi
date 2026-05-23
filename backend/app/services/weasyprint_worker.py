import logging
import sys
from pathlib import Path

from weasyprint import CSS, HTML


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    if len(sys.argv) != 5:
        logger.error("Expected 4 arguments: html_path css_path output_path base_url")
        return 2

    html_path = Path(sys.argv[1])
    css_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])
    base_url = sys.argv[4]

    logger.info(
        "Worker started. html=%s css=%s output=%s base_url=%s",
        html_path,
        css_path,
        output_path,
        base_url,
    )

    document = HTML(filename=str(html_path), base_url=base_url)
    stylesheet = CSS(filename=str(css_path))
    document.write_pdf(target=str(output_path), stylesheets=[stylesheet])
    logger.info("Worker finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
