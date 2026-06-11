# Роля на модула: Entity image adapter към Wikipedia.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from __future__ import annotations

from urllib.parse import quote

import httpx

from app.image_research.providers.base import BaseImageProvider
from app.image_research.schemas import ImageCandidate

USER_AGENT = "AuraSlidesAI/1.0 (https://example.com; contact@auraslidesai.local)"
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json; charset=utf-8",
}


class WikipediaProvider(BaseImageProvider):
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    async def search(
        self, query: str, per_page: int, orientation: str | None, image_type: str | None = None
    ) -> list[ImageCandidate]:
        # Роля в pipeline-а: изпълнява търсене към provider и връща кандидати, а не окончателно избран asset.
        # Входът идва през `self` (неуточнен тип), `query` (str), `per_page` (int), `orientation` (str | None), `image_type` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `self._title_candidates`, `self._candidate_titles`, `httpx.AsyncClient`, `summary.raise_for_status`; така се вижда кои отговорности функцията делегира.
        # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
        # Изходен договор: `list[ImageCandidate]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        # `titles` пази резултата от `self._title_candidates`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        titles = self._title_candidates(query)
        # `api_titles` пази резултата от `self._candidate_titles`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
        api_titles = await self._candidate_titles(query, per_page=min(per_page, 5))
        # Обхождаме `api_titles` като `title`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for title in api_titles:
            # Това условие е decision point: `title not in titles`.
            # При вярно условие се активира `titles.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
            if title not in titles:
                titles.append(title)

        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=DEFAULT_HEADERS) as client:
            # Обхождаме `titles` като `title`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
            # Цикълът държи обработката еднаква за всеки елемент.
            for title in titles:
                # `summary` пази резултата от `client.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
                # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
                summary = await client.get(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'), safe=':_()/')}"
                )
                # Това условие е decision point: `summary.status_code == 404`.
                # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
                if summary.status_code == 404:
                    continue
                # Това условие е decision point: `summary.status_code == 403`.
                # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
                if summary.status_code == 403:
                    continue
                summary.raise_for_status()
                # `data` пази резултата от `summary.json`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
                data = summary.json()
                # `thumbnail` пази резултата от `data.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
                thumbnail = data.get("originalimage") or data.get("thumbnail") or {}
                # `image_url` държи външна resource референция; тя още не е локален asset и може да изисква download.
                image_url = thumbnail.get("source")
                # `source_url` държи външна resource референция; тя още не е локален asset и може да изисква download.
                source_url = data.get("content_urls", {}).get("desktop", {}).get("page")
                # Това условие е decision point: `not image_url or not source_url`.
                # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
                if not image_url or not source_url:
                    continue
                # `description` пази резултата от `data.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
                description = data.get("description") or data.get("extract")
                return [
                    ImageCandidate(
                        id=f"wikipedia-{data.get('title', title)}",
                        source="wikipedia",
                        title=data.get("title") or title,
                        image_url=image_url,
                        preview_url=(data.get("thumbnail") or {}).get("source") or image_url,
                        source_url=source_url,
                        author="Wikipedia",
                        license_name="CC BY-SA",
                        license_url="https://creativecommons.org/licenses/by-sa/4.0/",
                        width=thumbnail.get("width"),
                        height=thumbnail.get("height"),
                        tags=[description] if description else [],
                        categories=[data.get("type") or ""],
                        page_title=data.get("title") or title,
                    )
                ]
        return []

    def _title_candidates(self, query: str) -> list[str]:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `title_candidates` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `query` (str); имената показват каква част от контекста е собственост на тази стъпка.
        # Функцията работи основно с локални стойности и не делегира към други services.
        # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
        # Изходен договор: `list[str]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        # `clean` пази резултата от `' '.join(query.split()).strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        clean = " ".join(query.split()).strip(" .,:;")
        variants = [clean]
        # Това условие е decision point: `':' in clean`.
        # При вярно условие се активира `variants.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if ":" in clean:
            variants.append(clean.split(":", 1)[0].strip())
        # Това условие е decision point: `' - ' in clean`.
        # При вярно условие се активира `variants.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if " - " in clean:
            variants.append(clean.split(" - ", 1)[0].strip())
        # Това условие е decision point: `',' in clean`.
        # При вярно условие се активира `variants.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if "," in clean:
            variants.append(clean.split(",", 1)[0].strip())
        return [value for index, value in enumerate(variants) if value and value not in variants[:index]]

    async def _candidate_titles(self, query: str, per_page: int) -> list[str]:
        # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `candidate_titles` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
        # Входът идва през `self` (неуточнен тип), `query` (str), `per_page` (int); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `httpx.AsyncClient`, `resp.raise_for_status`, `resp.json`; така се вижда кои отговорности функцията делегира.
        # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
        # Изходен договор: `list[str]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        async with httpx.AsyncClient(timeout=20, headers=DEFAULT_HEADERS) as client:
            # `resp` пази резултата от `client.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
            resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "list": "search",
                    "format": "json",
                    "srsearch": query,
                    "srlimit": min(max(per_page, 1), 5),
                    "srnamespace": 0,
                },
            )
            # Това условие е decision point: `resp.status_code == 403`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`[]`) и прескачаме ненужната останала работа.
            if resp.status_code == 403:
                return []
            resp.raise_for_status()
            # `results` пази резултата от `resp.json().get('query', {}).get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            results = resp.json().get("query", {}).get("search", [])
        return [item.get("title", "") for item in results if item.get("title")]
