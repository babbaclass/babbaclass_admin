import os
import subprocess
import sys
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template_string,
    stream_with_context,
    url_for,
)

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_QUERY_SCRIPT = os.path.join(BASE_DIR, "1_db_query.py")
BRENCH_SCRIPT = os.path.join(BASE_DIR, "2_brench.py")
STORE_SCRIPT = os.path.join(BASE_DIR, "3_store.py")
GOOGLE_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/13lY4Euru3aYonPVfwlibjTQjxI5RBSxjTHIaQ9WmbLo/"
    "edit?gid=1705520401#gid=1705520401"
)


def _run_python(target_path: str):
    """공통 파이썬 스크립트 실행 헬퍼."""
    completed = subprocess.run(
        [sys.executable, target_path],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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


def _stream_python(target_path: str):
    """서브프로세스 stdout/stderr를 SSE로 한 줄씩 내보낸다."""

    def generate():
        if not os.path.exists(target_path):
            yield "data:파일을 찾지 못했습니다.\n\n"
            yield "event: done\ndata:404\n\n"
            return

        yield "data:실행을 시작합니다...\n\n"
        process = subprocess.Popen(
            [sys.executable, target_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            cleaned = line.rstrip("\r\n")
            yield f"data:{cleaned}\n\n"
        ret = process.wait()
        yield f"event: done\ndata:{ret}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # 일부 프록시 버퍼링 방지
        "Connection": "keep-alive",
    }
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers=headers,
    )


@app.route("/")
def root():
    return redirect(url_for("store_dashboard"))


@app.route("/store")
def store_dashboard():
    """버튼으로 각 스크립트를 실행하거나 구글 시트를 여는 대시보드."""
    return render_template_string(
        """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>지사/원 매출 대시보드</title>
  <style>
    :root {
      --bg: #0b1726;
      --panel: #132338;
      --accent: #60d394;
      --text: #e9f1ff;
      --muted: #9fb3cc;
      --danger: #ff6b6b;
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
    }
    .shell {
      width: 90%;
      max-width: 1100px;
      background: var(--panel);
      border: 1px solid #1f3553;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.45);
      padding: 28px;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 18px;
    }
    .title { font-size: 20px; font-weight: 700; letter-spacing: 0.3px; }
    .content { display: grid; grid-template-columns: 260px 1fr; gap: 18px; }
    .panel {
      background: #0f2035;
      border: 1px solid #1f3553;
      border-radius: 12px;
      padding: 18px;
    }
    .panel h3 { margin: 0 0 10px; font-size: 16px; font-weight: 700; }
    button {
      width: 100%;
      padding: 14px 16px;
      background: linear-gradient(135deg, var(--accent), #7ee0ae);
      border: none;
      border-radius: 10px;
      color: #0b1726;
      font-weight: 700;
      font-size: 15px;
      cursor: pointer;
      transition: transform 0.12s ease, box-shadow 0.12s ease, filter 0.12s ease;
      box-shadow: 0 10px 25px rgba(96, 211, 148, 0.35);
    }
    button:disabled { cursor: not-allowed; filter: grayscale(0.5); opacity: 0.8; box-shadow: none; }
    button:hover:not(:disabled) { transform: translateY(-1px); }
    button:active:not(:disabled) { transform: translateY(0); box-shadow: none; }
    .output {
      height: 320px;
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
    .footer { margin-top: 14px; font-size: 12px; color: var(--muted); text-align: right; }
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
    .error { color: var(--danger); }
  </style>
</head>
<body>
  <div class="shell">
    <div class="header">
      <div class="title">지사/원 매출 자동화</div>
      <div class="badge" id="status-pill">대기중</div>
    </div>
    <div class="content">
      <div class="panel">
        <h3>실행</h3>
        <p style="color: var(--muted); font-size: 14px; margin-top: 0;">
          버튼을 누르면 스크립트가 실행되고, 결과 로그가 오른쪽에 표시됩니다.
        </p>
        <button id="run-db-btn">1. 기본 데이터 생성</button>
        <div style="height: 10px;"></div>
        <button id="run-brench-btn">2. 지사 매출 생성</button>
        <div style="height: 10px;"></div>
        <button id="run-store-btn">3. 원별 매출 생성</button>
        <div style="height: 10px;"></div>
        <button id="run-google-btn">4. 구글 시트로 이동</button>
      </div>
      <div class="panel">
        <h3>결과 로그</h3>
        <div id="output" class="output">아직 실행 기록이 없습니다.</div>
      </div>
    </div>
    <div class="footer">
      사용 스크립트:
      <code>1_db_query.py</code>,
      <code>2_brench.py</code>,
      <code>3_store.py</code>
    </div>
  </div>
  <script>
    let evtSource = null;

    const runDbBtn = document.getElementById("run-db-btn");
    const runBrenchBtn = document.getElementById("run-brench-btn");
    const runStoreBtn = document.getElementById("run-store-btn");
    const runGoogleBtn = document.getElementById("run-google-btn");
    const output = document.getElementById("output");
    const statusPill = document.getElementById("status-pill");

    function setStatus(text, isError = false) {
      statusPill.textContent = text;
      statusPill.classList.toggle("error", isError);
    }

    function setButtons(disabled) {
      runDbBtn.disabled = disabled;
      runBrenchBtn.disabled = disabled;
      runStoreBtn.disabled = disabled;
      runGoogleBtn.disabled = disabled;
    }

    function closeStream() {
      if (evtSource) {
        evtSource.close();
        evtSource = null;
      }
    }

    function appendLine(text) {
      output.textContent = output.textContent
        ? output.textContent + "\\n" + text
        : text;
      output.scrollTop = output.scrollHeight;
    }

    function runStream(endpoint, label) {
      closeStream();
      setButtons(true);
      setStatus(label + " 실행 중...");
      output.textContent = "";
      evtSource = new EventSource(endpoint);

      evtSource.onmessage = (event) => {
        appendLine(event.data);
      };

      evtSource.addEventListener("done", (event) => {
        const code = parseInt(event.data, 10);
        const success = code === 0;
        setStatus(success ? label + " 완료" : label + " 실패", !success);
        if (!success) {
          appendLine("[종료 코드] " + code);
        }
        setButtons(false);
        closeStream();
      });

      evtSource.onerror = (event) => {
        appendLine("[error] 스트림 오류가 발생했습니다.");
        setStatus("오류", true);
        setButtons(false);
        closeStream();
      };
    }

    function openGoogleSheet() {
      window.open("{{ google_sheet_url }}", "_blank", "noopener");
      setStatus("구글 시트를 새 탭에서 열었습니다.");
    }

    runDbBtn.addEventListener("click", () => runStream("/stream/db", "기본 데이터"));
    runBrenchBtn.addEventListener("click", () => runStream("/stream/brench", "지사 매출"));
    runStoreBtn.addEventListener("click", () => runStream("/stream/store", "원별 매출"));
    runGoogleBtn.addEventListener("click", openGoogleSheet);
  </script>
</body>
</html>
        """,
        google_sheet_url=GOOGLE_SHEET_URL,
    )


@app.post("/run-db-query")
def run_db_query():
    """1_db_query.py 실행."""
    if not os.path.exists(DB_QUERY_SCRIPT):
        return jsonify(success=False, output="1_db_query.py 파일을 찾지 못했습니다."), 404
    success, combined_output = _run_python(DB_QUERY_SCRIPT)
    return jsonify(success=success, output=combined_output), (200 if success else 500)


@app.post("/run-brench")
def run_brench():
    """2_brench.py 실행."""
    if not os.path.exists(BRENCH_SCRIPT):
        return jsonify(success=False, output="2_brench.py 파일을 찾지 못했습니다."), 404
    success, combined_output = _run_python(BRENCH_SCRIPT)
    return jsonify(success=success, output=combined_output), (200 if success else 500)


@app.post("/run-store")
def run_store():
    """3_store.py 실행."""
    if not os.path.exists(STORE_SCRIPT):
        return jsonify(success=False, output="3_store.py 파일을 찾지 못했습니다."), 404
    success, combined_output = _run_python(STORE_SCRIPT)
    return jsonify(success=success, output=combined_output), (200 if success else 500)


@app.get("/stream/<name>")
def stream_script(name: str):
    """SSE로 실시간 로그 전송."""
    mapping = {
        "db": DB_QUERY_SCRIPT,
        "brench": BRENCH_SCRIPT,
        "store": STORE_SCRIPT,
    }
    target = mapping.get(name)
    if not target:
        return jsonify(success=False, output="unknown stream"), 404
    return _stream_python(target)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)
