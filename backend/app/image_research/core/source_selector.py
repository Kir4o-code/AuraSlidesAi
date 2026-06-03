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
    return " ".join(value.split()).strip()


def _named_entity_candidates(text: str) -> list[str]:
    pattern = re.compile(
        r"[A-ZА-ЯЁ][a-zа-яё]+(?:[-'][A-ZА-ЯЁ]?[a-zа-яё]+)?(?:\s+[A-ZА-ЯЁ0-9][a-zа-яё0-9]+(?:[-'][A-ZА-ЯЁ]?[a-zа-яё]+)?){1,3}",
        flags=re.UNICODE,
    )
    candidates: list[str] = []
    for match in pattern.findall(text):
        candidate = " ".join(match.split()).strip(" .,:;|")
        if not candidate:
            continue
        lowered_tokens = {token.lower() for token in re.findall(r"[^\W\d_]+", candidate, flags=re.UNICODE)}
        if lowered_tokens and lowered_tokens.issubset(GENERIC_ENTITY_WORDS):
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _entity_query(value: str) -> str:
    text = _token_text(value)
    match = re.search(r"['\"]([^'\"]+)['\"]", text)
    if match:
        return match.group(1).strip()

    candidates = _named_entity_candidates(text)
    if candidates:
        ranked = sorted(
            candidates,
            key=lambda candidate: (
                -sum(1 for token in re.findall(r"[^\W\d_]+", candidate, flags=re.UNICODE) if token.lower() not in GENERIC_ENTITY_WORDS),
                len(candidate),
            ),
        )
        return ranked[0]

    prefix = re.split(r"\s*[|:,-]\s*|\.\s", text, maxsplit=1)[0].strip()
    if 2 <= len(prefix.split()) <= 6:
        return prefix

    title_case = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z0-9.&'-]+){0,4}\b", text)
    if title_case:
        return max(title_case, key=len).strip()

    return compact_search_query(text, max_length=60)


def _has_any(text: str, hints: set[str]) -> bool:
    for hint in hints:
        if " " in hint:
            if hint in text:
                return True
            continue
        if re.search(rf"\b{re.escape(hint)}\b", text):
            return True
    return False


def _title_case_count(value: str) -> int:
    return len(re.findall(r"\b[A-Z][a-z0-9.&'-]+\b", value))


def _capitalized_token_count(value: str) -> int:
    count = 0
    for token in re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)?", value, flags=re.UNICODE):
        if not token:
            continue
        first = token[0]
        rest = token[1:]
        if first.isalpha() and first == first.upper() and (not rest or any(char.islower() for char in rest if char.isalpha())):
            count += 1
    return count


def _looks_like_named_entity(value: str) -> bool:
    tokens = [token for token in re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)?", value, flags=re.UNICODE) if token]
    if not 2 <= len(tokens) <= 4:
        return False
    upper_leading = 0
    for token in tokens:
        first = token[0]
        if first.isalpha() and first.isupper():
            upper_leading += 1
    return upper_leading >= max(2, len(tokens) - 1)


def select_image_source_with_reason(prompt: str, secondary_text: str | None = None) -> tuple[ImageSourceSelection, str]:
    original = _token_text(" ".join(part for part in [prompt, secondary_text or ""] if part))
    lowered = original.lower()
    query = _entity_query(prompt)
    title_case_words = max(_title_case_count(prompt), _capitalized_token_count(query))
    concept_hints = CONCEPT_HINTS | BULGARIAN_CONCEPT_HINTS
    person_hints = PERSON_HINTS | BULGARIAN_PERSON_HINTS
    company_hints = COMPANY_HINTS | BULGARIAN_COMPANY_HINTS
    organization_hints = ORGANIZATION_HINTS | BULGARIAN_ORGANIZATION_HINTS
    place_hints = PLACE_HINTS | BULGARIAN_PLACE_HINTS
    event_hints = EVENT_HINTS | BULGARIAN_EVENT_HINTS

    if _has_any(lowered, concept_hints):
        return ImageSourceSelection(
            entity_type=EntityType.CONCEPT,
            image_source=ResearchImageSource.STOCK,
            search_query=compact_search_query(original or prompt, max_length=60),
            confidence=0.92,
        ), "matched concept hints"

    if _has_any(lowered, person_hints) or ((_looks_like_named_entity(query) or title_case_words >= 2) and len(query.split()) <= 4 and not _has_any(lowered, company_hints | organization_hints | place_hints | event_hints)):
        confidence = 0.86 if _has_any(lowered, person_hints) else 0.72
        reason = "matched person hints" if _has_any(lowered, person_hints) else "short capitalized entity name without competing hints"
        return ImageSourceSelection(entity_type=EntityType.PERSON, image_source=ResearchImageSource.WIKIPEDIA, search_query=query, confidence=confidence), reason

    if _has_any(lowered, company_hints):
        return ImageSourceSelection(entity_type=EntityType.COMPANY, image_source=ResearchImageSource.WIKIPEDIA, search_query=query, confidence=0.88), "matched company hints"

    if _has_any(lowered, organization_hints):
        return ImageSourceSelection(entity_type=EntityType.ORGANIZATION, image_source=ResearchImageSource.WIKIPEDIA, search_query=query, confidence=0.84), "matched organization hints"

    if _has_any(lowered, place_hints):
        return ImageSourceSelection(entity_type=EntityType.PLACE, image_source=ResearchImageSource.WIKIPEDIA, search_query=query, confidence=0.84), "matched place hints"

    if _has_any(lowered, event_hints):
        return ImageSourceSelection(entity_type=EntityType.EVENT, image_source=ResearchImageSource.WIKIPEDIA, search_query=query, confidence=0.84), "matched event hints"

    if _has_any(lowered, PRODUCT_HINTS):
        return ImageSourceSelection(entity_type=EntityType.PRODUCT, image_source=ResearchImageSource.WIKIPEDIA, search_query=query, confidence=0.76), "matched product hints"

    concept_query = compact_search_query(original or prompt, max_length=60)
    return ImageSourceSelection(
        entity_type=EntityType.CONCEPT,
        image_source=ResearchImageSource.STOCK,
        search_query=concept_query,
        confidence=0.68,
    ), "fell back to generic concept search"


def select_image_source(prompt: str, secondary_text: str | None = None) -> ImageSourceSelection:
    selection, _ = select_image_source_with_reason(prompt, secondary_text)
    return selection
