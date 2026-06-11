# Роля на модула: Входната точка на FastAPI. Работи като електрическо табло: свързва middleware, static files и routes, но не върши бизнес логиката вместо тях.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# `BASE_DIR` е стабилната основна директория за backend конфигурацията; изчислява се спрямо файла, а не спрямо текущата shell директория.
BASE_DIR = Path(__file__).resolve().parent.parent
# `.env` се зарежда преди import-а на routes/services, защото част от тях създават settings още при import.
# Ако редът се обърне, те могат да прочетат празни или стари environment стойности.
load_dotenv(BASE_DIR / ".env")
logging.basicConfig(level=logging.INFO)

# Imports след конфигурацията са умишлени. `# noqa: E402` казва на linter-а, че нарушението на стандартния
# import order е нужно за правилния startup lifecycle, а не е пропуск.
from app.routes.presentations import router as presentations_router  # noqa: E402
from app.services.slide_generator import OUTPUT_DIR  # noqa: E402

# `app` е главният FastAPI application object, върху който се закачат middleware, routes и static files.
app = FastAPI(
    title="AuraSlides AI API",
    version="0.1.0",
    description="MVP API for AI-assisted, layout-based presentation generation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router-ът публикува API операциите, а mount-ът публикува вече генерираните файлове.
# Това разделя "създай ресурс" от "изтегли готовия ресурс".
app.include_router(presentations_router)
app.mount("/generated", StaticFiles(directory=OUTPUT_DIR), name="generated")


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    # Роля в pipeline-а: обработва стъпката `healthcheck` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Функцията няма входни параметри; тя чете конфигурация или създава общ ресурс.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
    # Изходен договор: `dict[str, str]`. Резултатът се подава към caller-а като стабилна междинна стойност за следващата стъпка.
    return {"status": "ok"}
