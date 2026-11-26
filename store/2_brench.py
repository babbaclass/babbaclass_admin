#!/usr/bin/env python
# coding: utf-8

import re
import sys
from datetime import datetime
from typing import Dict, List, Sequence, Set, Tuple

import gspread
from oauth2client.service_account import ServiceAccountCredentials

import config

# Sheet settings
SOURCE_WORKSHEET_NAME = "전체매출_raw"
TARGET_WORKSHEET_NAME = "지사별_매출분석"


def authenticate_google_sheets():
    """Authorize and return gspread client."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        config.GOOGLE_SHEET_CREDENTIALS_FILE, scope
    )
    client = gspread.authorize(creds)
    print("Authenticated Google Sheets.")
    return client


def ensure_worksheet(spreadsheet, title: str):
    """Return worksheet; create if missing."""
    try:
        worksheet = spreadsheet.worksheet(title)
        print(f"Found worksheet '{title}'.")
        return worksheet
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=title, rows="1000", cols="10")
        print(f"Created worksheet '{title}'.")
        return worksheet


def extract_company_names(worksheet) -> List[str]:
    """Extract unique company_name values from the source sheet."""
    rows = worksheet.get_all_values()
    if not rows:
        print("Source sheet is empty.")
        return []

    headers = rows[0]
    try:
        company_idx = next(
            idx for idx, name in enumerate(headers) if name.strip().lower() == "company_name"
        )
    except StopIteration:
        print("No 'company_name' column found in source sheet.")
        return []

    seen: Set[str] = set()
    unique_names: List[str] = []
    for row in rows[1:]:
        if company_idx < len(row):
            value = row[company_idx].strip()
            if value and value not in seen:
                seen.add(value)
                unique_names.append(value)

    print(f"Found {len(unique_names)} unique company_name values.")
    return unique_names


def extract_months(rows: Sequence[Sequence[str]], date_idx: int) -> List[str]:
    """Extract unique order_date months (YYYY-MM) sorted ascending."""
    if not rows:
        print("Source sheet is empty.")
        return []

    def to_month(cell: str):
        cell = cell.strip()
        if not cell:
            return None
        # Common ISO-like formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(cell, fmt).strftime("%Y-%m")
            except ValueError:
                continue
        # Fallback: detect leading YYYY-MM pattern
        m = re.match(r"(\d{4}-\d{2})", cell)
        return m.group(1) if m else None

    months_set: Set[str] = set()
    for row in rows[1:]:
        if date_idx < len(row):
            month = to_month(row[date_idx])
            if month:
                months_set.add(month)

    months = sorted(m for m in months_set if re.match(r"^\d{4}-\d{2}$", m))
    print(f"Found {len(months)} unique order_date months.")
    return months


def compute_totals(
    rows: Sequence[Sequence[str]],
    company_idx: int,
    date_idx: int,
    price_idx: int,
) -> Dict[Tuple[str, str], float]:
    """Sum total_amount by (company_name, YYYY-MM)."""
    totals: Dict[Tuple[str, str], float] = {}

    def to_month(cell: str) -> str:
        cell = cell.strip()
        if not cell:
            return ""
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(cell, fmt).strftime("%Y-%m")
            except ValueError:
                continue
        m = re.match(r"(\d{4}-\d{2})", cell)
        return m.group(1) if m else ""

    def to_price(cell: str) -> float:
        cell = cell.replace(",", "").strip()
        try:
            return float(cell)
        except ValueError:
            return 0.0

    for row in rows[1:]:
        if company_idx < len(row) and date_idx < len(row) and price_idx < len(row):
            company = row[company_idx].strip()
            month = to_month(row[date_idx])
            if not company or not month:
                continue
            price = to_price(row[price_idx])
            key = (company, month)
            totals[key] = totals.get(key, 0.0) + price

    return totals


def write_company_names(
    worksheet, names: List[str], months: List[str], totals: Dict[Tuple[str, str], float]
):
    """Write header, company names, and monthly totals to target sheet."""
    header = ["지사"] + months
    values = [header]
    for name in names:
        row_values = [name]
        for month in months:
            val = totals.get((name, month), "")
            row_values.append(val if val != 0 else "")
        values.append(row_values)
    worksheet.clear()
    worksheet.update(
        range_name="A1", values=values, value_input_option="USER_ENTERED"
    )
    apply_number_format(worksheet, len(values), len(header))
    print(
        f"Updated '{TARGET_WORKSHEET_NAME}' with {len(names)} names, {len(months)} month columns, and total_amount sums."
    )


def apply_number_format(worksheet, row_count: int, col_count: int):
    """Format numeric cells (B2:...) with thousand separators."""
    if row_count < 2 or col_count < 2:
        return
    try:
        sheet_id = worksheet._properties["sheetId"]
        body = {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,  # row 2
                            "endRowIndex": row_count,
                            "startColumnIndex": 1,  # col B
                            "endColumnIndex": col_count,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "numberFormat": {"type": "NUMBER", "pattern": "#,##0"}
                            }
                        },
                        "fields": "userEnteredFormat.numberFormat",
                    }
                }
            ]
        }
        worksheet.spreadsheet.batch_update(body)
    except Exception as e:
        print(f"Formatting warning: {e}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    client = authenticate_google_sheets()
    spreadsheet = client.open_by_key(config.DB_SPREADSHEET_ID)

    source_ws = ensure_worksheet(spreadsheet, SOURCE_WORKSHEET_NAME)
    rows = source_ws.get_all_values()
    if not rows:
        print("Source sheet is empty; nothing to do.")
        return

    headers = rows[0]
    try:
        company_idx = next(
            idx for idx, name in enumerate(headers) if name.strip().lower() == "company_name"
        )
        date_idx = next(
            idx for idx, name in enumerate(headers) if name.strip().lower() == "order_date"
        )
        price_idx = next(
            idx for idx, name in enumerate(headers) if name.strip().lower() == "total_amount"
        )
    except StopIteration:
        print("Required columns not found in source sheet (need company_name, order_date, total_amount).")
        return

    company_names = extract_company_names(source_ws)
    months = extract_months(rows, date_idx)
    totals = compute_totals(rows, company_idx, date_idx, price_idx)

    target_ws = ensure_worksheet(spreadsheet, TARGET_WORKSHEET_NAME)
    write_company_names(target_ws, company_names, months, totals)


if __name__ == "__main__":
    main()
