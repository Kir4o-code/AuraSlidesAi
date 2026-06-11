# Роля на модула: Малък semantic classifier, който свързва текстов смисъл с икона.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
from __future__ import annotations

import re

ICON_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("person", ("character", "person", "people", "leader", "hero", "villain", "cast", "team", "audience")),
    ("star", ("favorite", "standout", "best", "special", "strength", "highlight", "award")),
    ("book", ("lore", "story", "history", "learn", "research", "rule", "knowledge", "world")),
    ("map", ("place", "location", "town", "world", "journey", "route", "where", "geography")),
    ("clock", ("time", "timeline", "phase", "when", "before", "after", "night", "schedule")),
    ("eye", ("mystery", "clue", "discover", "understand", "watch", "attention", "hidden", "unknown")),
    ("shield", ("protect", "security", "survival", "safe", "risk", "defense", "guard")),
    ("home", ("home", "community", "town", "residents", "local", "school")),
    ("search", ("explore", "investigate", "question", "find", "evidence", "research")),
    ("heart", ("care", "human", "emotion", "love", "personal", "why it matters")),
    ("film", ("series", "movie", "film", "episode", "show", "scene")),
    ("chart", ("data", "growth", "metric", "impact", "result", "trend", "statistic")),
    ("bolt", ("energy", "action", "change", "power", "fast", "automation", "technology")),
    ("idea", ("idea", "insight", "lesson", "meaning", "concept", "takeaway")),
    ("target", ("goal", "focus", "purpose", "priority", "strategy", "objective")),
)

ROLE_DEFAULTS = {
    "timeline": "clock",
    "comparison": "target",
    "statistics": "chart",
    "media": "film",
    "notes": "idea",
}

FALLBACK_ICONS = ("target", "bolt", "idea", "chart", "book", "eye", "star", "map")


def choose_semantic_icon(text: str, *, role: str = "", index: int = 0) -> str:
    # Роля в pipeline-а: обработва стъпката `choose_semantic_icon` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `text` (str), `role` (str), `index` (int); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `re.findall`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str`. Резултатът се използва от следващия semantic/layout/rendering етап, без да зависи от конкретен файлов формат.
    # `normalized` е каноничната версия на входа, върху която сравнението е стабилно независимо от casing и излишни символи.
    normalized = " ".join(re.findall(r"[a-z0-9]+", text.lower()))
    best_icon = ""
    best_score = 0
    # Обхождаме `ICON_KEYWORDS` като `(icon, keywords)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for icon, keywords in ICON_KEYWORDS:
        # `score` е числова оценка за сравнение; тя позволява различни сигнали да участват в един ranking.
        score = sum(2 if " " in keyword else 1 for keyword in keywords if keyword in normalized)
        # Това условие е decision point: `score > best_score`.
        # При вярно условие се променя текущото състояние, което влияе на следващите стъпки.
        if score > best_score:
            best_icon = icon
            best_score = score
    # Това условие е decision point: `best_icon`.
    # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`best_icon`) и прескачаме ненужната останала работа.
    if best_icon:
        return best_icon
    # Обхождаме `ROLE_DEFAULTS.items()` като `(key, icon)`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for key, icon in ROLE_DEFAULTS.items():
        # Това условие е decision point: `key in role.lower()`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`icon`) и прескачаме ненужната останала работа.
        if key in role.lower():
            return icon
    return FALLBACK_ICONS[index % len(FALLBACK_ICONS)]
