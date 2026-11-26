import time
import os
import sys
from datetime import datetime # datetime 임포트
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys # Added for Keys.RETURN
import config # config.py 파일 임포트

# --- 사용자 설정 ---
UPLOAD_FILE_PATH = os.path.abspath("send_upload_sample.xls")

# --- 로그인 정보 ---
ID_INPUT_ID = "USER_ID"
PASSWORD_INPUT_ID = "USER_PW"
LOGIN_BUTTON_ID = "btnSubmit"

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
        # --- 다운로드 폴더 설정 ---
        script_dir = os.path.dirname(os.path.abspath(__file__))
        download_dir = os.path.join(script_dir, "send_number")
        os.makedirs(download_dir, exist_ok=True)
        print(f"엑셀 파일이 저장될 폴더: {download_dir}")

        chrome_options = Options()
        # 파일 다운로드 시 '다른 이름으로 저장' 대화 상자를 표시하지 않고, 지정된 폴더에 자동 저장하도록 설정
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        # chromedriver가 시스템 PATH에 설치되어 있다고 가정
        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.maximize_window()  # 창 크기 최대화로 클릭 방해 요소를 줄임

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

        # 2. 내역조회 페이지로 이동
        driver.get("https://new.ehappyday.kr/Search/sendInvoice")
        time.sleep(1) # 페이지 로딩 대기

        # 날짜 입력 # Added date input logic
        try:
            today_date = config.TARGET_DATE
            # 오늘 날짜를 'YYYY-MM-DD' 형식으로 가져옵니다.
            #today_date = datetime.now().strftime("%Y-%m-%d")
            print(f"날짜({today_date})를 입력합니다.")

            # 시작일 입력
            sdate_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "sdate")))
            driver.execute_script(f"arguments[0].value = '{today_date}';", sdate_element)

            # 종료일 입력
            edate_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "edate")))
            driver.execute_script(f"arguments[0].value = '{today_date}';", edate_element)

            # 날짜 입력 후 '검색' 버튼 클릭
            print("검색 버튼을 클릭합니다.")
            search_button_xpath = "//*[@id='frm_main']/div[2]/div[4]/div/span"
            search_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, search_button_xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", search_button)
            time.sleep(0.3)
            try:
                search_button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", search_button)
            time.sleep(5) # 검색 결과 로딩 대기

            # 엑셀 다운로드 버튼 클릭
            print("엑셀 다운로드 버튼을 클릭합니다.")
            excel_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//*[@id='excelBtn']")))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", excel_button)
            time.sleep(0.5)
            try:
                excel_button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", excel_button)

            # 파일 다운로드가 완료될 때까지 잠시 대기
            print("파일 다운로드를 10초간 대기합니다...")
            time.sleep(10)
            print("엑셀 파일 다운로드가 완료되었습니다.")
            
        except Exception as e:
            print(f"날짜 입력 중 오류가 발생했습니다: {e}")

        
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
