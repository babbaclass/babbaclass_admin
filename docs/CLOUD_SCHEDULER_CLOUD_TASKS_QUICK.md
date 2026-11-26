# Cloud Scheduler & Cloud Tasks - 빠른 이해 가이드

## 🎯 5분만에 이해하기

### 세 가지 핵심 개념

```
┌──────────────────────────────────────────────────────┐
│ 1️⃣ Cloud Scheduler: "언제?"                         │
│    → 정해진 시간에 자동으로 "시작 신호" 보냄          │
│    → 크론(Cron) 시간표 사용                          │
│    → 마치 시계 시침처럼 정확함                       │
├──────────────────────────────────────────────────────┤
│ 2️⃣ Cloud Tasks: "어떻게?"                           │
│    → "시작 신호"를 받으면 작업을 큐에 저장           │
│    → 큐에 쌓인 작업을 순차적으로 처리                │
│    → 마치 은행 대기표 같이 순서 관리                 │
├──────────────────────────────────────────────────────┤
│ 3️⃣ Cloud Run: "뭐?"                                │
│    → 실제로 일을 하는 작업자                        │
│    → 트리거 받으면 시작, 실행 엔드포인트 호출         │
│    → Makeshop 동기화 작업 수행                       │
└──────────────────────────────────────────────────────┘
```

---

## 📅 실제 일정 (매일 반복)

```
09:50 KST 예시
│
├─ 09:50:00
│  ↓
│  🔔 Cloud Scheduler가 "지금 시작하세요!" 신호 발송
│  
├─ 09:50:01 (1초 후)
│  ↓
│  🎯 Cloud Run 트리거 엔드포인트 도착
│  "작업을 큐에 추가해주세요"
│
├─ 09:50:02 (2초 후)
│  ↓
│  📦 Cloud Tasks 큐에 작업 추가
│  "상품 1234개, 회원 567개, 주문 890개 동기화"
│
├─ 09:50:03 (3초 후)
│  ↓
│  ⚡ Cloud Run 실행 엔드포인트 호출
│  "이제 실제 동기화를 시작하세요"
│
├─ 09:50:05 ~ 09:51:30 (대략 1분 30초)
│  ↓
│  ⚙️ 동기화 작업 진행
│  • 상품: 1234개 처리
│  • 회원: 567개 처리
│  • 주문: 890개 처리
│
└─ 09:51:31
   ✓ 동기화 완료!
   다음 실행: 13:50 KST
```

---

## 🔄 Cloud Scheduler의 역할

### 매일 정확한 시간에 깨우기

```
┌─────────────────────────────────────┐
│   Cloud Scheduler Job               │
│   "babba-sync-makeshop"             │
│                                     │
│   언제: 매일 09:50, 13:50 KST       │
│   뭐: HTTP POST 요청 발송           │
│   어디: 트리거 엔드포인트로 보냄    │
│   누가: babba-scheduler 서비스계정  │
└─────────────────────────────────────┘
         ↓
    매 6시간마다 실행
         ↓
    요청 보냄 (자동)
```

**장점:**
- ⏱️ 정확한 시간 관리
- 🔄 자동 반복
- 🛡️ 실패 시 자동 재시도
- 📊 실행 히스토리 추적

---

## 📦 Cloud Tasks의 역할

### 작업을 안전하게 관리하기

```
┌─────────────────────────────────────────────┐
│     Cloud Tasks Queue                       │
│     "makeshop-sync-queue"                   │
│                                             │
│  상태: RUNNING                              │
│  위치: asia-northeast3                      │
│  처리율: 초당 500개 작업                    │
│  재시도: 최대 100회                         │
│                                             │
│  ┌─────────────────────────────────────┐  │
│  │ Task 1: 상품 1234개 동기화          │  │
│  ├─────────────────────────────────────┤  │
│  │ Task 2: 회원 567개 동기화           │  │
│  ├─────────────────────────────────────┤  │
│  │ Task 3: 주문 890개 동기화           │  │
│  ├─────────────────────────────────────┤  │
│  │ Task 4: 진행 중...                  │  │
│  └─────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

**장점:**
- 📋 작업 큐 관리
- 🔄 순차 처리
- 🛡️ 자동 재시도 (100회)
- ⚡ 속도 제어 (초당 500개)
- 📊 작업 상태 추적

---

## 🏗️ 전체 파이프라인

### 한눈에 보는 흐름

```
시간: 09:50 KST
    │
    │ Cloud Scheduler
    │ "지금 시작!"
    ▼
