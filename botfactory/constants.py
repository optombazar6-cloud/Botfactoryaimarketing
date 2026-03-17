from __future__ import annotations

import re

EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)
TEMPLATE_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")

HEALTHCARE_KEYWORDS = (
    "klinika",
    "tibbiyot",
    "med",
    "shifoxona",
    "poliklinika",
    "stomatolog",
    "diagnostika",
    "hospital",
    "pharma",
    "apteka",
)
EDUCATION_KEYWORDS = (
    "oquv",
    "o'quv",
    "talim",
    "ta'lim",
    "kurs",
    "maktab",
    "education",
    "training",
    "learning",
    "akademiya",
    "academy",
)
LOGISTICS_KEYWORDS = (
    "logistika",
    "transport",
    "cargo",
    "yuk",
    "dispatch",
    "ekspeditor",
    "ekspeditorlik",
    "tashish",
    "delivery",
    "ombor",
    "warehouse",
)
BUSINESS_KEYWORDS = (
    "savdo",
    "retail",
    "shop",
    "store",
    "market",
    "it",
    "dastur",
    "software",
    "bank",
    "sugurta",
    "sug'urta",
    "insurance",
    "call center",
    "aloqa",
    "kommunikatsiya",
    "support",
    "crm",
)

LEAD_COLUMNS = [
    "Company ID",
    "Company Name",
    "Email",
    "Phone",
    "Category",
    "Activity Types",
    "Website",
    "Source URL",
    "Source Listing URL",
    "Lead Captured At",
    "Validation Status",
    "Lead Score",
    "Rating Value",
    "Rating Count",
    "Language",
    "Status",
    "LastContacted",
    "Sent At",
    "Last Error",
    "Template Used",
]

DEFAULT_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{subject}}</title>
</head>
<body style="margin:0;padding:0;background:#f5efe6;font-family:Arial,sans-serif;color:#1f2937;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{{preheader}}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5efe6;padding:28px 14px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:720px;background:#101418;border-radius:22px;overflow:hidden;">
          <tr>
            <td style="padding:22px 32px;background:linear-gradient(135deg,#c28b31 0%,#f1d08f 100%);">
              <div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#101418;font-weight:bold;">{{brand_name}}</div>
              <h1 style="margin:10px 0 0;font-size:30px;line-height:1.2;color:#101418;">{{headline}}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:34px 32px;color:#f8fafc;">
              <p style="margin:0 0 18px;font-size:16px;line-height:1.75;">{{greeting}}</p>
              <p style="margin:0 0 18px;font-size:16px;line-height:1.75;color:#d3d8df;">{{intro}}</p>
              <p style="margin:0 0 18px;font-size:16px;line-height:1.75;color:#d3d8df;">{{problem}}</p>
              <p style="margin:0 0 18px;font-size:16px;line-height:1.75;color:#d3d8df;">{{solution}}</p>
              <div style="margin:0 0 18px;padding:18px 20px;border:1px solid rgba(241,208,143,0.18);border-radius:16px;background:#141a20;">
                <p style="margin:0 0 8px;font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#f1d08f;">{{custom_offer_title}}</p>
                <p style="margin:0;font-size:15px;line-height:1.75;color:#d3d8df;">{{custom_offer}}</p>
              </div>
              <div style="margin:26px 0 0;padding:18px 20px;border:1px solid rgba(241,208,143,0.28);border-radius:16px;background:#171d23;">
                <p style="margin:0;font-size:16px;line-height:1.75;color:#fff1cb;"><strong>{{cta}}</strong></p>
              </div>
              <p style="margin:16px 0 0;font-size:13px;line-height:1.75;color:#d3d8df;">{{discovery_call_text}}</p>
              <p style="margin:28px 0 0;font-size:15px;line-height:1.7;color:#d3d8df;">
                Hurmat bilan,<br>
                <strong>{{signature_name}}</strong><br>
                {{signature_role}}<br>
                {{signature_company}}
              </p>
              <p style="margin:16px 0 0;font-size:13px;line-height:1.7;color:#94a3b8;">
                Telefon: {{signature_phone}}<br>
                Website: <a href="{{signature_website}}" style="color:#f1d08f;text-decoration:none;">{{signature_website}}</a><br>
                Email: <a href="mailto:{{sender_email}}" style="color:#f1d08f;text-decoration:none;">{{sender_email}}</a>
              </p>
              <p style="margin:16px 0 0;font-size:12px;line-height:1.7;color:#7f8ea3;">{{unsubscribe_text}}</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
