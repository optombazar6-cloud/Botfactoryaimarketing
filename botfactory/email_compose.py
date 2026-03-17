from __future__ import annotations

from urllib.parse import quote

import pandas as pd
from jinja2 import BaseLoader, Environment, select_autoescape

from botfactory.campaign_data import CAMPAIGN_COPY, LANGUAGE_LABELS
from botfactory.models import AppConfig, EmailDraft


def normalize_language(value: str) -> str:
    from goldenpages_scraper.utils import collapse_whitespace
    normalized = collapse_whitespace(value).casefold()
    if normalized.startswith("ru") or "рус" in normalized:
        return "ru"
    return "uz"


def greeting_for_language(language: str, company_name: str) -> str:
    if language == "ru":
        return f"Здравствуйте, команда {company_name}!"
    return f"Assalomu alaykum, {company_name} jamoasi!"


def reply_phrase_for_language(config: AppConfig, language: str) -> str:
    if language == "ru":
        return "Просто ответьте на это письмо"
    return config.brand.reply_phrase


def unsubscribe_text_for_language(config: AppConfig, language: str) -> str:
    if language == "ru":
        return "Если тема вам не интересна, просто ответьте словом 'Stop'."
    return config.brand.unsubscribe_text


def custom_offer_for_language(config: AppConfig, language: str) -> str:
    if language == "ru":
        return (
            "Кроме того, если вам требуется нестандартное решение на базе искусственного интеллекта "
            "(например: анализ данных, интеграция с внутренней системой, обработка документов или "
            "помощник для сотрудников), мы можем разработать его с нуля под ваши задачи."
        )
    return config.brand.custom_offer


def discovery_call_text_for_language(language: str, url: str, prefix: str) -> str:
    if not url:
        return ""
    return f"{prefix} {url}"


def campaign_key_for_category(category: str) -> str:
    normalized = category.casefold()
    if "custom" in normalized or "maxsus" in normalized:
        return "custom"
    if "tibbiyot" in normalized or "klinika" in normalized:
        return "healthcare"
    if "o'quv" in normalized or "oquv" in normalized or "ta'lim" in normalized:
        return "education"
    if "logistika" in normalized:
        return "logistics"
    return "general"


def pick_variant(seed: str) -> str:
    return "A" if sum(ord(character) for character in seed) % 2 == 0 else "B"


def render_text(template: str, context: dict[str, str]) -> str:
    class SafeFormatDict(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    return template.format_map(SafeFormatDict(**context))


def render_html_template(template_text: str, context: dict[str, str]) -> str:
    environment = Environment(
        loader=BaseLoader(),
        autoescape=select_autoescape(default=True),
    )
    template = environment.from_string(template_text)
    return template.render(**context)


def build_plain_text_body(context: dict[str, str]) -> str:
    return (
        f"{context['greeting']}\n\n"
        f"{context['intro']}\n\n"
        f"{context['problem']}\n\n"
        f"{context['offer_label']}\n"
        f"{context['category_offer']}\n\n"
        f"{context['solution']}\n\n"
        f"{context['custom_offer_title']}\n"
        f"{context['custom_offer']}\n\n"
        f"{context['cta']}\n\n"
        f"{context['discovery_call_text']}\n\n"
        f"{context['closing_text']}\n"
        f"{context['signature_name']}\n"
        f"{context['signature_role']}\n"
        f"{context['signature_company']}\n"
        f"{context['signature_phone']}\n"
        f"{context['signature_website']}\n\n"
        f"{context['unsubscribe_text']}"
    )


def contact_email_for_outreach(config: AppConfig) -> str:
    from goldenpages_scraper.utils import collapse_whitespace
    return (
        collapse_whitespace(config.smtp.reply_to)
        or collapse_whitespace(config.smtp.username)
        or collapse_whitespace(config.smtp.sender_email)
    )


def compose_outreach_email(config: AppConfig, row: pd.Series, template_text: str) -> EmailDraft:
    from botfactory.gemini import generate_ai_outreach
    from goldenpages_scraper.utils import collapse_whitespace

    company_name = collapse_whitespace(str(row.get("Company Name", ""))) or "hamkor"
    category = collapse_whitespace(str(row.get("Category", ""))) or "General Business"
    language = normalize_language(str(row.get("Language", "")) or config.default_language)
    activity_description = collapse_whitespace(str(row.get("Activity Types", "")))
    campaign_key = campaign_key_for_category(category)
    variant = pick_variant(f"{row.get('Email', '')}|{company_name}|{category}")
    copy_block = CAMPAIGN_COPY[language][campaign_key][variant]
    labels = LANGUAGE_LABELS[language]
    reply_phrase = reply_phrase_for_language(config, language)
    unsubscribe_text = unsubscribe_text_for_language(config, language)
    custom_offer_text = custom_offer_for_language(config, language)
    contact_email = contact_email_for_outreach(config)

    text_context = {
        "brand_name": config.brand.brand_name,
        "company_name": company_name,
        "category": category,
        "reply_phrase": reply_phrase,
    }
    subject = render_text(copy_block["subject"], text_context)
    ai_offer_text = generate_ai_outreach(
        config=config,
        company_name=company_name,
        category=category,
        description=activity_description,
        language=language,
    )
    category_offer_text = ai_offer_text or render_text(copy_block["solution"], text_context)
    html_context = {
        "subject": subject,
        "preheader": render_text(copy_block["preheader"], text_context),
        "brand_name": config.brand.brand_name,
        "company_name": company_name,
        "header_tagline": labels["header_tagline"],
        "offer_label": labels["offer_label"],
        "services_title": labels["services_title"],
        "service_ready_title": labels["service_ready_title"],
        "service_ready_body": labels["service_ready_body"],
        "service_custom_title": labels["service_custom_title"],
        "meeting_label": labels["meeting_label"],
        "meeting_link_prefix": labels["meeting_link_prefix"],
        "meeting_button": labels["meeting_button"],
        "contact_button": labels["contact_button"],
        "cta_prompt": labels["cta_prompt"],
        "mailto_href": f"mailto:{contact_email}?subject={quote(labels['mailto_subject'])}",
        "rights_text": labels["rights_text"],
        "location_text": labels["location_text"],
        "website_label": labels["website_label"],
        "contact_label": labels["contact_label"],
        "closing_text": labels["closing_text"],
        "headline": render_text(copy_block["headline"], text_context),
        "greeting": greeting_for_language(language, company_name),
        "intro": render_text(copy_block["intro"], text_context),
        "problem": render_text(copy_block["problem"], text_context),
        "solution": render_text(copy_block["solution"], text_context),
        "category_offer": category_offer_text,
        "custom_offer_title": labels["custom_offer_title"],
        "custom_offer": custom_offer_text,
        "cta": render_text(copy_block["cta"], text_context),
        "discovery_call_text": (
            discovery_call_text_for_language(language, config.brand.discovery_call_url, labels["meeting_link_prefix"])
            if config.brand.discovery_call_url
            else ""
        ),
        "discovery_call_url": config.brand.discovery_call_url,
        "your_email": contact_email,
        "signature_name": config.brand.signature_name,
        "signature_role": config.brand.signature_role,
        "signature_company": config.brand.signature_company,
        "signature_phone": config.brand.signature_phone,
        "signature_website": config.brand.signature_website,
        "sender_email": contact_email,
        "unsubscribe_text": unsubscribe_text,
    }
    return EmailDraft(
        subject=subject,
        html_body=render_html_template(template_text, html_context),
        plain_text_body=build_plain_text_body(html_context),
        template_used=f"{campaign_key}-{variant}{'-ai' if ai_offer_text else ''}",
    )
