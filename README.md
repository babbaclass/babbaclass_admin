# babba-api

FastAPI + Uvicorn을 Google Cloud Run에 배포하는 최소 비용 구성입니다.

- **프로젝트 ID**: `astute-window-472313-g9`
- **리전**: `asia-northeast3` (서울)
- **Artifact Registry**: `babba-registry`
- **Cloud Run 서비스**: `babba-api`

## 🚀 빠른 시작

### 1단계: gcloud CLI 설치 및 인증

```bash
# macOS에서 설치
brew install --cask google-cloud-sdk

# 또는 다운로드: https://cloud.google.com/sdk/docs/install

# 로그인 및 프로젝트 설정
gcloud auth login
gcloud config set project astute-window-472313-g9
```

### 2단계: 필요한 API 활성화

```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

### 3단계: 배포 실행

```bash
./build-and-deploy.sh
```

**완료! 배포 URL이 출력됩니다.**

---

## 로컬에서 Docker로 실행

### 🚀 자동 스크립트 사용 (권장)

```bash
# 1. 이미지 빌드 및 컨테이너 실행
chmod +x local-run.sh
./local-run.sh

# 2. 로그 확인
./local-run.sh --logs

# 3. 컨테이너 중지
./local-run.sh --stop

# 4. 컨테이너 셸 접속
./local-run.sh --shell

# 5. 정리 (컨테이너 및 이미지 제거)
./local-run.sh --clean
```

**사용 가능한 명령어:**

| 명령어 | 설명 |
|--------|------|
| `./local-run.sh` 또는 `./local-run.sh run` | 이미지 빌드 및 컨테이너 실행 |
| `./local-run.sh stop` | 실행 중인 컨테이너 중지 |
| `./local-run.sh logs` | 실시간 로그 확인 (Ctrl+C로 종료) |
| `./local-run.sh shell` | 컨테이너 셸 접속 |
| `./local-run.sh clean` | 컨테이너 및 이미지 완전 제거 |

### 📍 접속 URL

스크립트 실행 후 다음 URL을 사용:

- **API 루트**: http://127.0.0.1:8080/
- **Admin 패널**: http://127.0.0.1:8080/admin/
- **Swagger 문서**: http://127.0.0.1:8080/docs/

### 수동 실행 (스크립트 미사용)

1) 이미지 빌드

```bash
docker build -t babba-api:local .
```

2) 컨테이너 실행 (기본 포트 8080)

```bash
docker run --rm -p 8080:8080 -e PORT=8080 babba-api:local
```

3) 확인

```bash
curl http://localhost:8080/
```

## Google Cloud Run 배포 (최소 비용 구성)

로컬 Docker 빌드 → Artifact Registry 푸시 → Cloud Run 배포 (Cloud Build 미사용으로 빌드 비용 절감)

### 사전 준비

gcloud CLI 설치 및 로그인, 프로젝트 선택

```bash
gcloud auth login
gcloud config set project <YOUR_PROJECT_ID>
```

필요 API 활성화 (Cloud Build 제외)

```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

### 1단계: 환경 변수 설정

`build-and-deploy.sh` 스크립트를 사용하거나 아래 값을 수동 설정

```bash
export PROJECT_ID="<YOUR_PROJECT_ID>"
export REGION="asia-northeast3"              # 서울 리전 (또는 다른 리전)
export REGISTRY="asia-northeast3-docker.pkg.dev"
export REPO_NAME="babba"                    # Artifact Registry 리포지토리명
export SERVICE_NAME="babba-api"             # Cloud Run 서비스명
export IMAGE_NAME="babba-api"
export IMAGE_TAG="latest"
```

### 2단계: Artifact Registry 리포지토리 생성 (최초 1회)

```bash
gcloud artifacts repositories create $REPO_NAME \
  --repository-format=docker \
  --location=$REGION \
  --description="Docker repo for babba-api"
```

### 3단계: Docker 리포지토리에 인증 (로컬 머신에서 1회)

```bash
gcloud auth configure-docker $REGISTRY
```

### 4단계: 로컬에서 이미지 빌드 및 푸시

```bash
# 이미지 빌드 (로컬)
docker build -t $IMAGE_NAME:$IMAGE_TAG .

# 이미지 태그 지정 (Artifact Registry 경로)
docker tag $IMAGE_NAME:$IMAGE_TAG \
  $REGISTRY/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:$IMAGE_TAG

# Artifact Registry에 푸시
docker push $REGISTRY/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:$IMAGE_TAG
```

