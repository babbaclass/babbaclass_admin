#!/usr/bin/env python
# coding: utf-8

import os
import sys
from datetime import date, datetime
from typing import List, Sequence

import gspread
from gspread.utils import rowcol_to_a1
import mysql.connector
from mysql.connector import Error
from oauth2client.service_account import ServiceAccountCredentials

import config

# DB settings
DB_HOST = "34.22.93.96"
DB_PORT = 3306
DB_USER = os.environ.get("DB_USER") or "babbasmart"
DB_PASSWORD = "Babba123@"
DB_NAME = os.environ.get("MYSQL_DATABASE") or os.environ.get("DB_NAME") or "babba"

# 주문 구분용 키 컬럼/테이블
ORDER_KEY_COLUMN = os.environ.get("ORDER_KEY_COLUMN") or "ordernum"
ORDER_ITEM_TABLE = os.environ.get("ORDER_ITEM_TABLE") or "order_items"

# Google Sheet settings
TARGET_SPREADSHEET_ID = config.DB_SPREADSHEET_ID
TARGET_WORKSHEET_NAME = "전체매출_raw"


def get_db_connection():
    """Create and return MySQL connection."""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


def fetch_orders() -> List[Sequence]:
    """
    주문/상품/적립금 집계:
    - 총판매액: order_items.sell_price 합계
    - 사용적립금: orders.used_reserve 합계
    - total_amount = 총판매액 - 사용적립금
    사용자/회사 매핑은 제외하고, 관련 컬럼은 NULL로 반환한다.
    """
    query = f"""
        WITH filtered_orders AS (
            SELECT {ORDER_KEY_COLUMN}
            FROM orders
            WHERE pay_status = 'Y'
              AND order_status IN ('Y', 'S')
        ),
        item_totals AS (
            SELECT oi.{ORDER_KEY_COLUMN} AS order_key, SUM(oi.sell_price) AS total_sell_price
            FROM {ORDER_ITEM_TABLE} oi
            JOIN filtered_orders fo ON fo.{ORDER_KEY_COLUMN} = oi.{ORDER_KEY_COLUMN}
            GROUP BY oi.{ORDER_KEY_COLUMN}
        ),
        reserve_totals AS (
            SELECT o.{ORDER_KEY_COLUMN} AS order_key, SUM(o.used_reserve) AS total_used_reserve
            FROM orders o
            JOIN filtered_orders fo ON fo.{ORDER_KEY_COLUMN} = o.{ORDER_KEY_COLUMN}
            GROUP BY o.{ORDER_KEY_COLUMN}
        )
        SELECT
            o.id,
            o.order_date,
            o.sender,
            o.phone,
            COALESCE(it.total_sell_price, 0) - COALESCE(rt.total_used_reserve, 0) AS total_amount,
            o.member_id,
            o.email,
            NULL AS role_id,
            NULL AS company_id,
            NULL AS user_id,
            NULL AS user_name,
            NULL AS role_name,
            NULL AS company_name
        FROM orders o
        JOIN filtered_orders fo ON fo.{ORDER_KEY_COLUMN} = o.{ORDER_KEY_COLUMN}
        LEFT JOIN item_totals it ON it.order_key = o.{ORDER_KEY_COLUMN}
        LEFT JOIN reserve_totals rt ON rt.order_key = o.{ORDER_KEY_COLUMN}
        ORDER BY o.order_date DESC
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        print(f"Fetched {len(rows)} rows from orders.")
        return rows
    except Error as e:
        print(f"DB error: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


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
        worksheet = spreadsheet.add_worksheet(title=title, rows="1000", cols="20")
        print(f"Created worksheet '{title}'.")
        return worksheet


def serialize_row(row: Sequence) -> List[str]:
    """Convert DB row values to strings for Sheets."""
    serialized = []
    for value in row:
        if isinstance(value, datetime):
            serialized.append(value.strftime("%Y-%m-%d %H:%M:%S"))
        elif isinstance(value, date):
            serialized.append(value.strftime("%Y-%m-%d"))
        else:
            serialized.append("" if value is None else str(value))
    return serialized


def upload_orders_to_sheet(rows: List[Sequence]):
    """Upload orders data to target Google Sheet."""
    client = authenticate_google_sheets()
    spreadsheet = client.open_by_key(TARGET_SPREADSHEET_ID)
    worksheet = ensure_worksheet(spreadsheet, TARGET_WORKSHEET_NAME)

    memo_header = "비고"
    headers = [
        "id",
        "order_date",
        "sender",
        "phone",
        "total_amount",
        "member_id",
        "email",
        "role_id",
        "company_id",
        "user_id",
        "user_name",
        "role_name",
        "company_name",
        memo_header,
    ]
    serialized_rows = [serialize_row(row) for row in rows]

    def normalize_row(row: List[str]) -> List[str]:
        """Pad or trim a row to match headers length."""
        norm = list(row) + [""] * max(0, len(headers) - len(row))
        return norm[: len(headers)]

    def map_row_to_headers(row: List[str], source_headers_lower: List[str]) -> List[str]:
        """Rebuild a row using the target headers order."""
        source_map = {}
        for idx, key in enumerate(source_headers_lower):
            if idx < len(row):
                source_map[key] = row[idx]
        return [source_map.get(h.lower(), "") for h in headers]

    # Collect existing values to dedupe by ID.
    existing_values = worksheet.get_all_values()
    header_has_id = False
    id_idx = 0
    combined_by_id = {}

    if existing_values:
        header_lower = [cell.strip().lower() for cell in existing_values[0]]
        if "id" in header_lower:
            header_has_id = True
            id_idx = header_lower.index("id")
            for row in existing_values[1:]:
                if len(row) > id_idx and row[id_idx]:
                    combined_by_id[row[id_idx]] = map_row_to_headers(row, header_lower)

    # Merge new rows if ID not already present.
    if header_has_id:
        for row in serialized_rows:
            if row and row[0] and row[0] not in combined_by_id:
                combined_by_id[row[0]] = normalize_row(row)
        combined_rows = list(combined_by_id.values())
    else:
        # No header/ID present: start fresh with all rows.
        combined_rows = [normalize_row(row) for row in serialized_rows]

    # Sort by id (column 0) descending so highest/newest id on top.
    def sort_key(row: List[str]):
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return -1

    combined_rows_sorted = sorted(combined_rows, key=sort_key, reverse=True)
    values = [headers] + combined_rows_sorted

    worksheet.clear()
    if values:
        worksheet.update(range_name="A1", values=values, value_input_option="USER_ENTERED")
    updated_count = len(combined_rows_sorted)
    print(f"Updated sheet '{TARGET_WORKSHEET_NAME}' with {updated_count} data rows (sorted by order_date desc).")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_cell = rowcol_to_a1(1, len(headers) + 1)
    worksheet.update(
        range_name=timestamp_cell, values=[[now_str]], value_input_option="USER_ENTERED"
    )
    print(f"Wrote last-updated timestamp to {timestamp_cell}: {now_str}")
    print(f"Updated sheet '{TARGET_WORKSHEET_NAME}' with {updated_count} data rows.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    rows = fetch_orders()
    if not rows:
        print("No data fetched; sheet not updated.")
        return
    upload_orders_to_sheet(rows)


if __name__ == "__main__":
    main()
