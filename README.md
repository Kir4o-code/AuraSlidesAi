# AuraSlidesAi MVP

Layout-based presentation generator with a Next.js frontend and a FastAPI backend. Gemini 2.5 Flash plans the deck as structured JSON, Gemini 2.5 Flash Image generates slide images, and the backend owns rendering, styling, slide dimensions, and PDF generation.

## Stack

- Frontend: Next.js + Tailwind CSS
- Backend: FastAPI
- AI planning: Gemini 2.5 Flash
- AI images: Gemini 2.5 Flash Image
- Templates: Jinja2
- PDF export: WeasyPrint

## Project Structure

```text
backend/
frontend/
```

## Backend Setup

1. Create a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

3. Copy the environment file and add your Gemini API key:

```bash
cp .env.example .env
```

4. Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Backend endpoints:

- `POST /presentations/generate`
- `GET /health`
- `GET /generated/<file>.pdf`
- `GET /generated/gemini_images/<file>.png`

## Frontend Setup

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Optionally configure the backend URL:

```bash
cp .env.local.example .env.local
```

3. Start the frontend:

```bash
npm run dev
```

The frontend runs on `http://localhost:3000` by default and targets `http://localhost:8000`.

## Gemini Pipeline

- `gemini-2.5-flash` generates structured presentation JSON.
- The backend validates that JSON with Pydantic and normalizes it into the internal slide layouts.
- Slides that need images are sent to `gemini-2.5-flash-image`.
- Generated images are cached in `backend/generated/gemini_images/`.
- The cache key is based on slide content and image prompt, so images are reused unless the slide changes.
- The final PDF is exported from the validated JSON and any generated images.

## Notes

- PDFs are stored locally in `backend/generated/`.
- Generated images are stored locally in `backend/generated/gemini_images/`.
- The schema is built to support future features like saved presentations, async jobs, editor workflows, and richer asset processing.
