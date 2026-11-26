import time
import os
import sys
import re
from datetime import datetime # datetime 임포트
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys # Added for Keys.RETURN
from openpyxl import load_workbook
import importlib.util
import config # config.py 파일 임포트

# 1_create_order_excel.py(모듈명이 숫자로 시작해 직접 import 불가)에서 send_google_chat_message 로드
script_dir = os.path.dirname(os.path.abspath(__file__))
order_excel_path = os.path.join(script_dir, "1_create_order_excel.py")
spec = importlib.util.spec_from_file_location("create_order_excel", order_excel_path)
create_order_excel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(create_order_excel)
send_google_chat_message = create_order_excel.send_google_chat_message

# --- 파일 처리 유틸 ---
def count_rows_in_excel(file_path):
    """
    Upload 대상 엑셀의 데이터 건수를 헤더(첫 번째 행) 제외하고 계산한다.
    .xls은 xlrd로, 나머지는 openpyxl로 처리한다.
    """
    if not os.path.exists(file_path):
        return None, "업로드 파일을 찾을 수 없습니다."

    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".xls":
            try:
                import xlrd
            except ImportError:
                return None, "xlrd 패키지가 설치되어 있지 않습니다."
            book = xlrd.open_workbook(file_path)
            sheet = book.sheet_by_index(0)
            return max(sheet.nrows - 1, 0), None

        wb = load_workbook(file_path, read_only=True)
        ws = wb.active
        return max(ws.max_row - 1, 0), None
    except Exception as exc:
        return None, str(exc)

# --- 사용자 설정 ---
UPLOAD_FILE_PATH = os.path.abspath("send_upload_sample.xls")

# --- 로그인 정보 ---
ID_INPUT_ID = "USER_ID"
PASSWORD_INPUT_ID = "USER_PW"
LOGIN_BUTTON_ID = "btnSubmit"

def find_clickable_in_frames(driver, by, value, timeout=10):
    """
    현재 컨텍스트 → 기본 컨텍스트 → 모든 1레벨 iframe을 순회하며
    clickable 요소를 찾는다. 성공 시 해당 프레임에 머문다.
    """
    def wait_clickable():
        return WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    def wait_present():
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )

    # 1) 현재 컨텍스트
    try:
        return wait_clickable()
    except Exception as exc:
        last_exc = exc
    else:
        last_exc = None

    # 2) 기본 컨텍스트
    try:
        driver.switch_to.default_content()
        return wait_clickable()
    except Exception as exc:
        last_exc = exc

    # 3) 1레벨 iframe 순회
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for frame in frames:
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            return wait_clickable()
        except Exception as exc:
            last_exc = exc
            continue

    # 4) clickable 실패 시 presence 기준으로 최후 재시도
    try:
        driver.switch_to.default_content()
        return wait_present()
    except Exception as exc:
        last_exc = exc

    for frame in frames:
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            return wait_present()
        except Exception as exc:
            last_exc = exc
            continue

    driver.switch_to.default_content()
    raise TimeoutException(f"Element not clickable/present in any checked frame: {value}") from last_exc

def click_with_fallback(driver, locator_desc, by, value, timeout=10, script_dir=None):
    """
    셀렉터로 클릭 시도 → 스크롤 → 일반 클릭 → JS 클릭 순서로 재시도.
    실패 시 스크린샷/HTML을 남겨 디버깅에 도움을 준다.
    """
    try:
        elem = find_clickable_in_frames(driver, by, value, timeout=timeout)
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
        time.sleep(0.3)
        try:
            elem.click()
            return True
        except ElementClickInterceptedException:
            pass
        # JS fallback
        driver.execute_script("arguments[0].click();", elem)
        return True
    except Exception as exc:
        if script_dir:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shot = os.path.join(script_dir, f"click_error_{locator_desc}_{ts}.png")
            html = os.path.join(script_dir, f"click_error_{locator_desc}_{ts}.html")
            try:
                driver.save_screenshot(shot)
                with open(html, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"{locator_desc} 클릭 실패, 스크린샷/HTML 저장: {shot}, {html}")
            except Exception:
                print(f"{locator_desc} 클릭 실패 (추가 저장 실패)")
        raise

