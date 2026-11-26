# GCP Cloud Scheduler 설정 가이드

이 가이드는 babba-api에서 정산 배치 작업을 **GCP Cloud Scheduler**를 사용하여 자동화하는 방법을 설명합니다.

## 📋 개요

- **프로젝트 ID**: `astute-window-472313-g9`
- **리전**: `asia-northeast3` (서울)
- **Cloud Run 서비스**: `babba-api`
- **배치 작업**: 월별 정산 집계 (매월 1일 오전 00:01 KST)

---

## 🚀 빠른 시작 (5분)

### 1. 필수 API 활성화

```bash
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable cloud-build.googleapis.com
```

### 2. Cloud Scheduler Job 생성 (웹 콘솔)

1. **GCP 콘솔**: [Cloud Scheduler](https://console.cloud.google.com/cloudscheduler)
2. **지역**: `asia-northeast3` (서울)
3. **작업 생성** 클릭:
   - **이름**: `babba-settlement-monthly-aggregation`
   - **빈도**: `1 0 1 * *` (매월 1일 00:01 UTC = 09:01 KST)
   - **시간대**: `UTC` (또는 `Asia/Seoul`)

### 3. 실행 설정

| 항목 | 값 |
|------|-----|
| 프로토콜 | `HTTP` |
| URL | `https://babba-api-<hash>.run.app/api/batch/settlement-monthly-aggregation` |
| HTTP 메서드 | `POST` |
| 인증 | `OIDC token` |
| 서비스 계정 | `<project>@appspot.gserviceaccount.com` |

---

## 📚 상세 설정 가이드

### 단계별 설정 (CLI 방식)

#### 1단계: Cloud Scheduler API 활성화

```bash
# 필수 API 활성화
gcloud services enable cloudscheduler.googleapis.com

# 확인
gcloud services list --enabled | grep cloudscheduler
```

#### 2단계: 서비스 계정 권한 설정

```bash
# 프로젝트 ID 설정
export PROJECT_ID="astute-window-472313-g9"
export SERVICE_ACCOUNT="babba-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"

# 서비스 계정 생성 (이미 있으면 생략)
gcloud iam service-accounts create babba-scheduler \
  --display-name="Babba API Scheduler Service Account"

# Cloud Run Invoker 역할 부여
gcloud run services add-iam-policy-binding babba-api \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/run.invoker" \
  --region="asia-northeast3"
```

#### 3단계: Cloud Scheduler Job 생성 (CLI)

```bash
# 환경 변수 설정
export PROJECT_ID="astute-window-472313-g9"
export REGION="asia-northeast3"
export SERVICE_NAME="babba-api"
export SCHEDULE="1 0 1 * *"  # 매월 1일 00:01 UTC (09:01 KST)
export ENDPOINT="/api/batch/settlement-monthly-aggregation"

# Cloud Run 서비스 URL 조회
export SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --format 'value(status.url)')

# Job 생성
gcloud scheduler jobs create http babba-settlement-monthly-aggregation \
  --location=$REGION \
  --schedule="$SCHEDULE" \
  --time-zone="Asia/Seoul" \
  --http-method=POST \
  --uri="${SERVICE_URL}${ENDPOINT}" \
  --oidc-service-account-email="babba-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience="${SERVICE_URL}"
```

---

## ⏰ 스케줄 표현식 (CRON)

### 주요 예제

| 설명 | CRON 표현식 |
|------|-----------|
| 매월 1일 00:01 UTC | `1 0 1 * *` |
| 매월 1일 09:01 KST | `1 0 1 * *` (UTC) 또는 표준 시간에 조정 |
| 매주 월요일 09:00 | `0 9 * * 1` |
| 매일 자정 | `0 0 * * *` |
| 매 시간 정각 | `0 * * * *` |

**형식**: `분 시간 일 월 요일`
- **분**: 0-59
- **시간**: 0-23 (UTC)
- **일**: 1-31
- **월**: 1-12
- **요일**: 0-6 (0=일요일, 1=월요일, ...)

---

## 🔧 API 엔드포인트 구현

### babba-api에 배치 엔드포인트 추가

`app/routers/batch.py` (새 파일 생성):

```python
"""
배치 작업 라우터 (Cloud Scheduler 연동)
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.services.settlement_service import SettlementService
import logging

router = APIRouter(prefix="/api/batch", tags=["batch"])
logger = logging.getLogger(__name__)


@router.post("/settlement-monthly-aggregation")
async def settlement_monthly_aggregation(background_tasks: BackgroundTasks):
    """
    월별 정산 집계 배치 작업
    
    매월 1일 00:01 UTC (09:01 KST)에 자동 실행
    
    ✨ 주요 특징:
    - 파라미터 입력 불필요 (자동 계산)
    - 호출된 날짜의 이전달을 자동으로 정산
    - 예: 2025-01-01 실행 → 2024-12월 정산
    - 예: 2025-02-01 실행 → 2025-01월 정산
    
    처리 과정:
    - 지난달 1일 ~ 말일의 완료된 주문 집계
    - 사용자별/회사별 월간 정산액 계산
    - 배경 작업으로 비동기 처리 (타임아웃 방지)
    
    Returns:
        dict: 배치 작업 스케줄 결과
    """
    db = SessionLocal()
    
    try:
        # 지난달 계산
        today = datetime.utcnow().date()
        if today.day == 1:
            # 이미 1일이면 지난달 사용
            first_of_current = today
        else:
            # 1일이 아니면 지난달 사용
            first_of_current = today.replace(day=1)
        
        # 지난달 마지막 날 구하기
        last_day_of_prev_month = first_of_current - timedelta(days=1)
        year = last_day_of_prev_month.year
        month = last_day_of_prev_month.month
        
        logger.info(f"월별 정산 집계 시작: {year}-{month:02d}")
        
        # 배경 작업으로 비동기 처리
        background_tasks.add_task(
            _run_settlement_aggregation,
            db=db,
            year=year,
            month=month
        )
        
        return {
            "status": "success",
            "message": f"Settlement aggregation scheduled for {year}-{month:02d}",
            "target_period": f"{year}-{month:02d}"
        }
    
    except Exception as e:
        logger.error(f"배치 작업 실패: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _run_settlement_aggregation(db, year: int, month: int):
    """
    실제 정산 집계 처리 (배경 작업)
    """
    try:
        result = SettlementService.aggregate_completed_orders_to_settlement(
            db=db,
            year=year,
            month=month
        )
        logger.info(f"정산 집계 완료: {year}-{month:02d} - {result}")
    except Exception as e:
        logger.error(f"정산 집계 실패: {str(e)}", exc_info=True)
    finally:
        db.close()


@router.post("/settlement-daily-aggregation")
async def settlement_daily_aggregation(background_tasks: BackgroundTasks):
    """
    일별 정산 집계 배치 작업
    
    매일 자정 (UTC) 또는 원하는 시간에 실행
    - 어제 하루의 완료된 주문을 일간 정산으로 집계
    """
    db = SessionLocal()
    
    try:
        # 어제 날짜
        yesterday = (datetime.utcnow() - timedelta(days=1)).date()
        year = yesterday.year
        month = yesterday.month
        day = yesterday.day
        
        logger.info(f"일별 정산 집계 시작: {year}-{month:02d}-{day:02d}")
        
        background_tasks.add_task(
            _run_daily_settlement_aggregation,
            db=db,
            year=year,
            month=month,
            day=day
        )
        
        return {
            "status": "success",
            "message": f"Daily settlement aggregation scheduled for {year}-{month:02d}-{day:02d}",
            "target_date": f"{year}-{month:02d}-{day:02d}"
        }
    
    except Exception as e:
        logger.error(f"일별 배치 작업 실패: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _run_daily_settlement_aggregation(db, year: int, month: int, day: int):
    """실제 일별 정산 집계 처리"""
    try:
        # 여기에 일별 정산 로직 추가
        logger.info(f"일별 정산 집계 완료: {year}-{month:02d}-{day:02d}")
    except Exception as e:
        logger.error(f"일별 정산 집계 실패: {str(e)}", exc_info=True)
    finally:
        db.close()


@router.get("/batch-health")
async def batch_health():
    """
    배치 작업 상태 확인 (헬스 체크)
    Cloud Scheduler가 주기적으로 호출 가능
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "babba-api-batch"
    }
```

### app/main.py에 라우터 등록

기존 `app/main.py`에서:

```python
# 기존 라우터 imports
from app.routers import orders, products, members, organizations, settlements, users

# 새로운 배치 라우터 import 추가
from app.routers import batch

# FastAPI 앱 설정
app = FastAPI(
    title="Babba API",
    description="Babba API for settlement management"
)

# 기존 라우터 등록
app.include_router(orders.router)
app.include_router(products.router)
app.include_router(members.router)
app.include_router(organizations.router)
app.include_router(settlements.router)
app.include_router(users.router)

# 배치 라우터 등록 (새로 추가)
app.include_router(batch.router)
```

---

## 🛡️ 보안 설정

### OIDC 토큰 인증 (권장)

Cloud Scheduler는 자동으로 OIDC 토큰을 생성하여 요청에 포함:

```bash
# Job 생성 시 자동 설정
gcloud scheduler jobs create http ... \
  --oidc-service-account-email="babba-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience="${SERVICE_URL}"
```

### API 인증 헤더 검증 (선택)

FastAPI에서 인증 헤더 검증:

```python
from fastapi import Security, HTTPException
from google.auth.transport import requests
from google.oauth2 import id_token

async def verify_cloud_scheduler_token(request):
    """Cloud Scheduler OIDC 토큰 검증"""
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = auth_header[7:]  # "Bearer " 제거
    
    try:
        # 토큰 검증
        claims = id_token.verify_oauth2_token(token, requests.Request())
        return claims
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
```

---

## 📊 모니터링 및 로깅

### 1. Cloud Scheduler 작업 상태 확인

```bash
# 생성된 Job 목록
gcloud scheduler jobs list --location=asia-northeast3

# 특정 Job 상세 정보
gcloud scheduler jobs describe babba-settlement-monthly-aggregation \
  --location=asia-northeast3

# Job 실행 강제 실행 (테스트)
gcloud scheduler jobs run babba-settlement-monthly-aggregation \
  --location=asia-northeast3
```

### 2. Cloud Logging 확인

GCP 콘솔에서 로그 확인:

```bash
# 명령어 방식으로도 가능
gcloud logging read \
  'resource.type=cloud_run_revision AND \
   resource.labels.service_name=babba-api AND \
   severity=ERROR' \
  --limit 50 \
  --format json \
  --project=$PROJECT_ID
```

### 3. 애플리케이션 로깅 개선

`app/routers/batch.py`에서:

```python
import logging
from pythonjsonlogger import jsonlogger

# 구조화된 로깅 설정
logger = logging.getLogger()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

# 배치 작업에서 구조화된 로그
logger.info("settlement_aggregation_started", extra={
    "year": year,
    "month": month,
    "service": "babba-api-batch"
})
```

---

## 🧪 테스트 및 배포

### 로컬 테스트

```bash
# 로컬 서버 실행
./local-run.sh

# 다른 터미널에서 배치 엔드포인트 호출
curl -X POST http://localhost:8080/api/batch/settlement-monthly-aggregation \
  -H "Content-Type: application/json"
```

### Cloud Run에 배포

```bash
# 기존 배포 스크립트 실행
./build-and-deploy.sh

# 배포 확인
gcloud run services describe babba-api --region=asia-northeast3
```

### Job 수동 실행 (테스트)

```bash
gcloud scheduler jobs run babba-settlement-monthly-aggregation \
  --location=asia-northeast3

# 실행 결과 확인
gcloud scheduler jobs describe babba-settlement-monthly-aggregation \
  --location=asia-northeast3 \
  --format='table(lastExecutionTime, state, status)'
```

---

## 🚨 문제 해결

### Job이 실행되지 않음

```bash
# 1. Job 상태 확인
gcloud scheduler jobs describe babba-settlement-monthly-aggregation \
  --location=asia-northeast3

# 2. 서비스 계정 권한 확인
gcloud run services get-iam-policy babba-api \
  --region=asia-northeast3

# 3. Cloud Run 서비스 상태 확인
gcloud run services describe babba-api \
  --region=asia-northeast3 \
  --format='table(status.conditions)'

# 4. 로그 확인
gcloud logging read \
  'resource.type=cloud_run_revision AND \
   resource.labels.service_name=babba-api' \
  --limit 100 \
  --format='table(severity, timestamp, textPayload)'
```

### 401 Unauthorized 에러

```bash
# 서비스 계정에 Cloud Run Invoker 역할 확인
gcloud run services get-iam-policy babba-api \
  --region=asia-northeast3 \
  --format=json

# 역할 재부여
gcloud run services add-iam-policy-binding babba-api \
  --member="serviceAccount:babba-scheduler@astute-window-472313-g9.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=asia-northeast3
```

### 504 Gateway Timeout

- Cloud Run 인스턴스가 많은 시간을 소요하는 경우
- 배치 작업을 백그라운드 작업으로 분리하여 해결
- 현재 가이드의 `BackgroundTasks` 사용 권장

---

## 📈 권장 운영 가이드

### 1. 정산 일정

| 배치 | 스케줄 | 설명 |
|------|--------|------|
| 월별 집계 | 매월 1일 09:01 | 지난달의 모든 주문 정산 |
| 일별 확인 | 매일 09:00 | 어제 주문 상태 확인 |

### 2. 알림 설정

GCP Console → Cloud Scheduler에서:
- **Notification Channel**: Slack, Email 등 설정
- **실패 시 알림** 활성화

### 3. 성능 최적화

```python
# 배치 작업 시간 측정
import time

start = time.time()
result = SettlementService.aggregate_completed_orders_to_settlement(...)
duration = time.time() - start

logger.info(f"Settlement aggregation completed in {duration:.2f}s")
```

---

## 참고 자료

- [GCP Cloud Scheduler 공식 문서](https://cloud.google.com/scheduler/docs)
- [Cloud Scheduler CRON 형식](https://cloud.google.com/scheduler/docs/configuring/cron-job-schedules)
- [Cloud Run과 Scheduler 연동](https://cloud.google.com/scheduler/docs/quickstart)
- [FastAPI 백그라운드 작업](https://fastapi.tiangolo.com/tutorial/background-tasks/)
