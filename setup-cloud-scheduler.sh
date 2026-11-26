#!/bin/bash

#############################################################################
# setup-cloud-scheduler.sh
# 
# GCP Cloud Scheduler 통합 설정 스크립트
# 
# 필수: babba-sync-makeshop - Makeshop 동기화 (매일 17:30 KST)
#      - Cloud Tasks 경유: /tasks/sync/makeshop/trigger → makeshop-sync-queue → /run
#
# 선택: babba-settlement-monthly-aggregation - 정산 배치 (매월 10일 09:00 KST)
# 필수: babba-settlement-daily-aggregation - 일별 MTD (매일 21:00 KST)
#
# 사용법: chmod +x setup-cloud-scheduler.sh && ./setup-cloud-scheduler.sh
#############################################################################

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# 프로젝트 설정
PROJECT_ID="astute-window-472313-g9"
REGION="asia-northeast3"
SERVICE_NAME="babba-api"
SERVICE_ACCOUNT_NAME="babba-scheduler"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
CLOUD_RUN_SERVICE_ACCOUNT_NAME="cloud-run-sql"
CLOUD_RUN_SERVICE_ACCOUNT="${CLOUD_RUN_SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
TASKS_QUEUE_NAME="makeshop-sync-queue"
TASKS_QUEUE_LOCATION="$REGION"
TASKS_TRIGGER_ENDPOINT="/tasks/sync/makeshop/trigger"
TASKS_BACKGROUND_PATH="/tasks/sync/makeshop/run"

log_section "GCP Cloud Scheduler 통합 설정"

log_info "프로젝트 ID: $PROJECT_ID"
log_info "리전: $REGION"
log_info "서비스: $SERVICE_NAME"
log_info "서비스 계정: $SERVICE_ACCOUNT"
echo ""

# GCP 인증 재설정 (인증 토큰 갱신)
log_info "GCP 인증 확인 중..."
# if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &>/dev/null; then
#     log_warn "GCP 인증이 필요합니다"
#     log_info "다음 명령어를 실행하세요: gcloud auth login"
#     exit 1
# fi

# 비대화형 모드에서는 이미 인증된 것으로 가정
log_info "✓ GCP 인증 확인 완료"
echo ""
log_section "Step 1: 필수 API 활성화"

log_info "Cloud Scheduler API 활성화 중..."
gcloud services enable cloudscheduler.googleapis.com --project=$PROJECT_ID 2>/dev/null || \
    log_warn "API 활성화 실패 (이미 활성화되었을 수 있음)"

log_info "Cloud Tasks API 활성화 중..."
gcloud services enable cloudtasks.googleapis.com --project=$PROJECT_ID 2>/dev/null || \
    log_warn "API 활성화 실패 (이미 활성화되었을 수 있음)"

log_info "Cloud Build API 활성화 중..."
gcloud services enable cloud-build.googleapis.com --project=$PROJECT_ID 2>/dev/null || \
    log_warn "API 활성화 실패 (이미 활성화되었을 수 있음)"

log_info "✓ API 활성화 완료"
echo ""

# Step 1.5: Cloud Tasks 큐 생성
log_section "Step 1.5: Cloud Tasks 큐 생성"

log_info "Cloud Tasks 큐 생성 중: $TASKS_QUEUE_NAME"

# 큐가 이미 존재하는지 확인
if gcloud tasks queues describe $TASKS_QUEUE_NAME \
    --location=$TASKS_QUEUE_LOCATION \
    --project=$PROJECT_ID &>/dev/null; then
    log_info "✓ Cloud Tasks 큐가 이미 존재합니다"
else
    log_info "새 Cloud Tasks 큐 생성 중..."
    gcloud tasks queues create $TASKS_QUEUE_NAME \
        --location=$TASKS_QUEUE_LOCATION \
        --project=$PROJECT_ID
    log_info "✓ Cloud Tasks 큐 생성 완료"
fi