def main():
    # Windows 터미널에서 한글 깨짐 방지를 위해 출력 인코딩을 UTF-8로 설정
    sys.stdout.reconfigure(encoding='utf-8') # Added for encoding fix
    
    driver = None
    try:
        # 스크립트가 있는 디렉토리를 기준으로 login.txt 파일의 절대 경로를 생성합니다.
        script_dir = os.path.dirname(os.path.abspath(__file__))
        login_file_path = os.path.join(script_dir, "login.txt")
        with open(login_file_path, "r", encoding="utf-8") as f:
            user_id = f.readline().strip()
            password = f.readline().strip()
    except FileNotFoundError:
        print("오류: login.txt 파일을 찾을 수 없습니다.")
        return

    try:
        # --- 웹드라이버 설정 ---
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        driver = webdriver.Chrome(options=chrome_options)

        # --- 업로드 폴더 및 파일 설정 ---
        upload_folder = os.path.join(script_dir, "send_excel")  # 생성된 엑셀 위치
        if not os.path.isdir(upload_folder):
            print(f"업로드 폴더를 찾을 수 없습니다: {upload_folder}")
            return
        today_str = datetime.now().strftime("%m%d")
        upload_filename = f"택배발주사내_{today_str}_바스클.xls"
        upload_file_path = os.path.abspath(os.path.join(upload_folder, upload_filename))
        print(f"업로드 파일 경로: {upload_file_path} (exists={os.path.exists(upload_file_path)})")
        if not os.path.isfile(upload_file_path):
            print("업로드 대상 파일이 파일이 아니거나 접근할 수 없습니다. 업로드를 중단합니다.")
            return
        try:
            file_size = os.path.getsize(upload_file_path)
            print(f"업로드 파일 크기: {file_size} bytes")
        except Exception:
            pass

        expected_count, count_err = count_rows_in_excel(upload_file_path)
        if expected_count is not None:
            print(f"업로드 대상 건수: {expected_count}건")
        elif count_err:
            print(f"업로드 파일 건수 확인 실패: {count_err}")

        # 1. 로그인 ~ 팝업 처리
        driver.get("https://new.ehappyday.kr/Login")
        time.sleep(1)
        driver.find_element(By.ID, ID_INPUT_ID).send_keys(user_id)
        driver.find_element(By.ID, PASSWORD_INPUT_ID).send_keys(password)
        driver.find_element(By.ID, LOGIN_BUTTON_ID).click()
        print("로그인 완료. 팝업을 처리합니다.")
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '확인')]" ))).click()
        except Exception:
            pass # 첫 번째 팝업은 없을 수 있음
        time.sleep(1)
        try:
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@onclick, 'close_pop')]" ))).click()
        except Exception:
            pass # 두 번째 팝업도 없을 수 있음
        print("팝업 처리 완료.")

        # 2. 엑셀업로드 화면으로 이동
        driver.get("https://new.ehappyday.kr/Output/excelOutput02")
        time.sleep(1) # 페이지 로딩 대기

        # 파일 업로드
        try:
            upload_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="userfile"]'))
            )
            upload_path_for_selenium = os.path.realpath(upload_file_path)
            print(f"파일 업로드 시도 경로: {upload_path_for_selenium}")
            if not os.path.isfile(upload_path_for_selenium):
                raise FileNotFoundError(f"업로드 파일을 찾을 수 없습니다: {upload_path_for_selenium}")
            upload_input.send_keys(upload_path_for_selenium)
            print("업로드 파일을 선택했습니다.")

            # 업로드 후 필수 버튼(추가 확인/조회 등) 클릭
            click_with_fallback(
                driver,
                "확인/조회 버튼",
                By.XPATH,
                '//*[@id="file_form"]/div/div[2]/div[3]/table/tbody/tr/td[2]/button',
                timeout=15,
                script_dir=script_dir,
            )
            time.sleep(1)

            def parse_count(text):
                text = text.replace(",", "").strip()
                m = re.search(r"(\d+)", text)
                return int(m.group(1)) if m else None

            info_elem = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="tot_num"]'))
            )
            # 숫자가 0이거나 안 나오는 경우를 대비해 일정 시간 재시도
            actual_count = None
            try:
                actual_count = WebDriverWait(driver, 10).until(
                    lambda d: (c := parse_count(info_elem.text)) is not None and c >= 0 and c,
                )
            except Exception:
                actual_count = parse_count(info_elem.text)
            info_text = info_elem.text.strip()
            print(f"tot_num text: {info_text}, parsed actual_count: {actual_count}")

            if expected_count is not None and actual_count == expected_count:
                click_with_fallback(
                    driver,
                    "업로드 버튼",
                    By.XPATH,
                    '//*[@id="file_form"]/div/div[2]/div[4]/table/tbody/tr/td[1]/button',
                    timeout=15,
                    script_dir=script_dir,
                )
                print("건수가 일치하여 업로드 버튼을 클릭했습니다.")
                success_chat_text = "해피데이에 성공적으로 엑셀파일을 업로드 하였습니다."
                send_google_chat_message(success_chat_text, mention_user_id=getattr(config, "GOOGLE_CHAT_USER_ID", ""))
            else:
                chat_text = (
                    "건수가 일치 하지 않아 업로드 하지 않았습니다.\n"
                    f"기대 건수: {expected_count if expected_count is not None else '확인 불가'}, "
                    f"화면 표시 건수: {actual_count if actual_count is not None else '확인 불가'}"
                )
                send_google_chat_message(chat_text, mention_user_id=getattr(config, "GOOGLE_CHAT_USER_ID", ""))
                print(chat_text)
        except Exception as upload_exc:
            error_chat_text = "해피데이 업로드 처리중 오류가 발생하였습니다."
            send_google_chat_message(error_chat_text, mention_user_id=getattr(config, "GOOGLE_CHAT_USER_ID", ""))
            print(f"업로드 처리 중 오류가 발생했습니다: {upload_exc}")

        # 모든 작업 완료 후 잠시 대기
        print("모든 작업을 완료했습니다. 5초 후 브라우저를 종료합니다.")
        time.sleep(5)

    except Exception as e:
        print(f"스크립트 실행 중 오류가 발생했습니다: {e}")
        time.sleep(10)
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
