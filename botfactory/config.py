from __future__ import annotations

import argparse
from pathlib import Path

from goldenpages_scraper.utils import collapse_whitespace

from botfactory.env_utils import (
    getenv_bool,
    getenv_float,
    getenv_int,
    getenv_optional_int,
    getenv_raw,
    getenv_str,
    normalize_secret,
)
from botfactory.models import AppConfig, BrandConfig, GoogleSheetsConfig, SMTPConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="botfactory-lead-machine",
        description="GoldenPages scraper and Botfactory AI outreach automator.",
    )
    parser.add_argument("--mode", choices=["scrape", "email", "all", "sync-replies"], default="all")
    parser.add_argument("--seed-url", default=None)
    parser.add_argument("--max-companies", type=int, default=None)
    parser.add_argument("--max-pages-per-seed", type=int, default=None)
    parser.add_argument("--leads-file", type=Path, default=None)
    parser.add_argument("--template-file", type=Path, default=None)
    parser.add_argument("--email-max-per-run", type=int, default=None)
    parser.add_argument("--disable-priority-filter", action="store_true")
    parser.add_argument("--disable-mx-validation", action="store_true")
    return parser


def normalize_email_transport(value: str) -> str:
    normalized = collapse_whitespace(value).casefold()
    if normalized in {"", "auto"}:
        return "auto"
    if normalized in {"gmail-api", "gmail_api", "gmailapi"}:
        return "gmail-api"
    if normalized in {"brevo", "brevo-api", "brevo_api"}:
        return "brevo"
    if normalized in {"smtp", "gmail"}:
        return "smtp"
    raise ValueError("EMAIL_TRANSPORT must be one of: auto, gmail-api, brevo, smtp.")


def resolve_email_transport(
    preferred: str,
    *,
    brevo_api_key: str,
    gmail_api_client_id: str,
    gmail_api_refresh_token: str,
) -> str:
    if preferred == "auto":
        if gmail_api_client_id and gmail_api_refresh_token:
            return "gmail-api"
        return "brevo" if brevo_api_key else "smtp"
    return preferred


def email_transport_label(config: SMTPConfig) -> str:
    if config.transport == "gmail-api":
        return "Gmail API"
    if config.transport == "brevo":
        return "Brevo API"
    return f"SMTP ({config.host}:{config.port})"


