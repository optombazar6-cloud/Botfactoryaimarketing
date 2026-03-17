from __future__ import annotations

import os


def getenv_str(name: str, default: str = "") -> str:
    from goldenpages_scraper.utils import collapse_whitespace
    return collapse_whitespace(os.getenv(name, default))


def getenv_raw(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def getenv_int(name: str, default: int) -> int:
    raw_value = getenv_str(name)
    if not raw_value:
        return default
    if not raw_value.isdigit():
        raise ValueError(f"{name} must be an integer.")
    return int(raw_value)


def getenv_optional_int(name: str, default: int | None = None) -> int | None:
    raw_value = getenv_str(name)
    if not raw_value:
        return default
    if not raw_value.isdigit():
        raise ValueError(f"{name} must be an integer.")
    parsed = int(raw_value)
    return parsed if parsed > 0 else default


def getenv_float(name: str, default: float) -> float:
    raw_value = getenv_str(name)
    if not raw_value:
        return default
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float.") from exc


def getenv_bool(name: str, default: bool) -> bool:
    raw_value = getenv_str(name)
    if not raw_value:
        return default
    normalized = raw_value.casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean.")


def normalize_secret(value: str) -> str:
    return "".join(character for character in value if not character.isspace())
