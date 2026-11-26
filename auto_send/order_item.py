#!/usr/bin/env python
# coding: utf-8

import os
import sys
from datetime import datetime
import re
import mysql.connector
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import config

# MySQL 접속 정보
DB_HOST = "34.22.93.96"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "Fulfilled07!@"
# 데이터베이스 이름은 환경변수 MYSQL_DATABASE 또는 DB_NAME에서 읽으며, 기본값은 'babba' 입니다.
DB_NAME = os.environ.get("MYSQL_DATABASE") or os.environ.get("DB_NAME") or "babba"

# 구글 시트 정보
TARGET_SPREADSHEET_ID = config.DB_SPREADSHEET_ID
#TARGET_WORKSHEET_NAME = config.TARGET_SHEET_NAME
TARGET_WORKSHEET_NAME = "test"

# 추출 시작 ID
START_ID = 8646


def authenticate_google_sheets():
    """Google Sheets 클라이언트 인증"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(config.GOOGLE_SHEET_CREDENTIALS_FILE, scope)
    return gspread.authorize(creds)


def fetch_order_items_from_id(start_id: int):
    """order_items에서 start_id 이상 행의 주요 컬럼과 주문 정보(join) 조회"""
    query = """
        SELECT
            oi.id,
            oi.ordernum,
            oi.product_name,
            oi.basket_stock,
            o.order_date,
            o.sender,
            o.shipping_address
        FROM order_items oi
        LEFT JOIN `orders` o ON o.ordernum = oi.ordernum
        WHERE oi.id >= %s
    """

    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
        )
        cursor = conn.cursor()
        cursor.execute(query, (start_id,))
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "ordernum": row[1],
                "product_name": row[2],
                "basket_stock": row[3],
                "order_date": row[4],
                "sender": row[5],
                "shipping_address": row[6],
            }
            for row in rows
        ]
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def ensure_headers(ws, headers):
    """시트에 헤더가 없으면 작성"""
    current_headers = ws.row_values(1)
    if not current_headers or all(not h.strip() for h in current_headers):
        ws.update("A1", [headers])
        return
    # 기존 헤더가 있으면 그대로 둠


def append_orders_to_sheet(ordernums):
    """구글 시트에 order_items + 주문정보 행 추가"""
    client = authenticate_google_sheets()
    spreadsheet = client.open_by_key(TARGET_SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(TARGET_WORKSHEET_NAME)

    # 헤더 확인 및 필요한 컬럼 확보
    headers = worksheet.row_values(1)
    headers = headers if headers else []

    def find_col(name):
        name_norm = name.strip().lower()
        for idx, h in enumerate(headers, start=1):
            if h.strip().lower() == name_norm:
                return idx
        return None

    date_col = find_col("날짜")
    order_items_id_col = find_col("order_items_id")
    ordernum_col = find_col("ordernum")
    product_name_col = find_col("product_name")
    busu_col = find_col("부수")
    recipient_col = find_col("받는분")
    address_col = find_col("주소")

    updated_header = False
    if date_col is None:
        headers.append("날짜")
        date_col = len(headers)
        updated_header = True
    if order_items_id_col is None:
        headers.append("order_items_id")
        order_items_id_col = len(headers)
        updated_header = True
    if ordernum_col is None:
        headers.append("ordernum")
        ordernum_col = len(headers)
        updated_header = True
    if product_name_col is None:
        headers.append("product_name")
        product_name_col = len(headers)
        updated_header = True
    if busu_col is None:
        headers.append("부수")
        busu_col = len(headers)
        updated_header = True
    if recipient_col is None:
        headers.append("받는분")
        recipient_col = len(headers)
        updated_header = True
    if address_col is None:
        headers.append("주소")
        address_col = len(headers)
        updated_header = True

    if updated_header:
        worksheet.update("A1", [headers])

    if not ordernums:
        print("추가할 order_items 데이터가 없습니다.")
        return

    # 현재 데이터 행 수를 기준으로 추가할 시작 행 계산 (헤더 포함 길이 + 1)
    existing_rows = len(worksheet.get_all_values())
    start_row = existing_rows + 1 if existing_rows else 2  # 헤더가 없더라도 2행부터 데이터

    cells = []
    for i, item in enumerate(ordernums):
        row_idx = start_row + i
        order_date = item.get("order_date")
        order_date_str = ""
        if order_date:
            try:
                order_date_str = order_date.strftime("%Y-%m-%d")
            except AttributeError:
                # 문자열로 들어온 경우 앞부분 날짜만 사용
                order_date_str = str(order_date).strip()[:10]

        raw_address = item.get("shipping_address") or ""
        # 앞의 [숫자] 제거
        address_clean = re.sub(r"^\[[^\]]*\]\s*", "", str(raw_address)).strip()

        cells.append(gspread.Cell(row_idx, date_col, order_date_str))
        cells.append(gspread.Cell(row_idx, ordernum_col, item["ordernum"]))
        cells.append(gspread.Cell(row_idx, order_items_id_col, item["id"]))
        cells.append(gspread.Cell(row_idx, product_name_col, item["product_name"]))
        cells.append(gspread.Cell(row_idx, busu_col, item["basket_stock"]))
        cells.append(gspread.Cell(row_idx, recipient_col, item.get("sender") or ""))
        cells.append(gspread.Cell(row_idx, address_col, address_clean))

    worksheet.update_cells(cells, value_input_option="USER_ENTERED")
    print(f"{len(ordernums)}건을 시트 '{TARGET_WORKSHEET_NAME}'에 추가했습니다.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        ordernums = fetch_order_items_from_id(START_ID)
    except Exception as e:
        print(f"MySQL에서 데이터 조회 중 오류가 발생했습니다: {e}")
        return

    try:
        append_orders_to_sheet(ordernums)
    except Exception as e:
        print(f"구글 시트 업데이트 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    main()
