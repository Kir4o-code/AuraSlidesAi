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
    normalized = " ".join(re.findall(r"[a-z0-9]+", text.lower()))
    best_icon = ""
    best_score = 0
    for icon, keywords in ICON_KEYWORDS:
        score = sum(2 if " " in keyword else 1 for keyword in keywords if keyword in normalized)
        if score > best_score:
            best_icon = icon
            best_score = score
    if best_icon:
        return best_icon
    for key, icon in ROLE_DEFAULTS.items():
        if key in role.lower():
            return icon
    return FALLBACK_ICONS[index % len(FALLBACK_ICONS)]
