import csv
import time
from datetime import datetime
from pathlib import Path
from typing import List, Set

import gspread
from gspread.utils import rowcol_to_a1
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import config

LOGIN_URL = "https://babba-api-1024083500192.asia-northeast3.run.app/admin/login"
EXPORT_URL = "https://babba-api-1024083500192.asia-northeast3.run.app/admin/user/export/csv"
TARGET_FILENAME = "user_export.csv"
SYNC_SPREADSHEET_ID = "13lY4Euru3aYonPVfwlibjTQjxI5RBSxjTHIaQ9WmbLo"
SYNC_RAW_SHEET_NAME = "전체매출_raw"
SYNC_MEMBER_SHEET_NAME = "회원"
TARGET_WORKSHEET_NAME = "회원"

def load_credentials(path=Path("login.txt")):
    lines = path.read_text().splitlines()
    if len(lines) < 2:
        raise ValueError("login.txt must have ID on line 1 and password on line 2")
    return lines[0].strip(), lines[1].strip()

def wait_for_download(directory: Path, existing_names: Set[str], timeout: float = 30) -> Path:
    """Poll the download directory for a new CSV, avoiding pre-existing files."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        new_csvs = [p for p in directory.glob("*.csv") if p.name not in existing_names]
        if new_csvs:
            return max(new_csvs, key=lambda p: p.stat().st_mtime)
        time.sleep(0.5)
    raise TimeoutError("CSV download did not complete in time")


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
    return client


def load_csv_rows(path: Path) -> List[List[str]]:
    """Read CSV into list of rows (with header) as strings."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return [row for row in reader]


def ensure_worksheet(spreadsheet, title: str):
    """Return worksheet; create if missing."""
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows="2000", cols="20")


def upload_csv_to_sheet(rows: List[List[str]]):
    """Clear and upload CSV rows to target sheet, then stamp N1."""
    client = authenticate_google_sheets()
    spreadsheet = client.open_by_key(config.DB_SPREADSHEET_ID)
    worksheet = ensure_worksheet(spreadsheet, TARGET_WORKSHEET_NAME)
    worksheet.clear()
    if rows:
        worksheet.update(range_name="A1", values=rows, value_input_option="USER_ENTERED")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet.update(range_name="N1", values=[[now_str]], value_input_option="USER_ENTERED")
    print(f"스프레드시트 '{TARGET_WORKSHEET_NAME}' 업데이트 완료, N1에 타임스탬프 기록: {now_str}")