# Cloud Run 서비스 계정에 enqueue 권한 부여
log_info "Cloud Run 서비스 계정에 enqueue 권한 부여 중..."
gcloud tasks queues add-iam-policy-binding $TASKS_QUEUE_NAME \
    --location=$TASKS_QUEUE_LOCATION \
    --member="serviceAccount:${CLOUD_RUN_SERVICE_ACCOUNT}" \
    --role="roles/cloudtasks.enqueuer" \
    --project=$PROJECT_ID \
    --quiet || log_warn "권한 부여 실패 (이미 설정되었을 수 있음)"

log_info "✓ Cloud Tasks 큐 설정 완료"
echo ""

# Step 2: 서비스 계정 생성 (이미 있으면 생략)
log_section "Step 2: 서비스 계정 확인 및 생성"

if gcloud iam service-accounts describe $SERVICE_ACCOUNT --project=$PROJECT_ID &>/dev/null; then
    log_info "✓ 서비스 계정이 이미 존재합니다"
else
    log_info "서비스 계정 생성 중..."
    if gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
        --display-name="Babba API Scheduler Service Account" \
        --project=$PROJECT_ID 2>&1 | grep -q "already exists"; then
        log_info "✓ 서비스 계정이 이미 존재합니다"
    elif gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
        --display-name="Babba API Scheduler Service Account" \
        --project=$PROJECT_ID 2>/dev/null; then
        log_info "✓ 서비스 계정 생성 완료"
    else
        log_warn "서비스 계정 생성 실패 (이미 존재하거나 권한 문제)"
    fi
fi
echo ""

# Step 3: Cloud Run Invoker 역할 부여
log_section "Step 3: Cloud Run Invoker 역할 부여"

log_info "역할 부여 중..."
gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/run.invoker" \
    --region=$REGION \
    --project=$PROJECT_ID \
    --quiet || log_warn "역할 부여 실패 (이미 설정되었을 수 있음)"

log_info "✓ 역할 부여 완료"
echo ""

# Step 4: Cloud Run 서비스 URL 조회
log_section "Step 4: Cloud Run 서비스 URL 조회"

log_info "서비스 URL 조회 중..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region=$REGION \
    --format='value(status.url)' \
    --project=$PROJECT_ID)

if [ -z "$SERVICE_URL" ]; then
    log_error "Cloud Run 서비스를 찾을 수 없습니다"
    log_warn "다음 명령을 실행하세요: ./build-and-deploy.sh"
    exit 1
fi

log_info "서비스 URL: $SERVICE_URL"
echo ""

# Step 5: Cloud Scheduler Job 생성 (1. Makeshop 동기화)
log_section "Step 5: Cloud Scheduler Job 생성 - Makeshop 동기화"

JOB_NAME="babba-sync-makeshop"
SYNC_ENDPOINT="$TASKS_TRIGGER_ENDPOINT"
SYNC_SCHEDULE="30 17 * * *"  # 매일 17:30 KST

log_info "Job: $JOB_NAME"
log_info "  - 트리거 엔드포인트: $SYNC_ENDPOINT"
log_info "  - Cloud Tasks 백그라운드 엔드포인트: $TASKS_BACKGROUND_PATH"
log_info "  - 스케줄: $SYNC_SCHEDULE (매일 17:30 KST)"
log_info "  - 기능: 상품, 회원, 주문 통합 동기화"
echo ""

# 기존 Job 확인
if gcloud scheduler jobs describe $JOB_NAME --location=$REGION --project=$PROJECT_ID &>/dev/null; then
    log_warn "기존 Job이 있습니다. 업데이트 중..."
    gcloud scheduler jobs update http $JOB_NAME \
        --location=$REGION \
        --schedule="$SYNC_SCHEDULE" \
        --time-zone="Asia/Seoul" \
        --http-method=POST \
        --uri="${SERVICE_URL}${SYNC_ENDPOINT}" \
        --oidc-service-account-email=$SERVICE_ACCOUNT \
        --oidc-token-audience=$SERVICE_URL \
        --message-body='{}' \
        --project=$PROJECT_ID \
        --quiet
    log_info "✓ Job 업데이트 완료"
