#!/usr/bin/env python
# coding: utf-8

import os
import sys
import json
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from email.header import Header # Header 모듈 임포트
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from urllib import request, error
from datetime import datetime
import config

def authenticate_google_sheets():
    """Google Sheets API 인증을 수행하고 클라이언트 객체를 반환합니다."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(config.GOOGLE_SHEET_CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        print("Google Sheets 인증 성공.")
        return client
    except Exception as e:
        print(f"오류: Google Sheets 인증 실패: {e}")
        return None

def send_email_with_attachment(file_path, recipient_emails, subject, body):
    """
    지정된 엑셀 파일을 첨부하여 이메일을 발송합니다.
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = config.EMAIL_ADDRESS
        msg['To'] = ", ".join(recipient_emails)
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # 파일 첨부
        attachment = open(file_path, 'rb')
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        from email import encoders
        encoders.encode_base64(part)
        
        # 한글 파일명 인코딩 처리
        encoded_filename = Header(os.path.basename(file_path), 'utf-8').encode()
        part.add_header('Content-Disposition', 'attachment', filename=encoded_filename)
        msg.attach(part)
        attachment.close()

        # SMTP 서버 연결 및 이메일 발송
        print(f"이메일 발송을 위해 {config.SMTP_SERVER}:{config.SMTP_PORT}에 연결 중...")
        server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
        server.starttls() # TLS 보안 시작
        server.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(config.EMAIL_ADDRESS, recipient_emails, text)
        server.quit()

        print(f"엑셀 파일 '{os.path.basename(file_path)}'이(가) 이메일로 성공적으로 발송되었습니다.")
        print(f"수신자: {', '.join(recipient_emails)}")
        print(f"제목: {subject}")
    except smtplib.SMTPAuthenticationError:
        print("오류: 이메일 인증에 실패했습니다. 앱 비밀번호가 올바른지 확인해주세요.")
    except Exception as e:
        print(f"오류: 이메일 발송 중 문제가 발생했습니다: {e}")
        if "authentication" in str(e).lower():
            print("이메일 인증 오류일 수 있습니다. Gmail의 경우 앱 비밀번호를 사용해야 합니다.")


def send_google_chat_message(message, mention_user_id=None):
    """Send a text message to Google Chat via an incoming webhook."""
    webhook_url = getattr(config, "GOOGLE_CHAT_WEBHOOK_URL", None) or os.environ.get("GOOGLE_CHAT_WEBHOOK_URL")
    if not webhook_url:
        print("Google Chat webhook URL is not configured; chat notification skipped.")
        return False

    text_body = message
    if mention_user_id:
        # Google Chat mention format via webhook
        text_body = f"<users/{mention_user_id}> {message}"

    payload = json.dumps({"text": text_body}, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req) as resp:
            if 200 <= resp.status < 300:
                print("Google Chat message sent.")
                return True
            print(f"Failed to send Google Chat message: HTTP {resp.status}")
    except error.URLError as e:
        print(f"Error sending Google Chat message: {e}")
    return False


def save_df_as_xls(df, file_path):
    """
    pandas 2.x는 xlwt 엔진을 기본 지원하지 않으므로, xlwt로 직접 .xls를 생성하는 헬퍼.
    """
    try:
        import xlwt
    except ImportError:
        raise RuntimeError("xlwt 패키지가 설치되어 있지 않습니다.")

    wb = xlwt.Workbook()
    ws = wb.add_sheet("Sheet1")

    # 헤더 작성
    for col_idx, col_name in enumerate(df.columns):
        ws.write(0, col_idx, col_name)

    # 데이터 작성
    for row_idx, (_, row) in enumerate(df.iterrows(), start=1):
        for col_idx, col_name in enumerate(df.columns):
            ws.write(row_idx, col_idx, row[col_name])

    wb.save(file_path)
    return file_path


