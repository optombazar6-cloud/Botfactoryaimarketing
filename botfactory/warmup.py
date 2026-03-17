from __future__ import annotations

from datetime import datetime

from botfactory.models import AppConfig
from botfactory.utils import load_json_data, safe_int, write_json_data


def plan_warm_up_allowance(config: AppConfig) -> tuple[int, int]:
    if not config.warm_up_mode:
        return config.email_max_per_run, config.email_max_per_run

    state = load_json_data(
        config.warm_up_state_file,
        default={
            "start_date": datetime.now().date().isoformat(),
            "sent_counts": {},
        },
    )
    from goldenpages_scraper.utils import collapse_whitespace
    start_date_raw = collapse_whitespace(str(state.get("start_date", ""))) or datetime.now().date().isoformat()
    try:
        start_date = datetime.fromisoformat(start_date_raw).date()
    except ValueError:
        start_date = datetime.now().date()
        state["start_date"] = start_date.isoformat()

    days_elapsed = max((datetime.now().date() - start_date).days, 0)
    daily_limit = min(
        config.warm_up_start_daily_limit + (days_elapsed * config.warm_up_daily_increment),
        config.warm_up_max_daily_limit,
    )
    sent_counts = state.get("sent_counts", {})
    if not isinstance(sent_counts, dict):
        sent_counts = {}
        state["sent_counts"] = sent_counts
    today_key = datetime.now().date().isoformat()
    sent_today = safe_int(sent_counts.get(today_key, 0))
    write_json_data(config.warm_up_state_file, state)
    return max(daily_limit - sent_today, 0), max(daily_limit - sent_today, 0)


def record_warm_up_progress(config: AppConfig, sent_now: int) -> None:
    state = load_json_data(
        config.warm_up_state_file,
        default={
            "start_date": datetime.now().date().isoformat(),
            "sent_counts": {},
        },
    )
    sent_counts = state.get("sent_counts", {})
    if not isinstance(sent_counts, dict):
        sent_counts = {}
        state["sent_counts"] = sent_counts
    today_key = datetime.now().date().isoformat()
    sent_counts[today_key] = safe_int(sent_counts.get(today_key, 0)) + sent_now
    write_json_data(config.warm_up_state_file, state)
