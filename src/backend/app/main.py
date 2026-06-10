import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
logging.basicConfig(level=logging.INFO)

from app.routes.presentations import router as presentations_router  # noqa: E402
from app.services.slide_generator import OUTPUT_DIR  # noqa: E402

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

app.include_router(presentations_router)
app.mount("/generated", StaticFiles(directory=OUTPUT_DIR), name="generated")


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
