# Cloud Scheduler & Cloud Tasks 통합 동작 설명

## 📚 목차
1. [개념 설명](#개념-설명)
2. [아키텍처 다이어그램](#아키텍처-다이어그램)
3. [동작 흐름](#동작-흐름)
4. [사용 사례: Makeshop 동기화](#사용-사례-makeshop-동기화)
5. [각 컴포넌트 역할](#각-컴포넌트-역할)
6. [타이밍과 스케줄](#타이밍과-스케줄)
7. [에러 처리 및 재시도](#에러-처리-및-재시도)
8. [모니터링 및 로깅](#모니터링-및-로깅)

---

## 개념 설명

### Cloud Scheduler란?
**Cloud Scheduler는 시간 기반의 작업 스케줄러입니다.**

- **역할**: 정해진 시간에 자동으로 HTTP 요청을 보냅니다
- **특징**: 크론(Cron) 표현식을 사용하여 시간을 정의합니다
- **예시**: 매일 오전 9시 50분에 작업 시작
- **제한사항**: HTTP 요청을 보낼 뿐, 작업 큐를 관리하지 않습니다

### Cloud Tasks란?
**Cloud Tasks는 비동기 작업 큐(Task Queue) 서비스입니다.**

- **역할**: 작업을 큐에 저장하고 순차적으로 처리합니다
- **특징**: 대량의 작업을 효율적으로 관리하고 재시도를 처리합니다
- **예시**: 동기화 작업 100개를 큐에 추가하고 순차 처리
- **장점**: 서버 부하 분산, 자동 재시도, 작업 추적 가능

---

## 아키텍처 다이어그램

### 전체 흐름도

```
┌─────────────────────────────────────────────────────────────────┐
│                        Google Cloud Platform                     │
│                                                                  │
│  ┌────────────────┐                                             │
│  │ Cloud Scheduler│  (시간 기반 스케줄러)                      │
│  └────────┬───────┘                                             │
│           │                                                      │
│           │ 매일 09:50, 13:50 KST                              │
│           │ HTTP POST 요청 발송                                │
│           ▼                                                      │
│  ┌─────────────────────────────────────┐                       │
│  │      Cloud Run (babba-api)          │                       │
│  │  ┌─────────────────────────────┐   │                       │
│  │  │ POST /tasks/sync/makeshop/  │   │                       │
│  │  │      trigger                │   │  (트리거 엔드포인트)  │
│  │  │  • payload 수신             │   │                       │
│  │  │  • Cloud Tasks 큐에 작업    │   │                       │
│  │  │    추가                     │   │                       │
│  │  │  • task_name 반환           │   │                       │
│  │  └────────────┬────────────────┘   │                       │
│  └───────────────┼────────────────────┘                       │
│                  │                                              │
│                  │ Cloud Tasks 클라이언트                      │
│                  │ (google-cloud-tasks==2.21.0)               │
│                  ▼                                              │
│  ┌────────────────────────────────────┐                       │
│  │    Cloud Tasks Queue                │                       │
│  │  (makeshop-sync-queue)             │                       │
│  │                                    │                       │
│  │  ┌──────────────────────────────┐ │                       │
│  │  │ Task 1: {payload}            │ │  (작업 큐)           │
│  │  │ Task 2: {payload}            │ │  • 최대 500개/초     │
│  │  │ Task 3: {payload}            │ │  • 자동 재시도      │
│  │  │ ...                          │ │  • 타임아웃 관리    │
│  │  └──────────────────────────────┘ │                       │
│  └────────────┬───────────────────────┘                       │
│               │                                                 │
│               │ 큐에서 Task 가져오기                           │
│               │ (백그라운드 워커)                              │
│               ▼                                                 │
│  ┌─────────────────────────────────────┐                      │
│  │      Cloud Run (babba-api)          │                      │
│  │  ┌─────────────────────────────┐   │                      │
│  │  │ POST /tasks/sync/makeshop/  │   │                      │
│  │  │      run                    │   │  (실행 엔드포인트)   │
│  │  │  • Task payload 수신        │   │                      │
│  │  │  • Makeshop 동기화 실행     │   │                      │
│  │  │  • 결과 반환                │   │                      │
│  │  └────────┬─────────────────────┘  │                      │
│  │           │                        │                      │
│  │  ┌────────▼─────────────────────┐ │                      │
│  │  │  데이터베이스 (Cloud SQL)     │ │                      │
│  │  │  • 상품 동기화               │ │                      │
│  │  │  • 회원 동기화               │ │                      │
│  │  │  • 주문 동기화               │ │                      │
│  │  └─────────────────────────────┘ │                      │
│  └─────────────────────────────────────┘                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 동작 흐름

### 1️⃣ 스케줄 시간 도달

```
시간: 매일 09:50 (KST)
↓
Cloud Scheduler가 자동으로 깨어남
↓
구성된 HTTP 요청 준비
```

### 2️⃣ Cloud Scheduler → Cloud Run (트리거)

```
Cloud Scheduler가 보내는 요청:

POST https://babba-api-XXX.run.app/tasks/sync/makeshop/trigger
Headers:
  - Authorization: Bearer {OIDC_TOKEN}
  - Content-Type: application/json
Body:
  {}

응답:
{
  "status": "queued",
  "task": "projects/astute-window-472313-g9/locations/asia-northeast3/queues/makeshop-sync-queue/tasks/1234567890",
  "payload": {}
}
```

### 3️⃣ Cloud Run (트리거) → Cloud Tasks 큐

```
트리거 엔드포인트 (/tasks/sync/makeshop/trigger) 처리:

1. 요청 수신
2. Cloud Tasks 클라이언트 초기화
3. Task 객체 생성:
   {
     "http_request": {
       "http_method": "POST",
       "url": "https://babba-api-XXX.run.app/tasks/sync/makeshop/run",
       "headers": {"Content-Type": "application/json"},
       "body": JSON.stringify(payload),
       "oidc_token": {
         "service_account_email": "cloud-run-sql@...",
         "audience": "https://babba-api-XXX.run.app"
       }
     }
   }
4. Cloud Tasks 큐에 추가: client.create_task(parent=queue, task=task)
5. task_name 반환
```

### 4️⃣ Cloud Tasks 큐 관리

```
큐 상태:
┌──────────────────────────────────────┐
│  makeshop-sync-queue                 │
│  (asia-northeast3)                   │
│                                      │
│  상태: RUNNING                       │
│  최대 동시 처리: 1000개              │
│  초당 처리율: 500개/초               │
│  최대 재시도: 100회                  │
│  재시도 정책: 지수 백오프            │
│    - 최소 대기: 0.1초                │
│    - 최대 대기: 3600초               │
│    - 배수: 16배                      │
└──────────────────────────────────────┘
```

### 5️⃣ Cloud Tasks → Cloud Run (실행)

```
Cloud Tasks가 호출하는 요청:

POST https://babba-api-XXX.run.app/tasks/sync/makeshop/run
Headers:
  - Authorization: Bearer {SERVICE_ACCOUNT_OIDC_TOKEN}
  - Content-Type: application/json
Body:
  {
    "InquiryTimeFrom": null,
    "InquiryTimeTo": null
  }

응답 예시:
{
  "status": "success",
  "service": "babba-sync-makeshop-all",
  "timestamp": "2026-02-04T10:00:00+00:00",
  "synced_data": {
    "products": {
      "status": "success",
      "total_processed": 1234,
      "created": 50,
      "updated": 120
    },
    "members": {
      "status": "success",
      "total_processed": 567,
      "created": 10,
      "updated": 45
    },
    "orders": {
      "status": "success",
      "total_processed": 890,
      "created": 123,
      "updated": 456
    }
  }
}
```

### 6️⃣ 데이터베이스 업데이트

```
실행 엔드포인트에서:

1. _run_makeshop_sync() 호출
2. 상품 동기화 시작
   - Makeshop API에서 제품 조회
   - 로컬 DB와 비교
   - 신규 추가 / 기존 업데이트
3. 회원 동기화 시작
   - 동일 프로세스
4. 주문 동기화 시작
   - 시간 범위 기반 필터링
   - 동일 프로세스
5. 결과 반환
```

---

## 사용 사례: Makeshop 동기화

### 실제 실행 흐름

#### ⏰ 09:50 KST 실행 예시

```
시간대 타이밍:
- 09:50 KST = 00:50 UTC (Cloud Scheduler 사용 시간대)
- 이전 실행: 13:50 KST (04:50 UTC)
- 다음 실행: 다음날 09:50 KST

09:50 KST 실행 시:
┌─────────────────────────────────────────────────┐
│ 자동 계산 시간 범위                             │
├─────────────────────────────────────────────────┤
│ InquiryTimeFrom:                                │
│   → 전날 13:50 KST (어제 정산 시간)            │
│                                                 │
│ InquiryTimeTo:                                  │
│   → 오늘 09:49 KST (현재 실행 1분 전)          │
│                                                 │
│ 목적: 어제 오후 ~ 오늘 오전 데이터 동기화     │
└─────────────────────────────────────────────────┘

13:50 KST 실행 시:
┌─────────────────────────────────────────────────┐
│ 자동 계산 시간 범위                             │
├─────────────────────────────────────────────────┤
│ InquiryTimeFrom:                                │
│   → 오늘 09:50 KST (오전 실행 시간)            │
│                                                 │
│ InquiryTimeTo:                                  │
│   → 오늘 13:49 KST (현재 실행 1분 전)          │
│                                                 │
│ 목적: 오늘 오전 ~ 오후 데이터 동기화          │
└─────────────────────────────────────────────────┘
```

### 로그 예시

```
[통합 동기화] Step 1: 상품 동기화 시작
[상품 동기화] 시작: 전체 상품을 limit=1000으로 조회
[상품 동기화] 페이지 1 조회 중 (limit=1000)
[상품 동기화] 페이지 1 완료: 1000개 처리 (신규: 50, 수정: 120)
[상품 동기화] 페이지 2 조회 중 (limit=1000)
[상품 동기화] 모든 상품 조회 완료 (총 1234개)

[통합 동기화] Step 2: 회원 동기화 시작
[회원 동기화] 시작: 페이지네이션 기반 회원 조회
[회원 동기화] 페이지 1 조회 중 (limit=5000)
[회원 동기화] 모든 회원 조회 완료 (총 567개)

[통합 동기화] Step 3: 주문 동기화 시작
[주문 동기화] 시작: 2026-02-03 13:50:00 ~ 2026-02-04 09:49:00
[주문 동기화] 페이지 1 조회 중 (limit=1000)
[주문 동기화] 모든 주문 조회 완료 (총 890개)

[통합 동기화] 모든 동기화 작업 완료
```

---

## 각 컴포넌트 역할

### Cloud Scheduler의 역할

| 기능 | 설명 |
|------|------|
| **시간 관리** | 크론 표현식으로 정확한 시간 지정 |
| **요청 생성** | HTTP 요청 자동 생성 및 발송 |
| **인증 제공** | OIDC 토큰으로 보안 인증 |
| **재시도** | HTTP 요청 실패 시 자동 재시도 |
| **모니터링** | 실행 상태 로깅 |

**크론 표현식 설명:**
```
"50 0,4 * * *"
 │  │ │ │ │
 │  │ │ │ └─ 요일 (* = 매일)
 │  │ │ └─── 월 (* = 매월)
 │  │ └───── 일 (* = 매일)
 │  └─────── 시간 (0,4 = 00시, 04시 UTC)
 └────────── 분 (50 = 50분)

= 매일 00:50 UTC, 04:50 UTC 실행
= 매일 09:50 KST, 13:50 KST 실행 (KST = UTC+9)
```

### Cloud Tasks의 역할

| 기능 | 설명 |
|------|------|
| **큐 관리** | 작업을 안전하게 저장 및 관리 |
| **순차 처리** | 큐에 쌓인 작업을 순서대로 처리 |
| **속도 제어** | 초당 처리율 제한 (초당 500개) |
| **자동 재시도** | 실패한 작업 자동 재시도 |
| **작업 추적** | 각 작업의 상태 추적 가능 |
| **부하 분산** | 동시 처리 제한으로 서버 보호 |

### Cloud Run의 역할

| 엔드포인트 | 기능 |
|----------|------|
| **트리거** (`/tasks/sync/makeshop/trigger`) | Cloud Scheduler 요청 수신 → Cloud Tasks 큐에 작업 추가 |
| **실행** (`/tasks/sync/makeshop/run`) | Cloud Tasks 요청 수신 → 실제 동기화 작업 수행 |
| **동기화** (트리거 → 실행) | Makeshop API 호출 → DB 업데이트 |

---

## 타이밍과 스케줄

### Cloud Scheduler 설정

```yaml
Job Name: babba-sync-makeshop
Schedule: "50 0,4 * * *"  (UTC 기준)
Time Zone: UTC
HTTP Method: POST
Endpoint: /tasks/sync/makeshop/trigger
Service Account: babba-scheduler@...
```

### 일일 실행 일정

```
시각표 (한국 시간 KST = UTC+9)

00:00 ─────────────────────────────────────── 24:00
       │                                        │
       │ 09:50 KST                  13:50 KST  │
       │ (00:50 UTC)                (04:50 UTC)│
       │    ▼                           ▼       │
       │ ┌─────────────────────────────────┐  │
       │ │ Cloud Scheduler 실행            │  │
       │ │ → 트리거 엔드포인트 호출        │  │
       │ │ → Cloud Tasks 큐에 작업 추가    │  │
       │ └─────────────────────────────────┘  │
       │    │                           │       │
       │    ▼ (< 1초)                  ▼ (< 1초)
       │ ┌─────────────────────────────────┐  │
       │ │ Cloud Tasks 큐에서 작업 꺼냄    │  │
       │ │ → 실행 엔드포인트 호출          │  │
       │ └─────────────────────────────────┘  │
       │    │                           │       │
       │    ▼ (약 30~60초)            ▼ (약 30~60초)
       │ ┌─────────────────────────────────┐  │
       │ │ 동기화 작업 수행                │  │
       │ │ • 상품: 1234개                  │  │
       │ │ • 회원: 567개                   │  │
       │ │ • 주문: 890개                   │  │
       │ │ → 데이터베이스 업데이트         │  │
       │ └─────────────────────────────────┘  │
       │    │                           │       │
       │    ✓ 완료                      ✓ 완료  │
       │                                        │
```

---

## 에러 처리 및 재시도

### Cloud Scheduler의 재시도

```
Cloud Scheduler 요청 실패 시:

1차 시도: 09:50:00
  ↓ (실패)
재시도 #1: 09:50:01 (1초 후)
  ↓ (실패)
재시도 #2: 09:50:04 (4초 후)
  ↓ (실패)
재시도 #3: 09:50:16 (16초 후)
  ↓ (실패)
... (최대 재시도 횟수까지 계속)

재시도 정책:
- 지수 백오프 사용
- 각 재시도마다 대기 시간 증가
- 최대 재시도 횟수 설정 가능
```

### Cloud Tasks의 재시도

```
Cloud Tasks 작업 실패 시:

maxAttempts: 100 (최대 시도)
재시도 정책:
  minBackoff: 0.1초
  maxBackoff: 3600초 (1시간)
  maxDoublings: 16

재시도 일정:
1차: 0:00:00
2차: 0:00:00.1 (0.1초 후)
3차: 0:00:00.2 (0.2초 후)
4차: 0:00:00.4 (0.4초 후)
5차: 0:00:00.8 (0.8초 후)
...
최대: 1시간 대기 후 재시도
```

### 에러 종류별 처리

| 에러 | 원인 | 처리 방식 |
|------|------|---------|
| **연결 실패** | 네트워크 문제 | Cloud Tasks 자동 재시도 |
| **타임아웃** | 작업 시간 초과 | 재시도 또는 실패 처리 |
| **인증 실패** | OIDC 토큰 문제 | Cloud Scheduler 재시도 |
| **400 Bad Request** | 잘못된 요청 | 실패 처리 (재시도 안함) |
| **500 Server Error** | 서버 오류 | Cloud Tasks 자동 재시도 |
| **503 Service Unavailable** | 서비스 점검 | Cloud Tasks 자동 재시도 |

---

## 모니터링 및 로깅

### Cloud Scheduler 모니터링

```bash
# Job 상태 확인
gcloud scheduler jobs describe babba-sync-makeshop \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9

# Job 실행 히스토리 조회
gcloud logging read 'resource.type="cloud_scheduler_job" AND labels.job_name="babba-sync-makeshop"' \
  --limit=10 \
  --format=json

# Job 수동 실행 (테스트)
gcloud scheduler jobs run babba-sync-makeshop \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9
```

### Cloud Tasks 모니터링

```bash
# 큐 상태 확인
gcloud tasks queues describe makeshop-sync-queue \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9

# 큐의 모든 작업 조회
gcloud tasks list \
  --queue=makeshop-sync-queue \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9

# 특정 작업 상세 정보
gcloud tasks describe TASK_NAME \
  --queue=makeshop-sync-queue \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9
```

### Cloud Run 로깅

```bash
# Cloud Run 컨테이너 로그 조회
gcloud logging read 'resource.type="cloud_run_revision" AND labels.service_name="babba-api"' \
  --limit=50 \
  --format=short

# 에러만 필터링
gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR' \
  --limit=20 \
  --format=json
```

### 로그 예시

```
Cloud Scheduler 실행 로그:
2026-02-04T00:50:00Z - Job execution started
2026-02-04T00:50:01Z - HTTP POST to /tasks/sync/makeshop/trigger
2026-02-04T00:50:02Z - Response: 200 OK

Cloud Run 트리거 엔드포인트 로그:
2026-02-04T00:50:02Z - POST /tasks/sync/makeshop/trigger
2026-02-04T00:50:02Z - Initializing Cloud Tasks client
2026-02-04T00:50:03Z - Creating task in queue makeshop-sync-queue
2026-02-04T00:50:03Z - Task created: projects/.../tasks/1234567890
2026-02-04T00:50:03Z - Response: {"status": "queued", ...}

Cloud Run 실행 엔드포인트 로그:
2026-02-04T00:50:05Z - POST /tasks/sync/makeshop/run
2026-02-04T00:50:05Z - [통합 동기화] Step 1: 상품 동기화 시작
2026-02-04T00:50:35Z - [상품 동기화] 모든 상품 조회 완료 (총 1234개)
2026-02-04T00:50:40Z - [통합 동기화] Step 2: 회원 동기화 시작
2026-02-04T00:50:50Z - [회원 동기화] 모든 회원 조회 완료 (총 567개)
2026-02-04T00:50:55Z - [통합 동기화] Step 3: 주문 동기화 시작
2026-02-04T00:51:30Z - [주문 동기화] 모든 주문 조회 완료 (총 890개)
2026-02-04T00:51:30Z - [통합 동기화] 모든 동기화 작업 완료
2026-02-04T00:51:31Z - Response: {"status": "success", ...}
```

---

## 비교: 직접 호출 vs Cloud Tasks 사용

### ❌ 직접 호출 방식 (Cloud Scheduler → Cloud Run 직접)

```
Cloud Scheduler
        ↓
    POST /sync/makeshop/all (직접)
        ↓
    동기화 작업 수행 (동기식)
        ↓
    응답 대기 (타임아웃 가능)
        ↓
    결과 반환

문제점:
- Cloud Run 요청 타임아웃: 60분
- 작업 실패 시 데이터 손실 가능
- 동시 요청 제어 불가
- 작업 재시도 제한적
- 대량 작업 처리 어려움
```

### ✅ Cloud Tasks 사용 방식 (Cloud Scheduler → Cloud Tasks → Cloud Run)

```
Cloud Scheduler
        ↓
    POST /tasks/sync/makeshop/trigger (빠름)
        ↓
    Cloud Tasks 큐에 작업 추가 (< 1초)
        ↓
    응답 즉시 반환
        ↓
    Cloud Tasks 큐에서 순차 처리
        ↓
    POST /tasks/sync/makeshop/run
        ↓
    동기화 작업 수행
        ↓
    결과 저장

장점:
- 트리거 빠름 (< 1초)
- 타임아웃 문제 없음
- 자동 재시도 (100회)
- 동시 처리 제어 (초당 500개)
- 작업 상태 추적 가능
- 대량 작업 효율적 처리
```

---

## 결론

### 세 가지 서비스의 역할 정리

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Cloud Scheduler: "언제 시작할까?"                         │
│  → 매일 09:50, 13:50 KST에 알림을 보냄                    │
│                                                             │
│  Cloud Tasks: "어떻게 안전하게 처리할까?"                  │
│  → 큐를 통해 작업을 안전하게 관리하고 순차 처리            │
│                                                             │
│  Cloud Run: "무엇을 실행할까?"                             │
│  → 실제 비즈니스 로직 수행 (Makeshop 동기화)              │
│                                                             │
│  전체: 정확한 시간에 안전하게 작업을 실행하는 파이프라인   │
└─────────────────────────────────────────────────────────────┘
```

### 주요 특징

| 구분 | Cloud Scheduler | Cloud Tasks | Cloud Run |
|------|-----------------|-------------|-----------|
| **목적** | 시간 기반 실행 | 비동기 작업 관리 | 코드 실행 |
| **역할** | 언제 | 어떻게 | 무엇을 |
| **요청 방식** | HTTP 요청 발송 | 작업 큐 관리 | 엔드포인트 처리 |
| **확장성** | 1개 작업/실행 | 수천 개 작업 | 자동 스케일링 |
| **신뢰성** | 중간 (재시도 제한) | 높음 (100회 재시도) | 높음 (자동 복구) |

---

## 참고 자료

- [Google Cloud Scheduler 문서](https://cloud.google.com/scheduler/docs)
- [Google Cloud Tasks 문서](https://cloud.google.com/tasks/docs)
- [Cloud Run 통합 가이드](https://cloud.google.com/tasks/docs/integrating-cloud-run)
- [OIDC 토큰 인증](https://cloud.google.com/run/docs/authenticating/service-to-service)
