# 🚀 babba-api 시작하기 (Quick Start)

이 가이드는 `babba-api`를 Google Cloud Run에 빠르게 배포하기 위한 단계별 지침입니다.

## 📋 사전 조건

- Docker 설치됨 ✅
- gcloud CLI 설치됨 (또는 설치 필요)
- GCP 프로젝트 생성됨: `astute-window-472313-g9`

## 🔧 단계별 설정

### 1단계: gcloud CLI 설치 (아직 설치하지 않은 경우)

**macOS:**
```bash
brew install --cask google-cloud-sdk
```

**또는 직접 다운로드:**
- https://cloud.google.com/sdk/docs/install

**설치 확인:**
```bash
gcloud --version
```

### 2단계: gcloud 로그인 및 프로젝트 설정

```bash
# Google 계정으로 로그인
gcloud auth login

# 프로젝트 설정
gcloud config set project astute-window-472313-g9

# 현재 설정 확인
gcloud config list
```

### 3단계: 필요한 GCP API 활성화

```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

**예상 출력:**
```
Operation "operations/..." finished successfully.
```

### 4단계: Artifact Registry 리포지토리 생성 (선택사항 - 스크립트에서 자동 생성 가능)

```bash
gcloud artifacts repositories create babba-registry \
  --repository-format=docker \
  --location=asia-northeast3 \
  --description="Docker repo for babba-api"
```

### 5단계: Docker 인증 설정

```bash
gcloud auth configure-docker asia-northeast3-docker.pkg.dev
```

**프롬프트에서 "Y"를 입력하고 엔터**

### 6단계: 배포 스크립트 실행

```bash
chmod +x build-and-deploy.sh
./build-and-deploy.sh
```

**스크립트가 다음 작업을 자동으로 수행합니다:**
1. `.env` 파일 로드 (프로젝트 ID, 리전 등)
2. Artifact Registry 리포지토리 확인/생성
3. 로컬에서 Docker 이미지 빌드
4. Artifact Registry에 이미지 푸시
5. Cloud Run 배포

**예상 완료 시간: 2-5분**

### 7단계: 배포 완료 확인

스크립트가 완료되면 다음과 같은 출력이 표시됩니다:

```
[INFO] ================= 배포 완료 =================
[INFO] 서비스 URL: https://babba-api-xxxxx-nw.a.run.app
[INFO] API 호출 예시:
  curl https://babba-api-xxxxx-nw.a.run.app/
  curl 'https://babba-api-xxxxx-nw.a.run.app/items/42?q=test'
```

### 8단계: API 테스트

```bash
# 기본 엔드포인트
curl https://babba-api-xxxxx-nw.a.run.app/

# 아이템 조회
curl 'https://babba-api-xxxxx-nw.a.run.app/items/42?q=hello'

# 브라우저에서
# https://babba-api-xxxxx-nw.a.run.app/docs
```

## 📊 배포 후 관리

### Cloud Run 로그 확인

```bash
gcloud run services describe babba-api \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9

# 실시간 로그
gcloud logging read "resource.type=cloud_run_revision" \
  --limit 50 \
  --format json
```

### 최소 인스턴스 0으로 설정 (유휴 비용 제거)

```bash
gcloud run services update babba-api \
  --region=asia-northeast3 \
  --min-instances 0 \
  --project=astute-window-472313-g9
```

### 이미지 업데이트 배포

코드를 수정하고 다시 배포하려면:

```bash
./build-and-deploy.sh
```

또는 수동으로:

```bash
docker build -t babba-api:latest .
docker tag babba-api:latest asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest
docker push asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest
gcloud run deploy babba-api \
  --image asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9
```

### Artifact Registry 이미지 관리

```bash
# 이미지 목록 확인
gcloud artifacts docker images list asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry

# 불필요한 이미지 삭제
gcloud artifacts docker images delete \
  asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:old-tag
```

## 🆘 트러블슈팅

### gcloud 명령어를 찾을 수 없음

```bash
# gcloud 설치 확인
which gcloud

# 경로 추가 (필요시)
export PATH="/usr/local/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/bin:$PATH"
```

### Docker 빌드 실패

```bash
# Docker 실행 중인지 확인
docker ps

# 없으면 Docker Desktop 시작
```

### 배포 실패 - 인증 오류

```bash
# 인증 재설정
gcloud auth login
gcloud config set project astute-window-472313-g9

# Docker 인증 재설정
gcloud auth configure-docker asia-northeast3-docker.pkg.dev --quiet
```

### Artifact Registry 리포지토리 이미 존재

스크립트가 자동으로 확인하고 이미 존재하면 건너뜁니다. 문제가 있으면:

```bash
# 기존 리포지토리 확인
gcloud artifacts repositories describe babba-registry \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9
```

### 포트 오류

Dockerfile의 `PORT` 환경변수를 확인하세요:

```dockerfile
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

## 💡 팁 & 최적화

### .env 파일 커스터마이징

`.env` 파일을 편집하여 설정을 조정할 수 있습니다:

```bash
# 메모리 및 CPU 변경
MEMORY=512Mi
CPU=2

# 최대 인스턴스 조정
MAX_INSTANCES=50

# 최소 인스턴스 설정 (0 권장)
MIN_INSTANCES=0
```

### 비용 모니터링

```bash
# GCP Console에서 비용 확인
# https://console.cloud.google.com/billing/

# 또는 CLI로 구성원 확인
gcloud billing accounts list
```

## 📚 추가 리소스

- [Cloud Run 문서](https://cloud.google.com/run/docs)
- [Artifact Registry 문서](https://cloud.google.com/artifact-registry/docs)
- [GCP 배포 상세 가이드](./GCP_DEPLOYMENT.md)
- [비용 최적화](./GCP_DEPLOYMENT.md#-비용-절감-전략)

## 🎯 다음 단계

1. ✅ 배포 완료
2. 📊 모니터링 설정 (선택사항)
3. 🔐 비공개 API로 변경 (선택사항)
4. 🚀 CI/CD 파이프라인 추가 (선택사항)

---

**설정 완료! 이제 `./build-and-deploy.sh`를 실행하면 배포됩니다.** 🎉
