# Роля на модула: HTTP orchestration слой. Работи като диспечер: приема заявката, подава я последователно към planning, image enrichment, layout и export и превежда грешките към HTTP.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
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

# `router` е FastAPI регистърът за presentation endpoint-ите; main.py го включва като една цяла HTTP област.
router = APIRouter(prefix="/presentations", tags=["presentations"])
logger = logging.getLogger(__name__)


async def _generate_presentation_response(
    payload: GeneratePresentationRequest,
    request: Request,
    notify: Callable[[str], None] | None = None,
) -> GeneratePresentationResponse:
    # Роля в pipeline-а: Работи като диспечер на цялата HTTP операция: свързва planning, image enrichment, semantic preparation и export, без да изпълнява техните вътрешни алгоритми.
    # Входът идва през `payload` (GeneratePresentationRequest), `request` (Request); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `perf_counter`, `GeneratePresentationResponse`, `get_settings`, `prepare_export_bundle`; така се вижда кои отговорности функцията делегира.
    # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
    # Изходен договор: `GeneratePresentationResponse`. Крайният резултат се сериализира от FastAPI и се връща към frontend клиента.
    # `request_id` е кратък correlation id, с който всички логове за една HTTP заявка могат да се проследят като обща история.
    request_id = uuid4().hex[:8]
    # `started_at` е началният timestamp, нужен само за измерване на общата продължителност на pipeline-а.
    started_at = perf_counter()
    # `layouted_presentation` е renderer-ready версията на презентацията с вече изчислена геометрия.
    layouted_presentation = None
    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (GeminiConfigurationError, GeminiPlanningError, GeminiImageGenerationError, ValueError, Exception) в предвидимо поведение за горния слой.
    try:
        # Първият log е "касова бележка" за входа: не записва целия prompt, но пази достатъчно metadata,
        # за да сравним бавна или грешна заявка с избрания режим, тема и image source.
        logger.info(
            "[%s] Starting presentation generation. slide_count=%s style=%s planning_mode=%s image_source=%s prompt_chars=%s",
            request_id,
            payload.slide_count,
            payload.template.value if payload.template else payload.style,
            payload.planning_mode,
            payload.image_source,
            len(payload.prompt),
        )
        # Това е първата голяма граница в pipeline-а. Gemini service приема свободния потребителски текст,
        # но връща строг Presentation модел. Оттук надолу кодът вече не работи със суров AI отговор.
        # `presentation` е централният domain обект, който постепенно се обогатява със съдържание, изображения и export информация.
        # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
        presentation = await generate_presentation(
            prompt=payload.prompt,
            slide_count=payload.slide_count,
            style=payload.template.value if payload.template else payload.style,
            planning_mode=payload.planning_mode,
            slide_outline=payload.slide_outline,
        )
        # Това условие е decision point: `payload.template`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if payload.template:
            # Explicit template от клиента има по-висок приоритет от theme-а, предложен по време на AI planning.
            # Така frontend изборът остава авторитетен и всички следващи layout/export стъпки виждат една тема.
            presentation.theme = payload.template
        # `settings` е конфигурацията от environment, която включва или изключва външни услуги и избира модели.
        settings = get_settings()
        # Това условие е decision point: `payload.image_source == ImageSource.UNSPLASH or settings.enable_image_generation`.
        # При вярно условие се активира `enrich_presentation_images`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if payload.image_source == ImageSource.UNSPLASH or settings.enable_image_generation:
            logger.info(
                "[%s] Starting image enrichment. source=%s",
                request_id,
                payload.image_source,
            )
            # Image enrichment променя същия domain обект, като добавя ResolvedImageAsset към подходящите слайдове.
            # Стъпката е преди layout-а, защото renderer-ът трябва да знае дали има реален asset и неговите размери.
            # `presentation` е централният domain обект, който постепенно се обогатява със съдържание, изображения и export информация.
            # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
            presentation = await enrich_presentation_images(presentation, payload.image_source)
        else:
            logger.info(
                "[%s] Gemini image generation disabled by env. Prompts will still render in slide layouts.",
                request_id,
            )
        # Този предварителен semantic pass има две цели: response-ът да съдържа layout за frontend preview
        # и невалиден semantic договор да бъде хванат преди по-бавния файлов export.
        layouted_presentation, _semantic_theme = prepare_export_bundle(presentation)
        logger.info("[%s] Gemini planning complete. Rendering PPTX and PDF.", request_id)
        # PPTX/PDF rendering е синхронна и CPU/filesystem тежка работа. `to_thread` я мести извън event loop-а,
        # за да не замрази останалите FastAPI заявки, докато файловете се създават.
        pptx_name, pdf_name = await asyncio.to_thread(build_presentation_exports, presentation)
        logger.info(
            "[%s] Presentation export complete. pptx=%s pdf=%s duration=%.2fs",
            request_id,
            pptx_name,
            pdf_name,
            perf_counter() - started_at,
        )
    # Exception mapping-ът е част от API договора: caller-ът трябва да различава счупена конфигурация,
    # временен provider проблем и собствен невалиден input, вместо всички откази да изглеждат като generic 500.
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

    # Exporters връщат само файлови имена. Route-ът е правилното място да ги превърне в публични URL адреси,
    # защото само HTTP слоят познава base_url на текущата заявка и mounted `/generated` route.
    # `pdf_url` държи външна resource референция; тя още не е локален asset и може да изисква download.
    pdf_url = str(request.base_url).rstrip("/") + f"/generated/{pdf_name}" if pdf_name else None
    # `pptx_url` държи външна resource референция; тя още не е локален asset и може да изисква download.
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
