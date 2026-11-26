#!/usr/bin/env python
# coding: utf-8

import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Sequence, Tuple

import gspread
from gspread import Worksheet
from gspread.exceptions import APIError
from oauth2client.service_account import ServiceAccountCredentials

import config

# Sheet settings
SOURCE_WORKSHEET_NAME = "전체매출_raw"
APPLY_NUMBER_FORMAT = False  # 형식 적용을 끄면 write 요청을 줄일 수 있음
SLEEP_BETWEEN_WRITES = 2.0  # 요청 사이 대기(초)로 quota 429 완화


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


def build_worksheet_cache(spreadsheet) -> Dict[str, Worksheet]:
    """Fetch worksheet metadata once and build a title->worksheet map."""
    cache = {}
    for ws in spreadsheet.worksheets():
        cache[ws.title] = ws
    return cache


def ensure_worksheet_cached(spreadsheet, cache: Dict[str, Worksheet], title: str):
    """Return worksheet; create if missing, updating cache."""
    if title in cache:
        return cache[title]
    worksheet = spreadsheet.add_worksheet(title=title, rows="2000", cols="30")
    cache[title] = worksheet
    print(f"Created worksheet '{title}'.")
    # Small delay to avoid burst on creation.
    time.sleep(0.5)
    return worksheet


def find_column_indexes(headers: Sequence[str]) -> Dict[str, int]:
    """Locate required column indexes by header name (case-insensitive)."""
    header_map = {name.strip().lower(): idx for idx, name in enumerate(headers)}
    required = ["company_name", "sender", "role_name", "order_date", "total_amount"]
    missing = [name for name in required if name not in header_map]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    return {name: header_map[name] for name in required}


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


def gather_company_data(
    rows: Sequence[Sequence[str]], idx: Dict[str, int]
) -> Dict[str, Dict[str, object]]:
    """
    Group rows by company_name.
    Each entry contains:
        rows: list of data rows
        months: sorted list of YYYY-MM
        totals: {(sender, month): sum_price}
        roles: {sender: role_name_or_미지정}
    """
    companies: Dict[str, Dict[str, object]] = {}
    for row in rows[1:]:
        if len(row) <= max(idx.values()):
            continue
        company = row[idx["company_name"]].strip() or "미지정"
        sender = row[idx["sender"]].strip()
        role = row[idx["role_name"]].strip() or "미지정"
        month = to_month(row[idx["order_date"]])
        price = to_price(row[idx["total_amount"]])
        if not sender or not month:
            continue

        entry = companies.setdefault(
            company, {"rows": [], "months_set": set(), "totals": {}, "roles": {}}
        )
        entry["rows"].append(row)
        entry["months_set"].add(month)

        key = (sender, month)
        entry["totals"][key] = entry["totals"].get(key, 0.0) + price

        # Keep first non-empty role; default is already "미지정".
        if sender not in entry["roles"] or entry["roles"][sender] == "미지정":
            entry["roles"][sender] = role or "미지정"

    # finalize months to sorted list
    for data in companies.values():
        data["months"] = sorted(
            m for m in data["months_set"] if re.match(r"^\d{4}-\d{2}$", m)
        )
    return companies


def build_rows_for_company(
    company_name: str,
    data: Dict[str, object],
):
    months: List[str] = data["months"]
    totals: Dict[Tuple[str, str], float] = data["totals"]
    roles: Dict[str, str] = data["roles"]

    senders = sorted(set(roles.keys()))

    header = ["원장", "구분"] + months
    geisha_rows = []
    other_rows = []

    for sender in senders:
        role = roles.get(sender, "미지정") or "미지정"
        row_values = [sender, role]
        for month in months:
            val = totals.get((sender, month), 0.0)
            row_values.append(val if val != 0 else "")
        if role == "지사장":
            geisha_rows.append(row_values)
        else:
            other_rows.append(row_values)

    # Sort 지사장 rows by sender, others by sender
    geisha_rows.sort(key=lambda r: r[0])
    other_rows.sort(key=lambda r: r[0])

    return [header] + geisha_rows + other_rows


