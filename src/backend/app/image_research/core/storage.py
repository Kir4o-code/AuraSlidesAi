# Роля на модула: Файловата граница на research pipeline-а.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
import json
import re
import shutil
from pathlib import Path

from app.image_research.config import IMAGES_DIR, METADATA_DIR, TEMP_DIR


def slugify(value: str, fallback: str = "image_query") -> str:
    # Роля в pipeline-а: обработва стъпката `slugify` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str), `fallback` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.sub`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `slug` е четимата част на файловия идентификатор, получена от заглавието след нормализация.
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return (slug[:70] or fallback).strip("_")


def ensure_output_dirs(prompt_slug: str | None = None) -> None:
    # Роля в pipeline-а: обработва стъпката `ensure_output_dirs` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `prompt_slug` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `IMAGES_DIR.mkdir`, `TEMP_DIR.mkdir`, `METADATA_DIR.mkdir`, `(IMAGES_DIR / prompt_slug).mkdir`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: функцията не връща нов обект; ефектът ѝ е промяна на подадено състояние, файл или външна услуга.
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    # Това условие е decision point: `prompt_slug`.
    # При вярно условие се активира `(IMAGES_DIR / prompt_slug).mkdir`; така този branch избира конкретна стратегия, а не просто проверява стойност.
    if prompt_slug:
        (IMAGES_DIR / prompt_slug).mkdir(parents=True, exist_ok=True)
        (TEMP_DIR / prompt_slug).mkdir(parents=True, exist_ok=True)
        (METADATA_DIR / prompt_slug).mkdir(parents=True, exist_ok=True)


def save_metadata(request_id: str, data: dict, prompt_slug: str | None = None) -> Path:
    # Роля в pipeline-а: записва резултат от pipeline-а и връща стабилна референция към него.
    # Входът идва през `request_id` (str), `data` (dict), `prompt_slug` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `ensure_output_dirs`, `path.write_text`, `json.dumps`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `Path`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    ensure_output_dirs(prompt_slug)
    base = METADATA_DIR / prompt_slug if prompt_slug else METADATA_DIR
    path = base / f"{request_id}_metadata.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def copy_ranked_image(temp_path: str, request_id: str, rank: int, prompt_slug: str | None = None) -> Path:
    # Роля в pipeline-а: прави контролирано копие, за да запази оригиналния ресурс и очакваната файлова структура.
    # Входът идва през `temp_path` (str), `request_id` (str), `rank` (int), `prompt_slug` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `ensure_output_dirs`, `shutil.copyfile`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `Path`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    ensure_output_dirs(prompt_slug)
    base = IMAGES_DIR / prompt_slug if prompt_slug else IMAGES_DIR
    dest = base / f"{request_id}_{rank:02d}.jpg"
    shutil.copyfile(temp_path, dest)
    return dest
