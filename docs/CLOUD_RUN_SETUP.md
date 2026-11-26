# Cloud Run + Cloud SQL 연동 가이드

## 🔌 현재 설정

```
인스턴스명: babba-db
상태: RUNNABLE
데이터베이스: MySQL 8.0.41
연결명: astute-window-472313-g9:asia-northeast3:babba-db
IP 주소: 34.22.93.96
리전: asia-northeast3
```

---

## 📋 연동 단계

### Step 1: Cloud SQL 데이터베이스 & 사용자 생성

```bash
# Cloud SQL 연결
gcloud sql connect babba-db \
  --project=astute-window-472313-g9 \
  --user=root
```

**MySQL 프롬프트에서 실행:**

```sql
-- 데이터베이스 생성
CREATE DATABASE babba CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 애플리케이션 사용자 생성
CREATE USER 'babba_user'@'%' IDENTIFIED BY 'secure-password-here';

-- 권한 부여
GRANT ALL PRIVILEGES ON babba.* TO 'babba_user'@'%';
FLUSH PRIVILEGES;

-- 확인
SHOW DATABASES;
SELECT user, host FROM mysql.user;
```

**종료:**
```sql
EXIT;
```

---

### Step 2: `.env` 파일 업데이트

```bash
# 파일 위치: .env
CLOUD_SQL_INSTANCE="astute-window-472313-g9:asia-northeast3:babba-db"
DB_USER="babba_user"
DB_PASSWORD="secure-password-here"
DB_NAME="babba"
GCP_PROJECT_ID="astute-window-472313-g9"
REGION="asia-northeast3"
```

---

### Step 3: Cloud Run 서비스 계정 설정

#### 3-1. 서비스 계정 생성 (선택사항 - 이미 있으면 스킵)

```bash
gcloud iam service-accounts create cloud-run-sa \
  --display-name="Cloud Run Service Account" \
  --project=astute-window-472313-g9
```

#### 3-2. Cloud SQL 연결 권한 부여

```bash
# Cloud SQL 클라이언트 역할 부여
gcloud projects add-iam-policy-binding astute-window-472313-g9 \
  --member=serviceAccount:cloud-run-sa@astute-window-472313-g9.iam.gserviceaccount.com \
  --role=roles/cloudsql.client

# Cloud SQL 인스턴스 연결 사용자 역할 부여
gcloud sql instances patch babba-db \
  --add-settings-database-flags=cloudsql_iam_authentication=on \
  --project=astute-window-472313-g9
```

#### 3-3. 서비스 계정 ID 확인

```bash
gcloud iam service-accounts list \
  --project=astute-window-472313-g9 \
  --format='value(email)' | grep cloud-run
```

---

### Step 4: Dockerfile 업데이트

```dockerfile
# 기존 Dockerfile에서 다음 확인

FROM python:3.11-slim

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONDONTWRITEBYTECODE=1

# Cloud SQL Auth Proxy 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cloud SQL Auth Proxy 다운로드
RUN curl -o cloud-sql-proxy https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 \
    && chmod +x cloud-sql-proxy

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud SQL 프록시 + uvicorn 실행
CMD /app/cloud-sql-proxy -ip_address_types=PRIVATE \
    "astute-window-472313-g9:asia-northeast3:babba-db" \
    & exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8080}
```

---

### Step 5: `app/database.py` 업데이트

```python
"""
Database connection configuration for Cloud SQL
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

# 환경 변수
CLOUD_SQL_INSTANCE = os.getenv("CLOUD_SQL_INSTANCE", "astute-window-472313-g9:asia-northeast3:babba-db")
DB_USER = os.getenv("DB_USER", "babba_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "babba")
CLOUD_RUN_ENV = os.getenv("K_SERVICE", "")  # Cloud Run에서 자동 설정

# 데이터베이스 URL 구성
if CLOUD_RUN_ENV:
    # Cloud Run: Unix 소켓 사용 (Cloud SQL Auth Proxy)
    SQLALCHEMY_DATABASE_URL = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@/"
        f"{DB_NAME}?unix_socket=/cloudsql/{CLOUD_SQL_INSTANCE}"
    )
else:
    # 로컬 개발: TCP 연결
    SQLALCHEMY_DATABASE_URL = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@127.0.0.1:3306/{DB_NAME}"
    )

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Dependency for FastAPI to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

### Step 6: `.env` 파일 설정

```bash
# 파일 경로: .env

