# 🚀 Cloud Run + Cloud SQL 배포 최종 가이드

## 📋 현재 상태

✅ **준비됨:**
- Cloud SQL 인스턴스 생성됨 (`babba-db`)
- FastAPI 애플리케이션 준비됨
- Docker 설정 완료됨
- 배포 스크립트 준비됨

---

## 🎯 5단계 배포 프로세스

### **Step 1️⃣: Cloud SQL 초기화** (GCP 콘솔)

🔗 **URL**: https://console.cloud.google.com/sql/instances/babba-db

**경로:**
1. SQL 인스턴스 > `babba-db` 클릭
2. "연결" 탭 > "Cloud Shell에서 연결" 클릭
3. 다음 SQL 명령 실행:

```sql
CREATE DATABASE IF NOT EXISTS babba CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'babba_user'@'%' IDENTIFIED BY 'Fulfilled07!@';
GRANT ALL PRIVILEGES ON babba.* TO 'babba_user'@'%';
FLUSH PRIVILEGES;
```

✅ **확인:**
```sql
SHOW DATABASES;
SELECT user, host FROM mysql.user WHERE user='babba_user';
```

---

### **Step 2️⃣: Docker 설정 확인**

**파일**: `Dockerfile`

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl -o /usr/local/bin/cloud-sql-proxy https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 && \
    chmod +x /usr/local/bin/cloud-sql-proxy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8080

CMD /usr/local/bin/cloud-sql-proxy -instances=astute-window-472313-g9:asia-northeast3:babba-db=tcp:3306 & \
    exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
```

---

### **Step 3️⃣: 환경 변수 확인**

**파일**: `.env`

```properties
# GCP 프로젝트
GCP_PROJECT_ID=astute-window-472313-g9
REGION=asia-northeast3

# Artifact Registry
REGISTRY=asia-northeast3-docker.pkg.dev
REPO_NAME=babba-registry

# 서비스
SERVICE_NAME=babba-api
IMAGE_NAME=babba-api
IMAGE_TAG=latest

# Cloud SQL
CLOUD_SQL_INSTANCE=astute-window-472313-g9:asia-northeast3:babba-db
DB_USER=babba_user
DB_PASSWORD=Fulfilled07!@
DB_NAME=babba
```

---

### **Step 4️⃣: 배포 스크립트 실행**

**권장: 자동 배포 스크립트 사용**

```bash
./deploy.sh
```

**또는 수동 배포:**

```bash
# 서비스 계정 생성
gcloud iam service-accounts create cloud-run-sql \
  --display-name="Cloud Run Cloud SQL" \
  --project=astute-window-472313-g9

# Cloud SQL 권한 부여
gcloud projects add-iam-policy-binding astute-window-472313-g9 \
  --member=serviceAccount:cloud-run-sql@astute-window-472313-g9.iam.gserviceaccount.com \
  --role=roles/cloudsql.client \
  --quiet

# 저장소 생성
gcloud artifacts repositories create babba-registry \
  --repository-format=docker \
  --location=asia-northeast3 \
  --project=astute-window-472313-g9 2>&1 | grep -v "already exists"

# 이미지 빌드
docker build \
  -t asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest \
  .

# 이미지 푸시
docker push asia-northeast3-docker.pkg.dev/astute-window-472313-g9/babba-registry/babba-api:latest

# Cloud Run 배포
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

### **Step 5️⃣: 배포 확인 및 테스트**

**서비스 URL 확인:**

```bash
SERVICE_URL=$(gcloud run services describe babba-api \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --format='value(status.url)')

echo $SERVICE_URL
```

**API 테스트:**

```bash
# Health Check
curl $SERVICE_URL/health

# Swagger UI
open $SERVICE_URL/docs

# User 생성
curl -X POST $SERVICE_URL/users \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"testuser"}'

# User 조회
curl $SERVICE_URL/users
```

---

## 📊 아키텍처 다이어그램

```
┌─────────────────────────────────────────────┐
│         인터넷 사용자                         │
└────────────┬────────────────────────────────┘
             │ HTTPS
             ▼
┌─────────────────────────────────────────────┐
│         Cloud Run (babba-api)               │
│  • Python 3.11 + FastAPI                    │
│  • Uvicorn ASGI 서버                        │
│  • Cloud SQL Auth Proxy                     │
└────────────┬────────────────────────────────┘
             │ TCP 127.0.0.1:3306
             ▼
┌─────────────────────────────────────────────┐
│    Cloud SQL Auth Proxy (로컬)               │
│    포트: 3306                               │
└────────────┬────────────────────────────────┘
             │ SSL/TLS 암호화
             ▼
┌─────────────────────────────────────────────┐
│      Cloud SQL (babba-db)                   │
│  • MySQL 8.0.41                             │
│  • Enterprise Plus 에디션                   │
│  • 34.22.93.96:3306                         │
│  • asia-northeast3 리전                     │
└─────────────────────────────────────────────┘
```

