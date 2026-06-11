# Роля на модула: Мрежовата граница за сваляне на image assets.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
import re
import uuid

import httpx
from PIL import Image

from app.image_research.config import TEMP_DIR, get_unsplash_access_key


class DownloadError(Exception):
    # Роля на класа: Този custom exception маркира конкретен тип pipeline отказ, за да може горният слой да го преведе към правилен HTTP status или fallback.
    # Отделният exception тип позволява точно `except` правило без parsing на текстово съобщение.
    def __init__(self, message: str, status_code: int | None = None) -> None:
        # Роля в pipeline-а: обработва стъпката `init` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `message` (str), `status_code` (int | None); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `super().__init__`, `super`; така се вижда кои отговорности функцията делегира.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
        super().__init__(message)
        self.status_code = status_code


def _safe_name(value: str) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `safe_name` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.sub`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value)[:80]


async def download_image(image_url: str, prefix: str) -> str:
    # Роля в pipeline-а: материализира отдалечен ресурс като локален файл за следващите offline етапи.
    # Входът идва през `image_url` (str), `prefix` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `TEMP_DIR.mkdir`, `httpx.AsyncClient`, `path.write_bytes`, `_safe_name`; така се вижда кои отговорности функцията делегира.
    # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
    # Изходен договор: `str`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    # `name` пази резултата от `_safe_name`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    name = f"{_safe_name(prefix)}_{uuid.uuid4().hex[:10]}.jpg"
    path = TEMP_DIR / name
    async with httpx.AsyncClient(timeout=40, follow_redirects=True) as client:
        # `resp` пази резултата от `client.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
        resp = await client.get(
            image_url,
            headers={"User-Agent": "AuraSlidesAI/1.0 (https://example.com; contact@auraslidesai.local)"},
        )
        # Това условие е decision point: `resp.status_code >= 400`.
        # При вярно условие се активира `DownloadError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if resp.status_code >= 400:
            raise DownloadError(f"HTTP {resp.status_code}", resp.status_code)
        # Това условие е decision point: `not (resp.headers.get('content-type') or '').lower().startswith('image/')`.
        # При вярно условие се активира `ValueError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if not (resp.headers.get("content-type") or "").lower().startswith("image/"):
            raise ValueError("Downloaded content is not an image")
        path.write_bytes(resp.content)

    # Тук започва контролирана рискова зона: външна услуга, parsing, filesystem или rendering може да се провали.
    # `try/except` превръща техническите грешки (Exception) в предвидимо поведение за горния слой.
    try:
        with Image.open(path) as img:
            img.verify()
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise ValueError("Downloaded image is invalid") from exc
    return str(path)


async def track_remote_download(download_tracking_url: str | None) -> None:
    # Роля в pipeline-а: обработва стъпката `track_remote_download` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `download_tracking_url` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `get_unsplash_access_key`, `httpx.AsyncClient`; така се вижда кои отговорности функцията делегира.
    # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
    # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
    # Това условие е decision point: `not download_tracking_url`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`None`) и прескачаме ненужната останала работа.
    if not download_tracking_url:
        return
    headers = {"User-Agent": "AuraSlidesAI/1.0 (https://example.com; contact@auraslidesai.local)"}
    # `access_key` пази резултата от `get_unsplash_access_key`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    access_key = get_unsplash_access_key()
    # Това условие е decision point: `'api.unsplash.com' in download_tracking_url and access_key`.
    # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
    if "api.unsplash.com" in download_tracking_url and access_key:
        headers["Accept-Version"] = "v1"
        headers["Authorization"] = f"Client-ID {access_key}"
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        await client.get(download_tracking_url, headers=headers)