┌──────────────────────────────┐
│ Cloud Run 트리거 엔드포인트   │
│ /tasks/sync/makeshop/trigger │
└────────────┬─────────────────┘
             │
             │ 1. payload 받음
             │ 2. Cloud Tasks 클라이언트 초기화
             │ 3. Task 객체 생성
             │ 4. 큐에 추가
             ▼
       ┌───────────────┐
       │ Cloud Tasks   │
       │ 큐에 저장됨   │ ← 즉시 반환 (< 1초)
       └────────┬──────┘
                │
                │ 큐에서 가져오기
                │
                ▼
        ┌──────────────────────────────┐
        │ Cloud Run 실행 엔드포인트     │
        │ /tasks/sync/makeshop/run     │
        └────────┬─────────────────────┘
                 │
                 │ 1. payload 받음
                 │ 2. Makeshop API 호출
                 │ 3. DB 업데이트
                 │ 4. 결과 반환
                 ▼
        ┌──────────────────────────────┐
        │ 데이터베이스 (Cloud SQL)      │
        │ • 상품 업데이트               │
        │ • 회원 업데이트               │
        │ • 주문 업데이트               │
        └──────────────────────────────┘

결과: ✅ 동기화 완료
```

---

## ⏰ 시간 설정 (Cron 표현식)

### 현재 설정

```
"50 0,4 * * *"
```

**해석:**
```
분 시 일 월 요일
50  0  *  * *    → 00:50 UTC (09:50 KST)
50  4  *  * *    → 04:50 UTC (13:50 KST)
```

**실제 실행 시간:**
- 🌅 **09:50 KST** (서울 아침)
- 🌆 **13:50 KST** (서울 오후)

**매일 반복**

---

## 🔧 설정 파일 위치

| 파일 | 용도 |
|------|------|
| `setup-cloud-scheduler.sh` | Cloud Scheduler Job 자동 생성 스크립트 |
| `app/main.py` | 트리거/실행 엔드포인트 구현 |
| `requirements.txt` | Cloud Tasks 클라이언트 (`google-cloud-tasks==2.21.0`) |

---

## 🔍 실제 코드 흐름

### 1. Cloud Scheduler 요청

```bash
Cloud Scheduler가 보냄:

POST https://babba-api-XXX.run.app/tasks/sync/makeshop/trigger
Authorization: Bearer {OIDC_TOKEN}
Content-Type: application/json

Body: {}
```

### 2. 트리거 엔드포인트 처리

```python
# app/main.py
@app.post("/tasks/sync/makeshop/trigger")
def trigger_makeshop_sync(request: Request):
    # 1. payload 생성
    payload = MakeshopSyncTaskPayload(...)
    
    # 2. Cloud Tasks 클라이언트 초기화
    client = tasks_v2.CloudTasksClient()
    queue = client.queue_path(PROJECT_ID, LOCATION, QUEUE_NAME)
    
    # 3. Task 객체 생성
    task = {
        "http_request": {
            "http_method": "POST",
            "url": "https://.../tasks/sync/makeshop/run",
            "body": json.dumps(payload).encode("utf-8"),
            "oidc_token": {...}
        }
    }
    
    # 4. 큐에 추가
    created_task = client.create_task(parent=queue, task=task)
    
    # 5. 즉시 반환 (< 1초)
    return {"status": "queued", "task": created_task.name}