else
    log_info "새 Job 생성 중..."
    gcloud scheduler jobs create http $JOB_NAME \
        --location=$REGION \
        --schedule="$SYNC_SCHEDULE" \
        --time-zone="Asia/Seoul" \
        --http-method=POST \
        --uri="${SERVICE_URL}${SYNC_ENDPOINT}" \
        --oidc-service-account-email=$SERVICE_ACCOUNT \
        --oidc-token-audience=$SERVICE_URL \
        --message-body='{}' \
        --project=$PROJECT_ID
    log_info "✓ Job 생성 완료"
fi
echo ""
SYNC_JOB_NAME="$JOB_NAME"

# Step 7: Cloud Scheduler Job 생성 (2. 월별 정산 집계) - 자동 생성
log_section "Step 6: Cloud Scheduler Job 생성 - 정산 배치"

BATCH_JOB_NAME="babba-settlement-monthly-aggregation"
BATCH_ENDPOINT="/api/batch/settlement-monthly-aggregation"
BATCH_SCHEDULE="0 0 10 * *"

log_info "Job: $BATCH_JOB_NAME"
log_info "  - 엔드포인트: $BATCH_ENDPOINT"
log_info "  - 스케줄: $BATCH_SCHEDULE (매월 10일 09:00 KST)"
log_info "  - 기능: 월별 정산 집계 (지난달 자동 계산)"
log_info "  - 파라미터: 자동 계산 (수동 입력 없음)"
echo ""

# 기존 Job 확인
if gcloud scheduler jobs describe $BATCH_JOB_NAME --location=$REGION --project=$PROJECT_ID &>/dev/null; then
    log_warn "기존 Job이 있습니다. 업데이트 중..."
    gcloud scheduler jobs update http $BATCH_JOB_NAME \
        --location=$REGION \
        --schedule="$BATCH_SCHEDULE" \
        --time-zone="UTC" \
        --http-method=POST \
        --uri="${SERVICE_URL}${BATCH_ENDPOINT}" \
        --oidc-service-account-email=$SERVICE_ACCOUNT \
        --oidc-token-audience=$SERVICE_URL \
        --message-body='{}' \
        --project=$PROJECT_ID \
        --quiet
    log_info "✓ Job 업데이트 완료"
else
    log_info "새 Job 생성 중..."
    gcloud scheduler jobs create http $BATCH_JOB_NAME \
        --location=$REGION \
        --schedule="$BATCH_SCHEDULE" \
        --time-zone="UTC" \
        --http-method=POST \
        --uri="${SERVICE_URL}${BATCH_ENDPOINT}" \
        --oidc-service-account-email=$SERVICE_ACCOUNT \
        --oidc-token-audience=$SERVICE_URL \
        --message-body='{}' \
        --project=$PROJECT_ID
    log_info "✓ Job 생성 완료"
fi
echo ""

# Step 7: Cloud Scheduler Job 생성 (3. 일별 MTD 스냅샷)
log_section "Step 7: Cloud Scheduler Job 생성 - 일별 MTD 스냅샷"

DAILY_BATCH_JOB_NAME="babba-settlement-daily-aggregation"
DAILY_BATCH_ENDPOINT="/api/batch/settlement-daily-aggregation"
DAILY_BATCH_SCHEDULE="0 21 * * *"

log_info "Job: $DAILY_BATCH_JOB_NAME"
log_info "  - 엔드포인트: $DAILY_BATCH_ENDPOINT"
log_info "  - 스케줄: $DAILY_BATCH_SCHEDULE (매일 21:00 KST)"
log_info "  - 기능: 이번 달 누적(MTD) 정산 스냅샷 (소속 원장별 일별 매출)"
echo ""

if gcloud scheduler jobs describe $DAILY_BATCH_JOB_NAME --location=$REGION --project=$PROJECT_ID &>/dev/null; then
    log_warn "기존 Job이 있습니다. 업데이트 중..."
    gcloud scheduler jobs update http $DAILY_BATCH_JOB_NAME \
        --location=$REGION \
        --schedule="$DAILY_BATCH_SCHEDULE" \
        --time-zone="Asia/Seoul" \
        --http-method=POST \
        --uri="${SERVICE_URL}${DAILY_BATCH_ENDPOINT}" \
        --oidc-service-account-email=$SERVICE_ACCOUNT \
        --oidc-token-audience=$SERVICE_URL \
        --message-body='{}' \
        --project=$PROJECT_ID \
        --quiet
    log_info "✓ Job 업데이트 완료"
