# Cloud Scheduler 동기화 Job 설정 가이드 (통합)

Makeshop API와의 동기화를 자동화하기 위한 Cloud Scheduler Job 설정 가이드입니다.

## 📋 설정 Job

| Job 이름 | 실행 시간 | 대상 API | 설명 |
|----------|---------|---------|------|
| `babba-sync-makeshop` | 매일 09:50, 13:50 KST | `/tasks/sync/makeshop/trigger` | Cloud Tasks를 생성하여 `/tasks/sync/makeshop/run`에서 모든 Makeshop 데이터 통합 동기화 |

**통합 동기화 포함 항목**:
- 상품 동기화 (Products)
- 회원 동기화 (Members)
- 주문 동기화 (Orders)

---

## 🚀 자동 설정 (추천)

### 1단계: Cloud Run 배포 확인

```bash
./build-and-deploy.sh
```

### 2단계: 자동 설정 스크립트 실행

```bash
chmod +x setup-cloud-scheduler-sync-unified.sh
./setup-cloud-scheduler-sync-unified.sh
```

**끝! 동기화 Job이 매일 09:50, 13:50 KST에 자동으로 실행됩니다.**

---

## ⏰ 시간 설정 설명

**09:50 KST (UTC 00:50)**
- 업무 시작 10분 전에 최신 데이터 동기화

**13:50 KST (UTC 04:50)**
- 오후 2시(14:00) 업무 중간점에 한 번 더 동기화

### CRON 표현식

```
50 0,4 * * *
```

- **분**: 50 (매시간 50분)
- **시간**: 0,4 (UTC 00시, 04시 = KST 09:00, 13:00)
- **일**: * (매일)
- **월**: * (매월)
- **요일**: * (매주)

---

## 📊 설정된 Job 확인

### GCP 콘솔에서 확인