# GCP 설정
GCP_PROJECT_ID="astute-window-472313-g9"
REGION="asia-northeast3"

# Cloud SQL 설정
CLOUD_SQL_INSTANCE="astute-window-472313-g9:asia-northeast3:babba-db"
DB_USER="babba_user"
DB_PASSWORD="your-secure-password"
DB_NAME="babba"

# Cloud Run 설정
SERVICE_NAME="babba-api"
IMAGE_NAME="babba-api"
REGISTRY="asia.gcr.io"
```

---

### Step 7: Cloud Run 배포

#### 7-1. Docker 이미지 빌드 및 푸시

```bash
# Artifact Registry 저장소 생성
gcloud artifacts repositories create babba-registry \
  --repository-format=docker \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9 2>&1 | grep -v "already exists"

# 이미지 빌드
docker build -t asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest .

# 이미지 푸시
docker push asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest
```

#### 7-2. Cloud Run 배포

```bash
gcloud run deploy babba-api \
  --image=asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest \
  --platform=managed \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --allow-unauthenticated \
  --set-env-vars CLOUD_SQL_INSTANCE="astute-window-472313-g9:asia-northeast3:babba-db",DB_USER="babba_user",DB_PASSWORD="your-password",DB_NAME="babba" \
  --service-account=cloud-run-sa@astute-window-472313-g9.iam.gserviceaccount.com \
  --memory=512Mi \
  --cpu=1 \
  --timeout=300
```

---

### Step 8: 배포 확인

```bash
# Cloud Run 서비스 상태 확인
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

## 🧪 배포 후 테스트

### API 테스트

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

## 🔒 보안 팁

### 1. 환경 변수 보호

❌ **하지 말 것:**
```bash
--set-env-vars DB_PASSWORD="password"  # 노출됨
```

✅ **권장:**
```bash
# Cloud Secret Manager 사용
gcloud secrets create db-password \
  --data-file=- <<< "your-password" \
  --project=astute-window-472313-g9

# Cloud Run에서 참조
--set-env-vars DB_PASSWORD_SECRET="projects/astute-window-472313-g9/secrets/db-password/versions/latest"
```

### 2. Cloud SQL 연결 보안

```bash
# SSL/TLS 강제
gcloud sql instances patch babba-db \
  --require-ssl \
  --project=astute-window-472313-g9

# 공개 IP 비활성화 (프라이빗 필요 시)
gcloud sql instances patch babba-db \
  --network-tie-admin \
  --project=astute-window-472313-g9
```

---

## 📊 아키텍처

```
┌──────────────────┐
│   Cloud Run      │
│  (babba-api)     │
└────────┬─────────┘
         │
    Cloud SQL
    Auth Proxy
         │
         ▼
┌──────────────────┐
│   Cloud SQL      │
│   (babba-db)     │
│  MySQL 8.0.41    │
└──────────────────┘
```

---

## 🚀 다음 단계

1. ✅ Cloud SQL 데이터베이스 & 사용자 생성
2. ✅ `.env` 파일 업데이트
3. ✅ 서비스 계정 설정
4. ✅ Docker 이미지 빌드 & 푸시
5. ✅ Cloud Run 배포
6. ✅ API 테스트

모든 단계를 순서대로 진행하세요!

---

## 🆘 문제 해결

### Cloud SQL 연결 실패

```bash
# 로그 확인
gcloud run services describe babba-api \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --format='value(status)'

# 더 상세한 로그
gcloud logging read "resource.service.name=babba-api" \
  --limit 50 \
  --format json \
  --project=astute-window-472313-g9
```

### 권한 문제

```bash
# 서비스 계정 확인
gcloud iam service-accounts list \
  --project=astute-window-472313-g9

# 역할 확인
gcloud projects get-iam-policy astute-window-472313-g9 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:cloud-run-sa*"
```

---

**이제 Cloud Run과 Cloud SQL이 연동됩니다! 🎉**
