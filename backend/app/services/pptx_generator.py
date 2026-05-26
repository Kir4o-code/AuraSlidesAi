from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.schemas.presentation import Presentation
from app.services.layout_engine import build_pptx_presentation


OUTPUT_DIR = Path(__file__).resolve().parents[2] / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_pptx(presentation: Presentation, asset_id: str | None = None) -> str:
    asset_id = asset_id or uuid4().hex
    output_name = f"{asset_id}.pptx"
    output_path = OUTPUT_DIR / output_name

    deck = build_pptx_presentation(presentation)
    deck.core_properties.title = presentation.title
    deck.core_properties.subject = "AuraSlidesAi presentation export"
    deck.core_properties.author = "AuraSlidesAi"
    deck.save(output_path)

    return output_name