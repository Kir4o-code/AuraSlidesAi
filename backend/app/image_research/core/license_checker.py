ALLOWED_LICENSES = {
    "Unsplash License",
    "CC0",
    "Public Domain",
    "CC BY",
    "CC BY-SA",
}


def canonical_license(license_name: str | None) -> str | None:
    if not license_name:
        return None
    clean = " ".join(license_name.replace("-", "-").split())
    upper = clean.upper()
    if "PUBLIC DOMAIN" in upper or upper in {"PD", "PDM"}:
        return "Public Domain"
    if upper.startswith("CC0"):
        return "CC0"
    if upper.startswith("CC BY-SA"):
        return "CC BY-SA"
    if upper.startswith("CC BY"):
        return "CC BY"
    for allowed in ALLOWED_LICENSES:
        if clean == allowed:
            return allowed
    return None


def is_allowed_license(license_name: str | None) -> bool:
    return canonical_license(license_name) in ALLOWED_LICENSES


def license_score(license_name: str | None) -> float:
    return 1.0 if is_allowed_license(license_name) else 0.0
