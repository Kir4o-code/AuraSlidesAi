# Роля на модула: Избира правилния тип източник според това дали prompt-ът търси named entity или обща визуална сцена.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from __future__ import annotations

import re

from app.image_research.core.search_planner import compact_search_query
from app.image_research.schemas import EntityType, ImageSourceSelection, ResearchImageSource

PERSON_HINTS = {
    "scientist",
    "president",
    "prime minister",
    "politician",
    "athlete",
    "actor",
    "actress",
    "singer",
    "celebrity",
    "philosopher",
    "inventor",
    "mathematician",
    "physicist",
    "biologist",
}
COMPANY_HINTS = {
    "inc",
    "corp",
    "corporation",
    "company",
    "ltd",
    "llc",
    "plc",
    "ag",
    "group",
    "holdings",
}
ORGANIZATION_HINTS = {
    "university",
    "foundation",
    "association",
    "agency",
    "committee",
    "institute",
    "laboratory",
    "museum",
    "bank",
    "ngo",
    "council",
    "commission",
    "organization",
}
PLACE_HINTS = {
    "tower",
    "bridge",
    "mount",
    "mountain",
    "river",
    "city",
    "country",
    "palace",
    "cathedral",
    "temple",
    "castle",
    "monument",
    "landmark",
    "island",
}
EVENT_HINTS = {
    "war",
    "revolution",
    "battle",
    "election",
    "conference",
    "olympics",
    "cup",
    "festival",
    "summit",
    "crisis",
    "earthquake",
    "pandemic",
}
PRODUCT_HINTS = {
    "iphone",
    "ipad",
    "macbook",
    "tesla model",
    "playstation",
    "xbox",
    "chatgpt",
    "gemini",
    "drug",
    "vaccine",
    "platform",
    "software",
    "app",
    "device",
    "model",
}
CONCEPT_HINTS = {
    "machine learning",
    "cloud computing",
    "finance",
    "marketing",
    "teamwork",
    "education",
    "nature",
    "strategy",
    "leadership",
    "innovation",
    "healthcare",
    "artificial intelligence",
    "technology",
}
SCIENTIFIC_STRUCTURE_HINTS = {
    "dna",
    "rna",
    "double helix",
    "base pair",
    "base pairs",
    "nucleotide",
    "nucleotides",
    "ribosome",
    "ribosomal",
    "rrna",
    "adenine",
    "thymine",
    "guanine",
    "cytosine",
    "molecular structure",
    "cell structure",
}

BULGARIAN_PERSON_HINTS = {
    "учен",
    "политик",
    "президент",
    "министър",
    "певец",
    "актьор",
    "математик",
    "физик",
    "биолог",
}
BULGARIAN_COMPANY_HINTS = {
    "компания",
    "корпорация",
    "група",
    "холдинг",
}
BULGARIAN_ORGANIZATION_HINTS = {
    "университет",
    "фондация",
    "асоциация",
    "агенция",
    "институт",
    "музей",
    "банка",
    "организация",
}
BULGARIAN_PLACE_HINTS = {
    "град",
    "държава",
    "кула",
    "мост",
    "река",
    "планина",
    "замък",
    "паметник",
    "остров",
}
BULGARIAN_EVENT_HINTS = {
    "война",
    "революция",
    "битка",
    "избори",
    "конференция",
    "фестивал",
    "криза",
    "пандемия",
}
BULGARIAN_CONCEPT_HINTS = {
    "машинно обучение",
    "облачни изчисления",
    "финанси",
    "маркетинг",
    "образование",
    "природа",
    "технологии",
    "изкуствен интелект",
}
BULGARIAN_SCIENTIFIC_STRUCTURE_HINTS = {
    "днк",
    "рнк",
    "двойна спирала",
    "базови двойки",
    "нуклеотид",
    "рибозома",
    "рибозомна",
    "аденин",
    "тимин",
    "гуанин",
    "цитозин",
    "молекулна структура",
}

GENERIC_ENTITY_WORDS = {
    "the",
    "and",
    "life",
    "legacy",
    "rise",
    "fall",
    "regime",
    "history",
    "years",
    "power",
    "early",
    "period",
    "policy",
    "economy",
    "foreign",
    "politics",
    "на",
    "и",
    "животът",
    "живот",
    "наследството",
    "ранни",
    "години",
    "възход",
    "властта",
    "режима",
    "залезът",
    "икономиката",
    "политика",
    "историята",
    "период",
    "външна",
}


def _token_text(value: str) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `token_text` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Функцията работи основно с локални стойности и не делегира към други services.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    return " ".join(value.split()).strip()