### 5단계: Cloud Run 배포

```bash
gcloud run deploy $SERVICE_NAME \
  --image $REGISTRY/$PROJECT_ID/$REPO_NAME/$IMAGE_NAME:$IMAGE_TAG \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 256Mi \
  --cpu 1 \
  --max-instances 100
```

### 자동 배포 스크립트 사용 (권장)

`build-and-deploy.sh`를 사용하면 위 과정을 자동화할 수 있습니다.

```bash
chmod +x build-and-deploy.sh
./build-and-deploy.sh
```

### 비용 절감 팁

| 항목 | 기본값 | 절감 팁 |
|------|--------|---------|
| 빌드 | Cloud Build | **로컬 빌드** (이 가이드) |
| 스토리지 | 이미지 저장 | 필요 없는 태그 정기 삭제 (`gcloud artifacts docker images delete ...`) |
| 메모리 | 256Mi | 최소값 (간단한 API는 256Mi로 충분) |
| CPU | 1 | 기본값 (요청 중에만 청구) |
| 요청당 비용 | 기본 | 프리 티어 활용 (월 200만 건 무료) |
| 최소 인스턴스 | 1 | **0** 추천 (사용 안 할 때 비용 X, 콜드 스타트 용인 가능) |

최소 인스턴스 0으로 설정 시 첫 요청에 약 1-2초 지연 발생 (트래픽 없을 때 비용 0)

```bash
# 최소 인스턴스 0 설정 (배포 후 변경)
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --min-instances 0
```

### 참고

- Cloud Run은 컨테이너 시작 시 `PORT` 환경변수를 설정합니다. `Dockerfile`은 `${PORT:-8080}`를 사용하므로 자동으로 포트를 인식합니다.
- 리전: 서울 `asia-northeast3`, 도쿄 `asia-northeast1`, 싱가포르 `asia-southeast1` 등
- 로컬 빌드로 **Cloud Build 비용(시간당 과금) 완전 제거**
- 더 자세한 Cloud Run 과금 정보: https://cloud.google.com/run/pricing

---

## 📚 가이드 문서

프로젝트에 포함된 상세 가이드 문서들입니다.

### 🚀 시작 가이드

| 문서 | 설명 | 소요시간 |
|------|------|---------|
| [**QUICKSTART.md**](./QUICKSTART.md) | 프로젝트 기본 설정 및 로컬 실행 | 5분 |
| [**MAKESHOP_QUICK_START.md**](./MAKESHOP_QUICK_START.md) | Makeshop API 3단계 빠른 시작 | 3분 |

### 📖 상세 설정 가이드

| 문서 | 설명 | 대상 |
|------|------|------|
| [**DEPLOYMENT_GUIDE.md**](./DEPLOYMENT_GUIDE.md) | Cloud Run 배포 최종 가이드 (5단계) | 프로덕션 배포 |
| [**CLOUD_RUN_SETUP.md**](./CLOUD_RUN_SETUP.md) | Cloud Run + Cloud SQL 완전 설정 (8단계) | 엔드-투-엔드 구성 |
| [**CLOUD_RUN_DEPLOY.md**](./CLOUD_RUN_DEPLOY.md) | Cloud Run 배포 빠른 참조 | 빠른 참고 |
| [**LOCAL_TEST.md**](./LOCAL_TEST.md) | 로컬에서 SQLite로 테스트 | 개발 환경 |
| [**LOCAL_TEST_RESULT.md**](./LOCAL_TEST_RESULT.md) | 로컬 테스트 결과 및 검증 | 테스트 결과 |
| [**MAKESHOP_SETUP.md**](./MAKESHOP_SETUP.md) | Makeshop API 완전 설정 가이드 | Makeshop 통합 |
| [**MAKESHOP_INTEGRATION_DONE.md**](./MAKESHOP_INTEGRATION_DONE.md) | Makeshop 통합 완료 요약 | 통합 상태 확인 |

### 💰 비용 분석

