from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pandas as pd

from botfactory.constants import LEAD_COLUMNS
from botfactory.models import GoogleSheetsConfig

try:
    import gspread
    from google.oauth2.service_account import Credentials as GoogleServiceAccountCredentials
except Exception:
    gspread = None
    GoogleServiceAccountCredentials = None

_GOOGLE_SHEETS_WORKSHEETS: dict[str, Any] = {}


def load_google_service_account_info(sheets_config: GoogleSheetsConfig) -> dict[str, Any]:
    if sheets_config.service_account_file:
        return json.loads(Path(sheets_config.service_account_file).read_text(encoding="utf-8"))
    if sheets_config.service_account_json_b64:
        decoded_json = base64.b64decode(sheets_config.service_account_json_b64.encode("utf-8")).decode("utf-8")
        return json.loads(decoded_json)
    raise RuntimeError("Google Sheets service account credentials are missing.")


def get_google_sheets_worksheet(sheets_config: GoogleSheetsConfig) -> Any:
    cache_key = f"{sheets_config.spreadsheet_id}:{sheets_config.worksheet_name}"
    cached_worksheet = _GOOGLE_SHEETS_WORKSHEETS.get(cache_key)
    if cached_worksheet is not None:
        return cached_worksheet
    if gspread is None or GoogleServiceAccountCredentials is None:
        raise RuntimeError("Google Sheets support requires gspread and google-auth.")

    service_account_info = load_google_service_account_info(sheets_config)
    credentials = GoogleServiceAccountCredentials.from_service_account_info(
        service_account_info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(sheets_config.spreadsheet_id)
    try:
        worksheet = spreadsheet.worksheet(sheets_config.worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=sheets_config.worksheet_name,
            rows=max(2000, len(LEAD_COLUMNS) * 100),
            cols=max(24, len(LEAD_COLUMNS) + 4),
        )
    _GOOGLE_SHEETS_WORKSHEETS[cache_key] = worksheet
    return worksheet


def load_leads_dataframe_from_google_sheets(sheets_config: GoogleSheetsConfig) -> pd.DataFrame | None:
    from goldenpages_scraper.utils import collapse_whitespace
    try:
        worksheet = get_google_sheets_worksheet(sheets_config)
        values = worksheet.get_all_values()
    except Exception:
        return None

    if not values:
        return pd.DataFrame(columns=LEAD_COLUMNS)

    header = [collapse_whitespace(str(item)) for item in values[0]]
    data_rows = values[1:]
    if not any(header):
        return pd.DataFrame(columns=LEAD_COLUMNS)

    normalized_rows: list[dict[str, str]] = []
    column_count = len(header)
    for row in data_rows:
        padded_row = list(row) + [""] * max(column_count - len(row), 0)
        normalized_rows.append({header[index]: padded_row[index] for index in range(column_count) if header[index]})
    return pd.DataFrame(normalized_rows)


def save_leads_dataframe_to_google_sheets(dataframe: pd.DataFrame, sheets_config: GoogleSheetsConfig) -> None:
    from botfactory.leads import ensure_lead_columns
    worksheet = get_google_sheets_worksheet(sheets_config)
    normalized_frame = ensure_lead_columns(dataframe).fillna("").astype(str)
    values = [list(normalized_frame.columns)] + normalized_frame.values.tolist()
    worksheet.clear()
    worksheet.update("A1", values, value_input_option="USER_ENTERED")