def build_config(args: argparse.Namespace) -> AppConfig:
    from botfactory.email_compose import normalize_language

    seed_url = collapse_whitespace(args.seed_url or getenv_str("SCRAPE_SEED_URL", ""))
    leads_file = args.leads_file or Path(getenv_str("LEADS_FILE", "botfactory_leads.xlsx"))
    template_file = args.template_file or Path(getenv_str("TEMPLATE_FILE", "template.html"))
    scraper_output_dir = Path(getenv_str("SCRAPER_OUTPUT_DIR", "output"))
    logs_dir = Path(getenv_str("LOGS_DIR", "logs"))
    blacklist_file = Path(getenv_str("BLACKLIST_FILE", str(logs_dir / "blacklist.json")))
    warm_up_state_file = Path(getenv_str("WARM_UP_STATE_FILE", str(logs_dir / "warmup_state.json")))
    max_companies = args.max_companies if args.max_companies is not None else getenv_optional_int("SCRAPER_MAX_COMPANIES")
    max_pages_per_seed = (
        args.max_pages_per_seed if args.max_pages_per_seed is not None else getenv_optional_int("SCRAPER_MAX_PAGES_PER_SEED")
    )
    email_max_per_run = (
        args.email_max_per_run if args.email_max_per_run is not None else getenv_optional_int("EMAIL_MAX_PER_RUN", 50)
    )
    delay_min_seconds = getenv_float("EMAIL_DELAY_MIN_SECONDS", 10.0)
    delay_max_seconds = getenv_float("EMAIL_DELAY_MAX_SECONDS", 20.0)
    filter_priority_categories = not args.disable_priority_filter and getenv_bool("FILTER_PRIORITY_CATEGORIES", True)
    validate_email_mx = not args.disable_mx_validation and getenv_bool("VALIDATE_EMAIL_MX", True)
    reply_sync_enabled = getenv_bool("REPLY_SYNC_ENABLED", True)
    warm_up_mode = getenv_bool("WARM_UP_MODE", True)
    default_language = normalize_language(getenv_str("OUTREACH_LANGUAGE", "uz"))
    gemini_enabled = getenv_bool("GEMINI_ENABLED", True)
    gemini_api_key = normalize_secret(getenv_str("GEMINI_API_KEY", ""))
    gemini_model = getenv_str("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
    google_sheets_enabled = getenv_bool("GOOGLE_SHEETS_ENABLED", False)
    preferred_email_transport = normalize_email_transport(getenv_str("EMAIL_TRANSPORT", "auto"))
    brevo_api_key = normalize_secret(getenv_str("BREVO_API_KEY", ""))
    gmail_api_client_id = normalize_secret(getenv_str("GMAIL_API_CLIENT_ID", ""))
    gmail_api_client_secret = normalize_secret(getenv_str("GMAIL_API_CLIENT_SECRET", ""))
    gmail_api_refresh_token = normalize_secret(getenv_str("GMAIL_API_REFRESH_TOKEN", ""))
    email_transport = resolve_email_transport(
        preferred_email_transport,
        brevo_api_key=brevo_api_key,
        gmail_api_client_id=gmail_api_client_id,
        gmail_api_refresh_token=gmail_api_refresh_token,
    )
    sender_email = getenv_str("EMAIL_SENDER_EMAIL", getenv_str("GMAIL_EMAIL", ""))

    if args.mode in {"scrape", "all"} and not seed_url:
        raise ValueError("SCRAPE_SEED_URL is missing. Set it in .env or pass --seed-url.")
    if delay_min_seconds < 0 or delay_max_seconds < 0 or delay_min_seconds > delay_max_seconds:
        raise ValueError("Email delay values are invalid.")
    if email_max_per_run < 1:
        raise ValueError("EMAIL_MAX_PER_RUN must be at least 1.")

    smtp = SMTPConfig(
        transport=email_transport,
        host=getenv_str("SMTP_HOST", "smtp.gmail.com"),
        port=getenv_int("SMTP_PORT", 465),
        username=getenv_str("GMAIL_EMAIL"),
        password=normalize_secret(getenv_str("GMAIL_APP_PASSWORD")),
        sender_email=sender_email,
        from_name=getenv_str("EMAIL_FROM_NAME", "Botfactory AI"),
        reply_to=getenv_str("EMAIL_REPLY_TO", getenv_str("GMAIL_EMAIL")),
        retry_limit=getenv_int("SMTP_RETRY_LIMIT", 3),
        api_key=brevo_api_key,
        api_url=getenv_str("BREVO_API_URL", "https://api.brevo.com/v3/smtp/email"),
        request_timeout_seconds=getenv_float("EMAIL_REQUEST_TIMEOUT_SECONDS", 30.0),
        sandbox_mode=getenv_bool("BREVO_SANDBOX_MODE", False),
        oauth_client_id=gmail_api_client_id,
        oauth_client_secret=gmail_api_client_secret,
        oauth_refresh_token=gmail_api_refresh_token,
        oauth_token_url=getenv_str("GMAIL_API_TOKEN_URL", "https://oauth2.googleapis.com/token"),
        gmail_api_send_url=getenv_str("GMAIL_API_SEND_URL", "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"),
    )
    brand_name = getenv_str("BOTFACTORY_BRAND_NAME", "Botfactory AI")
    brand = BrandConfig(
        brand_name=brand_name,
        reply_phrase=getenv_str("EMAIL_REPLY_PHRASE", "Shunchaki 'Ha' deb javob yozing"),
        unsubscribe_text=getenv_str(
            "EMAIL_UNSUBSCRIBE_TEXT",
            "Agar ushbu mavzu sizga qiziq bo'lmasa, 'Stop' deb javob bering.",
        ),
        custom_offer=getenv_str(
            "CUSTOM_SOLUTIONS_TEXT",
            "Bundan tashqari, agar sizga biznesingiz uchun maxsus AI yechim kerak bo'lsa "
            "(masalan: data analytics, ichki CRM integratsiyasi, hujjatlar bilan ishlovchi AI "
            "yoki xodimlar uchun AI-yordamchi), biz uni aynan sizning talablaringiz asosida "
            "noldan ishlab chiqib bera olamiz.",
        ),
        discovery_call_url=getenv_str("DISCOVERY_CALL_URL", ""),
        signature_name=getenv_str("EMAIL_SIGNATURE_NAME", brand_name),
        signature_role=getenv_str("EMAIL_SIGNATURE_ROLE", "AI Automation Agency"),
        signature_company=getenv_str("EMAIL_SIGNATURE_COMPANY", brand_name),
        signature_phone=getenv_str("EMAIL_SIGNATURE_PHONE", "+998901234567"),
        signature_website=getenv_str("EMAIL_SIGNATURE_WEBSITE", "https://botfactory.ai"),
    )
    sheets: GoogleSheetsConfig | None = None
    if google_sheets_enabled:
        spreadsheet_id = getenv_str("GOOGLE_SHEETS_SPREADSHEET_ID")
        worksheet_name = getenv_str("GOOGLE_SHEETS_WORKSHEET", "Leads")
        service_account_json_b64 = normalize_secret(getenv_raw("GOOGLE_SERVICE_ACCOUNT_JSON_B64", ""))
        service_account_file = collapse_whitespace(getenv_raw("GOOGLE_SERVICE_ACCOUNT_FILE", ""))
        if not spreadsheet_id:
            raise ValueError("GOOGLE_SHEETS_SPREADSHEET_ID is required when GOOGLE_SHEETS_ENABLED=true.")
        if not service_account_json_b64 and not service_account_file:
            raise ValueError(
                "GOOGLE_SERVICE_ACCOUNT_JSON_B64 or GOOGLE_SERVICE_ACCOUNT_FILE is required when GOOGLE_SHEETS_ENABLED=true."
            )
        sheets = GoogleSheetsConfig(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name,
            service_account_json_b64=service_account_json_b64,
            service_account_file=service_account_file,
        )
    return AppConfig(
        mode=args.mode,
        seed_url=seed_url or None,
        leads_file=leads_file,
        template_file=template_file,
        logs_dir=logs_dir,
        blacklist_file=blacklist_file,
        warm_up_state_file=warm_up_state_file,
        scraper_output_dir=scraper_output_dir,
        max_companies=max_companies,
        max_pages_per_seed=max_pages_per_seed,
        delay_min_seconds=delay_min_seconds,
        delay_max_seconds=delay_max_seconds,
        email_max_per_run=email_max_per_run,
        filter_priority_categories=filter_priority_categories,
        validate_email_mx=validate_email_mx,
        reply_sync_enabled=reply_sync_enabled,
        imap_host=getenv_str("IMAP_HOST", "imap.gmail.com"),
        imap_port=getenv_int("IMAP_PORT", 993),
        imap_folder=getenv_str("IMAP_FOLDER", "INBOX"),
        unsubscribe_keywords=tuple(
            chunk
            for chunk in [
                collapse_whitespace(item).casefold()
                for item in getenv_str("UNSUBSCRIBE_KEYWORDS", "stop,unsubscribe,remove,bekor").split(",")
            ]
            if chunk
        ),
        warm_up_mode=warm_up_mode,
        warm_up_start_daily_limit=getenv_int("WARM_UP_START_DAILY_LIMIT", 5),
        warm_up_daily_increment=getenv_int("WARM_UP_DAILY_INCREMENT", 5),
        warm_up_max_daily_limit=getenv_int("WARM_UP_MAX_DAILY_LIMIT", 50),
        default_language=default_language,
        gemini_enabled=gemini_enabled,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        sheets=sheets,
        smtp=smtp,
        brand=brand,
    )
