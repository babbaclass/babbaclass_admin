#!/usr/bin/env python
# coding: utf-8

import os
import sys
import mysql.connector
from datetime import datetime, date, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import importlib.util
import config

# DB 설정
DB_HOST = "34.22.93.96"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "Fulfilled07!@"
DB_NAME = os.environ.get("MYSQL_DATABASE") or os.environ.get("DB_NAME") or "babba"

# 구글 시트 설정
TARGET_SPREADSHEET_ID = config.DB_SPREADSHEET_ID
# 오늘 날짜 기준으로 시트 이름 생성 (예: 2026년 01월_바스클)
TARGET_WORKSHEET_NAME = datetime.now().strftime("%Y년 %m월_바스클")

# 1_create_order_excel.py(모듈명이 숫자로 시작해 직접 import 불가)에서 send_google_chat_message 로드
script_dir = os.path.dirname(os.path.abspath(__file__))
order_excel_path = os.path.join(script_dir, "1_create_order_excel.py")
spec = importlib.util.spec_from_file_location("create_order_excel", order_excel_path)
create_order_excel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(create_order_excel)
send_google_chat_message = create_order_excel.send_google_chat_message

def normalize_date(value):
    """
    입력 값을 date 객체로 변환.
    - datetime/date 그대로 처리
    - 엑셀 시리얼 숫자(int/float)
    - 문자열: YYYY-MM-DD / YYYY.MM.DD / YYYY/MM/DD / MM-DD-YYYY / MM-DD-YY 등
    실패 시 None 반환
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value if not isinstance(value, datetime) else value.date()
    if isinstance(value, (int, float)):
        try:
            base = datetime(1899, 12, 30)  # Excel date origin
            return (base + timedelta(days=int(value))).date()
        except Exception:
            pass
    text = str(value).strip()
    if not text:
        return None
    text = text.split()[0].replace(".", "-").replace("/", "-")
    for fmt in ("%Y-%m-%d", "%y-%m-%d", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def authenticate_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(config.GOOGLE_SHEET_CREDENTIALS_FILE, scope)
    return gspread.authorize(creds)


def fetch_invoice_rows():
    """구글 시트에서 발송요청일이 오늘이고 ordernum/송장번호가 모두 있는 행만 추출"""
    client = authenticate_google_sheets()
    ws = client.open_by_key(TARGET_SPREADSHEET_ID).worksheet(TARGET_WORKSHEET_NAME)
    records = ws.get_all_records()

    if not records:
        print("시트에 데이터가 없습니다.")
        return []

    today = datetime.now().date()
    print(f"오늘 날짜: {today}")
    total = len(records)
    with_ord_inv = 0
    with_ord_inv_and_date = 0
    with_today = 0
    filtered = []
    for row in records:
        # 헤더에 공백/대소문자 차이가 있을 수 있으므로 키를 정규화
        row_norm = {str(k).strip().lower(): v for k, v in row.items()}
        ordernum = str(row_norm.get("ordernum", "")).strip()
        invoice = str(row_norm.get("송장번호", "")).strip()
        request_date = normalize_date(row_norm.get("발송요청일"))
        if ordernum and invoice:
            with_ord_inv += 1
            if request_date:
                with_ord_inv_and_date += 1
            if request_date == today:
                with_today += 1
        if ordernum and invoice and request_date == today:
            filtered.append({"ordernum": ordernum, "invoice": invoice})

    print(f"총 {total}건 중 ordernum/송장번호 모두 있음: {with_ord_inv}, 날짜 파싱 성공: {with_ord_inv_and_date}, 오늘 날짜 일치: {with_today}")
    if with_today != len(filtered):
        print("필터 제외된 행 예시 3건:")
        shown = 0
        for row in records:
            row_norm = {str(k).strip().lower(): v for k, v in row.items()}
            ordernum = str(row_norm.get("ordernum", "")).strip()
            invoice = str(row_norm.get("송장번호", "")).strip()
            request_date = normalize_date(row_norm.get("발송요청일"))
            if ordernum and invoice and request_date and request_date != today:
                print(f"- ordernum={ordernum}, invoice={invoice}, 발송요청일(raw)={row_norm.get('발송요청일')}, parsed={request_date}")
                shown += 1
            if shown >= 3:
                break

    print(f"시트에서 업데이트 대상 {len(filtered)}건을 찾았습니다. (발송요청일=오늘, 송장번호/ordernum 존재)")
    return filtered


def get_order_id_by_ordernum(ordernum):
    """ordernum으로 order 테이블에서 order_id(id) 조회"""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()
        query = "SELECT id FROM orders WHERE ordernum = %s LIMIT 1"
        cursor.execute(query, (ordernum,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return result[0]
        else:
            print(f"[주문 조회] ordernum={ordernum}에 해당하는 order를 찾을 수 없습니다.")
            return None
    except Exception as e:
        print(f"[주문 조회] Error: {str(e)}")
        return None


def register_tracking_for_orders(rows):
    """송장 번호가 있는 주문들에 대해 메이크샵에 송장 등록 후 (성공 목록, 실패 ordernum 목록) 반환"""
    if not rows:
        return [], []
    
    # 배포된 서버 URL 사용 (환경변수가 없으면 기본값)
    api_base_url = os.environ.get("API_SERVER_URL", "https://babba-api-1024083500192.asia-northeast3.run.app")
    api_url = f"{api_base_url}/api/makeshop/register-tracking"
    successful_rows = []
    failed_orders = []
    
    for row in rows:
        try:
            ordernum = str(row["ordernum"]).strip()
            delinum = str(row["invoice"]).strip()
            
            if not ordernum or not delinum:
                continue
            
            # ordernum으로 order 테이블에서 order_id 조회
            order_id = get_order_id_by_ordernum(ordernum)
            if not order_id:
                print(f"[송장 등록] ordernum={ordernum}: order_id를 찾을 수 없어 건너뜀")
                failed_orders.append(ordernum)
                continue
            
            payload = {
                "order_id": str(order_id),
                "delicom": "3",  # 기본값: CJ대한통운
                "delinum": delinum
            }
            
            response = requests.post(api_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    print(f"[송장 등록] Order {order_id} (ordernum={ordernum}): 성공 - {delinum}")
                    successful_rows.append(row)
                else:
                    print(f"[송장 등록] Order {order_id} (ordernum={ordernum}): 실패 - {result.get('message')}")
                    failed_orders.append(ordernum)
            else:
                print(f"[송장 등록] Order {order_id} (ordernum={ordernum}): API 오류 - HTTP {response.status_code}")
                failed_orders.append(ordernum)
                
        except Exception as e:
            print(f"[송장 등록] Error: {str(e)}")
            failed_orders.append(row.get("ordernum"))
    
    print(f"\n[송장 등록 결과] 성공: {len(successful_rows)}건, 실패: {len(failed_orders)}건")
    if failed_orders:
        print(f"실패한 주문(ordernum): {failed_orders}")
    
    return successful_rows, failed_orders


def update_send_number(rows):
    """DB의 order_items.send_number와 orders.send_number를 업데이트"""
    if not rows:
        return 0, []

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
        cleaned_rows = []
        for row in rows:
            ordernum = str(row["ordernum"]).strip()
            invoice = str(row["invoice"]).strip()
            if not ordernum or not invoice:
                continue
            cleaned_rows.append({"ordernum": ordernum, "invoice": invoice})

        if not cleaned_rows:
            print("업데이트할 정제된 데이터가 없습니다.")
            return 0, []

        data = [(r["invoice"], r["ordernum"]) for r in cleaned_rows]

        # order_items 테이블 업데이트는 현재 사용하지 않음
        # sql_items = "UPDATE order_items SET send_number = %s WHERE ordernum = %s"
        # cursor.executemany(sql_items, data)
        # items_updated = cursor.rowcount
        sql_orders = "UPDATE orders SET send_number = %s WHERE ordernum = %s"
        updated = 0
        not_found = []
        for inv, ord_no in data:
            cursor.execute(sql_orders, (inv, ord_no))
            if cursor.rowcount:
                updated += cursor.rowcount
            else:
                not_found.append(ord_no)

        conn.commit()
        print(f"orders에 {updated}건의 송장번호를 업데이트했습니다.")
        if not_found:
            print(f"업데이트되지 않은 ordernum {len(not_found)}건: {not_found}")
        return updated, not_found
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        rows = fetch_invoice_rows()
        total_candidates = len(rows)

        # 송장 등록 API 호출 (성공 목록과 실패 목록 반환)
        tracked_rows, failed_orders = register_tracking_for_orders(rows)
        # 송장 등록 성공한 rows만 DB 업데이트
        updated_count, not_found_orders = update_send_number(tracked_rows)

        # Google Chat 알림
        summary_lines = [
            "[송장 등록 요약]",
            f"- 대상 행: {total_candidates}건",
            f"- API 등록 성공: {len(tracked_rows)}건",
            f"- API 등록 실패: {len(failed_orders)}건"
            + (
                f" (예: {', '.join(failed_orders[:5])}" + (" 외 ..." if len(failed_orders) > 5 else "") + ")"
                if failed_orders
                else ""
            ),
            f"- DB 업데이트 성공: {updated_count}건",
            f"- DB 미존재 ordernum: {len(not_found_orders)}건"
            + (
                f" (예: {', '.join(not_found_orders[:5])}" + (" 외 ..." if len(not_found_orders) > 5 else "") + ")"
                if not_found_orders
                else ""
            ),
        ]
        chat_message = "\n".join(summary_lines)
        try:
            send_google_chat_message(chat_message, mention_user_id=getattr(config, "GOOGLE_CHAT_USER_ID", ""))
        except Exception as chat_exc:
            print(f"Google Chat 알림 실패: {chat_exc}")
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")


if __name__ == "__main__":
    main()
