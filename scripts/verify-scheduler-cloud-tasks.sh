#!/bin/bash
#############################################################################
# Cloud Scheduler Job + Cloud Tasks 연동 검증
#
# Makeshop 동기화만 Cloud Tasks 경유:
#   Scheduler → POST /tasks/sync/makeshop/trigger
#            → Cloud Tasks (makeshop-sync-queue)
#            → POST /tasks/sync/makeshop/run
#
# 정산 배치(월별/일별 MTD)는 Cloud Tasks 없이 Scheduler가 Cloud Run을 직접 호출:
#   Scheduler → POST /api/batch/settlement-*-aggregation
#
# 사용법:
#   ./scripts/verify-scheduler-cloud-tasks.sh
#   VERIFY_SCHEDULER_LIVE_TEST=1 ./scripts/verify-scheduler-cloud-tasks.sh
#############################################################################

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-astute-window-472313-g9}"
REGION="${REGION:-asia-northeast3}"
SERVICE_NAME="${SERVICE_NAME:-babba-api}"
TASKS_QUEUE_NAME="${TASKS_QUEUE_NAME:-makeshop-sync-queue}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}✓${NC} $1"; }
fail() { echo -e "${RED}✗${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}!${NC} $1"; }
info() { echo "  $1"; }

echo ""
echo "=== Cloud Scheduler / Cloud Tasks 검증 ==="
echo "Project: $PROJECT_ID  Region: $REGION"
echo ""

SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --format='value(status.url)')"
[ -n "$SERVICE_URL" ] || fail "Cloud Run 서비스 URL을 가져올 수 없습니다: $SERVICE_NAME"
pass "Cloud Run URL: $SERVICE_URL"

# --- Cloud Tasks 큐 ---
if gcloud tasks queues describe "$TASKS_QUEUE_NAME" \
  --location="$REGION" \
  --project="$PROJECT_ID" &>/dev/null; then
  QUEUE_STATE="$(gcloud tasks queues describe "$TASKS_QUEUE_NAME" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format='value(state)')"
  pass "Cloud Tasks 큐 존재: $TASKS_QUEUE_NAME (state=$QUEUE_STATE)"
else
  fail "Cloud Tasks 큐 없음: $TASKS_QUEUE_NAME (setup-cloud-scheduler.sh Step 1.5 실행 필요)"
fi

# --- Job 공통 조회 ---
job_uri() {
  gcloud scheduler jobs describe "$1" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format='value(httpTarget.uri)' 2>/dev/null || true
}

job_schedule() {
  gcloud scheduler jobs describe "$1" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format='value(schedule)' 2>/dev/null || true
}

job_tz() {
  gcloud scheduler jobs describe "$1" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format='value(timeZone)' 2>/dev/null || true
}

job_state() {
  gcloud scheduler jobs describe "$1" \
    --location="$REGION" \
    --project="$PROJECT_ID" \
    --format='value(state)' 2>/dev/null || true
}

assert_job() {
  local name="$1"
  local expected_path="$2"
  local expected_schedule="$3"
  local expected_tz="$4"
  local uses_cloud_tasks="$5"

  local uri schedule tz state
  uri="$(job_uri "$name")"
  schedule="$(job_schedule "$name")"
  tz="$(job_tz "$name")"
  state="$(job_state "$name")"

  [ -n "$uri" ] || fail "Scheduler Job 없음: $name (setup-cloud-scheduler.sh 실행 필요)"

  pass "Scheduler Job: $name (state=$state)"
  info "schedule=$schedule  timeZone=$tz"
  info "uri=$uri"

  [[ "$uri" == *"$expected_path"* ]] || fail "$name URI가 예상과 다릅니다. expected=*${expected_path}* actual=$uri"
  [ "$schedule" = "$expected_schedule" ] || warn "$name 스케줄 확인: expected=$expected_schedule actual=$schedule"
  [ "$tz" = "$expected_tz" ] || warn "$name 타임존 확인: expected=$expected_tz actual=$tz"

  if [ "$uses_cloud_tasks" = "yes" ]; then
    pass "$name → Cloud Tasks 경유 (trigger 엔드포인트)"
  else
    pass "$name → Cloud Run 직접 호출 (Cloud Tasks 미사용, BackgroundTasks 처리)"
  fi
}

echo ""
echo "--- Job 설정 ---"
assert_job "babba-sync-makeshop" \
  "/tasks/sync/makeshop/trigger" \
  "30 17 * * *" \
  "Asia/Seoul" \
  "yes"

assert_job "babba-settlement-monthly-aggregation" \
  "/api/batch/settlement-monthly-aggregation" \
  "0 0 10 * *" \
  "UTC" \
  "no"

assert_job "babba-settlement-daily-aggregation" \
  "/api/batch/settlement-daily-aggregation" \
  "0 21 * * *" \
  "Asia/Seoul" \
  "no"

echo ""
echo "--- 아키텍처 요약 ---"
info "Makeshop: Scheduler → /tasks/sync/makeshop/trigger → $TASKS_QUEUE_NAME → /tasks/sync/makeshop/run"
info "월별 정산: Scheduler → /api/batch/settlement-monthly-aggregation (FastAPI BackgroundTasks)"
info "일별 MTD: Scheduler → /api/batch/settlement-daily-aggregation (FastAPI BackgroundTasks)"

if [ "${VERIFY_SCHEDULER_LIVE_TEST:-0}" != "1" ]; then
  echo ""
  pass "설정 검증 완료 (라이브 테스트 생략. 실행: VERIFY_SCHEDULER_LIVE_TEST=1 $0)"
  exit 0
fi

echo ""
echo "--- 라이브 테스트: Makeshop Scheduler → Cloud Tasks ---"
warn "babba-sync-makeshop 수동 실행 (동기화 부하 발생 가능)"
gcloud scheduler jobs run babba-sync-makeshop \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --quiet

sleep 25

LOG_FILTER='resource.type="cloud_run_revision" AND resource.labels.service_name="'"$SERVICE_NAME"'" AND (textPayload=~"\\[CT\\]" OR textPayload=~"통합 동기화" OR textPayload=~"INFO:app.main:\\[CT\\]")'
if gcloud logging read "$LOG_FILTER" \
  --project="$PROJECT_ID" \
  --limit=20 \
  --freshness=5m \
  --format='value(textPayload)' 2>/dev/null | tee /tmp/babba-sync-live.log | grep -q '\[CT\]'; then
  pass "Cloud Tasks enqueue 로그 확인 ([CT])"
else
  fail "최근 5분 내 [CT] 로그 없음 — trigger→Cloud Tasks 경로 점검 필요"
fi

if grep -q '통합 동기화' /tmp/babba-sync-live.log 2>/dev/null; then
  pass "동기화 실행 로그 확인 (/tasks/sync/makeshop/run)"
else
  warn "동기화 본문 로그는 아직 없을 수 있습니다 (큐 처리 지연). Cloud Tasks 콘솔에서 task 상태를 확인하세요."
fi

echo ""
pass "라이브 테스트 완료"
