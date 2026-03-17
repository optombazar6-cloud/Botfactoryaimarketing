from __future__ import annotations

from typing import Any

from botfactory.models import AppConfig

try:
    from google import genai as google_genai
    from google.genai import types as google_genai_types
except Exception:
    google_genai = None
    google_genai_types = None

_GEMINI_CLIENTS: dict[str, Any] = {}


def get_gemini_client(api_key: str) -> Any | None:
    if not api_key or google_genai is None:
        return None
    cached_client = _GEMINI_CLIENTS.get(api_key)
    if cached_client is not None:
        return cached_client
    try:
        client = google_genai.Client(api_key=api_key)
    except Exception:
        return None
    _GEMINI_CLIENTS[api_key] = client
    return client


def build_gemini_prompt(
    company_name: str,
    category: str,
    description: str,
    language: str,
    reply_phrase: str,
) -> str:
    description_text = description or "Faoliyati haqida qo'shimcha tavsif ko'rsatilmagan."
    if language == "ru":
        description_text = description or "Дополнительное описание деятельности не указано."
        return (
            "Ты опытный B2B-маркетолог агентства Botfactory AI.\n"
            f"Компания: {company_name}\n"
            f"Категория: {category}\n"
            f"Описание деятельности: {description_text}\n\n"
            "Задача: напиши короткий персонализированный текст письма от имени Botfactory AI.\n"
            "Требования:\n"
            "- Язык: русский.\n"
            "- Объем: 4-5 коротких предложений.\n"
            "- Тон: профессиональный, теплый и уверенный.\n"
            "- Упомяни вероятную проблему компании в ее сфере.\n"
            "- Покажи, что у нас есть как готовые интеллектуальные агенты, так и индивидуальные решения под бизнес.\n"
            "- Не добавляй приветствие и подпись, они уже есть в шаблоне письма.\n"
            f"- Заверши мягким призывом ответить на письмо: {reply_phrase}.\n"
            "- Не пиши тему письма, заголовки, списки, markdown и кавычки вокруг ответа.\n"
            "- Не используй англоязычные рекламные штампы без необходимости.\n"
        )
    return (
        "Siz Botfactory AI agentligining tajribali B2B marketing mutaxassisisiz.\n"
        f"Kompaniya: {company_name}\n"
        f"Kategoriya: {category}\n"
        f"Faoliyati: {description_text}\n\n"
        "Vazifa: Botfactory AI nomidan ushbu kompaniya uchun qisqa va shaxsiylashtirilgan outreach matni yozing.\n"
        "Talablar:\n"
        "- Til: o'zbek tili.\n"
        "- Uzunlik: 4-5 ta qisqa gap.\n"
        "- Ohang: professional, samimiy va ishonchli.\n"
        "- Kompaniyaning o'z sohasidagi ehtimoliy muammosini tilga oling.\n"
        "- Bizda tayyor sun'iy intellekt agentlari ham, biznesga mos noldan quriladigan maxsus yechimlar ham borligini ko'rsating.\n"
        "- Salomlashuv va imzo yozmang, ular email shablonida allaqachon bor.\n"
        f"- Yakunda yumshoq CTA bo'lsin: {reply_phrase}.\n"
        "- Subject, sarlavha, ro'yxat, markdown yoki qo'shtirnoq yozmang.\n"
        "- Keraksiz inglizcha reklama iboralarini ishlatmang.\n"
    )


def extract_gemini_text(response: Any) -> str:
    from goldenpages_scraper.utils import collapse_whitespace
    text = collapse_whitespace(str(getattr(response, "text", "") or ""))
    if text:
        return text
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = collapse_whitespace(str(getattr(part, "text", "") or ""))
            if part_text:
                return part_text
    return ""


def clean_ai_outreach_text(text: str) -> str:
    import re
    from goldenpages_scraper.utils import collapse_whitespace
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip().strip("\"' ")
    cleaned = re.sub(r"^(matn|xat|tekst|текст)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"^(assalomu\s+alaykum[^.!?]*[.!?]\s*|zdravstvuyte[^.!?]*[.!?]\s*|здравствуйте[^.!?]*[.!?]\s*)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return collapse_whitespace(cleaned)


def generate_ai_outreach(
    config: AppConfig,
    company_name: str,
    category: str,
    description: str,
    language: str,
) -> str | None:
    from botfactory.email_compose import reply_phrase_for_language
    if not config.gemini_enabled or not config.gemini_api_key:
        return None
    client = get_gemini_client(config.gemini_api_key)
    if client is None:
        return None
    prompt = build_gemini_prompt(
        company_name=company_name,
        category=category,
        description=description,
        language=language,
        reply_phrase=reply_phrase_for_language(config, language),
    )
    try:
        generation_config = (
            google_genai_types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.95,
                top_k=40,
                max_output_tokens=300,
            )
            if google_genai_types is not None
            else None
        )
        response = client.models.generate_content(
            model=config.gemini_model,
            contents=prompt,
            config=generation_config,
        )
    except Exception:
        return None
    text = clean_ai_outreach_text(extract_gemini_text(response))
    return text or None
