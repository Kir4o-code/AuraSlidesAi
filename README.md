# AuraSlides AI

AuraSlides AI е приложение за генериране на презентации. FastAPI backend-ът
използва Gemini за създаване на структурирано съдържание и изображения, а
Next.js frontend-ът визуализира слайдовете и позволява export към PPTX и PDF.

## Структура

```text
src/
  backend/       # FastAPI приложение и генерирани файлове
  frontend/      # Next.js приложение
tests/           # Python unit tests с pytest
pyproject.toml   # pytest конфигурация
requirements.txt
requirements-dev.txt
.gitignore
README.md
```

## Изисквания

- Python 3.11 - 3.13 (препоръчително Python 3.12)
- Node.js 20+
- npm
- Gemini API ключ

## Инсталация

Създайте и активирайте Python virtual environment от корена на проекта:

```bash
py -3.12 -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

Инсталирайте frontend библиотеките:

```bash
cd src/frontend
npm install
cd ../..
```

Създайте `src/backend/.env` и добавете необходимите настройки, включително:

```dotenv
GEMINI_API_KEY=your_api_key
```

По желание копирайте `src/frontend/.env.local.example` като
`src/frontend/.env.local`, за да зададете различен backend URL.

## Стартиране

Backend:

```bash
cd src/backend
uvicorn app.main:app --reload --port 8000
```

Frontend, в отделен terminal:

```bash
cd src/frontend
npm run dev
```

Frontend-ът е достъпен на `http://localhost:3000`, а API-то на
`http://localhost:8000`. Основните API endpoints са:

- `GET /health`
- `POST /presentations/generate`
- `GET /generated/<file>`

Генерираните изображения, PPTX и PDF файлове се пазят в
`src/backend/generated/`.

## Тестове

От корена на проекта:

```bash
pytest
```

Тестове с coverage отчет:

```bash
pytest --cov=app --cov-report=term-missing
```

Статична проверка и форматиране на Python кода:

```bash
ruff check src/backend/app tests
ruff format --check src/backend/app tests
```

Frontend проверка:

```bash
cd src/frontend
npm run build
```