def update_company_sheet(spreadsheet, company_name: str, values: List[List[object]]):
    """Create/clear/update sheet for a company."""
    title = company_name or "미지정"
    worksheet = ensure_worksheet_cached(spreadsheet, WORKSHEET_CACHE, title)
    try:
        existing_values = worksheet.get_all_values()
        existing_rows = len(existing_values)
    except Exception:
        existing_values = []
        existing_rows = 0

    # Pad with blanks to overwrite old data if new dataset is smaller.
    cols = len(values[0]) if values else 1
    if existing_rows > len(values):
        values = values + [[""] * cols for _ in range(existing_rows - len(values))]

    # 변경 없을 때 건너뛰기 (shape 맞춰 비교)
    def normalize(data: List[List[object]], rows: int, cols: int) -> List[List[str]]:
        norm = []
        for row in data:
            r = list(row) + [""] * max(0, cols - len(row))
            norm.append(r[:cols])
        if len(norm) < rows:
            norm += [[""] * cols for _ in range(rows - len(norm))]
        return norm[:rows]

    rows_to_compare = max(len(values), existing_rows)
    norm_new = normalize(values, rows_to_compare, cols)
    norm_old = normalize(existing_values, rows_to_compare, cols)

    if norm_new == norm_old:
        print(f"Skip '{title}' (no changes).")
        time.sleep(SLEEP_BETWEEN_WRITES)
        return

    retries = 2
    for attempt in range(retries + 1):
        try:
            worksheet.update(
                range_name="A1", values=values, value_input_option="USER_ENTERED"
            )
            break
        except APIError as err:
            if "429" in str(err) and attempt < retries:
                wait = 2 * (attempt + 1)
                print(f"Write quota hit for '{title}', retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise
    apply_number_format(worksheet, len(values), cols)
    # Small delay to avoid hitting write quota.
    time.sleep(SLEEP_BETWEEN_WRITES)
    print(f"Updated sheet '{title}' with {len(values) - 1} rows.")


def apply_number_format(worksheet, row_count: int, col_count: int):
    """Format numeric cells (C2:...) with thousand separators."""
    if not APPLY_NUMBER_FORMAT:
        return
    if row_count < 2 or col_count < 3:
        return
    try:
        sheet_id = worksheet._properties.get("sheetId")
        body = {
            "requests": [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,  # row 2
                            "endRowIndex": row_count,
                            "startColumnIndex": 2,  # col C (month columns start)
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
        try:
            worksheet.spreadsheet.batch_update(body)
        except APIError as err:
            if "429" in str(err):
                time.sleep(2)
                worksheet.spreadsheet.batch_update(body)
            else:
                raise
    except Exception as e:
        print(f"Formatting warning: {e}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    client = authenticate_google_sheets()
    spreadsheet = client.open_by_key(config.DB_SPREADSHEET_ID)
    global WORKSHEET_CACHE
    WORKSHEET_CACHE = build_worksheet_cache(spreadsheet)

    source_ws = WORKSHEET_CACHE.get(SOURCE_WORKSHEET_NAME)
    if not source_ws:
        source_ws = ensure_worksheet_cached(spreadsheet, WORKSHEET_CACHE, SOURCE_WORKSHEET_NAME)
    rows = source_ws.get_all_values()
    if not rows:
        print("Source sheet is empty; nothing to do.")
        return

    try:
        idx = find_column_indexes(rows[0])
    except ValueError as e:
        print(str(e))
        return

    companies = gather_company_data(rows, idx)
    if not companies:
        print("No company data found; nothing to update.")
        return

    for company_name, data in companies.items():
        values = build_rows_for_company(company_name, data)
        update_company_sheet(spreadsheet, company_name, values)


if __name__ == "__main__":
    main()