| 문서 | 설명 | 대상 |
|------|------|------|
| [**COST_SUMMARY.md**](./COST_SUMMARY.md) | 월간 비용 한눈에 보기 | 빠른 참조 |
| [**COST_ESTIMATION.md**](./COST_ESTIMATION.md) | db-f1-micro 상세 비용 분석 | 비용 최적화 |
| [**COST_ESTIMATION_DETAILED.md**](./COST_ESTIMATION_DETAILED.md) | 정확한 시간 단위 계산 및 할인 | 재무 분석 |
| [**CLOUD_SQL_EDITION.md**](./CLOUD_SQL_EDITION.md) | Cloud SQL 에디션 비교 | 버전 선택 |
| [**CLOUD_SQL_SETUP.md**](./CLOUD_SQL_SETUP.md) | Cloud SQL 기본 설정 | DB 초기화 |

### 📋 기타 문서

| 문서 | 설명 |
|------|------|
| [**ADMIN_PANEL.md**](./ADMIN_PANEL.md) | FastAPI Admin 패널 사용 가이드 |
| [**GCP_DEPLOYMENT.md**](./GCP_DEPLOYMENT.md) | GCP 배포 기본 정보 |

---

## 📖 가이드별 추천 읽기 순서

### 🟢 초보자 경로
1. `README.md` (현재 문서) - 프로젝트 개요
2. `QUICKSTART.md` - 기본 설정
3. `LOCAL_TEST.md` - 로컬 테스트
4. `MAKESHOP_QUICK_START.md` - Makeshop 연동

### 🟡 배포 준비 경로
1. `DEPLOYMENT_GUIDE.md` - 배포 가이드
2. `CLOUD_RUN_SETUP.md` - 상세 설정
3. `COST_ESTIMATION.md` - 비용 확인

### 🔴 전문가 경로
1. `CLOUD_RUN_SETUP.md` - 엔드-투-엔드 구성
2. `MAKESHOP_SETUP.md` - Makeshop API 완전 가이드
3. `COST_ESTIMATION_DETAILED.md` - 정확한 비용 분석

### 💼 비용 최적화 경로
1. `COST_SUMMARY.md` - 빠른 참조
2. `COST_ESTIMATION.md` - 시나리오별 분석
3. `COST_ESTIMATION_DETAILED.md` - 할인 적용 계산
4. `CLOUD_SQL_EDITION.md` - 에디션 비교

---

## 🏗️ 프로젝트 구조

```
babba-api/
├── README.md                          # 프로젝트 개요
├── QUICKSTART.md                      # 빠른 시작
├── DEPLOYMENT_GUIDE.md                # 배포 가이드
├── CLOUD_RUN_SETUP.md                 # Cloud Run 설정
├── CLOUD_RUN_DEPLOY.md                # Cloud Run 배포
├── CLOUD_SQL_SETUP.md                 # Cloud SQL 설정
├── CLOUD_SQL_EDITION.md               # 에디션 비교
├── COST_SUMMARY.md                    # 비용 요약
├── COST_ESTIMATION.md                 # 비용 추정
├── COST_ESTIMATION_DETAILED.md        # 상세 비용 분석
├── LOCAL_TEST.md                      # 로컬 테스트
├── LOCAL_TEST_RESULT.md               # 테스트 결과
├── MAKESHOP_SETUP.md                  # Makeshop API 설정
├── MAKESHOP_QUICK_START.md            # Makeshop 빠른 시작
├── MAKESHOP_INTEGRATION_DONE.md       # 통합 완료 요약
├── ADMIN_PANEL.md                     # Admin 패널
├── GCP_DEPLOYMENT.md                  # GCP 배포
│
├── requirements.txt                   # Python 의존성
├── Dockerfile                         # Cloud Run 컨테이너
├── .env.makeshop                      # Makeshop 환경변수 템플릿
│
├── app/
│   ├── __init__.py
│   ├── main.py                        # FastAPI 메인 앱
│   ├── models.py                      # SQLAlchemy ORM 모델
│   ├── database.py                    # DB 연결 설정
│   ├── admin.py                       # FastAPI Admin 설정
│   └── services/
│       ├── __init__.py
│       └── makeshop_service.py        # Makeshop API 클라이언트
│
├── main_local.py                      # 로컬 SQLite 테스트 앱
├── babba_local.db                     # 로컬 테스트 DB
│
├── deploy.sh                          # 배포 자동화 스크립트
├── build-and-deploy.sh                # 빌드 및 배포 스크립트
├── local-run.sh                       # 로컬 Docker 빌드 및 실행 스크립트 ⭐
└── main_local.py                      # 로컬 SQLite 테스트 앱
```