def create_daily_order_excel(client):
    """
    구글 시트에서 오늘 날짜의 배송 목록을 가져와 엑셀 파일로 저장합니다.
    """
    try:
        # 1. 구글 스프레드시트 및 워크시트 열기
        spreadsheet = client.open_by_key(config.DB_SPREADSHEET_ID)
        worksheet_name = config.TARGET_SHEET_NAME
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            print(f"'{worksheet_name}' 워크시트를 찾았습니다.")
        except gspread.WorksheetNotFound:
            print(f"오류: '{worksheet_name}' 워크시트를 찾을 수 없습니다.")
            return

        # 2. 시트 데이터 가져오기 및 DataFrame 변환 (원본 행번호 포함)
        all_values = worksheet.get_all_values()
        if len(all_values) < 2:
            print("시트에 데이터가 없습니다.")
            return

        headers = all_values[0]
        rows = all_values[1:]
        data_with_rownum = []
        for idx, row in enumerate(rows, start=2):  # 실제 시트 행 번호 (헤더가 1행)
            row_dict = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
            row_dict["_rownum"] = idx
            data_with_rownum.append(row_dict)

        sheet_df = pd.DataFrame(data_with_rownum)
        print(f"구글 시트에서 총 {len(sheet_df)}건의 데이터를 불러왔습니다.")

        # 3. 발송요청일/재고유무가 비어 있는 데이터 필터링
        target_date_obj = datetime.strptime(config.TARGET_DATE, '%Y-%m-%d')
        target_date_str = target_date_obj.strftime('%Y-%m-%d') # 파일명/메일에 사용

        def is_blank(value):
            if pd.isna(value):
                return True
            return str(value).strip() == ""

        required_filter_cols = ['발송요청일', '재고유무', '날짜', '도서명']
        missing_filter_cols = [col for col in required_filter_cols if col not in sheet_df.columns]
        if missing_filter_cols:
            print(f"필터링에 필요한 컬럼이 없습니다: {missing_filter_cols}")
            return

        pending_orders_df = sheet_df[
            sheet_df['발송요청일'].apply(is_blank)
            & sheet_df['재고유무'].apply(is_blank)
            & (~sheet_df['날짜'].apply(is_blank))
            & (~sheet_df['도서명'].apply(is_blank))
        ].copy()

        if pending_orders_df.empty:
            print("발송요청일/재고유무 비어 있고 도서명이 채워진 주문 데이터가 없습니다.")
            return

        print(f"발송요청일·재고유무 미기재 주문 {len(pending_orders_df)}건을 찾았습니다.")

        # 본사 출고 주문은 ISBN 검사 및 해피데이 발주 대상에서 제외합니다.
        if '비고2' in pending_orders_df.columns:
            headquarters_remarks = pending_orders_df['비고2'].fillna('').astype(str).str.replace(r'\s+', '', regex=True)
            headquarters_mask = headquarters_remarks.isin(['본사출고', '본사츌고'])
            headquarters_count = int(headquarters_mask.sum())
            if headquarters_count:
                # 본사 출고도 처리 날짜는 기록하되 해피데이 엑셀에는 포함하지 않습니다.
                request_col_idx = sheet_df.columns.get_loc('발송요청일') + 1
                headquarters_updates = [
                    gspread.Cell(int(row['_rownum']), request_col_idx, target_date_str)
                    for _, row in pending_orders_df.loc[headquarters_mask].iterrows()
                ]
                worksheet.update_cells(headquarters_updates)
                pending_orders_df = pending_orders_df.loc[~headquarters_mask].copy()
                print(f"비고2가 '본사 출고'인 주문 {headquarters_count}건을 해피데이 발주 대상에서 제외했습니다.")
                print(f"본사 출고 주문의 '발송요청일'을 {target_date_str}로 {headquarters_count}건 업데이트했습니다.")

        if pending_orders_df.empty:
            print("본사 출고 주문을 제외한 해피데이 발주 대상이 없어 엑셀 생성 및 발송을 건너뜁니다.")
            return

        isbn_column_candidates = [col for col in pending_orders_df.columns if "ISBN" in str(col)]
        isbn_column_name = isbn_column_candidates[0] if isbn_column_candidates else "ISBN\n(vlookup 적용중)"
        if isbn_column_name not in pending_orders_df.columns:
            print(f"ISBN 컬럼({isbn_column_name})을 찾을 수 없어 엑셀 생성을 중단합니다.")
            return

        # '#NA'/'#N/A'/NA 등 오류 값을 모두 감지
        def is_isbn_missing(val):
            if pd.isna(val):
                return True
            v = str(val).strip().upper()
            return v in {"#NA", "#N/A", "NA"} or v.startswith("#N/A")

        isbn_missing_mask = pending_orders_df[isbn_column_name].apply(is_isbn_missing)
        missing_isbn_count = int(isbn_missing_mask.sum())
        if missing_isbn_count > 0:
            chat_message = f"도서 정보에 ISBN이 누락된 것 {missing_isbn_count}건 있습니다"
            send_google_chat_message(chat_message, mention_user_id=getattr(config, "GOOGLE_CHAT_USER_ID", ""))
            print("ISBN 누락 건이 있어 엑셀 생성을 건너뜁니다.")
            return

        # 선택된 건의 '발송요청일'을 오늘 날짜로 시트에 기록 (추출 대상 행만)
        request_col_idx = sheet_df.columns.get_loc('발송요청일') + 1  # gspread는 1-based
        updates = [
            gspread.Cell(int(row["_rownum"]), request_col_idx, target_date_str)
            for _, row in pending_orders_df.iterrows()
        ]
        if updates:
            worksheet.update_cells(updates)
            print(f"'발송요청일'을 오늘 날짜({target_date_str})로 {len(updates)}건 업데이트했습니다.")

        # 4. 요청된 규칙에 따라 엑셀 파일용 DataFrame 생성
        output_df = pd.DataFrame()

        # '전화번호': 구글 시트 '전화번호'에서 '-', 맨 앞 '0' 제거
        # .astype(str)으로 모든 값을 문자열로 변환하여 오류 방지
        def format_phone_number(phone):
            phone_str = str(phone).replace('-', '')
            if phone_str.startswith('0'):
                return phone_str[1:]
            return phone_str
        output_df['전화번호'] = pending_orders_df['전화번호'].apply(format_phone_number)

        output_df['받는분'] = pending_orders_df['받는분']
        output_df['연락처'] = pending_orders_df['전화번호'] # '연락처'는 구글 시트 '전화번호' 원본
        output_df['주소'] = pending_orders_df['주소']
        output_df['도서명'] = pending_orders_df['도서명']
        # ISBN을 문자열로 변환하여 엑셀에서 지수 표기법으로 표시되는 것을 방지
        output_df['ISBN'] = pending_orders_df[isbn_column_name].astype(str)
        output_df['부수'] = pending_orders_df['부수']
        output_df['공급률'] = '0' # 고정값
        output_df['증정도장'] = 'N' # 고정값
        output_df['비고'] = pending_orders_df['비고']

        print("요청된 규칙에 따라 엑셀 데이터를 성공적으로 가공했습니다.")

        # 5. 엑셀 파일로 저장
        # 파일명 형식: 택배발주사내_MMDD_바스클.xls
        file_date = target_date_obj.strftime('%m%d')
        output_filename = f"택배발주사내_{file_date}_바스클.xls"

        # 스크립트가 있는 폴더/send_excel에 저장
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, "send_excel")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)

        try:
            # pandas 2.x 이상에서는 xlwt 엔진이 기본 포함되지 않으므로 직접 xlwt로 저장
            save_df_as_xls(output_df, output_path)
        except Exception as save_exc:
            print(f".xls 형식 저장 실패 (xlwt 필요): {save_exc}")
            return
        print(f"\n엑셀 파일이 성공적으로 생성되었습니다: {output_path}")

        # 6. 생성된 엑셀 파일을 이메일로 발송
        email_subject = f"[{target_date_obj.strftime('%Y-%m-%d')}]_바스클 발주 내용"
        email_body = f"{target_date_obj.strftime('%Y-%m-%d')}의 주문건은 {len(pending_orders_df)}건 입니다."
        
        send_email_with_attachment(output_path, config.EMAIL_RECIPIENTS, email_subject, email_body)

    except Exception as e:
        print(f"엑셀 파일 생성 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    gsheet_client = authenticate_google_sheets()
    if gsheet_client:
        create_daily_order_excel(gsheet_client)