---

## 🔍 배포 후 모니터링

### Cloud Run 로그 확인

```bash
# 실시간 로그
gcloud logging read \
  "resource.service.name=babba-api AND resource.type=cloud_run_revision" \
  --limit=50 \
  --format=json \
  --project=astute-window-472313-g9 | jq '.[] | {time:.timestamp, message:.textPayload}'

# Cloud Logging 콘솔
# https://console.cloud.google.com/logs/query
```

### Cloud SQL 모니터링

```bash
# 연결 상태 확인
gcloud sql instances describe babba-db \
  --project=astute-window-472313-g9 \
  --format='table(name,state,ipAddresses[0].ipAddress,settings.tier)'

# 데이터베이스 크기 확인
gcloud sql backups list \
  --instance=babba-db \
  --project=astute-window-472313-g9
```

---

## 💰 비용 추정

**월간 비용 (현재 구성):**

| 항목 | 비용 |
|------|------|
| Cloud SQL (db-perf-optimized-N-2) | $215 |
| 스토리지 (10GB) | $2 |
| Cloud Run (512Mi, 0-100 인스턴스) | ~$5-20 |
| **합계** | **$222-237/월** |

---

## ✅ 배포 체크리스트

- [ ] Cloud SQL 데이터베이스 생성 (GCP 콘솔)
- [ ] 사용자 `babba_user` 생성
- [ ] `.env` 파일 확인
- [ ] Dockerfile 확인
- [ ] Docker 설치 확인
- [ ] Colima/Docker Desktop 실행
- [ ] `./deploy.sh` 실행 또는 수동 배포
- [ ] 서비스 URL 확인
- [ ] `/health` 엔드포인트 테스트
- [ ] `/users` 엔드포인트 테스트
- [ ] Cloud Run 로그 확인

---

## 🔐 보안 체크리스트

- [ ] 환경 변수 `.env` 파일 `.gitignore` 추가
- [ ] Cloud SQL SSL/TLS 활성화
- [ ] Cloud Run 서비스 인증 필요 (필요시)
- [ ] Secret Manager에 비밀번호 저장 (권장)
- [ ] IAM 역할 최소 권한 원칙 따름
- [ ] Cloud SQL 공개 IP 비활성화 (필요시)

---

## 🆘 문제 해결

### Cloud Run 배포 실패

```bash
# 로그 확인
gcloud run services describe babba-api --region=asia-northeast3 --project=astute-window-472313-g9

# 이전 버전으로 롤백
gcloud run services update-traffic babba-api --to-revisions LATEST=0 --region=asia-northeast3 --project=astute-window-472313-g9
```

### Cloud SQL 연결 실패

```bash
# 인스턴스 상태 확인
gcloud sql instances describe babba-db --project=astute-window-472313-g9

# 연결 테스트
gcloud sql connect babba-db --project=astute-window-472313-g9 --user=root
```

### Docker 빌드 실패

```bash
# Colima 상태 확인
colima status

# Colima 재시작
colima restart

# Docker 테스트
docker ps
```

---

## 📚 참고 문서

- [CLOUD_RUN_SETUP.md](./CLOUD_RUN_SETUP.md) - 자세한 설정 가이드
- [CLOUD_RUN_DEPLOY.md](./CLOUD_RUN_DEPLOY.md) - 빠른 배포 가이드
- [COST_SUMMARY.md](./COST_SUMMARY.md) - 비용 요약
- [README.md](./README.md) - 프로젝트 개요

---

## 🎉 배포 완료!

모든 단계를 완료하면:

✅ FastAPI 앱이 Cloud Run에서 실행됨  
✅ Cloud SQL에 연결됨  
✅ Swagger UI로 API 문서 확인 가능  
✅ 프로덕션 환경에서 자동 스케일링  
✅ 월 $220-240 비용으로 운영 가능

---

**마지막 단계: `./deploy.sh` 실행 또는 위 Step 4 수동 배포를 진행하세요! 🚀**