def sync_member_info_to_sales_raw():
    client = authenticate_google_sheets()
    ss = client.open_by_key(SYNC_SPREADSHEET_ID)
    raw_sh = ss.worksheet(SYNC_RAW_SHEET_NAME)
    mem_sh = ss.worksheet(SYNC_MEMBER_SHEET_NAME)

    raw = raw_sh.get_all_values()
    mem = mem_sh.get_all_values()
    if len(raw) < 2 or len(mem) < 2:
        return

    rh = raw[0]
    mh = mem[0]

    def find_idx(headers, name):
        return headers.index(name) if name in headers else -1

    # ---- 전체매출_raw 헤더 ----
    r_member_id = find_idx(rh, "member_id")
    r_user = find_idx(rh, "user_name")
    r_role_name = find_idx(rh, "role_name")
    r_company = find_idx(rh, "company_name")
    r_phone = find_idx(rh, "phone")
    r_sender = find_idx(rh, "sender")
    r_name_col = find_idx(rh, "이름")  # sender 없을 때만 폴백

    # ---- 회원 헤더 ----
    m_login_id = find_idx(mh, "로그인ID")
    m_name = find_idx(mh, "이름")
    m_role = find_idx(mh, "역할명")
    m_company = find_idx(mh, "회사명")
    m_rep_phone = find_idx(mh, "대표 연락처")

    # ---- 필수 헤더 체크 ----
    miss = []
    if r_member_id < 0:
        miss.append("전체매출_raw: member_id")
    if r_user < 0:
        miss.append("전체매출_raw: user_name")
    if r_role_name < 0:
        miss.append("전체매출_raw: role_name")
    if r_company < 0:
        miss.append("전체매출_raw: company_name")
    if r_phone < 0:
        miss.append("전체매출_raw: phone")
    if r_sender < 0 and r_name_col < 0:
        miss.append("전체매출_raw: sender(또는 이름)")

    if m_login_id < 0:
        miss.append("회원: 로그인ID")
    if m_name < 0:
        miss.append("회원: 이름")
    if m_role < 0:
        miss.append("회원: 역할명")
    if m_company < 0:
        miss.append("회원: 회사명")
    if m_rep_phone < 0:
        miss.append("회원: 대표 연락처")

    if miss:
        raise ValueError("헤더를 못 찾음:\n- " + "\n- ".join(miss))

    def norm_id(value):
        return str(value or "").strip().lower()

    def norm_name_strict(value):
        return str(value or "").strip()

    def phone_digits(value):
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    def phone_last8(digits):
        d = str(digits or "")
        return d[-8:] if len(d) >= 8 else d

    def get_cell(row, idx):
        return row[idx] if 0 <= idx < len(row) else ""

    def get_raw_name(row):
        value = get_cell(row, r_sender) if r_sender >= 0 else get_cell(row, r_name_col)
        return norm_name_strict(value)

    # ---------- 회원 맵 ----------
    map_by_login_id = {}
    map_by_name_strict = {}
    map_by_phone_digits = {}
    map_by_phone_last8 = {}

    for i in range(1, len(mem)):
        row = mem[i]
        if all(str(v or "").strip() == "" for v in row):
            continue

        info = {
            "name": get_cell(row, m_name),
            "role_name": get_cell(row, m_role),
            "company": get_cell(row, m_company),
            "name_key": norm_name_strict(get_cell(row, m_name)),
        }

        login_id = norm_id(get_cell(row, m_login_id))
        if login_id:
            map_by_login_id[login_id] = info

        if info["name_key"] and info["name_key"] not in map_by_name_strict:
            map_by_name_strict[info["name_key"]] = info

        rep = phone_digits(get_cell(row, m_rep_phone))
        if rep:
            if rep not in map_by_phone_digits:
                map_by_phone_digits[rep] = info
            last8 = phone_last8(rep)
            if last8 and last8 not in map_by_phone_last8:
                map_by_phone_last8[last8] = info

    # ---------- 업데이트 ----------
    updated_by_id = 0
    updated_by_phone = 0
    updated_by_name = 0
    marked_unknown = 0

    width = len(rh)
    for i in range(1, len(raw)):
        if len(raw[i]) < width:
            raw[i] = raw[i] + [""] * (width - len(raw[i]))

    # 1차: member_id == 로그인ID
    for i in range(1, len(raw)):
        row = raw[i]
        mid = norm_id(get_cell(row, r_member_id))
        if not mid:
            continue
        mem_info = map_by_login_id.get(mid)
        if not mem_info:
            continue
        row[r_company] = mem_info["company"]
        row[r_user] = mem_info["name"]
        row[r_role_name] = mem_info["role_name"]
        updated_by_id += 1

    # 2차: company_name이 빈 값이면, 전화번호 우선 매칭
    for i in range(1, len(raw)):
        row = raw[i]
        if str(get_cell(row, r_company)).strip():
            continue
        raw_digits = phone_digits(get_cell(row, r_phone))
        if not raw_digits:
            continue
        mem_info = map_by_phone_digits.get(raw_digits)
        if not mem_info:
            mem_info = map_by_phone_last8.get(phone_last8(raw_digits))
        if not mem_info:
            continue
        row[r_company] = mem_info["company"]
        row[r_user] = mem_info["name"]
        row[r_role_name] = mem_info["role_name"]
        updated_by_phone += 1

    # 3차: 그래도 company_name이 빈 값이면, sender 기준 완전일치
    for i in range(1, len(raw)):
        row = raw[i]
        if str(get_cell(row, r_company)).strip():
            continue
        raw_name_key = get_raw_name(row)
        if not raw_name_key:
            continue
        mem_info = map_by_name_strict.get(raw_name_key)
        if not mem_info:
            continue
        row[r_company] = mem_info["company"]
        row[r_user] = mem_info["name"]
        row[r_role_name] = mem_info["role_name"]
        updated_by_name += 1

    # 4차: 미지정
    for i in range(1, len(raw)):
        row = raw[i]
        if str(get_cell(row, r_company)).strip():
            continue
        row[r_company] = "미지정"
        marked_unknown += 1

    end_cell = rowcol_to_a1(len(raw), width)
    raw_sh.update(f"A1:{end_cell}", raw, value_input_option="USER_ENTERED")
    print(
        f"회원 정보 동기화 완료: ID {updated_by_id}행, "
        f"전화 {updated_by_phone}행, 이름 {updated_by_name}행, 미지정 {marked_unknown}행"
    )


def main():
    username, password = load_credentials()
    download_dir = Path.cwd()
    target_path = download_dir / TARGET_FILENAME
    if target_path.exists():
        target_path.unlink()
    existing = {p.name for p in download_dir.glob("*.csv")}

    options = webdriver.ChromeOptions()
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "safebrowsing.enabled": True,
            "safebrowsing.disable_download_protection": True,
        },
    )
    # options.add_argument("--headless=new")  # enable if you want headless
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    try:
        driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="username"]'))).send_keys(username)
        wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="password"]'))).send_keys(password)
        wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div/form/button'))).click()
        wait.until(EC.url_changes(LOGIN_URL))
        print("Login attempted; current URL:", driver.current_url)

        # After login, wait 2 seconds, then navigate to the CSV export page to trigger download.
        time.sleep(2)
        driver.get(EXPORT_URL)
        downloaded = wait_for_download(download_dir, existing_names=existing)
        if downloaded.resolve() != target_path.resolve():
            downloaded = downloaded.replace(target_path)
        print(f"SUCCESS: Downloaded CSV to {downloaded}")

        # CSV를 전량 교체 방식으로 업로드: 데이터 규모가 크지 않아 단순히 전체 갱신이 안정적이고 빠릅니다.
        rows = load_csv_rows(downloaded)
        upload_csv_to_sheet(rows)
        time.sleep(10)
        sync_member_info_to_sales_raw()
    except Exception as exc:
        print(f"FAILURE: {exc}")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
