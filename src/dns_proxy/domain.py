import re


_DOMAIN_PATTERN = re.compile(r"^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.?$")


def normalize_domain(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized.endswith("."):
        normalized = normalized[:-1]
    return normalized


def is_valid_domain(value: str) -> bool:
    if not value:
        return False
    if value.startswith(".") or ".." in value:
        return False
    if not _DOMAIN_PATTERN.fullmatch(value):
        return False
    labels = value[:-1].split(".") if value.endswith(".") else value.split(".")
    return all(0 < len(label) <= 63 and not label.startswith("-") and not label.endswith("-") for label in labels)


def domain_matches(name: str, entry: str) -> bool:
    return name == entry or name.endswith("." + entry)
