import logging
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.presentation import GeneratePresentationRequest, GeneratePresentationResponse
from app.services.feature_flags import is_image_generation_enabled
from app.services.gemini_service import (
    GeminiConfigurationError,
    GeminiPlanningError,
    generate_presentation,
)
from app.services.image_service import enrich_presentation_images
from app.services.pdf_exporter import PdfExportError
from app.services.slide_generator import build_presentation_exports


router = APIRouter(prefix="/presentations", tags=["presentations"])
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GeneratePresentationResponse)
async def generate_presentation_route(
    payload: GeneratePresentationRequest,
    request: Request,
) -> GeneratePresentationResponse:
    request_id = uuid4().hex[:8]
    started_at = perf_counter()
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
        env_image_switch = is_image_generation_enabled()
        should_generate_images = payload.generate_images and env_image_switch
        logger.info(
            "[%s] Image generation flags. request=%s env=%s effective=%s",
            request_id,
            payload.generate_images,
            env_image_switch,
            should_generate_images,
        )
        if should_generate_images:
            logger.info("[%s] Starting Gemini image generation for image slides.", request_id)
            presentation = await enrich_presentation_images(presentation)
        else:
            logger.info("[%s] Image generation skipped.", request_id)
        logger.info("[%s] Gemini planning complete. Rendering PPTX and PDF.", request_id)
        pptx_name, pdf_name = build_presentation_exports(presentation)
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
    except PdfExportError as exc:
        logger.exception("[%s] PDF export error.", request_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
        pptx_url=pptx_url,
        pdf_url=pdf_url,
    )
