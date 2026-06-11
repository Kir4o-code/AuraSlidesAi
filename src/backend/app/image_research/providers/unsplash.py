# Роля на модула: Stock photo adapter към Unsplash.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.image_research.config import get_unsplash_access_key
from app.image_research.providers.base import BaseImageProvider
from app.image_research.schemas import ImageCandidate

logger = logging.getLogger(__name__)


def _with_resize_params(url: str, orientation: str | None) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `with_resize_params` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `url` (str), `orientation` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `urlparse`, `urlunparse`, `parse_qsl`, `parsed._replace`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `parsed` пази резултата от `urlparse`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    parsed = urlparse(url)
    # `query` пази резултата от `parse_qsl`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["fm"] = "jpg"
    query["q"] = "80"
    # Това условие е decision point: `orientation == 'portrait'`.
    # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
    if orientation == "portrait":
        query["h"] = "1400"
    else:
        query["w"] = "1600"
    return urlunparse(parsed._replace(query=urlencode(query)))


def _with_referral(url: str) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `with_referral` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `url` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `urlparse`, `urlunparse`, `parse_qsl`, `parsed._replace`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `parsed` пази резултата от `urlparse`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    parsed = urlparse(url)
    # `query` пази резултата от `parse_qsl`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["utm_source"] = "AuraSlidesAI"
    query["utm_medium"] = "referral"
    return urlunparse(parsed._replace(query=urlencode(query)))


class UnsplashProvider(BaseImageProvider):
    # Роля на класа: Класът групира общо състояние и операции, които принадлежат на една pipeline отговорност.
    # Методите получават `self`, затова могат да споделят конфигурация и кеширани ресурси без глобални променливи.
    async def search(
        self, query: str, per_page: int, orientation: str | None, image_type: str | None = None
    ) -> list[ImageCandidate]:
        # Роля в pipeline-а: изпълнява търсене към provider и връща кандидати, а не окончателно избран asset.
        # Входът идва през `self` (неуточнен тип), `query` (str), `per_page` (int), `orientation` (str | None), `image_type` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
        # Основните преходи навън са към `get_unsplash_access_key`, `RuntimeError`, `httpx.AsyncClient`, `resp.raise_for_status`; така се вижда кои отговорности функцията делегира.
        # `async def` позволява функцията да използва `await`: при мрежово чакане event loop-ът може да обслужва други заявки вместо thread-ът да стои блокиран.
        # Изходен договор: `list[ImageCandidate]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
        # `access_key` пази резултата от `get_unsplash_access_key`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        access_key = get_unsplash_access_key()
        # Това условие е decision point: `not access_key`.
        # При вярно условие се активира `RuntimeError`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if not access_key:
            raise RuntimeError("UNSPLASH_ACCESS_KEY is not configured.")

        params = {
            "query": query,
            "page": 1,
            "per_page": min(max(per_page, 5), 30),
            "order_by": "relevant",
            "content_filter": "high",
        }
        # `orientation_value` пази резултата от `{'square': 'squarish'}.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        orientation_value = {"square": "squarish"}.get(orientation or "", orientation)
        # Това условие е decision point: `orientation_value in {'landscape', 'portrait', 'squarish'}`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if orientation_value in {"landscape", "portrait", "squarish"}:
            params["orientation"] = orientation_value

        headers = {
            "Accept-Version": "v1",
            "Authorization": f"Client-ID {access_key}",
            "User-Agent": "AuraSlidesAI/1.0",
        }
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            # `resp` пази резултата от `client.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            # `await` спира само тази coroutine до готов резултат; останалите FastAPI задачи могат да продължат.
            resp = await client.get("https://api.unsplash.com/search/photos", params=params, headers=headers)
            # Това условие е decision point: `resp.status_code in {401, 403, 429}`.
            # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`[]`) и прескачаме ненужната останала работа.
            if resp.status_code in {401, 403, 429}:
                body = resp.text.strip()
                logger.warning(
                    "Unsplash search rejected. status=%s query=%r remaining=%s limit=%s body=%s",
                    resp.status_code,
                    query,
                    resp.headers.get("X-Ratelimit-Remaining"),
                    resp.headers.get("X-Ratelimit-Limit"),
                    body[:600],
                )
                return []
            resp.raise_for_status()
            # `data` пази резултата от `resp.json`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            data = resp.json()

        out: list[ImageCandidate] = []
        # Обхождаме `data.get('results', [])` като `item`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
        # Цикълът държи обработката еднаква за всеки елемент.
        for item in data.get("results", []):
            # `urls` пази резултата от `item.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            urls = item.get("urls") or {}
            # `links` пази резултата от `item.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            links = item.get("links") or {}
            # `user` пази резултата от `item.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            user = item.get("user") or {}
            # `image_url` държи външна resource референция; тя още не е локален asset и може да изисква download.
            image_url = urls.get("raw") or urls.get("full") or urls.get("regular")
            # `source_url` държи външна resource референция; тя още не е локален asset и може да изисква download.
            source_url = links.get("html")
            # Това условие е decision point: `not image_url or not source_url`.
            # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
            if not image_url or not source_url:
                continue

            # `tags` пази резултата от `tag.get`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
            tags = [tag.get("title", "") for tag in item.get("tags", []) if isinstance(tag, dict) and tag.get("title")]
            page_title = item.get("description") or item.get("alt_description") or item.get("slug")
            author_name = user.get("name") or user.get("username")

            out.append(
                ImageCandidate(
                    id=f"unsplash-{item.get('id')}",
                    source="unsplash",
                    title=page_title,
                    image_url=_with_resize_params(image_url, orientation),
                    preview_url=urls.get("small") or urls.get("thumb") or urls.get("regular"),
                    source_url=_with_referral(source_url),
                    author=author_name,
                    license_name="Unsplash License",
                    license_url="https://unsplash.com/license",
                    download_tracking_url=links.get("download_location"),
                    width=item.get("width"),
                    height=item.get("height"),
                    tags=tags,
                    categories=[item.get("color") or ""],
                    page_title=page_title,
                )
            )
        return out
