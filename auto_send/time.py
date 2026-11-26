import glob
import os
import subprocess
import sys
import time
from datetime import date, datetime, time as dt_time, timedelta
from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEND_NUMBER_DIR = os.path.join(BASE_DIR, "send_number")
GOOGLE_SCRIPT = os.path.join(BASE_DIR, "4_send_number_to_google.py")
DB_SCRIPT = os.path.join(BASE_DIR, "5_send_nm_to_db.py")
SCHEDULE_TIME = dt_time(hour=18, minute=0)
WAIT_AFTER_SEND_SECONDS = 600  # 10 minutes


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def has_today_excel(target_date: Optional[date] = None) -> bool:
    target = target_date or datetime.now().date()
    date_str = target.strftime("%Y%m%d")
    pattern = os.path.join(SEND_NUMBER_DIR, f"택배운송장_{date_str}*.xlsx")
    matches = glob.glob(pattern)
    return len(matches) > 0


def run_script(script_path: str, label: str) -> bool:
    if not os.path.exists(script_path):
        log(f"{label}: 스크립트를 찾을 수 없습니다 -> {script_path}")
        return False

    log(f"{label}: 실행 시작")
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        completed = subprocess.run(
            [sys.executable, script_path],
            cwd=BASE_DIR,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except Exception as exc:  # subprocess 실행 자체가 실패할 때
        log(f"{label}: 실행 중 예외 발생 -> {exc}")
        return False

    if completed.stdout:
        log(f"{label} stdout:\n{completed.stdout.strip()}")
    if completed.stderr:
        log(f"{label} stderr:\n{completed.stderr.strip()}")

    if completed.returncode == 0:
        log(f"{label}: 정상 종료")
        return True

    log(f"{label}: 종료 코드 {completed.returncode}")
    return False


def run_daily_flow(target_date: date) -> None:
    date_label = target_date.strftime("%Y-%m-%d")

    if has_today_excel(target_date):
        log(f"{date_label}: 이미 송장 엑셀 존재. 스케줄러를 종료합니다.")
        sys.exit(0)

    log(f"{date_label}: 송장 엑셀 없음. 4_send_number_to_google.py 실행.")
    ok = run_script(GOOGLE_SCRIPT, "4_send_number_to_google.py")
    if not ok:
        log(f"{date_label}: 4_send_number_to_google.py 실패로 인해 후속 작업 중단.")
        return

    log("10분 대기 후 5_send_nm_to_db.py 실행합니다.")
    time.sleep(WAIT_AFTER_SEND_SECONDS)
    run_script(DB_SCRIPT, "5_send_nm_to_db.py")


def main():
    log("스케줄러 시작(윈도우 작업 스케줄러용 단발 실행)")
    today = datetime.now().date()

    if has_today_excel(today):
        log("오늘 송장 엑셀 이미 존재. 스크립트를 종료합니다.")
        return

    # 윈도우 작업 스케줄러에서 호출될 때마다 하루 치만 처리하고 종료한다.
    run_daily_flow(today)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("사용자 종료로 스케줄러를 종료합니다.")