def _named_entity_candidates(text: str) -> list[str]:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `named_entity_candidates` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `text` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.compile`, `pattern.findall`, `lowered_tokens.issubset`, `re.findall`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `list[str]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `pattern` пази резултата от `re.compile`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    pattern = re.compile(
        r"[A-ZА-ЯЁ][a-zа-яё]+(?:[-'][A-ZА-ЯЁ]?[a-zа-яё]+)?(?:\s+[A-ZА-ЯЁ0-9][a-zа-яё0-9]+(?:[-'][A-ZА-ЯЁ]?[a-zа-яё]+)?){1,3}",
        flags=re.UNICODE,
    )
    # `candidates` е работният списък с image резултати, който pipeline-ът филтрира и подрежда.
    candidates: list[str] = []
    # Обхождаме `pattern.findall(text)` като `match`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for match in pattern.findall(text):
        # `candidate` е един възможен image резултат, който още не е минал всички проверки и scoring.
        candidate = " ".join(match.split()).strip(" .,:;|")
        # Това условие е decision point: `not candidate`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if not candidate:
            continue
        # `lowered_tokens` пази резултата от `token.lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
        lowered_tokens = {token.lower() for token in re.findall(r"[^\W\d_]+", candidate, flags=re.UNICODE)}
        # Това условие е decision point: `lowered_tokens and lowered_tokens.issubset(GENERIC_ENTITY_WORDS)`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if lowered_tokens and lowered_tokens.issubset(GENERIC_ENTITY_WORDS):
            continue
        # Това условие е decision point: `candidate not in candidates`.
        # При вярно условие се активира `candidates.append`; така този branch избира конкретна стратегия, а не просто проверява стойност.
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _entity_query(value: str) -> str:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `entity_query` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_token_text`, `re.search`, `_named_entity_candidates`, `re.findall`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `text` е нормализирано работно копие на текста; оригиналът остава непокътнат, а проверките стават върху предвидим формат.
    text = _token_text(value)
    # `match` пази резултата от `re.search`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    match = re.search(r"['\"]([^'\"]+)['\"]", text)
    # Това условие е decision point: `match`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`match.group(1).strip()`) и прескачаме ненужната останала работа.
    if match:
        return match.group(1).strip()

    # `candidates` е работният списък с image резултати, който pipeline-ът филтрира и подрежда.
    candidates = _named_entity_candidates(text)
    # Това условие е decision point: `candidates`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`ranked[0]`) и прескачаме ненужната останала работа.
    if candidates:
        # `ranked` е кандидатите след оценяване, подредени така, че най-подходящият да бъде първи.
        ranked = sorted(
            candidates,
            key=lambda candidate: (
                -sum(
                    1
                    for token in re.findall(r"[^\W\d_]+", candidate, flags=re.UNICODE)
                    if token.lower() not in GENERIC_ENTITY_WORDS
                ),
                len(candidate),
            ),
        )
        return ranked[0]

    # `prefix` пази резултата от `re.split('\\s*[|:,-]\\s*|\\.\\s', text, maxsplit=1)[0].strip`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    prefix = re.split(r"\s*[|:,-]\s*|\.\s", text, maxsplit=1)[0].strip()
    # Това условие е decision point: `2 <= len(prefix.split()) <= 6`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`prefix`) и прескачаме ненужната останала работа.
    if 2 <= len(prefix.split()) <= 6:
        return prefix

    # `title_case` пази резултата от `re.findall`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    title_case = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z0-9.&'-]+){0,4}\b", text)
    # Това условие е decision point: `title_case`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`max(title_case, key=len).strip()`) и прескачаме ненужната останала работа.
    if title_case:
        return max(title_case, key=len).strip()

    return compact_search_query(text, max_length=60)


def _has_any(text: str, hints: set[str]) -> bool:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `has_any` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `text` (str), `hints` (set[str]); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.search`, `re.escape`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bool`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # Обхождаме `hints` като `hint`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for hint in hints:
        # Това условие е decision point: `' ' in hint`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if " " in hint:
            # Това условие е decision point: `hint in text`.
            # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `True`, без да проверява по-слабите правила отдолу.
            if hint in text:
                return True
            continue
        # Това условие е decision point: `re.search(f'\\b{re.escape(hint)}\\b', text)`.
        # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `True`, без да проверява по-слабите правила отдолу.
        if re.search(rf"\b{re.escape(hint)}\b", text):
            return True
    return False


def _title_case_count(value: str) -> int:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `title_case_count` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.findall`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `int`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    return len(re.findall(r"\b[A-Z][a-z0-9.&'-]+\b", value))


