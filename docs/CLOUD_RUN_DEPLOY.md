# ⚡ 빠른 Cloud Run 배포 가이드

## 🚀 현재 상태

✅ **Cloud SQL 생성됨**
- 인스턴스: `babba-db`
- 데이터베이스 버전: MySQL 8.0.41
- 리전: asia-northeast3

---

## 📋 남은 작업

### Step 1: Cloud SQL 초기화 (GCP 콘솔)

**경로**: https://console.cloud.google.com/sql/instances

1. **`babba-db` 클릭**
2. **"연결" 탭 클릭**
3. **상단 "Cloud Shell에서 연결" 클릭**
4. **아래 SQL 명령 실행:**

```sql
-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS babba CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 사용자 생성
CREATE USER IF NOT EXISTS 'babba_user'@'%' IDENTIFIED BY 'Fulfilled07!@';

-- 권한 부여
GRANT ALL PRIVILEGES ON babba.* TO 'babba_user'@'%';
FLUSH PRIVILEGES;

-- 확인
SHOW DATABASES;
SELECT user, host FROM mysql.user WHERE user='babba_user';
```

---

### Step 2: 서비스 계정 생성

```bash
gcloud iam service-accounts create cloud-run-sql \
  --display-name="Cloud Run Cloud SQL" \
  --project=astute-window-472313-g9

# Cloud SQL 클라이언트 역할 부여
gcloud projects add-iam-policy-binding astute-window-472313-g9 \
  --member=serviceAccount:cloud-run-sql@astute-window-472313-g9.iam.gserviceaccount.com \
  --role=roles/cloudsql.client \
  --quiet
```

---

### Step 3: Dockerfile 확인 및 업데이트

**현재 위치**: `/Users/hoonlee/Documents/GitHub/babba-api/Dockerfile`

**필수 설정:**

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# Cloud SQL Auth Proxy 다운로드
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl -o /usr/local/bin/cloud-sql-proxy https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 && \
    chmod +x /usr/local/bin/cloud-sql-proxy

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# 두 프로세스 시작
CMD /usr/local/bin/cloud-sql-proxy -instances=astute-window-472313-g9:asia-northeast3:babba-db=tcp:3306 & \
    exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
```

---

### Step 4: `app/database.py` 확인

**현재 설정이 맞는지 확인:**

```python
# 환경 변수 사용 확인
CLOUD_SQL_INSTANCE = os.getenv("CLOUD_SQL_INSTANCE", "astute-window-472313-g9:asia-northeast3:babba-db")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Fulfilled07!@")
DB_NAME = os.getenv("DB_NAME", "")

# Cloud Run 감지
CLOUD_RUN_ENV = os.getenv("K_SERVICE", "")

# URL 구성
if CLOUD_RUN_ENV:
    # Cloud Run: TCP 연결 (Proxy 사용)
    SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@127.0.0.1:3306/{DB_NAME}"
else:
    # 로컬: TCP 연결
    SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@127.0.0.1:3306/{DB_NAME}"
```

---

### Step 5: Docker 이미지 빌드 & 푸시

```bash
# 저장소 생성 (이미 있으면 스킵)
gcloud artifacts repositories create babba-registry \
  --repository-format=docker \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9 2>&1 | grep -v "already exists"

# 이미지 빌드
cd /Users/hoonlee/Documents/GitHub/babba-api

docker build \
  -t asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest \
  .

# 이미지 푸시
docker push asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest
```

---

### Step 6: Cloud Run 배포

```bash
gcloud run deploy babba-api \
  --image=asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest \
  --platform=managed \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --allow-unauthenticated \
  --service-account=cloud-run-sql@astute-window-472313-g9.iam.gserviceaccount.com \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300 \
  --set-env-vars \
    CLOUD_SQL_INSTANCE="astute-window-472313-g9:asia-northeast3:babba-db",\
    DB_USER="babba_user",\
    DB_PASSWORD="Fulfilled07!@",\
    DB_NAME="babba"
```

---

### Step 7: 배포 확인

```bash
# 서비스 상태 확인
gcloud run services describe babba-api \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9

# 서비스 URL 확인
gcloud run services describe babba-api \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --format='value(status.url)'
```

---

### Step 8: API 테스트

```bash
# 서비스 URL 저장
SERVICE_URL=$(gcloud run services describe babba-api \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --format='value(status.url)')

# Health Check
curl $SERVICE_URL/health

# User 생성
curl -X POST $SERVICE_URL/users \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"testuser"}'

# User 조회
curl $SERVICE_URL/users
```

---

## ⚙️ 환경 변수

**.env 파일 (현재 상태)**

```properties
CLOUD_SQL_INSTANCE=astute-window-472313-g9:asia-northeast3:babba-db
DB_USER=babba_user
DB_PASSWORD=Fulfilled07!@
DB_NAME=babba
```

---

## 🔒 보안 (선택사항)

### Secret Manager 사용 (권장)

```bash
# 비밀번호 저장
echo -n "Fulfilled07!@" | gcloud secrets create db-password \
  --data-file=- \
  --project=astute-window-472313-g9

# 서비스 계정에 접근 권한 부여
gcloud secrets add-iam-policy-binding db-password \
  --member=serviceAccount:cloud-run-sql@astute-window-472313-g9.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor \
  --project=astute-window-472313-g9
```

---

## 📊 최종 아키텍처

```
┌─────────────────────┐
│  Cloud Run          │
│  (babba-api)        │
│                     │
│ ┌─────────────────┐ │
│ │ Cloud SQL Auth  │ │
│ │ Proxy (Port:    │ │
│ │ 3306)           │ │
│ └────────┬────────┘ │
└─────────┼───────────┘
          │ TCP (127.0.0.1:3306)
          ▼
┌─────────────────────┐
│  Cloud SQL          │
│  (babba-db)         │
│  MySQL 8.0.41       │
│  34.22.93.96        │
└─────────────────────┘
```

---

## ✅ 체크리스트

- [ ] Cloud SQL 데이터베이스 생성 (GCP 콘솔)
- [ ] 사용자 생성 (SQL 명령 실행)
- [ ] 서비스 계정 생성
- [ ] Docker 이미지 빌드
- [ ] Docker 이미지 푸시
- [ ] Cloud Run 배포
- [ ] API 테스트

---

**이제 모든 단계를 자동화할 준비가 되었습니다! 🚀**

다음 명령을 차례로 실행하세요.
