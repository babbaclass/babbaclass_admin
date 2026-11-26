# Cloud Scheduler 설정 실행 가이드

## 📋 사전 요구사항

- GCP 프로젝트가 설정되어 있음
- gcloud CLI가 설치되어 있음
- Cloud Run에 babba-api가 배포되어 있음

## 🚀 실행 방법

### 1단계: GCP 인증 확인

```bash
gcloud auth list
```

활성 계정이 표시되어야 합니다. 만약 없다면:

```bash
gcloud auth login
```

### 2단계: Cloud Scheduler Job 설정

```bash
cd /Users/hoonlee/Documents/GitHub/babba-api
bash setup-cloud-scheduler.sh
```

### 3단계: 스크립트 대화형 입력

스크립트가 실행되면 다음 질문이 나타납니다:

```
월별 정산 배치 Job을 생성하시겠습니까? (y/n): 
```

- `y` 입력: 정산 배치 Job도 생성
- `n` 입력: 동기화 Job만 생성

```
Makeshop 동기화 Job을 수동으로 실행하시겠습니까? (y/n): 
```

- `y` 입력: Job을 수동으로 실행하여 테스트
- `n` 입력: 스킵

```
로그를 확인하시겠습니까? (y/n): 
```

- `y` 입력: Cloud Logging에서 최근 로그 출력
- `n` 입력: 스킵

---

## 📊 생성되는 Job

### 필수: Makeshop 동기화

**Job 이름**: `babba-sync-makeshop`

- **실행 시간**: 매일 09:50, 13:50 KST
- **엔드포인트**: `/tasks/sync/makeshop/trigger` (Cloud Tasks 큐 `makeshop-sync-queue`에 작업을 넣고 `/tasks/sync/makeshop/run`에서 실행)
- **역할**:
  - 상품 동기화 (Products)
  - 회원 동기화 (Members)
  - 주문 동기화 (Orders)

Cloud Scheduler는 `/tasks/sync/makeshop/trigger`에서 작업을 생성하고, `makeshop-sync-queue`에 넣은 뒤 `/tasks/sync/makeshop/run`에서 실제 동기화를 실행합니다.

#### 주문 검색 범위 자동 계산

| 실행 시간 | InquiryTimeFrom | InquiryTimeTo |
|----------|-----------------|---------------|
| 09:50 KST | 전날 13:50 | 오늘 09:49 |
| 13:50 KST | 오늘 09:50 | 오늘 13:49 |

### 선택: 정산 배치

**Job 이름**: `babba-settlement-monthly-aggregation`

- **실행 시간**: 매월 1일 09:01 KST
- **엔드포인트**: `/api/batch/settlement-monthly-aggregation`
- **역할**: 월별 정산 집계

---

## ✅ 설정 확인

### GCP 콘솔에서 확인

1. [Cloud Scheduler](https://console.cloud.google.com/cloudscheduler?project=astute-window-472313-g9)
2. 리전: `asia-northeast3` 선택
3. 생성된 Job 목록 확인

### 명령어로 확인

```bash
# 모든 Job 목록
gcloud scheduler jobs list --location=asia-northeast3

# 특정 Job 상세 정보
gcloud scheduler jobs describe babba-sync-makeshop --location=asia-northeast3
```

---

## 🧪 테스트 실행

### 수동으로 Job 실행

```bash
# Makeshop 동기화 Job 실행
gcloud scheduler jobs run babba-sync-makeshop --location=asia-northeast3

# 정산 배치 Job 실행
gcloud scheduler jobs run babba-settlement-monthly-aggregation --location=asia-northeast3
```

### 로그 확인

```bash
# 최근 실행 로그 (Cloud Logging)
gcloud logging read \
  'resource.type=cloud_run_revision AND \
   resource.labels.service_name=babba-api' \
  --limit=20 \
  --format='table(severity, timestamp, jsonPayload.status)'
```

---

## ❌ 문제 해결

### "GCP 인증이 필요합니다" 에러

```bash
gcloud auth login
```

### "Cloud Run 서비스를 찾을 수 없습니다" 에러

Cloud Run에 babba-api가 배포되어 있는지 확인:

```bash
gcloud run services list --region=asia-northeast3
```

배포되지 않았다면:

```bash
./build-and-deploy.sh
```

### Job이 실행되지 않음

서비스 계정 권한 확인:

```bash
gcloud run services get-iam-policy babba-api --region=asia-northeast3
```

권한 부여:

```bash
gcloud run services add-iam-policy-binding babba-api \
  --member="serviceAccount:babba-scheduler@astute-window-472313-g9.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=asia-northeast3
```

---

## 📚 참고 문서

- 빠른 가이드: [CLOUD_SCHEDULER_QUICKSTART.md](CLOUD_SCHEDULER_QUICKSTART.md)
- 동기화 상세: [docs/CLOUD_SCHEDULER_SYNC_UNIFIED.md](docs/CLOUD_SCHEDULER_SYNC_UNIFIED.md)
- 정산 배치 상세: [docs/CLOUD_SCHEDULER_SETUP.md](docs/CLOUD_SCHEDULER_SETUP.md)