```

### 3. Cloud Tasks 큐 처리

```
대기 중인 Task를 가져와서:

POST https://babba-api-XXX.run.app/tasks/sync/makeshop/run
Authorization: Bearer {SERVICE_ACCOUNT_TOKEN}
Content-Type: application/json

Body: {"InquiryTimeFrom": null, "InquiryTimeTo": null}
```

### 4. 실행 엔드포인트 처리

```python
# app/main.py
@app.post("/tasks/sync/makeshop/run")
def run_makeshop_sync_task(payload: MakeshopSyncTaskPayload, db: Session):
    # 실제 동기화 로직 실행
    return _run_makeshop_sync(db, payload.InquiryTimeFrom, payload.InquiryTimeTo)
```

---

## ⚠️ 에러가 발생하면?

### Cloud Scheduler 요청 실패

```
1차 시도: 실패
  ↓ (1초 후)
2차 시도: 실패
  ↓ (지수 백오프로 증가)
...
최대 재시도까지 반복
```

### Cloud Tasks 작업 실패

```
Task 처리 중 오류: 실패
  ↓ (0.1초 후)
1차 재시도: 실패
  ↓ (0.2초 후)
2차 재시도: 실패
  ↓ (지수 백오프로 최대 3600초까지)
...
최대 100회 재시도
```

---

## 📊 모니터링하기

### Cloud Scheduler Job 확인

```bash
# Job 상태 확인
gcloud scheduler jobs describe babba-sync-makeshop \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9

# Job 수동 실행 (테스트)
gcloud scheduler jobs run babba-sync-makeshop \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9
```

### Cloud Tasks 큐 확인

```bash
# 큐 상태 확인
gcloud tasks queues describe makeshop-sync-queue \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9

# 큐의 작업 조회
gcloud tasks list \
  --queue=makeshop-sync-queue \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9
```

### Cloud Run 로그 확인

```bash
# 트리거 엔드포인트 로그
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~/trigger/' \
  --limit=20 --format=short

# 실행 엔드포인트 로그
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~/run/' \
  --limit=20 --format=short
```

---

## ✅ 체크리스트

### 배포 확인

- [ ] Cloud Run 서비스 배포됨
- [ ] `/health` 엔드포인트 정상 (200 OK)
- [ ] `/health/db` 엔드포인트 정상 (연결됨)
- [ ] `/makeshop/health` 엔드포인트 정상 (API 연결됨)

### Cloud Tasks 설정

- [ ] `makeshop-sync-queue` 큐 생성됨
- [ ] 큐 상태: `RUNNING`
- [ ] 위치: `asia-northeast3`
- [ ] Cloud Run 서비스 계정에 권한 부여됨

### Cloud Scheduler 설정 (선택사항)

- [ ] `setup-cloud-scheduler.sh` 스크립트 실행
- [ ] Job 생성됨: `babba-sync-makeshop`
- [ ] Job 상태: 활성화됨
- [ ] 스케줄: "50 0,4 * * *" (매일 09:50, 13:50 KST)

---

## 🎓 더 자세히 배우기

**더 자세한 내용은:**
→ [CLOUD_SCHEDULER_CLOUD_TASKS_FLOW.md](./CLOUD_SCHEDULER_CLOUD_TASKS_FLOW.md) 참고

**코드 구현 보기:**
→ `app/main.py` 의 Cloud Tasks 관련 코드 참고

**GCP 공식 문서:**
- [Cloud Scheduler](https://cloud.google.com/scheduler/docs)
- [Cloud Tasks](https://cloud.google.com/tasks/docs)

---

**이 가이드로 이해가 됐으면:**
✅ Cloud Scheduler = 시간 관리자  
✅ Cloud Tasks = 작업 큐 관리자  
✅ Cloud Run = 실제 작업자  

모두 함께 작동하여 **정확한 시간에 안전하게 작업을 실행**합니다! 🚀