else
    log_info "새 Job 생성 중..."
    gcloud scheduler jobs create http $DAILY_BATCH_JOB_NAME \
        --location=$REGION \
        --schedule="$DAILY_BATCH_SCHEDULE" \
        --time-zone="Asia/Seoul" \
        --http-method=POST \
        --uri="${SERVICE_URL}${DAILY_BATCH_ENDPOINT}" \
        --oidc-service-account-email=$SERVICE_ACCOUNT \
        --oidc-token-audience=$SERVICE_URL \
        --message-body='{}' \
        --project=$PROJECT_ID
    log_info "✓ Job 생성 완료"
fi
echo ""

# Step 8: Job 설정 확인
log_section "Step 8: 생성된 Job 확인"

log_info "Cloud Scheduler Job 목록:"
echo ""
gcloud scheduler jobs list \
    --location=$REGION \
    --project=$PROJECT_ID \
    --filter="name:babba-*" \
    --format="table(name, schedule, status)" || log_warn "Job 목록 조회 실패"
echo ""

# Step 9: 최종 안내
log_section "✅ Step 9: 설정 완료!"

echo ""
log_info "Cloud Scheduler Job이 생성되었습니다"
echo ""
echo -e "${BLUE}📊 설정 요약:${NC}"
echo ""
echo "0️⃣  Cloud Tasks 큐"
echo "   - 이름: $TASKS_QUEUE_NAME"
echo "   - 리전: $TASKS_QUEUE_LOCATION"
echo "   - enqueuer 권한: $CLOUD_RUN_SERVICE_ACCOUNT"
echo "   - 백그라운드 엔드포인트: $TASKS_BACKGROUND_PATH"
echo ""
echo "1️⃣  Makeshop 동기화 Job"
echo "   - 이름: $SYNC_JOB_NAME"
echo "   - 실행: 매일 17:30 KST"
echo "   - 내용: 상품, 회원, 주문 통합 동기화"
echo "   - 주문 범위: 최근 30일 (Makeshop 30일 제한, 일 단위 청크 조회)"
echo ""

echo "2️⃣  정산 배치 Job"
echo "   - 이름: $BATCH_JOB_NAME"
echo "   - 실행: 매월 1일 09:01 KST"
echo "   - 내용: 월별 정산 집계"
echo "   - 파라미터: 지난달을 자동으로 계산"
echo "     * 1월 1일 실행: 12월 정산"
echo "     * 2월 1일 실행: 1월 정산"
echo "     * (이전달을 자동으로 계산하므로 수동 입력 필요 없음)"
echo ""

echo "3️⃣  일별 MTD 스냅샷 Job"
echo "   - 이름: $DAILY_BATCH_JOB_NAME"
echo "   - 실행: 매일 21:00 KST"
echo "   - 내용: 이번 달 1일~당일 누적 정산 스냅샷"
echo "   - 용도: 소속 원장별 일별 매출 화면"
echo ""

echo -e "${BLUE}📚 문서 참고:${NC}"
echo "  - 동기화 설정: docs/CLOUD_SCHEDULER_SYNC_UNIFIED.md"
echo "  - 정산 배치: docs/CLOUD_SCHEDULER_SETUP.md"
echo "  - 가이드: docs/CLOUD_SCHEDULER_SYNC_UNIFIED.md"
echo ""

echo -e "${BLUE}🔍 다음 단계:${NC}"
echo "  1. GCP 콘솔 확인: https://console.cloud.google.com/cloudscheduler?project=$PROJECT_ID"
echo "  2. 로그 확인: gcloud logging read ... (위의 명령어 참고)"
echo "  3. Job 상태: gcloud scheduler jobs list --location=$REGION --project=$PROJECT_ID"
echo ""

echo -e "${GREEN}🎉 모든 설정이 완료되었습니다!${NC}"
echo ""
