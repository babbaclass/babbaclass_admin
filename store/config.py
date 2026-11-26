#!/usr/bin/env python
# coding: utf-8

import os
# config.py
from datetime import datetime

# --- 공통 설정 ---
TARGET_DATE = datetime.now().strftime("%Y-%m-%d")

# Google Sheets API 설정
# 새로 요청된 배송 목록 스프레드시트 ID
DB_SPREADSHEET_ID = "13lY4Euru3aYonPVfwlibjTQjxI5RBSxjTHIaQ9WmbLo"


# 현재 연도와 월을 기반으로 동적 시트 이름 생성 (예: '2025년 12월_바스클')
TARGET_SHEET_NAME = f"{datetime.now().strftime('%Y년 %m월')}_바스클"

# Google Sheets API 인증을 위한 credentials.json 파일 경로
GOOGLE_SHEET_CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
GOOGLE_CHAT_WEBHOOK_URL = "https://chat.googleapis.com/v1/spaces/AAQA4jqTRdo/messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&token=lJjaGhbZb5GRhDmuEF09LUReijzMjPSt1uWPWy_rwZQ"
GOOGLE_CHAT_USER_ID = os.environ.get("GOOGLE_CHAT_USER_ID", "")


# 이메일 설정
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "babbasmartclass@easyspub.co.kr"
EMAIL_PASSWORD = "iiicdyusaclvlama"  # 앱 비밀번호
EMAIL_RECIPIENTS = ["sk@easyspub.co.kr", "bongfish@naver.com", "hjmin31@easyspub.co.kr"]
#EMAIL_RECIPIENTS = ["bongfish@naver.com"]
EMAIL_SPREADSHEET_ID = "1HqapmgRRaUdGZ5H9u8PozdVuiPd58C5LRIXOK8avg-c"
