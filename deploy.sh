#!/bin/bash

# Cloud Run + Cloud SQL 자동 배포 스크립트

set -e  # 오류 발생 시 중지

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 설정값 로드
source .env

# 환경 변수 호환 처리: .env에 PROJECT_ID만 있는 경우를 대비
GCP_PROJECT_ID=${GCP_PROJECT_ID:-$PROJECT_ID}

echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "${BLUE}Cloud Run + Cloud SQL 배포 스크립트${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}\n"

# Step 1: 서비스 계정 생성
echo -e "${YELLOW}[Step 1/6] 서비스 계정 생성 중...${NC}"
SA_NAME="cloud-run-sql"
SA_EMAIL="${SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe $SA_EMAIL --project=$GCP_PROJECT_ID &>/dev/null; then
    echo -e "${GREEN}✓ 서비스 계정 이미 존재${NC}"
else
    echo -e "${YELLOW}서비스 계정 생성 중...${NC}"
    gcloud iam service-accounts create $SA_NAME \
        --display-name="Cloud Run Cloud SQL" \
        --project=$GCP_PROJECT_ID
    echo -e "${GREEN}✓ 서비스 계정 생성됨${NC}"
fi

# Step 2: Cloud SQL 권한 부여
echo -e "\n${YELLOW}[Step 2/6] Cloud SQL 권한 부여 중...${NC}"
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member=serviceAccount:$SA_EMAIL \
    --role=roles/cloudsql.client \
    --quiet --verbosity=none
echo -e "${GREEN}✓ Cloud SQL 권한 부여 완료${NC}"

# Step 3: Artifact Registry 저장소 생성
echo -e "\n${YELLOW}[Step 3/8] Artifact Registry 저장소 생성 중...${NC}"
if gcloud artifacts repositories describe $REPO_NAME --location=$REGION --project=$GCP_PROJECT_ID &>/dev/null; then
    echo -e "${GREEN}✓ 저장소 이미 존재${NC}"
else
    echo -e "${YELLOW}저장소 생성 중...${NC}"
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --project=$GCP_PROJECT_ID
    echo -e "${GREEN}✓ 저장소 생성됨${NC}"
fi

# Step 4: Docker 마이그레이션 이미지 빌드
echo -e "\n${YELLOW}[Step 4/8] Docker 마이그레이션 이미지 빌드 중...${NC}"
MIGRATION_IMAGE_URI="${REGISTRY}/${GCP_PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}-migration:${IMAGE_TAG}"
echo -e "${BLUE}마이그레이션 이미지 URI: ${MIGRATION_IMAGE_URI}${NC}"

docker build -f Dockerfile.migration -t $MIGRATION_IMAGE_URI .
echo -e "${GREEN}✓ Docker 마이그레이션 이미지 빌드 완료${NC}"

# Step 5: Docker 서비스 이미지 빌드
echo -e "\n${YELLOW}[Step 5/8] Docker 서비스 이미지 빌드 중...${NC}"
IMAGE_URI="${REGISTRY}/${GCP_PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:${IMAGE_TAG}"
echo -e "${BLUE}서비스 이미지 URI: ${IMAGE_URI}${NC}"

docker build -t $IMAGE_URI .
echo -e "${GREEN}✓ Docker 서비스 이미지 빌드 완료${NC}"

# Step 6: Docker 이미지 푸시
echo -e "\n${YELLOW}[Step 6/8] Docker 이미지 푸시 중...${NC}"
docker push $MIGRATION_IMAGE_URI
docker push $IMAGE_URI
echo -e "${GREEN}✓ Docker 이미지 푸시 완료${NC}"

# Step 7: Cloud Run Job 배포 및 실행 (마이그레이션)
echo -e "\n${YELLOW}[Step 7/8] Cloud Run Job 마이그레이션 실행 중...${NC}"
JOB_NAME="${SERVICE_NAME}-migration"

echo -e "${YELLOW}마이그레이션 Job 배포...${NC}"
gcloud run jobs deploy $JOB_NAME \
    --image=$MIGRATION_IMAGE_URI \
    --region=$REGION \
    --project=$GCP_PROJECT_ID \
    --service-account=$SA_EMAIL \
    --memory=${MEMORY:-512Mi} \
    --cpu=${CPU:-1} \
    --set-env-vars "CLOUD_SQL_INSTANCE=${CLOUD_SQL_INSTANCE},DB_USER=${DB_USER},DB_PASSWORD=${DB_PASSWORD},DB_NAME=${DB_NAME}" \
    --execute-now \
    --quiet

echo -e "${GREEN}✓ Cloud Run Job 마이그레이션 실행됨${NC}"

# Step 8: Cloud Run 서비스 배포
echo -e "\n${YELLOW}[Step 8/8] Cloud Run 서비스 배포 중...${NC}"
gcloud run deploy $SERVICE_NAME \
    --image=$IMAGE_URI \
    --platform=managed \
    --region=$REGION \
    --project=$GCP_PROJECT_ID \
    --allow-unauthenticated \
    --service-account=$SA_EMAIL \
    --memory=${MEMORY:-512Mi} \
    --cpu=${CPU:-1} \
    --timeout=300 \
    --set-env-vars "CLOUD_SQL_INSTANCE=${CLOUD_SQL_INSTANCE},DB_USER=${DB_USER},DB_PASSWORD=${DB_PASSWORD},DB_NAME=${DB_NAME}"

echo -e "${GREEN}✓ 배포 완료!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region=$REGION \
    --project=$GCP_PROJECT_ID \
    --format='value(status.url)')

echo -e "${GREEN}✓ 배포 완료!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════${NC}"
echo -e "\n서비스 URL: ${GREEN}${SERVICE_URL}${NC}"
echo -e "\n테스트 명령어:"
echo -e "  # Health Check"
echo -e "  ${YELLOW}curl ${SERVICE_URL}/health${NC}"
echo -e "\n  # User 생성"
echo -e "  ${YELLOW}curl -X POST ${SERVICE_URL}/users \\${NC}"
echo -e "  ${YELLOW}-H 'Content-Type: application/json' \\${NC}"
echo -e "  ${YELLOW}-d '{\"email\":\"test@example.com\",\"username\":\"testuser\"}'${NC}"
echo -e "\n  # User 조회"
echo -e "  ${YELLOW}curl ${SERVICE_URL}/users${NC}"
echo -e "\n  # Swagger UI"
echo -e "  ${YELLOW}${SERVICE_URL}/docs${NC}"
echo -e "\n${BLUE}═══════════════════════════════════════════${NC}\n"
