#!/usr/bin/env python
# coding: utf-8

import os
import sys
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from email.header import Header # Header 모듈 임포트
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
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

        # 2. 시트 데이터 가져오기 및 DataFrame 변환
        sheet_data = worksheet.get_all_records()
        if not sheet_data:
            print("시트에 데이터가 없습니다.")
            return
            
        sheet_df = pd.DataFrame(sheet_data)
        print(f"구글 시트에서 총 {len(sheet_df)}건의 데이터를 불러왔습니다.")

        # 3. config.py의 TARGET_DATE에 해당하는 데이터 필터링
        target_date_obj = datetime.strptime(config.TARGET_DATE, '%Y-%m-%d')
        target_date_str = target_date_obj.strftime('%Y-%m-%d') # 구글 시트의 날짜 형식과 일치하도록 수정

        # 시트의 '날짜' 컬럼 값과 비교하기 위해 문자열로 통일
        today_orders_df = sheet_df[sheet_df['날짜'].astype(str).str.strip() == target_date_str].copy()

        if today_orders_df.empty:
            print(f"'{target_date_str}' 날짜에 해당하는 주문 데이터가 없습니다.")
            return

        print(f"지정된 날짜({target_date_str})의 주문 {len(today_orders_df)}건을 찾았습니다.")

        # 4. 요청된 규칙에 따라 엑셀 파일용 DataFrame 생성
        output_df = pd.DataFrame()

        # '전화번호': 구글 시트 '전화번호'에서 '-', 맨 앞 '0' 제거
        # .astype(str)으로 모든 값을 문자열로 변환하여 오류 방지
        def format_phone_number(phone):
            phone_str = str(phone).replace('-', '')
            if phone_str.startswith('0'):
                return phone_str[1:]
            return phone_str
        output_df['전화번호'] = today_orders_df['전화번호'].apply(format_phone_number)

        output_df['받는분'] = today_orders_df['받는분']
        output_df['연락처'] = today_orders_df['전화번호'] # '연락처'는 구글 시트 '전화번호' 원본
        output_df['주소'] = today_orders_df['주소']
        output_df['도서명'] = today_orders_df['도서명']
        # ISBN을 문자열로 변환하여 엑셀에서 지수 표기법으로 표시되는 것을 방지
        output_df['ISBN'] = today_orders_df['ISBN\n(vlookup 적용중)'].astype(str)
        output_df['부수'] = today_orders_df['부수']
        output_df['공급률'] = '0' # 고정값
        output_df['증정도장'] = 'N' # 고정값
        output_df['비고'] = today_orders_df['비고']

        print("요청된 규칙에 따라 엑셀 데이터를 성공적으로 가공했습니다.")

        # 5. 엑셀 파일로 저장
        # 파일명 형식: 택배발주사내_MMDD_바스클.xlsx
        file_date = target_date_obj.strftime('%m%d')
        output_filename = f"택배발주사내_{file_date}_바스클.xlsx"

        # 스크립트가 있는 폴더에 저장
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, output_filename)

        output_df.to_excel(output_path, index=False, engine='openpyxl')
        print(f"\n엑셀 파일이 성공적으로 생성되었습니다: {output_path}")

        # 6. 생성된 엑셀 파일을 이메일로 발송
        email_subject = f"[{target_date_obj.strftime('%Y-%m-%d')}]_바스클 발주 내용"
        email_body = f"{target_date_obj.strftime('%Y-%m-%d')}의 주문건은 {len(today_orders_df)}건 입니다."
        
        send_email_with_attachment(output_path, config.EMAIL_RECIPIENTS, email_subject, email_body)

    except Exception as e:
        print(f"엑셀 파일 생성 중 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    gsheet_client = authenticate_google_sheets()
    if gsheet_client:
        create_daily_order_excel(gsheet_client)