# Роля на модула: Entity и encyclopedic image adapter към Wikimedia Commons.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from __future__ import annotations

import html

import httpx

from app.image_research.core.license_checker import canonical_license
from app.image_research.providers.base import BaseImageProvider
from app.image_research.schemas import ImageCandidate

USER_AGENT = "AuraSlidesAI/1.0 (https://example.com; contact@auraslidesai.local)"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json; charset=utf-8",
}


class WikimediaCommonsProvider(BaseImageProvider):
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    async def search(
        self, query: str, per_page: int, orientation: str | None, image_type: str | None = None
    ) -> list[ImageCandidate]:
        # Роля в pipeline-а: изпълнява търсене към provider и връща кандидати, а не окончателно избран asset.
        # Входът идва през `self` (неуточнен тип), `query` (str), `per_page` (int), `orientation` (str | None), `image_type` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `httpx.AsyncClient`, `resp.raise_for_status`, `canonical_license`, `page.get('title', '').replace`; така се вижда кои отговорности функцията делегира.
        # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
        # Изходен договор: `list[ImageCandidate]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": min(max(per_page, 3), 12),
            "prop": "imageinfo|categories",
            "iiprop": "url|size|extmetadata",
            "iiurlwidth": 1600,
            "cllimit": 10,
        }
        async with httpx.AsyncClient(timeout=25, headers=DEFAULT_HEADERS) as client:
            # `resp` пази резултата от `client.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
            resp = await client.get("https://commons.wikimedia.org/w/api.php", params=params)
            # Това условие е decision point: `resp.status_code == 403`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`[]`) и прескачаме ненужната останала работа.
            if resp.status_code == 403:
                return []
            resp.raise_for_status()
            # `pages` пази резултата от `(resp.json().get('query') or {}).get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            pages = (resp.json().get("query") or {}).get("pages") or {}

        # `candidates` е работният списък с image резултати, който pipeline-ът филтрира и подрежда.
        candidates: list[ImageCandidate] = []
        # Обхождаме `pages.items()` като `(page_id, page)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for page_id, page in pages.items():
            # `image_info` пази резултата от `page.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            image_info = (page.get("imageinfo") or [{}])[0]
            # `image_url` държи външна resource референция; тя още не е локален asset и може да изисква download.
            image_url = image_info.get("thumburl") or image_info.get("url")
            # `source_url` държи външна resource референция; тя още не е локален asset и може да изисква download.
            source_url = page.get("canonicalurl") or f"https://commons.wikimedia.org/?curid={page_id}"
            # Това условие е decision point: `not image_url or not source_url`.
            # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
            if not image_url or not source_url:
                continue
            # `original_url` държи външна resource референция; тя още не е локален asset и може да изисква download.
            original_url = image_info.get("url") or ""
            # Това условие е decision point: `not image_info.get('thumburl') and original_url.lower().split('?', 1)[0].endswith(('.ogv'...`.
            # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
            if not image_info.get("thumburl") and original_url.lower().split("?", 1)[0].endswith(
                (".ogv", ".webm", ".mp4", ".mp3", ".ogg", ".wav")
            ):
                continue
            # `metadata` е възможностите и ограниченията на един layout кандидат.
            metadata = image_info.get("extmetadata") or {}
            # `license_name` пази резултата от `canonical_license`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            license_name = canonical_license((metadata.get("LicenseShortName") or {}).get("value"))
            # Това условие е decision point: `license_name is None`.
            # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
            if license_name is None:
                continue
            # `categories` пази резултата от `str(category.get('title', '')).replace`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
            categories = [
                str(category.get("title", "")).replace("Category:", "")
                for category in (page.get("categories") or [])
                if category.get("title")
            ]
            author = html.unescape((metadata.get("Artist") or {}).get("value") or "").strip() or None
            title = page.get("title", "").replace("File:", "")
            candidates.append(
                ImageCandidate(
                    id=f"commons-{page_id}",
                    source="wikimedia_commons",
                    title=title,
                    image_url=image_url,
                    preview_url=image_url,
                    source_url=source_url,
                    author=author,
                    license_name=license_name,
                    license_url=(metadata.get("LicenseUrl") or {}).get("value"),
                    width=image_info.get("width"),
                    height=image_info.get("height"),
                    tags=categories[:6],
                    categories=categories,
                    page_title=page.get("title"),
                )
            )
        return candidates
