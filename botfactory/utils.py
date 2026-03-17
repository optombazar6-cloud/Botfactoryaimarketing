from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from botfactory.constants import EMAIL_RE


def safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def truncate_error(message: str, limit: int = 240) -> str:
    from goldenpages_scraper.utils import collapse_whitespace
    cleaned = collapse_whitespace(message)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def normalize_pipe_list(value: Any, *, emails_only: bool = False) -> list[str]:
    from goldenpages_scraper.utils import collapse_whitespace
    text = collapse_whitespace(str(value))
    if not text:
        return []

    seen: set[str] = set()
    items: list[str] = []
    for piece in text.split("|"):
        candidate = collapse_whitespace(piece).strip(" ,;")
        if not candidate:
            continue
        if emails_only and not EMAIL_RE.match(candidate):
            continue
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(candidate)
    return items


def email_key(email: Any) -> str:
    from goldenpages_scraper.utils import collapse_whitespace
    candidate = collapse_whitespace(str(email)).lower()
    if not candidate or not EMAIL_RE.match(candidate):
        return ""
    return candidate


def strip_html(value: str) -> str:
    from goldenpages_scraper.utils import collapse_whitespace
    return collapse_whitespace(re.sub(r"<[^>]+>", " ", value))


def contains_unsubscribe_keyword(body_text: str, keywords: Sequence[str]) -> bool:
    normalized = body_text.casefold()
    return any(keyword in normalized for keyword in keywords if keyword)


def write_json_log(logs_dir: Path, log_type: str, payload: dict[str, Any]) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"{log_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output = {
        "log_type": log_type,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        **payload,
    }
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_json_data(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(default)
    if not isinstance(payload, dict):
        return dict(default)
    merged = dict(default)
    merged.update(payload)
    return merged


def write_json_data(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
