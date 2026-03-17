from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from botfactory.constants import LEAD_COLUMNS, HEALTHCARE_KEYWORDS, EDUCATION_KEYWORDS, LOGISTICS_KEYWORDS, BUSINESS_KEYWORDS
from botfactory.models import GoogleSheetsConfig, LeadBuildResult
from botfactory.utils import email_key, normalize_pipe_list, safe_float, safe_int
from botfactory.validation import is_usable_email_validation, validate_email_address


def contains_keyword(haystack: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.casefold() in haystack for keyword in keywords)


def infer_category(company_name: str, activity_types: str) -> str:
    haystack = f"{company_name} {activity_types}".casefold()
    if contains_keyword(haystack, HEALTHCARE_KEYWORDS):
        return "Tibbiyot"
    if contains_keyword(haystack, EDUCATION_KEYWORDS):
        return "O'quv markazi"
    if contains_keyword(haystack, LOGISTICS_KEYWORDS):
        return "Logistika"
    if contains_keyword(haystack, BUSINESS_KEYWORDS):
        return "General Business"
    return "Other"


def has_landline_phone(phone: str) -> bool:
    mobile_prefixes = {"33", "50", "55", "77", "88", "90", "91", "93", "94", "95", "97", "98", "99"}
    for raw_phone in normalize_pipe_list(phone):
        digits = "".join(character for character in raw_phone if character.isdigit())
        if digits.startswith("998"):
            digits = digits[3:]
        if len(digits) < 2:
            continue
        if digits[:2] not in mobile_prefixes:
            return True
    return False


def calculate_lead_score(
    *,
    website: str,
    phone: str,
    rating_value: float,
    rating_count: int,
) -> int:
    score = 0
    if website:
        score += 10
    if has_landline_phone(phone):
        score += 5
    if rating_value >= 4.5 and rating_count >= 2:
        score += 15
    return score


def ensure_lead_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    frame = dataframe.copy()
    for column in LEAD_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    frame["Status"] = frame["Status"].replace("", "New").fillna("New")
    frame["LastContacted"] = frame["LastContacted"].replace("", "None").fillna("None")
    frame["Lead Score"] = frame["Lead Score"].replace("", "0").fillna("0")
    frame["Rating Value"] = frame["Rating Value"].replace("", "0").fillna("0")
    frame["Rating Count"] = frame["Rating Count"].replace("", "0").fillna("0")
    frame["Language"] = frame["Language"].replace("", "uz").fillna("uz")
    return frame[LEAD_COLUMNS]


def normalize_lead_record(row: dict[str, Any]) -> dict[str, str]:
    from goldenpages_scraper.utils import collapse_whitespace
    normalized: dict[str, str] = {}
    for column in LEAD_COLUMNS:
        normalized[column] = collapse_whitespace(str(row.get(column, "")))
    normalized["Email"] = normalized["Email"].lower()
    normalized["Status"] = normalized["Status"] or "New"
    normalized["LastContacted"] = normalized["LastContacted"] or "None"
    return normalized


def build_leads_dataframe(
    scraped_df: pd.DataFrame,
    *,
    filter_priority_categories: bool,
    validate_email_mx: bool,
    default_language: str,
) -> LeadBuildResult:
    from goldenpages_scraper.utils import collapse_whitespace
    rows: list[dict[str, str]] = []
    rows_with_email = 0
    skipped_priority_rows = 0
    invalid_email_rows = 0

    for row in scraped_df.fillna("").to_dict(orient="records"):
        emails = normalize_pipe_list(row.get("emails", ""), emails_only=True)
        if not emails:
            continue

        rows_with_email += len(emails)
        company_name = collapse_whitespace(str(row.get("company_name", "")))
        activity_types = " | ".join(normalize_pipe_list(row.get("activity_types", "")))
        category = infer_category(company_name, activity_types)
        rating_value = safe_float(row.get("rating_value", 0.0))
        rating_count = safe_int(row.get("rating_count", 0))
        if filter_priority_categories and category == "Other":
            skipped_priority_rows += len(emails)
            continue

        phone = " | ".join(normalize_pipe_list(row.get("phones", "")))
        captured_at = datetime.now().isoformat(timespec="seconds")

        for email in emails:
            validation_status = validate_email_address(email, validate_email_mx=validate_email_mx)
            if not is_usable_email_validation(validation_status):
                invalid_email_rows += 1
                continue
            lead_score = calculate_lead_score(
                website=collapse_whitespace(str(row.get("website", ""))),
                phone=phone,
                rating_value=rating_value,
                rating_count=rating_count,
            )
            rows.append(
                {
                    "Company ID": collapse_whitespace(str(row.get("company_id", ""))),
                    "Company Name": company_name,
                    "Email": email,
                    "Phone": phone,
                    "Category": category,
                    "Activity Types": activity_types,
                    "Website": collapse_whitespace(str(row.get("website", ""))),
                    "Source URL": collapse_whitespace(str(row.get("source_url", ""))),
                    "Source Listing URL": collapse_whitespace(str(row.get("source_listing_url", ""))),
                    "Lead Captured At": captured_at,
                    "Validation Status": validation_status,
                    "Lead Score": str(lead_score),
                    "Rating Value": str(rating_value),
                    "Rating Count": str(rating_count),
                    "Language": default_language,
                    "Status": "New",
                    "LastContacted": "None",
                    "Sent At": "",
                    "Last Error": "",
                    "Template Used": "",
                }
            )

    dataframe = pd.DataFrame(rows, columns=LEAD_COLUMNS)
    if dataframe.empty:
        return LeadBuildResult(
            dataframe=ensure_lead_columns(dataframe),
            rows_with_email=rows_with_email,
            targeted_valid_rows=0,
            skipped_priority_rows=skipped_priority_rows,
            invalid_email_rows=invalid_email_rows,
        )

    dataframe["_email_key"] = dataframe["Email"].map(email_key)
    dataframe = dataframe[dataframe["_email_key"] != ""].drop_duplicates("_email_key", keep="first")
    dataframe = dataframe.drop(columns="_email_key").reset_index(drop=True)
    return LeadBuildResult(
        dataframe=ensure_lead_columns(dataframe),
        rows_with_email=rows_with_email,
        targeted_valid_rows=len(dataframe.index),
        skipped_priority_rows=skipped_priority_rows,
        invalid_email_rows=invalid_email_rows,
    )


