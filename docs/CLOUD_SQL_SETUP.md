# Cloud SQL 연동 설정 가이드

## 📋 현재 설정

- **Cloud SQL 인스턴스**: `babba-db` (MySQL 8.4)
- **데이터베이스**: `babba`
- **루트 사용자**: `root`
- **리전**: `asia-northeast3` (서울)

## 🚀 배포 전 필수 작업

### 1단계: 로컬 테스트 (선택사항)

```bash
# Cloud SQL Auth Proxy 다운로드 (로컬 테스트용)
curl -o cloud-sql-proxy https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64
chmod +x cloud-sql-proxy

# Cloud SQL Auth Proxy 실행 (별도 터미널)
./cloud-sql-proxy astute-window-472313-g9:asia-northeast3:babba-db --ip 127.0.0.1

# 다른 터미널에서 로컬 서버 시작
export CLOUD_SQL_INSTANCE=""
export DB_USER="root"
export DB_PASSWORD="Fulfilled07!@"
export DB_NAME="babba"
uvicorn app.main:app --reload
```

### 2단계: Cloud Run에 필요한 권한 설정

Cloud Run 서비스 계정에 Cloud SQL 클라이언트 역할 추가:

```bash
PROJECT_ID="astute-window-472313-g9"
SERVICE_ACCOUNT="$(gcloud iam service-accounts list --filter='displayName:cloud-run' --format='value(email)' --project=$PROJECT_ID)"

# 기본 Cloud Run 서비스 계정
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/cloudsql.client"
```

### 3단계: 배포

```bash
./build-and-deploy.sh
```

## 🔧 환경 변수 설정

배포 시 다음 환경 변수가 자동으로 설정됩니다:

```bash
export CLOUD_SQL_INSTANCE="astute-window-472313-g9:asia-northeast3:babba-db"
export DB_USER="root"
export DB_PASSWORD="Fulfilled07!@"
export DB_NAME="babba"
```

## 🧪 API 테스트

### Swagger UI 접속
```
https://babba-api-xxxxx.a.run.app/docs
```

### 사용자 생성
```bash
curl -X POST https://babba-api-xxxxx.a.run.app/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "testuser"
  }'
```

### 사용자 목록 조회
```bash
curl https://babba-api-xxxxx.a.run.app/users
```

### 헬스 체크
```bash
curl https://babba-api-xxxxx.a.run.app/health
```

## 📊 생성된 테이블

### users 테이블
```sql
- id: INT (Primary Key)
- email: VARCHAR(255) (Unique)
- username: VARCHAR(100) (Unique)
- is_active: BOOLEAN
- created_at: DATETIME
- updated_at: DATETIME
```

### partners 테이블
```sql
- id: INT (Primary Key)
- name: VARCHAR(255)
- description: TEXT
- is_active: BOOLEAN
- created_at: DATETIME
- updated_at: DATETIME
```

## 🔐 보안 주의사항

1. **데이터베이스 접근 제한**
   - Cloud Run에서만 접근 가능하도록 설정됨
   - 로컬 테스트는 Cloud SQL Auth Proxy 필수

2. **비밀번호 관리**
   - `.env` 파일은 Git에 커밋하지 않도록 `.gitignore`에 추가됨
   - Cloud Run 환경 변수로 안전하게 관리

3. **Cloud SQL 인스턴스 보안**
   - 공개 IP 비활성화 권장
   - Private IP 사용 (설정됨)

## 🆘 트러블슈팅

### 연결 거부 (Connection Refused)
```bash
# 로컬 테스트: Cloud SQL Auth Proxy 실행 확인
ps aux | grep cloud-sql-proxy

# Cloud Run: 서비스 계정 권한 확인
gcloud projects get-iam-policy astute-window-472313-g9 \
  --flatten="bindings[].members" \
  --filter="bindings.role:cloudsql.client"
```

### 타임아웃 오류
- 로컬: 방화벽 설정 확인
- Cloud Run: Cloud SQL 인스턴스 상태 확인
  ```bash
  gcloud sql instances describe babba-db --project=astute-window-472313-g9
  ```

### 인증 오류
```bash
# 비밀번호 재설정
gcloud sql users set-password root \
  --instance=babba-db \
  --password='Fulfilled07!@' \
  --project=astute-window-472313-g9
```

## 📈 모니터링

### Cloud SQL 로그 확인
```bash
gcloud logging read "resource.type=cloudsql_database" \
  --limit=50 \
  --project=astute-window-472313-g9
```

### Cloud Run 로그에서 DB 연결 확인
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=babba-api" \
  --limit=50 \
  --project=astute-window-472313-g9
```

---

**이제 Cloud SQL과 Cloud Run이 완벽히 연동되었습니다!** 🎉
