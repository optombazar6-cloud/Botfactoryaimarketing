from __future__ import annotations

from botfactory.constants import EMAIL_RE
from botfactory.models import AppConfig

try:
    import dns.resolver
except Exception:
    dns = None


def validate_email_address(email: str, *, validate_email_mx: bool) -> str:
    from goldenpages_scraper.utils import collapse_whitespace
    candidate = collapse_whitespace(email).lower()
    if not EMAIL_RE.match(candidate):
        return "invalid-syntax"
    if not validate_email_mx:
        return "valid-syntax"
    if dns is None:
        return "mx-unchecked"

    domain = candidate.rsplit("@", 1)[-1]
    try:
        answers = dns.resolver.resolve(domain, "MX")
        return "valid-mx" if len(answers) > 0 else "no-mx"
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return "no-mx"
    except (dns.resolver.NoNameservers, dns.resolver.LifetimeTimeout):
        return "mx-unchecked"
    except Exception:
        return "mx-unchecked"


def is_usable_email_validation(validation_status: str) -> bool:
    return validation_status in {"valid-mx", "valid-syntax", "mx-unchecked"}


def validate_email_config(config: AppConfig) -> None:
    missing = []
    if config.smtp.transport == "gmail-api":
        if not config.smtp.username:
            missing.append("GMAIL_EMAIL")
        if not config.smtp.oauth_client_id:
            missing.append("GMAIL_API_CLIENT_ID")
        if not config.smtp.oauth_client_secret:
            missing.append("GMAIL_API_CLIENT_SECRET")
        if not config.smtp.oauth_refresh_token:
            missing.append("GMAIL_API_REFRESH_TOKEN")
    elif config.smtp.transport == "brevo":
        if not config.smtp.api_key:
            missing.append("BREVO_API_KEY")
        if not config.smtp.sender_email:
            missing.append("EMAIL_SENDER_EMAIL")
    else:
        if not config.smtp.username:
            missing.append("GMAIL_EMAIL")
        if not config.smtp.password:
            missing.append("GMAIL_APP_PASSWORD")
    if missing:
        raise ValueError(f"Missing required email settings: {', '.join(missing)}")
    if config.reply_sync_enabled and (not config.smtp.username or not config.smtp.password):
        raise ValueError("Reply sync requires GMAIL_EMAIL and GMAIL_APP_PASSWORD for IMAP access.")
    if (
        config.reply_sync_enabled
        and config.imap_host.casefold() == "imap.gmail.com"
        and len(config.smtp.password) != 16
    ):
        raise ValueError(
            "Reply sync with Gmail IMAP requires GMAIL_APP_PASSWORD to be a 16-character Gmail App Password."
        )
    if (
        config.smtp.transport == "smtp"
        and config.smtp.host.casefold() == "smtp.gmail.com"
        and len(config.smtp.password) != 16
    ):
        raise ValueError(
            "GMAIL_APP_PASSWORD must be a 16-character Gmail App Password. "
            "Enable Google 2-Step Verification, create an App Password, and paste it into .env."
        )
