# 배포 및 테스트 체크리스트

## 1️⃣ GitHub Actions 배포 상태 확인

**URL**: https://github.com/Fulfilled-Inc/babba-api/actions

### 확인 단계:
1. "Deploy to Cloud Run" 워크플로우 실행 확인
2. 각 단계 상태 확인:
   - ✅ Checkout code
   - ✅ Authenticate with Google Cloud
   - ✅ Set up Cloud SDK
   - ✅ Build Docker image
   - ✅ Configure Docker for Artifact Registry
   - ✅ Push Docker image
   - ✅ Deploy to Cloud Run
   - ✅ Deployment complete

## 2️⃣ Cloud Run 서비스 배포 확인

**명령어**:
```bash
gcloud run services describe babba-api --region=asia-northeast3 \
  --format='table(status.conditions[0].status,status.url)'
```

**예상 결과**:
- Status: `True` (Ready)
- URL: `https://babba-api-*.run.app`

## 3️⃣ 서비스 헬스 체크

**명령어**:
```bash
curl https://babba-api-kitlcurzpa-du.a.run.app/health
```

**예상 응답**:
```json
{"status": "healthy"}
```

## 4️⃣ 데이터베이스 마이그레이션 확인

### 방법 1: Cloud Run 로그 확인
```bash
gcloud run services logs read babba-api --region=asia-northeast3 --limit=50
```

**마이그레이션 성공 시 로그에 나타나야 하는 메시지**:
```
Running database migrations...
[DEBUG] Constructing database URL...
✓ Migrations completed
Starting Uvicorn on port 8080
```

### 방법 2: Cloud SQL에서 직접 확인

```bash
# Cloud SQL Proxy를 통해 로컬 포트 3306에 연결
cloud_sql_proxy -instances=astute-window-472313-g9:asia-northeast3:babba-db=tcp:3306

# 다른 터미널에서:
mysql -h 127.0.0.1 -u root -p'Fulfilled07!@' babba -e "DESCRIBE users;"
```

**마이그레이션 성공 시 결과에 포함되어야 하는 컬럼**:
- `password_hash` (VARCHAR 255, NULL 가능)
- `is_admin` (BOOLEAN, DEFAULT 0)

## 5️⃣ Admin 계정 생성 (선택사항)

마이그레이션이 성공했으면, admin 계정을 생성할 수 있습니다.

### Step 1: Bcrypt 해시 생성

**로컬에서 Python 실행**:
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
password_hash = pwd_context.hash("admin123")
print(password_hash)
```

### Step 2: 데이터베이스에 admin 계정 추가

```sql
USE babba;

INSERT INTO users (
  username, 
  email, 
  password_hash, 
  is_admin, 
  is_active, 
  created_at, 
  updated_at
) VALUES (
  'admin',
  'admin@babba.local',
  '$2b$12$[생성된_bcrypt_해시]',
  TRUE,
  TRUE,
  NOW(),
  NOW()
);
```

### Step 3: Admin 로그인 테스트

**URL**: https://babba-api-kitlcurzpa-du.a.run.app/admin/

**로그인 정보**:
- **사용자명**: admin
- **비밀번호**: admin123

## 📋 트러블슈팅

### 마이그레이션 실패
- 로그 확인: `gcloud run services logs read babba-api --region=asia-northeast3 --limit=100`
- Cloud SQL 연결 확인: Cloud SQL Proxy가 포트 3306에서 실행 중인지 확인
- 환경 변수 확인: `CLOUD_SQL_INSTANCE`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` 확인

### 서비스 500 에러
- Cloud Run 로그 확인
- SQLAlchemy 모델 정의 확인
- 데이터베이스 연결 문자열 확인

### Admin 로그인 실패
- 사용자 계정이 `is_admin=TRUE`로 설정되어 있는지 확인
- 비밀번호 해시가 올바르게 저장되었는지 확인

## ✅ 완료 체크리스트

- [ ] GitHub Actions 워크플로우 성공
- [ ] Cloud Run 서비스 배포됨 (status=Ready)
- [ ] /health 엔드포인트 응답 확인
- [ ] 데이터베이스 마이그레이션 완료 (password_hash, is_admin 컬럼 추가됨)
- [ ] Admin 계정 로그인 테스트 통과 (선택사항)
