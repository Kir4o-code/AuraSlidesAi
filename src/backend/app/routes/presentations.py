import asyncio
import json
import logging
from collections.abc import Callable
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.schemas.presentation import GeneratePresentationRequest, GeneratePresentationResponse, ImageSource
from app.services.gemini_service import (
    GeminiConfigurationError,
    GeminiImageGenerationError,
    GeminiPlanningError,
    generate_presentation,
    get_settings,
)
from app.services.image_service import enrich_presentation_images
from app.services.slide_generator import build_presentation_exports, prepare_export_bundle

router = APIRouter(prefix="/presentations", tags=["presentations"])
logger = logging.getLogger(__name__)


async def _generate_presentation_response(
    payload: GeneratePresentationRequest,
    request: Request,
    notify: Callable[[str], None] | None = None,
) -> GeneratePresentationResponse:
    notify = notify or (lambda _stage: None)
    request_id = uuid4().hex[:8]
    started_at = perf_counter()
    layouted_presentation = None
    logger.info(
        "[%s] Starting presentation generation. slide_count=%s style=%s planning_mode=%s image_source=%s prompt_chars=%s",
        request_id,
        payload.slide_count,
        payload.template.value if payload.template else payload.style,
        payload.planning_mode,
        payload.image_source,
        len(payload.prompt),
    )
    notify("planning")
    presentation = await generate_presentation(
        prompt=payload.prompt,
        slide_count=payload.slide_count,
        style=payload.template.value if payload.template else payload.style,
        planning_mode=payload.planning_mode,
        slide_outline=payload.slide_outline,
    )
    notify("validation")
    if payload.template:
        presentation.theme = payload.template
    settings = get_settings()
    if payload.image_source == ImageSource.UNSPLASH or settings.enable_image_generation:
        notify("images")
        logger.info(
            "[%s] Starting image enrichment. source=%s",
            request_id,
            payload.image_source,
        )
        presentation = await enrich_presentation_images(presentation, payload.image_source)
    else:
        logger.info(
            "[%s] Gemini image generation disabled by env. Prompts will still render in slide layouts.",
            request_id,
        )
    notify("export")
    layouted_presentation, _semantic_theme = prepare_export_bundle(presentation)
    logger.info("[%s] Rendering PPTX and PDF.", request_id)
    pptx_name, pdf_name = await asyncio.to_thread(build_presentation_exports, presentation)
    logger.info(
        "[%s] Presentation export complete. pptx=%s pdf=%s duration=%.2fs",
        request_id,
        pptx_name,
        pdf_name,
        perf_counter() - started_at,
    )

    pdf_url = str(request.base_url).rstrip("/") + f"/generated/{pdf_name}" if pdf_name else None
    pptx_url = str(request.base_url).rstrip("/") + f"/generated/{pptx_name}"
    return GeneratePresentationResponse(
        presentation=presentation,
        layouted_presentation=layouted_presentation,
        pptx_url=pptx_url,
        pdf_url=pdf_url,
    )


def _generation_http_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, GeminiConfigurationError):
        return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    if isinstance(exc, (GeminiPlanningError, GeminiImageGenerationError)):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Presentation generation failed unexpectedly.",
    )


@router.post("/generate", response_model=GeneratePresentationResponse)
async def generate_presentation_route(
    payload: GeneratePresentationRequest,
    request: Request,
) -> GeneratePresentationResponse:
    try:
        return await _generate_presentation_response(payload, request)
    except Exception as exc:
        logger.exception("Presentation generation failed.")
        raise _generation_http_exception(exc) from exc


@router.post("/generate-stream")
async def generate_presentation_stream_route(
    payload: GeneratePresentationRequest,
    request: Request,
) -> StreamingResponse:
    async def stream():
        queue: asyncio.Queue[str] = asyncio.Queue()
        task = asyncio.create_task(_generate_presentation_response(payload, request, queue.put_nowait))
        try:
            while not task.done() or not queue.empty():
                try:
                    stage = await asyncio.wait_for(queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue
                yield json.dumps({"type": "progress", "stage": stage}) + "\n"

            result = await task
            yield json.dumps({"type": "result", "data": result.model_dump(mode="json")}) + "\n"
        except Exception as exc:
            logger.exception("Streamed presentation generation failed.")
            error = _generation_http_exception(exc)
            yield json.dumps({"type": "error", "detail": error.detail}) + "\n"

    return StreamingResponse(
        stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
