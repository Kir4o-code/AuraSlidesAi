from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import FRONTEND_DIR, IMAGES_DIR
from app.core.researcher import ImageResearcher
from app.core.storage import ensure_output_dirs
from app.schemas import ImageResearchRequest, ImageResearchResponse

ensure_output_dirs()

app = FastAPI(title="Image Researcher")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

researcher = ImageResearcher()

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "Image Researcher"}


@app.post("/api/research", response_model=ImageResearchResponse)
async def research(request: ImageResearchRequest) -> ImageResearchResponse:
    return await researcher.research(request)
