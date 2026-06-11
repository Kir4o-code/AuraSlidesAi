# Роля на модула: Лицензионната защита преди кандидатът да бъде допуснат до крайния резултат.
# Чети коментарите като обяснение на причината за кода и връзката му със следващия слой, а не като буквален превод на Python синтаксиса.
ALLOWED_LICENSES = {
    "Unsplash License",
    "CC0",
    "Public Domain",
    "CC BY",
    "CC BY-SA",
}


def canonical_license(license_name: str | None) -> str | None:
    # Роля в pipeline-а: уеднаквява външна стойност към вътрешния речник на приложението.
    # Входът идва през `license_name` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `clean.upper`, `normalized.startswith`, `upper.replace('_', ' ').replace`, `upper.replace`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `str | None`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    # Това условие е decision point: `not license_name`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `None`, без да проверява по-слабите правила отдолу.
    if not license_name:
        return None
    # `clean` пази резултата от `' '.join`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    clean = " ".join(license_name.split())
    # `upper` пази резултата от `clean.upper`, за да бъде проверен или използван в следващите стъпки вместо операцията да се повтори.
    upper = clean.upper()
    # `normalized` е каноничната версия на входа, върху която сравнението е стабилно независимо от casing и излишни символи.
    normalized = " ".join(upper.replace("_", " ").replace("-", " ").split())
    # Това условие е decision point: `'PUBLIC DOMAIN' in upper or upper in {'PD', 'PDM'}`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'Public Domain'`, без да проверява по-слабите правила отдолу.
    if "PUBLIC DOMAIN" in upper or upper in {"PD", "PDM"}:
        return "Public Domain"
    # Това условие е decision point: `normalized.startswith('CC0')`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'CC0'`, без да проверява по-слабите правила отдолу.
    if normalized.startswith("CC0"):
        return "CC0"
    # Това условие е decision point: `normalized.startswith('CC BY SA')`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'CC BY-SA'`, без да проверява по-слабите правила отдолу.
    if normalized.startswith("CC BY SA"):
        return "CC BY-SA"
    # Това условие е decision point: `normalized.startswith('CC BY')`.
    # Това е приоритетно правило: първото съвпадение печели и класифицира входа като `'CC BY'`, без да проверява по-слабите правила отдолу.
    if normalized.startswith("CC BY"):
        return "CC BY"
    # Обхождаме `ALLOWED_LICENSES` като `allowed`, защото всеки елемент трябва да мине през една и съща pipeline стъпка.
    # Цикълът държи обработката еднаква за всеки елемент.
    for allowed in ALLOWED_LICENSES:
        # Това условие е decision point: `clean == allowed`.
        # Това е guard clause: при вярно условие вече имаме достатъчно надежден резултат (`allowed`) и прескачаме ненужната останала работа.
        if clean == allowed:
            return allowed
    return None


def is_allowed_license(license_name: str | None) -> bool:
    # Роля в pipeline-а: обработва стъпката `is_allowed_license` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `license_name` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `canonical_license`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `bool`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    return canonical_license(license_name) in ALLOWED_LICENSES


def license_score(license_name: str | None) -> float:
    # Роля в pipeline-а: обработва стъпката `license_score` като отделна отговорност, така че caller-ът да използва резултата без да познава вътрешните проверки и междинни стойности.
    # Входът идва през `license_name` (str | None); имената показват каква част от контекста е собственост на тази стъпка.
    # Основните преходи навън са към `is_allowed_license`; така се вижда кои отговорности функцията делегира.
    # Типовете в сигнатурата документират договора за caller-а и позволяват грешки да се хващат преди runtime.
    # Изходен договор: `float`. Резултатът остава в image research подсистемата или се връща към image_service за обогатяване на слайда.
    return 1.0 if is_allowed_license(license_name) else 0.0
