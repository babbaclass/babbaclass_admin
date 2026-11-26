import os
import subprocess
import sys
from datetime import datetime

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORDER_SCRIPT = os.path.join(BASE_DIR, "1_create_order_excel.py")
HAPPYDAY_SCRIPT = os.path.join(BASE_DIR, "2_send_happyday.py")
GOOGLE_SCRIPT = os.path.join(BASE_DIR, "4_send_number_to_google.py")
MAKESHOP_SCRIPT = os.path.join(BASE_DIR, "5_send_nm_to_db.py")
MANUAL_MAKESHOP_SCRIPT = os.path.join(BASE_DIR, "6_send_nm_to_db_manual.py")

PAGE_TEMPLATE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>주문 관리 도우미</title>
  <style>
    :root {
      --bg: #0b1726;
      --panel: #132338;
      --accent: #60d394;
      --text: #e9f1ff;
      --muted: #9fb3cc;
      --danger: #ff6b6b;
      --input-bg: #0c1b2d;
      --input-border: #27486d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "Noto Sans KR", sans-serif;
      background: radial-gradient(circle at 20% 20%, #122848, #0b1726 40%);
      color: var(--text);
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 24px;
    }
    .shell {
      width: 90%;
      max-width: 1100px;
      background: var(--panel);
      border: 1px solid #1f3553;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
      padding: 28px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 18px;
      gap: 16px;
    }
    .title {
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0.3px;
    }
    .content {
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 18px;
    }
    .panel {
      background: #0f2035;
      border: 1px solid #1f3553;
      border-radius: 12px;
      padding: 18px;
    }
    .panel h3 {
      margin: 0 0 10px;
      font-size: 16px;
      font-weight: 700;
    }
    .panel p {
      color: var(--muted);
      font-size: 14px;
      margin: 0 0 14px;
      line-height: 1.6;
    }
    button,
    input[type="date"] {
      width: 100%;
      border-radius: 10px;
      font-size: 15px;
    }
    button {
      padding: 14px 16px;
      background: linear-gradient(135deg, var(--accent), #7ee0ae);
      border: none;
      color: #0b1726;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease;
      box-shadow: 0 10px 25px rgba(96, 211, 148, 0.35);
    }
    button:disabled {
      cursor: not-allowed;
      filter: grayscale(0.5);
      opacity: 0.8;
      box-shadow: none;
    }
    button:hover:not(:disabled) { transform: translateY(-1px); }
    button:active:not(:disabled) {
      transform: translateY(0);
      box-shadow: none;
    }
    input[type="date"] {
      padding: 12px 14px;
      color: var(--text);
      background: var(--input-bg);
      border: 1px solid var(--input-border);
    }
    input[type="date"]:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(96, 211, 148, 0.18);
    }
    input[type="date"]:disabled {
      opacity: 0.8;
      cursor: not-allowed;
    }
    .spacer { height: 10px; }
    .field-label {
      color: var(--muted);
      font-size: 13px;
      margin: 16px 0 8px;
    }
    .field-help {
      color: var(--muted);
      font-size: 12px;
      margin: 8px 0 0;
      line-height: 1.5;
    }
    .output {
      height: 380px;
      background: #0c1b2d;
      border: 1px solid #1f3553;
      border-radius: 12px;
      padding: 14px;
      overflow: auto;
      font-family: "SFMono-Regular", Consolas, "Courier New", monospace;
      font-size: 13px;
      white-space: pre-wrap;
      line-height: 1.5;
    }
    .footer {
      margin-top: 14px;
      font-size: 12px;
      color: var(--muted);
      text-align: right;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(96, 211, 148, 0.14);
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
    }
    .error {
      color: var(--danger);
      background: rgba(255, 107, 107, 0.12);
    }
    @media (max-width: 860px) {
      .content {
        grid-template-columns: 1fr;
      }
      .output {
        height: 300px;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="header">
      <div class="title">주문 관리 도우미</div>
      <div class="badge" id="status-pill">대기 중</div>
    </div>
    <div class="content">
      <div class="panel">
        <h3>실행</h3>
        <p>버튼을 누르면 스크립트를 실행하고 결과 로그를 오른쪽 패널에 보여줍니다.</p>
        <button id="run-btn">1. 주문 엑셀 생성</button>
        <div class="spacer"></div>
        <button id="run-happyday-btn">2. 해피데이 업로드</button>
        <div class="spacer"></div>
        <button id="run-google-btn">3. 송장번호 확인</button>
        <div class="spacer"></div>
        <button id="run-makeshop-btn">4. 송장번호 메이크샵 등록</button>

        <div class="field-label">수동 메이크샵 등록 날짜</div>
        <input id="manual-date" type="date" />
        <p class="field-help">선택한 날짜를 <code>6_send_nm_to_db_manual.py</code>에 전달합니다.</p>
        <button id="run-manual-makeshop-btn">5. 수동 메이크샵 등록</button>
      </div>
      <div class="panel">
        <h3>결과 로그</h3>
        <div id="output" class="output">아직 실행 기록이 없습니다.</div>
      </div>
    </div>
    <div class="footer">
      사용 스크립트:
      <code>1_create_order_excel.py</code>,
      <code>2_send_happyday.py</code>,
      <code>4_send_number_to_google.py</code>,
      <code>5_send_nm_to_db.py</code>,
      <code>6_send_nm_to_db_manual.py</code>
    </div>
  </div>
  <script>
    const runBtn = document.getElementById("run-btn");
    const runHappydayBtn = document.getElementById("run-happyday-btn");
    const runGoogleBtn = document.getElementById("run-google-btn");
    const runMakeshopBtn = document.getElementById("run-makeshop-btn");
    const runManualMakeshopBtn = document.getElementById("run-manual-makeshop-btn");
    const manualDateInput = document.getElementById("manual-date");
    const output = document.getElementById("output");
    const statusPill = document.getElementById("status-pill");
    const actionButtons = [
      runBtn,
      runHappydayBtn,
      runGoogleBtn,
      runMakeshopBtn,
      runManualMakeshopBtn,
    ];

    function setStatus(text, isError = false) {
      statusPill.textContent = text;
      statusPill.classList.toggle("error", isError);
    }

    function setRunningState(isRunning) {
      actionButtons.forEach((button) => {
        button.disabled = isRunning;
      });
      manualDateInput.disabled = isRunning;
    }

    function setDefaultManualDate() {
      const now = new Date();
      const localNow = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
      manualDateInput.value = localNow.toISOString().slice(0, 10);
    }

    async function runScript(endpoint, label, payload = null) {
      setRunningState(true);
      setStatus(label + " 실행 중...");
      output.textContent = "실행 중입니다. 잠시만 기다려 주세요...";

      try {
        const options = { method: "POST" };
        if (payload) {
          options.headers = { "Content-Type": "application/json" };
          options.body = JSON.stringify(payload);
        }

        const res = await fetch(endpoint, options);
        const data = await res.json();

        output.textContent = data.output || "(출력 없음)";
        setStatus(data.success ? label + " 완료" : label + " 실패", !data.success);
      } catch (err) {
        output.textContent = "요청 실패: " + err;
        setStatus("오류", true);
      } finally {
        setRunningState(false);
      }
    }

    runBtn.addEventListener("click", () => runScript("/run-script", "주문 엑셀 생성"));
    runHappydayBtn.addEventListener("click", () => runScript("/run-happyday", "해피데이 업로드"));
    runGoogleBtn.addEventListener("click", () => runScript("/run-google", "송장번호 확인"));
    runMakeshopBtn.addEventListener("click", () => runScript("/run-makeshop", "송장번호 메이크샵 등록"));
    runManualMakeshopBtn.addEventListener("click", () => {
      const targetDate = manualDateInput.value;
      if (!targetDate) {
        output.textContent = "수동 메이크샵 등록 날짜를 먼저 선택하세요.";
        setStatus("입력 필요", true);
        manualDateInput.focus();
        return;
      }

      runScript("/run-makeshop-manual", "수동 메이크샵 등록", {
        target_date: targetDate,
      });
    });

    setDefaultManualDate();
  </script>
</body>
</html>
"""


def _run_python(target_path: str, args=None):
    """공통 파이썬 스크립트 실행 함수."""
    command = [sys.executable, target_path]
    if args:
        command.extend(args)

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    parts = []
    if stdout:
        parts.append(stdout.strip())
    if stderr:
        parts.append("\n[stderr]\n" + stderr.strip())
    combined = "\n".join(parts) if parts else "(출력 없음)"
    return completed.returncode == 0, combined


def _validate_iso_date(raw_value: str) -> str:
    datetime.strptime(raw_value, "%Y-%m-%d")
    return raw_value


@app.route("/")
def index():
    return render_template_string(PAGE_TEMPLATE)


@app.post("/run-script")
def run_script():
    if not os.path.exists(ORDER_SCRIPT):
        return jsonify(success=False, output="1_create_order_excel.py 파일을 찾을 수 없습니다."), 404
    success, combined_output = _run_python(ORDER_SCRIPT)
    return jsonify(success=success, output=combined_output), (200 if success else 500)


@app.post("/run-happyday")
def run_happyday():
    if not os.path.exists(HAPPYDAY_SCRIPT):
        return jsonify(success=False, output="2_send_happyday.py 파일을 찾을 수 없습니다."), 404
    success, combined_output = _run_python(HAPPYDAY_SCRIPT)
    return jsonify(success=success, output=combined_output), (200 if success else 500)


@app.post("/run-google")
def run_google():
    if not os.path.exists(GOOGLE_SCRIPT):
        return jsonify(success=False, output="4_send_number_to_google.py 파일을 찾을 수 없습니다."), 404
    success, combined_output = _run_python(GOOGLE_SCRIPT)
    return jsonify(success=success, output=combined_output), (200 if success else 500)


@app.post("/run-makeshop")
def run_makeshop():
    if not os.path.exists(MAKESHOP_SCRIPT):
        return jsonify(success=False, output="5_send_nm_to_db.py 파일을 찾을 수 없습니다."), 404
    success, combined_output = _run_python(MAKESHOP_SCRIPT)
    return jsonify(success=success, output=combined_output), (200 if success else 500)


@app.post("/run-makeshop-manual")
def run_makeshop_manual():
    if not os.path.exists(MANUAL_MAKESHOP_SCRIPT):
        return jsonify(success=False, output="6_send_nm_to_db_manual.py 파일을 찾을 수 없습니다."), 404

    payload = request.get_json(silent=True) or {}
    target_date = str(payload.get("target_date", "")).strip()
    if not target_date:
        return jsonify(success=False, output="수동 메이크샵 등록 날짜를 먼저 선택하세요."), 400

    try:
        target_date = _validate_iso_date(target_date)
    except ValueError:
        return (
            jsonify(
                success=False,
                output=f"날짜 형식이 올바르지 않습니다: {target_date} (예: 2026-04-21)",
            ),
            400,
        )

    success, combined_output = _run_python(MANUAL_MAKESHOP_SCRIPT, args=[target_date])
    return jsonify(success=success, output=combined_output), (200 if success else 500)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "0.0.0.0")
    app.run(host=host, port=port, debug=True)
