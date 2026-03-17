from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(slots=True)
class SMTPConfig:
    transport: str
    host: str
    port: int
    username: str
    password: str
    sender_email: str
    from_name: str
    reply_to: str
    retry_limit: int
    api_key: str
    api_url: str
    request_timeout_seconds: float
    sandbox_mode: bool
    oauth_client_id: str
    oauth_client_secret: str
    oauth_refresh_token: str
    oauth_token_url: str
    gmail_api_send_url: str


@dataclass(slots=True)
class BrandConfig:
    brand_name: str
    reply_phrase: str
    unsubscribe_text: str
    custom_offer: str
    discovery_call_url: str
    signature_name: str
    signature_role: str
    signature_company: str
    signature_phone: str
    signature_website: str


@dataclass(slots=True)
class GoogleSheetsConfig:
    spreadsheet_id: str
    worksheet_name: str
    service_account_json_b64: str
    service_account_file: str


@dataclass(slots=True)
class AppConfig:
    mode: str
    seed_url: str | None
    leads_file: Path
    template_file: Path
    logs_dir: Path
    blacklist_file: Path
    warm_up_state_file: Path
    scraper_output_dir: Path
    max_companies: int | None
    max_pages_per_seed: int | None
    delay_min_seconds: float
    delay_max_seconds: float
    email_max_per_run: int
    filter_priority_categories: bool
    validate_email_mx: bool
    reply_sync_enabled: bool
    imap_host: str
    imap_port: int
    imap_folder: str
    unsubscribe_keywords: tuple[str, ...]
    warm_up_mode: bool
    warm_up_start_daily_limit: int
    warm_up_daily_increment: int
    warm_up_max_daily_limit: int
    default_language: str
    gemini_enabled: bool
    gemini_api_key: str
    gemini_model: str
    sheets: GoogleSheetsConfig | None
    smtp: SMTPConfig
    brand: BrandConfig


@dataclass(slots=True)
class LeadBuildResult:
    dataframe: pd.DataFrame
    rows_with_email: int
    targeted_valid_rows: int
    skipped_priority_rows: int
    invalid_email_rows: int


@dataclass(slots=True)
class ScrapePhaseResult:
    total_scraped_rows: int
    rows_with_email: int
    targeted_valid_rows: int
    skipped_priority_rows: int
    invalid_email_rows: int
    new_leads_added: int
    existing_leads_updated: int
    total_leads_in_file: int
    output_file: Path


@dataclass(slots=True)
class SendPhaseResult:
    pending_before: int
    sent_now: int
    failed_now: int
    skipped_sent: int
    blacklisted_skipped: int
    warm_up_remaining: int
    reply_blacklisted_now: int
    output_file: Path


@dataclass(slots=True)
class EmailDraft:
    subject: str
    html_body: str
    plain_text_body: str
    template_used: str


@dataclass(slots=True)
class ReplySyncResult:
    matched_messages: int
    blacklisted_now: int
    total_blacklisted: int
    error: str = ""
