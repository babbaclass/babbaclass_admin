# babba-api: Cloud Run 최소 비용 배포 가이드

이 가이드는 로컬 Docker 빌드 + Artifact Registry + Cloud Run을 사용하여 **Cloud Build 비용 없이** 배포하는 방법을 설명합니다.

## 📋 빠른 시작

```bash
# 1. gcloud 설정 (첫 1회)
gcloud auth login
gcloud config set project YOUR-PROJECT-ID

# 2. 환경 변수 설정 (또는 .env.example을 참고하여 .env 생성)
export PROJECT_ID="YOUR-PROJECT-ID"
export REGION="asia-northeast3"

# 3. 배포 스크립트 실행 (자동으로 모든 단계 처리)
./build-and-deploy.sh
```

## 🚀 배포 프로세스

### 단계별 수동 배포

```bash
# 1. 환경 변수 설정
export PROJECT_ID="YOUR-PROJECT-ID"
export REGION="asia-northeast3"
export REGISTRY="asia-northeast3-docker.pkg.dev"
export REPO_NAME="babba"
export SERVICE_NAME="babba-api"
export IMAGE_NAME="babba-api"
export IMAGE_TAG="latest"

# 2. Artifact Registry API 활성화
gcloud services enable artifactregistry.googleapis.com run.googleapis.com

# 3. Artifact Registry 리포지토리 생성 (최초 1회)
gcloud artifacts repositories create $REPO_NAME \
  --repository-format=docker \
  --location=$REGION \
  --description="Docker repo for babba-api"

# 4. Docker 인증 설정
gcloud auth configure-docker $REGISTRY

# 5. 로컬에서 이미지 빌드
docker build -t $IMAGE_NAME:$IMAGE_TAG .

# 6. 이미지 태그 지정
docker tag $IMAGE_NAME:$IMAGE_TAG \
  $REGISTRY/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:$IMAGE_TAG

# 7. Artifact Registry에 푸시
docker push $REGISTRY/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:$IMAGE_TAG

# 8. Cloud Run 배포
gcloud run deploy $SERVICE_NAME \
  --image $REGISTRY/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:$IMAGE_TAG \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 256Mi \
  --cpu 1 \
  --max-instances 2
```

## 💰 비용 절감 전략

### 1. Cloud Build 제거 ✅
- **이 가이드의 방식**: 로컬 빌드 → Artifact Registry 푸시 → Cloud Run 배포
- **제거된 비용**: Cloud Build 시간당 과금 (약 $0.003/분)

### Artifact Registry 과금
- **스토리지**: 0.5GB 이하 무료 (이 프로젝트는 ~200MB이므로 무료) ✅
- **데이터 전송**: 같은 리전 내 무료 (asia-northeast3 → asia-northeast3) ✅
- **합계 비용**: $0

### 2. 최소 인스턴스 설정
```bash
# 배포 후, 최소 인스턴스를 0으로 설정 (유휴 시간 비용 제거)
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --min-instances 0
```
- **트레이드오프**: 첫 요청에 1-2초 콜드 스타트 발생
- **절감**: 트래픽 없을 때 완전히 무료

### 3. 리소스 최소화
```bash
# 배포 시 최소 리소스로 설정
gcloud run deploy $SERVICE_NAME \
  --memory 256Mi \      # 최소값 128Mi도 가능 (간단한 API는 256Mi 충분)
  --cpu 1 \             # 요청 중에만 과금
  --max-instances 100   # 필요시 조정
```

### 4. Cloud Run 무료 할당량 활용
- **월 200만 건 요청**: 무료
- **월 600,000 GB-초**: 무료
- **월 60,000 vCPU-초**: 무료
- 대부분의 소규모 애플리케이션은 프리 티어 범위 내

## 📊 월간 예상 비용 (최소 구성)

| 항목 | 비용 | 비고 |
|------|------|------|
| Cloud Build | **$0** ✅ | 로컬 빌드 사용 |
| Artifact Registry 스토리지 | **$0** ✅ | 0.5GB 미만 무료 (~200MB) |
| Artifact Registry 전송 | **$0** ✅ | 같은 리전 내 무료 |
| Cloud Run (프리 티어) | **$0** ✅ | 월 200만 건까지 무료 |
| **합계 (기본 트래픽)** | **$0** 🎉 | 트래픽 없을 때 완전 무료 |
| 소규모 (500만 건 요청) | ~$0.50 - $1 | 초과분 요청 비용만 발생 |

**모든 빌드/저장/배포 인프라 비용 완전 제거!** 🚀

## 🔧 로컬 테스트

```bash
# Docker 이미지 로컬 테스트
docker build -t babba-api:local .
docker run --rm -p 8080:8080 -e PORT=8080 babba-api:local

# 다른 터미널에서
curl http://localhost:8080/
curl 'http://localhost:8080/items/42?q=test'
```

## 📝 이미지 관리

```bash
# Artifact Registry의 이미지 목록 확인
gcloud artifacts docker images list $REGISTRY/$PROJECT_ID/$REPO_NAME

# 불필요한 이미지 삭제 (스토리지 비용 절감)
gcloud artifacts docker images delete \
  $REGISTRY/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:old-tag

# 모든 태그 삭제 (최신만 유지)
gcloud artifacts docker images delete \
  $REGISTRY/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME --delete-tags
```

## 🌍 리전별 위치

| 리전 | 코드 | 위치 |
|------|------|------|
| 서울 | `asia-northeast3` | 한국 |
| 도쿄 | `asia-northeast1` | 일본 |
| 싱가포르 | `asia-southeast1` | 싱가포르 |
| 홍콩 | `asia-east1` | 홍콩 |
| 미국 동부 | `us-east1` | 미국 |

## 🔐 보안 및 인증

### 공개 API (현재 설정)
```bash
--allow-unauthenticated  # 누구나 접근 가능
```

### 비공개 API (권장)
```bash
# 배포 시 인증 요구
gcloud run deploy $SERVICE_NAME \
  --image ... \
  --no-allow-unauthenticated

# 접근 시 인증 토큰 필요
TOKEN=$(gcloud auth print-identity-token)
curl -H "Authorization: Bearer $TOKEN" https://babba-api-xxxxx.run.app/
```

## 📚 추가 리소스

- [Cloud Run 가격](https://cloud.google.com/run/pricing)
- [Artifact Registry 가격](https://cloud.google.com/artifact-registry/pricing)
- [Cloud Run 설정 참고](https://cloud.google.com/run/docs/configuring/services)
- [gcloud run deploy 옵션](https://cloud.google.com/sdk/gcloud/reference/run/deploy)

## 🆘 트러블슈팅

### 이미지 푸시 실패
```bash
# Docker 인증 재설정
gcloud auth configure-docker $REGISTRY --quiet
docker push $REGISTRY/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:$IMAGE_TAG
```

### Cloud Run 배포 실패
```bash
# 서비스 로그 확인
gcloud run services describe $SERVICE_NAME --region=$REGION
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
  --limit 50 --format json
```

### 포트 오류
- Dockerfile의 `${PORT:-8080}`이 환경변수를 인식하는지 확인
- `--port 8080` 플래그가 배포 명령에 포함되어 있는지 확인

---

**이 구성으로 Cloud Build 비용을 완전히 제거하고 최소한의 인프라 비용으로 FastAPI 서비스를 운영할 수 있습니다!**