def merge_with_existing_leads(
    leads_file: Path,
    new_df: pd.DataFrame,
    sheets_config: GoogleSheetsConfig | None = None,
) -> tuple[pd.DataFrame, int, int]:
    from goldenpages_scraper.utils import collapse_whitespace
    existing_df = load_leads_dataframe(leads_file, sheets_config)
    merged_rows: dict[str, dict[str, str]] = {}

    for row in existing_df.fillna("").to_dict(orient="records"):
        key = email_key(row.get("Email", ""))
        if key:
            merged_rows[key] = normalize_lead_record(row)

    new_count = 0
    updated_count = 0
    for row in new_df.fillna("").to_dict(orient="records"):
        normalized = normalize_lead_record(row)
        key = email_key(normalized.get("Email", ""))
        if not key:
            continue

        if key not in merged_rows:
            merged_rows[key] = normalized
            new_count += 1
            continue

        existing = merged_rows[key]
        changed = False
        for column in LEAD_COLUMNS:
            if column in {"Status", "LastContacted", "Sent At", "Last Error", "Template Used"}:
                continue
            incoming = collapse_whitespace(str(normalized.get(column, "")))
            if incoming and incoming != collapse_whitespace(str(existing.get(column, ""))):
                existing[column] = incoming
                changed = True

        if not collapse_whitespace(str(existing.get("Status", ""))):
            existing["Status"] = "New"
        if not collapse_whitespace(str(existing.get("LastContacted", ""))):
            existing["LastContacted"] = "None"
        merged_rows[key] = existing
        if changed:
            updated_count += 1

    final_df = pd.DataFrame(list(merged_rows.values()), columns=LEAD_COLUMNS)
    if final_df.empty:
        return ensure_lead_columns(final_df), new_count, updated_count

    final_df["_sent_rank"] = final_df["Status"].fillna("").astype(str).str.casefold().eq("sent").astype(int)
    final_df["_lead_score_sort"] = pd.to_numeric(final_df["Lead Score"], errors="coerce").fillna(0)
    final_df = (
        final_df.sort_values(
            ["_sent_rank", "_lead_score_sort", "Category", "Company Name", "Email"],
            ascending=[True, False, True, True, True],
        )
        .drop(columns=["_sent_rank", "_lead_score_sort"])
        .reset_index(drop=True)
    )
    return ensure_lead_columns(final_df), new_count, updated_count


def load_leads_dataframe(leads_file: Path, sheets_config: GoogleSheetsConfig | None = None) -> pd.DataFrame:
    if sheets_config:
        from botfactory.sheets import load_leads_dataframe_from_google_sheets
        sheets_frame = load_leads_dataframe_from_google_sheets(sheets_config)
        if sheets_frame is not None:
            return ensure_lead_columns(sheets_frame)
    if not leads_file.exists():
        return ensure_lead_columns(pd.DataFrame(columns=LEAD_COLUMNS))
    return ensure_lead_columns(pd.read_excel(leads_file, keep_default_na=False))


def save_leads_dataframe(
    dataframe: pd.DataFrame,
    leads_file: Path,
    sheets_config: GoogleSheetsConfig | None = None,
) -> None:
    leads_file.parent.mkdir(parents=True, exist_ok=True)
    normalized_frame = ensure_lead_columns(dataframe)
    normalized_frame.to_excel(leads_file, index=False)
    if sheets_config:
        from botfactory.sheets import save_leads_dataframe_to_google_sheets
        save_leads_dataframe_to_google_sheets(normalized_frame, sheets_config)


def load_email_template(template_file: Path) -> str:
    from botfactory.constants import DEFAULT_HTML_TEMPLATE
    if template_file.exists():
        return template_file.read_text(encoding="utf-8")
    return DEFAULT_HTML_TEMPLATE
