from __future__ import annotations

import imaplib
import json
from datetime import datetime
from email import message_from_bytes
from email.utils import parseaddr
from pathlib import Path

import pandas as pd

from botfactory.models import AppConfig, ReplySyncResult
from botfactory.utils import (
    contains_unsubscribe_keyword,
    email_key,
    load_json_data,
    safe_int,
    strip_html,
    write_json_data,
)


def load_blacklist(blacklist_file: Path) -> dict[str, dict[str, str]]:
    from goldenpages_scraper.utils import collapse_whitespace
    if not blacklist_file.exists():
        return {}
    try:
        payload = json.loads(blacklist_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    blacklist: dict[str, dict[str, str]] = {}
    for email_address, meta in payload.items():
        key = email_key(email_address)
        if not key or not isinstance(meta, dict):
            continue
        blacklist[key] = {
            "reason": collapse_whitespace(str(meta.get("reason", ""))) or "manual",
            "detected_at": collapse_whitespace(str(meta.get("detected_at", ""))),
            "source": collapse_whitespace(str(meta.get("source", ""))),
        }
    return blacklist


def save_blacklist(blacklist_file: Path, blacklist: dict[str, dict[str, str]]) -> None:
    blacklist_file.parent.mkdir(parents=True, exist_ok=True)
    blacklist_file.write_text(
        json.dumps(blacklist, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def apply_blacklist_to_leads(leads_df: pd.DataFrame, blacklist: dict[str, dict[str, str]]) -> int:
    blacklisted_count = 0
    for row_index, row in leads_df.iterrows():
        key = email_key(row.get("Email", ""))
        if not key or key not in blacklist:
            continue
        if str(leads_df.at[row_index, "Status"]).strip().casefold() == "sent":
            continue
        leads_df.at[row_index, "Status"] = "Blacklisted"
        leads_df.at[row_index, "Last Error"] = f"Blacklisted: {blacklist[key].get('reason', 'manual')}"
        blacklisted_count += 1
    return blacklisted_count


def extract_message_text(message: object) -> str:
    from goldenpages_scraper.utils import collapse_whitespace
    payloads: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type not in {"text/plain", "text/html"}:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = part.get_payload(decode=True).decode(charset, errors="ignore")
            except Exception:
                continue
            payloads.append(strip_html(text) if content_type == "text/html" else collapse_whitespace(text))
    else:
        charset = message.get_content_charset() or "utf-8"
        try:
            text = message.get_payload(decode=True).decode(charset, errors="ignore")
        except Exception:
            text = ""
        payloads.append(strip_html(text) if message.get_content_type() == "text/html" else collapse_whitespace(text))
    return collapse_whitespace(" ".join(payloads))


def sync_reply_blacklist(config: AppConfig) -> ReplySyncResult:
    from botfactory.leads import load_leads_dataframe
    from goldenpages_scraper.utils import collapse_whitespace
    blacklist = load_blacklist(config.blacklist_file)
    known_lead_emails: set[str] = set()
    if config.sheets or config.leads_file.exists():
        leads_df = load_leads_dataframe(config.leads_file, config.sheets)
        known_lead_emails = {
            email_key(value)
            for value in leads_df["Email"].tolist()
            if email_key(value)
        }
    state_path = config.logs_dir / "reply_sync_state.json"
    state = load_json_data(state_path, default={"last_uid": 0})
    state_exists = state_path.exists()
    last_uid = safe_int(state.get("last_uid", 0))
    matched_messages = 0
    blacklisted_now = 0

    try:
        with imaplib.IMAP4_SSL(config.imap_host, config.imap_port) as mailbox:
            mailbox.login(config.smtp.username, config.smtp.password)
            mailbox.select(config.imap_folder)
            status, data = mailbox.uid("search", None, "ALL")
            if status != "OK":
                return ReplySyncResult(0, 0, len(blacklist), "Could not search IMAP inbox.")

            uid_values = [
                chunk
                for chunk in (data[0] or b"").decode().split()
                if chunk.isdigit() and int(chunk) > last_uid
            ]
            if not state_exists and last_uid == 0:
                all_uid_values = [int(chunk) for chunk in (data[0] or b"").decode().split() if chunk.isdigit()]
                state["last_uid"] = max(all_uid_values, default=0)
                write_json_data(state_path, state)
                return ReplySyncResult(
                    0,
                    0,
                    len(blacklist),
                    "Reply sync initialized. Only future replies will be tracked.",
                )
            max_uid = last_uid
            for uid_text in uid_values:
                uid_value = int(uid_text)
                fetch_status, fetch_data = mailbox.uid("fetch", uid_text, "(RFC822)")
                max_uid = max(max_uid, uid_value)
                if fetch_status != "OK" or not fetch_data:
                    continue

                raw_parts = [part[1] for part in fetch_data if isinstance(part, tuple) and len(part) > 1]
                if not raw_parts:
                    continue
                message = message_from_bytes(raw_parts[0])
                sender_email = email_key(parseaddr(message.get("From", ""))[1])
                if not sender_email or (known_lead_emails and sender_email not in known_lead_emails):
                    continue

                combined_text = " ".join(
                    [
                        collapse_whitespace(str(message.get("Subject", ""))),
                        extract_message_text(message),
                    ]
                ).casefold()
                if not contains_unsubscribe_keyword(combined_text, config.unsubscribe_keywords):
                    continue

                matched_messages += 1
                if sender_email not in blacklist:
                    blacklist[sender_email] = {
                        "reason": "reply-stop",
                        "detected_at": datetime.now().isoformat(timespec="seconds"),
                        "source": "imap-reply",
                    }
                    blacklisted_now += 1

            state["last_uid"] = max_uid
            write_json_data(state_path, state)
            save_blacklist(config.blacklist_file, blacklist)
            return ReplySyncResult(matched_messages, blacklisted_now, len(blacklist))
    except Exception as exc:
        return ReplySyncResult(matched_messages, blacklisted_now, len(blacklist), str(exc))