---

## 🔗 빠른 링크

### 📄 신규 문서 (2025-11-02)
- ⭐ [docs/INDEX.md](./docs/INDEX.md) - 모든 문서 인덱스
- 🚀 [docs/LOCAL_BUILD_GUIDE.md](./docs/LOCAL_BUILD_GUIDE.md) - 로컬 Docker 빌드 가이드
- 🔧 [docs/SQLADMIN_INTEGRATION.md](./docs/SQLADMIN_INTEGRATION.md) - sqladmin 통합 가이드

### 📚 기타 가이드
- 🚀 [QUICKSTART.md](./QUICKSTART.md) - 5분 안에 시작
- 📦 [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - 배포 방법
- 💰 [COST_SUMMARY.md](./COST_SUMMARY.md) - 월간 비용
- 🔌 [MAKESHOP_QUICK_START.md](./MAKESHOP_QUICK_START.md) - Makeshop 연동
- 📚 [MAKESHOP_SETUP.md](./MAKESHOP_SETUP.md) - Makeshop 완전 가이드
- 🧪 [LOCAL_TEST.md](./LOCAL_TEST.md) - 로컬 테스트

---

## 💡 주요 기능

✅ **FastAPI** - 현대적 Python 웹 프레임워크  
✅ **SQLAlchemy 2.0+** - 강력한 ORM  
✅ **Cloud SQL** - 관리형 MySQL 데이터베이스  
✅ **Cloud Run** - 서버리스 컨테이너 실행  
✅ **Makeshop API** - 이커머스 플랫폼 통합  
✅ **자동 Swagger 문서** - `/docs` 엔드포인트  
✅ **Admin Tools** - CSV 템플릿/임포트, Google Sheet 임포트(`/admin/tools-ui` 및 `/admin-api/*`)

### Admin Tools 빠른 사용법

- CSV 회사 템플릿 다운로드: `GET /admin-api/tools/templates/companies.csv`
- CSV 회사 임포트: `POST /admin-api/tools/import/companies` (multipart/form-data, `file` 필드)
- GUI: `/admin/tools-ui`에서 템플릿/업로드 버튼 제공
- Google Sheet → DB 임포트: `POST /admin-api/sheets/import`
  - Body(JSON):
    ```json
    {
      "sheet_url": "https://docs.google.com/spreadsheets/d/XXXXX",
      "sheet_name": "시트명(옵션)",
      "table_name": "테이블명(옵션)",
      "truncate_before": false
    }
    ```
  - 동작: CSV로 다운로드 → 스키마 추론 → 테이블 생성/보강 → 데이터 적재
  - 안전 장치:
    - 테이블명은 기본적으로 `sheet_` 접두사가 강제됩니다(예: `sheet_google_sheet`).
    - 일부 예약 테이블명은 자동으로 `_data`가 붙습니다.
  - URL 예시:
    - 그대로 사용 가능: `https://docs.google.com/spreadsheets/d/<ID>/edit?gid=<GID>`
    - 서비스가 자동 변환: `.../export?format=csv&gid=<GID>` 형태로 변경하여 CSV를 조회합니다.
  - 성공 응답 예시:
    ```json
    {
      "status": "ok",
      "table_name": "google_sheet",
      "created_table": true,
      "columns": {"name": "VARCHAR(255)", "price": "INT"},
      "rows_inserted": 42
    }
    ```
  - 대표 에러 케이스:
    - `시트 가져오기 실패: CSV 데이터가 비었습니다.` → 빈 시트 / 잘못된 sheet_name
    - `Google Sheet을 찾을 수 없습니다(404). URL의 ID/gid가 올바른지 확인하세요.`
    - `Google Sheet 접근이 거부되었습니다(403). 시트 공유 설정을 '링크가 있는 모든 사용자'로 변경하세요.`
    - 너무 긴 텍스트: 자동으로 TEXT 컬럼 지정
    - 중복 헤더: `header`, `header_1`, `header_2` 형태로 자동 리네이밍

---

## 📞 추가 정보

자세한 내용은 해당 가이드 문서를 참고하세요!# Test deployment trigger