1. [GCP Cloud Scheduler](https://console.cloud.google.com/cloudscheduler)
2. 리전: `asia-northeast3` (서울) 선택
3. 다음 Job이 생성되었는지 확인:
   - `babba-sync-makeshop`

### 명령어로 확인

```bash
# Job 목록 조회
gcloud scheduler jobs list --location=asia-northeast3

# 통합 동기화 Job 상세 정보
gcloud scheduler jobs describe babba-sync-makeshop \
  --location=asia-northeast3
```

---

  resource.labels.service_name=babba-api AND 
  jsonPayload.endpoint=~"/tasks/sync/makeshop.*"' \
### 수동으로 Job 실행

```bash
# 통합 동기화 Job 수동 실행
gcloud scheduler jobs run babba-sync-makeshop \
  --location=asia-northeast3
```

### 로컬에서 테스트

```bash
# 1. 로컬 서버 실행
./local-run.sh

# 2. 다른 터미널에서 트리거 엔드포인트 호출 (Cloud Tasks 생성)
curl -X POST http://localhost:8080/tasks/sync/makeshop/trigger

# 3. 응답 확인 (성공 응답 예)
# {
#   "status": "success",
#   "service": "babba-sync-makeshop-all",
#   "timestamp": "2025-12-11T...",
#   "synced_data": {
#     "products": {...},
#     "members": {...},
#     "orders": {...}
#   }
# }
```

---

## 📝 로그 확인

### Cloud Run 로그 조회

```bash
# 최근 동기화 작업 로그
gcloud logging read \
  'resource.type=cloud_run_revision AND \
   resource.labels.service_name=babba-api AND \
   jsonPayload.endpoint=~"/tasks/sync/makeshop.*"' \
  --limit=50 \
  --format='table(severity, timestamp, jsonPayload.status)'
```

### GCP 콘솔에서 로그 확인

1. **Cloud Logging** → **로그 탐색기**
2. 필터:
   ```
  resource.type="cloud_run_revision"
  AND resource.labels.service_name="babba-api"
  AND (httpRequest.requestUrl=~".*/tasks/sync/makeshop/.*")
   ```
3. 최근 실행 기록 확인

---

## 📅 스케줄 변경하기

### 실행 시간 변경 예

```bash
# 예: 06:50, 12:50 KST로 변경 (UTC 21:50, 03:50)
# CRON: 50 21,3 * * *
gcloud scheduler jobs update http babba-sync-makeshop \
  --location=asia-northeast3 \
  --schedule="50 21,3 * * *"
```

### 자주 사용하는 CRON 표현식

| 설명 | CRON |
|------|------|
| 매일 09:50, 13:50 KST | `50 0,4 * * *` |
| 매일 06:50, 12:50 KST | `50 21,3 * * *` |
| 매일 10:00, 14:00, 18:00 KST | `0 1,5,9 * * *` |
| 매일 한 번 09:00 KST | `0 0 * * *` |
| 1시간마다 | `0 * * * *` |

---

## 🛠️ 수동 설정 (스크립트를 실행하지 않으려면)

### 필수 API 활성화

```bash
gcloud services enable cloudscheduler.googleapis.com
```

### GCP 콘솔에서 직접 생성

1. **Cloud Scheduler** → **작업 생성**
2. 다음 정보 입력:
   - **이름**: `babba-sync-makeshop`
   - **빈도**: `50 0,4 * * *` (매일 09:50, 13:50 KST)
  - **시간대**: UTC
  - **프로토콜**: HTTP
  - **URL**: `https://babba-api-<hash>.run.app/tasks/sync/makeshop/trigger`
  - **백그라운드 엔드포인트**: `/tasks/sync/makeshop/run` (Cloud Tasks가 실제 동기화를 실행)
  - **HTTP 메서드**: POST
  - **인증**: OIDC 토큰
  - **서비스 계정**: `babba-scheduler@astute-window-472313-g9.iam.gserviceaccount.com`

---

## ☁️ Cloud Tasks 큐 + 권한

Cloud Scheduler는 `/tasks/sync/makeshop/trigger`에서 요청을 받아 Cloud Tasks 큐에 작업을 넣고, `/tasks/sync/makeshop/run`에서 실제 Makeshop 동기화를 수행합니다.

1. **Cloud Tasks 큐 생성**
  ```bash
  gcloud tasks queues create makeshop-sync-queue \
    --location=asia-northeast3 \
    --project=astute-window-472313-g9
  ```

2. **enqueuer IAM 권한 부여 (Cloud Run 서비스 계정)**
  ```bash
  gcloud tasks queues add-iam-policy-binding makeshop-sync-queue \
    --location=asia-northeast3 \
    --member="serviceAccount:cloud-run-sql@astute-window-472313-g9.iam.gserviceaccount.com" \
    --role="roles/cloudtasks.enqueuer" \
    --project=astute-window-472313-g9
  ```

3. **환경 변수 및 배포 확인**
  - Cloud Run 서비스는 `deploy.sh`/`build-and-deploy.sh`에서 `--service-account=cloud-run-sql@...`로 배포되어야 합니다.
  - Cloud Tasks가 `/tasks/sync/makeshop/run`을 호출할 때 사용할 OIDC 토큰은 `TASKS_SERVICE_ACCOUNT=cloud-run-sql@astute-window-472313-g9.iam.gserviceaccount.com` 환경 변수로 설정하세요.

4. **자동 설정 스크립트**
  `setup-cloud-scheduler.sh`을 실행하면 위 큐/권한 설정과 scheduler job 등록이 자동으로 진행됩니다.

## 💡 통합 엔드포인트의 장점

### 1. 효율성
- **1개 Job**: 3개의 분리된 Job 대신 하나의 Job만 필요
- **순차 처리**: 상품 → 회원 → 주문 순서로 안정적 처리
- **네트워크 효율**: 1번의 인증, 1번의 초기화

### 2. 신뢰성
- **원자성**: 세 데이터 세트가 함께 업데이트됨
- **에러 처리**: 각 단계의 에러를 개별 추적 가능
- **로깅**: 전체 프로세스의 흐름을 하나의 로그에서 확인

### 3. 비용 절감
- **호출 감소**: 월 60회 → 월 20회 (3배 감소)
- **리소스 사용**: 한 번의 초기화와 인증

---

## ❌ 문제 해결

### Job이 실행되지 않는 경우

```bash
# 1. Job 상태 확인
gcloud scheduler jobs describe babba-sync-makeshop \
  --location=asia-northeast3 \
  --format='table(state, status.message)'

# 2. 서비스 계정 권한 확인
gcloud run services get-iam-policy babba-api --region=asia-northeast3

# 3. Cloud Run 서비스 상태 확인
gcloud run services describe babba-api --region=asia-northeast3
```

### 403 Forbidden 에러

```bash
# 서비스 계정에 Cloud Run 실행 권한 부여
gcloud run services add-iam-policy-binding babba-api \
  --member="serviceAccount:babba-scheduler@astute-window-472313-g9.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=asia-northeast3
```

### 동기화가 너무 오래 걸리는 경우

- **Job 타임아웃**: Cloud Scheduler 기본 1800초(30분)
- **해결 방법**:
  ```bash
  gcloud scheduler jobs update http babba-sync-makeshop \
    --location=asia-northeast3 \
    --http-method=POST \
    --oidc-service-account-email=babba-scheduler@astute-window-472313-g9.iam.gserviceaccount.com \
    --timeout=3600s  # 60분으로 변경
  ```

---

## 📚 추가 참고

- **동기화 API 엔드포인트**:
  - `/tasks/sync/makeshop/trigger` (POST) - Cloud Scheduler가 호출하는 트리거로, `makeshop-sync-queue`에 작업을 넣습니다
  - `/tasks/sync/makeshop/run` (POST) - Cloud Tasks가 요청을 보낼 실제 실행 엔드포인트이며, `TASKS_SERVICE_ACCOUNT`로 인증해야 합니다
  - `/sync/makeshop/all` (POST) - 수동 확인용 단일 호출 (직접 실행하면 로그인이 차단될 수 있으므로 주의)
  - `/sync/makeshop/products` (POST) - 상품만 동기화 (개별 호출 가능)
  - `/sync/makeshop/members` (POST) - 회원만 동기화 (개별 호출 가능)
  - `/sync/makeshop/orders` (POST) - 주문만 동기화 (개별 호출 가능)
- **Cloud Run 배포 가이드**: [docs/CLOUD_RUN_DEPLOY.md](CLOUD_RUN_DEPLOY.md)
- **정산 배치 Job**: [docs/CLOUD_SCHEDULER_SETUP.md](CLOUD_SCHEDULER_SETUP.md)

---

## 🎯 체크리스트

- [ ] Cloud Run에 최신 버전 배포됨
- [ ] `setup-cloud-scheduler-sync-unified.sh` 실행 완료
- [ ] GCP 콘솔에서 Job 확인
- [ ] Job을 수동으로 실행하여 테스트
- [ ] 실행 로그에서 성공 메시지 확인
- [ ] 자동 실행 대기 (다음 날 09:50)

**시간대 참고**:
- **UTC** 기준으로 스케줄 설정됨
- **서울(KST) = UTC + 9시간**
- 예: 09:50 KST = 00:50 UTC
