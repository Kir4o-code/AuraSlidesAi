import os
import asyncio
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.presentation import GeneratePresentationRequest, GeneratePresentationResponse
from app.services.gemini_service import (
    GeminiConfigurationError,
    GeminiImageGenerationError,
    GeminiPlanningError,
    get_settings,
    generate_presentation,
)
from app.services.image_service import enrich_presentation_images
from app.services.slide_generator import build_presentation_exports, prepare_export_bundle


router = APIRouter(prefix="/presentations", tags=["presentations"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GeneratePresentationResponse)
async def generate_presentation_route(
    payload: GeneratePresentationRequest,
    request: Request,
) -> GeneratePresentationResponse:
    request_id = uuid4().hex[:8]
    started_at = perf_counter()
    layouted_presentation = None
    try:
        logger.info(
            "[%s] Starting presentation generation. slide_count=%s style=%s prompt_chars=%s",
            request_id,
            payload.slide_count,
            payload.style,
            len(payload.prompt),
        )
        presentation = await generate_presentation(
            prompt=payload.prompt,
            slide_count=payload.slide_count,
            style=payload.style,
        )
        settings = get_settings()
        if settings.enable_image_generation:
            logger.info(
                "[%s] Starting image enrichment for image-backed slides. source=%s",
                request_id,
                payload.image_source,
            )
            presentation = await enrich_presentation_images(presentation, payload.image_source)
        else:
            logger.info(
                "[%s] Image generation disabled by env. Prompts will still render in slide layouts.",
                request_id,
            )
        layouted_presentation, _semantic_theme = prepare_export_bundle(presentation)
        logger.info("[%s] Gemini planning complete. Rendering PPTX and PDF.", request_id)
        pptx_name, pdf_name = await asyncio.to_thread(build_presentation_exports, presentation)
        logger.info(
            "[%s] Presentation export complete. pptx=%s pdf=%s duration=%.2fs",
            request_id,
            pptx_name,
            pdf_name,
            perf_counter() - started_at,
        )
    except GeminiConfigurationError as exc:
        logger.exception("[%s] Gemini configuration error.", request_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    except GeminiPlanningError as exc:
        logger.exception("[%s] Gemini planning error.", request_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except GeminiImageGenerationError as exc:
        logger.exception("[%s] Gemini image generation error.", request_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        logger.exception("[%s] Presentation validation error.", request_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive API guard
        logger.exception("[%s] Unexpected presentation generation error.", request_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Presentation generation failed unexpectedly.",
        ) from exc

    pdf_url = str(request.base_url).rstrip("/") + f"/generated/{pdf_name}"
    pptx_url = str(request.base_url).rstrip("/") + f"/generated/{pptx_name}"
    return GeneratePresentationResponse(
        presentation=presentation,
        layouted_presentation=layouted_presentation,
        pptx_url=pptx_url,
        pdf_url=pdf_url,
    )
