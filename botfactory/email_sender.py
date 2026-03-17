from __future__ import annotations

import base64
import random
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

import requests

from botfactory.models import SMTPConfig
from botfactory.utils import truncate_error

_GMAIL_API_TOKENS: dict[str, tuple[str, float]] = {}


def get_gmail_api_access_token(smtp_config: SMTPConfig) -> tuple[str | None, str]:
    from goldenpages_scraper.utils import collapse_whitespace
    cache_key = smtp_config.oauth_refresh_token
    cached = _GMAIL_API_TOKENS.get(cache_key)
    if cached is not None:
        access_token, expires_at = cached
        if time.time() < expires_at - 60:
            return access_token, ""

    payload = {
        "client_id": smtp_config.oauth_client_id,
        "client_secret": smtp_config.oauth_client_secret,
        "refresh_token": smtp_config.oauth_refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        response = requests.post(
            smtp_config.oauth_token_url,
            data=payload,
            timeout=smtp_config.request_timeout_seconds,
        )
    except requests.RequestException as exc:
        return None, f"Gmail API token request failed: {exc}"

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {}

    if response.status_code != 200:
        return None, f"Gmail API token error {response.status_code}: {collapse_whitespace(str(response_payload))}"

    access_token = collapse_whitespace(str(response_payload.get("access_token", "")))
    expires_in = int(response_payload.get("expires_in", 3600) or 3600)
    if not access_token:
        return None, "Gmail API token response did not include access_token."
    _GMAIL_API_TOKENS[cache_key] = (access_token, time.time() + expires_in)
    return access_token, ""


def send_email_via_gmail_api(
    smtp_config: SMTPConfig,
    to_email: str,
    subject: str,
    html_body: str,
    plain_text_body: str,
) -> tuple[bool, str]:
    from goldenpages_scraper.utils import collapse_whitespace
    access_token, token_error = get_gmail_api_access_token(smtp_config)
    if not access_token:
        return False, token_error

    sender_email = smtp_config.sender_email or smtp_config.username
    message = EmailMessage()
    message["From"] = formataddr((smtp_config.from_name, sender_email))
    message["To"] = to_email
    message["Subject"] = subject
    message["Reply-To"] = smtp_config.reply_to or smtp_config.username
    message.set_content(plain_text_body)
    message.add_alternative(html_body, subtype="html")

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body_payload: dict[str, Any] = {"raw": raw_message}

    try:
        response = requests.post(
            smtp_config.gmail_api_send_url,
            headers=headers,
            json=body_payload,
            timeout=smtp_config.request_timeout_seconds,
        )
    except requests.RequestException as exc:
        return False, f"Gmail API send failed: {exc}"

    if 200 <= response.status_code < 300:
        return True, ""

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = response.text.strip()
    return False, f"Gmail API {response.status_code}: {collapse_whitespace(str(response_payload))}"


def send_email_via_brevo(
    smtp_config: SMTPConfig,
    to_email: str,
    subject: str,
    html_body: str,
    plain_text_body: str,
) -> tuple[bool, str]:
    from goldenpages_scraper.utils import collapse_whitespace
    sender_email = smtp_config.sender_email or smtp_config.username
    if not sender_email:
        return False, "EMAIL_SENDER_EMAIL is missing."

    payload: dict[str, Any] = {
        "sender": {"name": smtp_config.from_name, "email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": plain_text_body,
    }
    reply_to = collapse_whitespace(smtp_config.reply_to or smtp_config.username)
    if reply_to:
        payload["replyTo"] = {"email": reply_to, "name": smtp_config.from_name}

    headers = {
        "api-key": smtp_config.api_key,
        "accept": "application/json",
        "content-type": "application/json",
    }
    if smtp_config.sandbox_mode:
        headers["X-Sib-Sandbox"] = "drop"

    try:
        response = requests.post(
            smtp_config.api_url,
            headers=headers,
            json=payload,
            timeout=smtp_config.request_timeout_seconds,
        )
    except requests.RequestException as exc:
        return False, f"Brevo request failed: {exc}"

    if 200 <= response.status_code < 300:
        return True, ""

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = response.text.strip()
    return False, f"Brevo API {response.status_code}: {collapse_whitespace(str(response_payload))}"


def send_email_once(
    smtp_config: SMTPConfig,
    to_email: str,
    subject: str,
    html_body: str,
    plain_text_body: str,
) -> tuple[bool, str]:
    if smtp_config.transport == "gmail-api":
        return send_email_via_gmail_api(smtp_config, to_email, subject, html_body, plain_text_body)
    if smtp_config.transport == "brevo":
        return send_email_via_brevo(smtp_config, to_email, subject, html_body, plain_text_body)

    message = EmailMessage()
    message["From"] = formataddr((smtp_config.from_name, smtp_config.sender_email or smtp_config.username))
    message["To"] = to_email
    message["Subject"] = subject
    message["Reply-To"] = smtp_config.reply_to or smtp_config.username
    message.set_content(plain_text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_config.host, smtp_config.port, context=context, timeout=30) as server:
            server.login(smtp_config.username, smtp_config.password)
            server.send_message(message)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def send_email_with_backoff(
    smtp_config: SMTPConfig,
    to_email: str,
    subject: str,
    html_body: str,
    plain_text_body: str,
) -> tuple[bool, str]:
    last_error = ""
    for attempt in range(1, smtp_config.retry_limit + 1):
        success, error_message = send_email_once(smtp_config, to_email, subject, html_body, plain_text_body)
        if success:
            return True, ""
        last_error = error_message
        if attempt >= smtp_config.retry_limit:
            break
        wait_seconds = min(90.0, (2 ** (attempt - 1)) * 3 + random.uniform(0.5, 1.5))
        time.sleep(wait_seconds)
    return False, last_error
