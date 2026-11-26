#!/bin/bash

#############################################################################
# build-and-deploy.sh
# 로컬에서 Docker 이미지를 빌드하고 Artifact Registry에 푸시한 뒤
# Cloud Run으로 배포하는 자동화 스크립트
#
# 사용법: ./build-and-deploy.sh
# 또는: PROJECT_ID=my-project REGION=asia-northeast3 ./build-and-deploy.sh
#############################################################################

set -e  # 에러 발생 시 스크립트 중단

# 색상 정의 (터미널 출력용)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================================
# 0. .env 파일 로드
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ -f "$ENV_FILE" ]; then
    log_info ".env 파일을 로드 중..."
    source "$ENV_FILE"
    log_info ".env 파일 로드 완료"
else
    log_warn ".env 파일이 없습니다. .env.example을 .env로 복사하고 편집하세요."
    log_warn "cp .env.example .env"
    exit 1
fi

echo ""

# ============================================================================
# 1. 환경 변수 설정
# ============================================================================

PROJECT_ID="${PROJECT_ID:=$(gcloud config get-value project 2>/dev/null || echo "")}"
if [ -z "$PROJECT_ID" ]; then
    log_error "PROJECT_ID를 찾을 수 없습니다. .env 파일에서 PROJECT_ID를 설정하거나 'gcloud config set project <PROJECT_ID>'를 실행하세요."
    exit 1
fi

REGION="${REGION:-asia-northeast3}"
REGISTRY="${REGISTRY:-asia-northeast3-docker.pkg.dev}"
REPO_NAME="${REPO_NAME:-babba-registry}"
SERVICE_NAME="${SERVICE_NAME:-babba-api}"
IMAGE_NAME="${IMAGE_NAME:-babba-api}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
MEMORY="${MEMORY:-256Mi}"
CPU="${CPU:-1}"
MAX_INSTANCES="${MAX_INSTANCES:-2}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"

FULL_IMAGE_PATH="${REGISTRY}/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}"
FULL_IMAGE_URL="${FULL_IMAGE_PATH}:${IMAGE_TAG}"

log_info "================= 배포 환경 설정 ================="
log_info "프로젝트 ID: $PROJECT_ID"
log_info "리전: $REGION"
log_info "Artifact Registry: $REGISTRY"
log_info "리포지토리: $REPO_NAME"
log_info "서비스명: $SERVICE_NAME"
log_info "이미지 경로: $FULL_IMAGE_URL"
log_info "메모리: $MEMORY | CPU: $CPU | 최대 인스턴스: $MAX_INSTANCES"
echo ""

# ============================================================================
# 2. gcloud 로그인 확인
# ============================================================================

log_info "gcloud 로그인 상태 확인 중..."
if ! gcloud auth list 2>/dev/null | grep -q ACTIVE; then
    log_warn "gcloud 로그인이 필요합니다."
    gcloud auth login
fi
echo ""

# ============================================================================
# 3. Artifact Registry 리포지토리 확인 (없으면 생성)
# ============================================================================

log_info "Artifact Registry 리포지토리 확인 중..."
if gcloud artifacts repositories describe $REPO_NAME --location=$REGION --project=$PROJECT_ID &>/dev/null; then
    log_info "리포지토리 '$REPO_NAME' 이미 존재합니다."
else
    log_warn "리포지토리 '$REPO_NAME'을 생성 중..."
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="Docker repo for babba-api" \
        --project=$PROJECT_ID
    log_info "리포지토리 생성 완료"
fi
echo ""

# ============================================================================
# 4. Docker 리포지토리 인증 설정
# ============================================================================

log_info "Docker 리포지토리 인증 설정 중..."
gcloud auth configure-docker ${REGISTRY} --quiet --project=$PROJECT_ID
log_info "인증 설정 완료"
echo ""

# ============================================================================
# 5. Docker 이미지 빌드 (로컬)
# ============================================================================

log_info "Docker 이미지 빌드 중... (이미지: $IMAGE_NAME:$IMAGE_TAG)"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
log_info "이미지 빌드 완료"
echo ""

# ============================================================================
# 6. 이미지 태그 지정 (Artifact Registry 경로)
# ============================================================================

log_info "이미지 태그 지정 중... ($FULL_IMAGE_URL)"
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${FULL_IMAGE_URL}
log_info "태그 지정 완료"
echo ""

# ============================================================================
# 7. Artifact Registry에 푸시
# ============================================================================

log_info "Artifact Registry에 푸시 중... ($FULL_IMAGE_URL)"
docker push ${FULL_IMAGE_URL}
log_info "푸시 완료"
echo ""

# ============================================================================
# 8. Cloud Run 배포
# ============================================================================

log_info "Cloud Run 배포 중... (서비스: $SERVICE_NAME)"
gcloud run deploy ${SERVICE_NAME} \
    --image ${FULL_IMAGE_URL} \
    --region ${REGION} \
    --project=${PROJECT_ID} \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --memory ${MEMORY} \
    --cpu ${CPU} \
    --max-instances ${MAX_INSTANCES}

log_info "Cloud Run 배포 완료"
echo ""

# ============================================================================
# 9. 최소 인스턴스 설정 (필요시)
# ============================================================================

if [ "$MIN_INSTANCES" != "0" ]; then
    log_info "최소 인스턴스를 ${MIN_INSTANCES}로 설정 중..."
    gcloud run services update ${SERVICE_NAME} \
        --region=${REGION} \
        --project=${PROJECT_ID} \
        --min-instances ${MIN_INSTANCES}
fi

echo ""

# ============================================================================
# 10. 배포 정보 출력
# ============================================================================

log_info "================= 배포 완료 ================="
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID} --format='value(status.url)' 2>/dev/null || echo "https://배포-URL")
log_info "서비스 URL: $SERVICE_URL"
log_info "API 호출 예시:"
echo "  curl $SERVICE_URL/"
echo "  curl '$SERVICE_URL/items/42?q=test'"
echo ""
if [ "$MIN_INSTANCES" = "0" ]; then
    log_warn "최소 인스턴스 0으로 설정되어 있습니다. 첫 요청에 1-2초 콜드 스타트가 발생할 수 있습니다."
fi