def _capitalized_token_count(value: str) -> int:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `capitalized_token_count` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.findall`, `first.isalpha`, `first.upper`, `char.islower`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `int`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    count = 0
    # Обхождаме `re.findall("[^\\W\\d_]+(?:[-'][^\\W\\d_]+)?", value, flags=re.UNICODE)` като `token`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for token in re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)?", value, flags=re.UNICODE):
        # Това условие е decision point: `not token`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if not token:
            continue
        first = token[0]
        rest = token[1:]
        # Това условие е decision point: `first.isalpha() and first == first.upper() and (not rest or any((char.islower() for char...`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if (
            first.isalpha()
            and first == first.upper()
            and (not rest or any(char.islower() for char in rest if char.isalpha()))
        ):
            count += 1
    return count


def _looks_like_named_entity(value: str) -> bool:
    # Роля в pipeline-а: Това е вътрешна помощна стъпка: обработва стъпката `looks_like_named_entity` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `value` (str); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.findall`, `first.isalpha`, `first.isupper`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bool`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `tokens` е theme настройките, които държат визуалното решение последователно между layouts и exporters.
    # Comprehension синтаксисът комбинира обхождане и филтриране в една стойност; резултатът съдържа само елементите, минали условието.
    tokens = [token for token in re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)?", value, flags=re.UNICODE) if token]
    # Това условие е decision point: `not 2 <= len(tokens) <= 4`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `False`, без да проверява по-слабите правила отдолу.
    if not 2 <= len(tokens) <= 4:
        return False
    upper_leading = 0
    # Обхождаме `tokens` като `token`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for token in tokens:
        first = token[0]
        # Това условие е decision point: `first.isalpha() and first.isupper()`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if first.isalpha() and first.isupper():
            upper_leading += 1
    return upper_leading >= max(2, len(tokens) - 1)


def select_image_source_with_reason(prompt: str, secondary_text: str | None = None) -> tuple[ImageSourceSelection, str]:
    # Роля в pipeline-а: Решава дали prompt-ът описва named entity или обща сцена и избира encyclopedic или stock provider път.
    # Входът идва през `prompt` (str), `secondary_text` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `_token_text`, `_entity_query`, `_has_any`, `compact_search_query`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `tuple[ImageSourceSelection, str]`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # `original` пази резултата от `_token_text`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    original = _token_text(" ".join(part for part in [prompt, secondary_text or ""] if part))
    # `primary_lowered` пази резултата от `_token_text(prompt).lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    primary_lowered = _token_text(prompt).lower()
    # `lowered` пази резултата от `original.lower`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    lowered = original.lower()
    # `query` пази резултата от `_entity_query`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    query = _entity_query(prompt)
    # `title_case_words` пази резултата от `_title_case_count`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    title_case_words = max(_title_case_count(prompt), _capitalized_token_count(query))
    concept_hints = CONCEPT_HINTS | BULGARIAN_CONCEPT_HINTS
    person_hints = PERSON_HINTS | BULGARIAN_PERSON_HINTS
    company_hints = COMPANY_HINTS | BULGARIAN_COMPANY_HINTS
    organization_hints = ORGANIZATION_HINTS | BULGARIAN_ORGANIZATION_HINTS
    place_hints = PLACE_HINTS | BULGARIAN_PLACE_HINTS
    event_hints = EVENT_HINTS | BULGARIAN_EVENT_HINTS
    scientific_structure_hints = SCIENTIFIC_STRUCTURE_HINTS | BULGARIAN_SCIENTIFIC_STRUCTURE_HINTS

    # Това условие е decision point: `_has_any(lowered, scientific_structure_hints)`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`(ImageSourceSelection(entity_type=EntityType.PRODUCT, image_source=ResearchImageSource.WI...`) и прескачаме ненужната останала работа.
    if _has_any(lowered, scientific_structure_hints):
        primary_mentions_rna = "rna" in primary_lowered or "рнк" in primary_lowered
        primary_mentions_dna = "dna" in primary_lowered or "днк" in primary_lowered
        if primary_mentions_rna or (("rna" in lowered or "рнк" in lowered) and not primary_mentions_dna):
            if any(
                term in primary_lowered
                for term in (
                    "vaccine",
                    "therapeutic",
                    "therapy",
                    "crispr",
                    "guide",
                    "transfer",
                    "ribosome",
                    "ribosomal",
                    "transcription",
                    "microrna",
                    "mirna",
                    "sirna",
                    "polymerase",
                )
            ):
                # `query` пази резултата от `compact_search_query`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
                query = compact_search_query(prompt, max_length=60)
            else:
                query = "RNA molecule" if "molecule" in lowered or "молекул" in lowered else "RNA"
        elif primary_mentions_dna or "dna" in lowered or "днк" in lowered:
            if any(
                term in primary_lowered
                for term in (
                    "base pair",
                    "base pairs",
                    "adenine",
                    "thymine",
                    "guanine",
                    "cytosine",
                    "базови",
                    "аденин",
                    "тимин",
                    "гуанин",
                    "цитозин",
                )
            ):
                query = "DNA base pairs"
            elif "helix" in primary_lowered or "спирала" in primary_lowered:
                query = "DNA double helix"
            else:
                query = "DNA"
        else:
            # `query` пази резултата от `compact_search_query`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
            query = compact_search_query(original or prompt, max_length=60)
        return ImageSourceSelection(
            entity_type=EntityType.PRODUCT,
            image_source=ResearchImageSource.WIKIPEDIA,
            search_query=query,
            confidence=0.86,
        ), "matched scientific structure; using encyclopedia media first"

    # Това условие е decision point: `_has_any(lowered, concept_hints)`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`(ImageSourceSelection(entity_type=EntityType.CONCEPT, image_source=ResearchImageSource.ST...`) и прескачаме ненужната останала работа.
    if _has_any(lowered, concept_hints):
        return ImageSourceSelection(
            entity_type=EntityType.CONCEPT,
            image_source=ResearchImageSource.STOCK,
            search_query=compact_search_query(original or prompt, max_length=60),
            confidence=0.92,
        ), "matched concept hints"

    # Това условие е decision point: `_has_any(lowered, person_hints) or ((_looks_like_named_entity(query) or title_case_words...`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`(ImageSourceSelection(entity_type=EntityType.PERSON, image_source=ResearchImageSource.WIK...`) и прескачаме ненужната останала работа.
    if _has_any(lowered, person_hints) or (
        (_looks_like_named_entity(query) or title_case_words >= 2)
        and len(query.split()) <= 4
        and not _has_any(lowered, company_hints | organization_hints | place_hints | event_hints)
    ):
        # `confidence` пази резултата от `_has_any`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        confidence = 0.86 if _has_any(lowered, person_hints) else 0.72
        # `reason` пази резултата от `_has_any`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
        reason = (
            "matched person hints"
            if _has_any(lowered, person_hints)
            else "short capitalized entity name without competing hints"
        )
        return ImageSourceSelection(
            entity_type=EntityType.PERSON,
            image_source=ResearchImageSource.WIKIPEDIA,
            search_query=query,
            confidence=confidence,
        ), reason

    # Това условие е decision point: `_has_any(lowered, company_hints)`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`(ImageSourceSelection(entity_type=EntityType.COMPANY, image_source=ResearchImageSource.WI...`) и прескачаме ненужната останала работа.
    if _has_any(lowered, company_hints):
        return ImageSourceSelection(
            entity_type=EntityType.COMPANY,
            image_source=ResearchImageSource.WIKIPEDIA,
            search_query=query,
            confidence=0.88,
        ), "matched company hints"

    # Това условие е decision point: `_has_any(lowered, organization_hints)`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`(ImageSourceSelection(entity_type=EntityType.ORGANIZATION, image_source=ResearchImageSour...`) и прескачаме ненужната останала работа.
    if _has_any(lowered, organization_hints):
        return ImageSourceSelection(
            entity_type=EntityType.ORGANIZATION,
            image_source=ResearchImageSource.WIKIPEDIA,
            search_query=query,
            confidence=0.84,
        ), "matched organization hints"

    # Това условие е decision point: `_has_any(lowered, place_hints)`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`(ImageSourceSelection(entity_type=EntityType.PLACE, image_source=ResearchImageSource.WIKI...`) и прескачаме ненужната останала работа.
    if _has_any(lowered, place_hints):
        return ImageSourceSelection(
            entity_type=EntityType.PLACE,
            image_source=ResearchImageSource.WIKIPEDIA,
            search_query=query,
            confidence=0.84,
        ), "matched place hints"

    # Това условие е decision point: `_has_any(lowered, event_hints)`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`(ImageSourceSelection(entity_type=EntityType.EVENT, image_source=ResearchImageSource.WIKI...`) и прескачаме ненужната останала работа.
    if _has_any(lowered, event_hints):
        return ImageSourceSelection(
            entity_type=EntityType.EVENT,
            image_source=ResearchImageSource.WIKIPEDIA,
            search_query=query,
            confidence=0.84,
        ), "matched event hints"

    if _has_any(lowered, PRODUCT_HINTS):
        return ImageSourceSelection(
            entity_type=EntityType.PRODUCT,
            image_source=ResearchImageSource.WIKIPEDIA,
            search_query=query,
            confidence=0.76,
        ), "matched product hints"

    # `concept_query` пази резултата от `compact_search_query`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    concept_query = compact_search_query(original or prompt, max_length=60)
    return ImageSourceSelection(
        entity_type=EntityType.CONCEPT,
        image_source=ResearchImageSource.STOCK,
        search_query=concept_query,
        confidence=0.68,
    ), "fell back to generic concept search"
