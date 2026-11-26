# 로컬 테스트 가이드

## 📋 개요

이 가이드는 SQLite 데이터베이스를 사용하여 로컬에서 FastAPI 애플리케이션과 Admin 패널을 테스트하는 방법을 설명합니다.

## 🚀 빠른 시작

### 1단계: 패키지 설치

```bash
pip install -r requirements.txt
```

### 2단계: 서버 실행

```bash
uvicorn main_local:app --reload --host 0.0.0.0 --port 8000
```

출력:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Application startup complete
```

### 3단계: 브라우저에서 테스트

다음 URL들을 브라우저에서 열어보세요:

| 기능 | URL |
|------|-----|
| **Swagger UI (API 테스트)** | http://localhost:8000/docs |
| **ReDoc (API 문서)** | http://localhost:8000/redoc |
| **Admin 패널** | http://localhost:8000/admin |
| **Health Check** | http://localhost:8000/health |
| **Root Info** | http://localhost:8000 |

## 📊 Admin 패널 테스트

### Admin 패널 로그인

1. http://localhost:8000/admin 방문
2. 기본 자격증명으로 로그인:
   - **Username**: `admin`
   - **Password**: `admin`

### Users 관리

1. **Create User** (생성)
   - "Users" 메뉴에서 "+" 버튼 클릭
   - Email, Username 입력
   - Save 클릭

2. **View Users** (조회)
   - Users 리스트 확인
   - 검색 가능 (email, username)

3. **Edit User** (수정)
   - 사용자 클릭
   - 정보 수정
   - Save 클릭

4. **Delete User** (삭제)
   - 사용자 체크박스 선택
   - Delete 버튼 클릭

### Partners 관리

1. **Create Partner** (생성)
   - "Partners" 메뉴에서 "+" 버튼 클릭
   - Name, Description 입력
   - Save 클릭

2. **View Partners** (조회)
   - Partners 리스트 확인
   - 검색 가능 (name)

3. **Edit Partner** (수정)
   - 파트너 클릭
   - 정보 수정
   - Save 클릭

4. **Delete Partner** (삭제)
   - 파트너 체크박스 선택
   - Delete 버튼 클릭

## 🔌 API 엔드포인트 테스트 (Swagger UI 사용)

### Users API

```bash
# Create User
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "john_doe"
  }'

# List Users
curl http://localhost:8000/users

# Get User
curl http://localhost:8000/users/1

# Delete User
curl -X DELETE http://localhost:8000/users/1
```

### Partners API

```bash
# Create Partner
curl -X POST http://localhost:8000/partners \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ABC Company",
    "description": "Partner description"
  }'

# List Partners
curl http://localhost:8000/partners

# Get Partner
curl http://localhost:8000/partners/1

# Delete Partner
curl -X DELETE http://localhost:8000/partners/1
```

## 📁 데이터 저장 위치

SQLite 데이터베이스 파일:
```
babba_local.db  (워크스페이스 루트)
```

**주의**: 이 파일을 git에 커밋하지 마세요! `.gitignore`에 이미 추가되어 있습니다.

## 🔄 데이터 초기화

데이터를 초기화하려면 `babba_local.db` 파일을 삭제하고 서버를 다시 시작하세요:

```bash
rm babba_local.db
uvicorn main_local:app --reload
```

## 🐛 트러블슈팅

### 포트 8000이 이미 사용 중일 때

```bash
# 다른 포트 사용
uvicorn main_local:app --reload --port 8001
```

### ImportError: cannot import name 'setup_admin'

```bash
# 패키지 재설치
pip install -r requirements.txt --force-reinstall
```

### Admin 패널에 로그인할 수 없음

1. 캐시 삭제 후 새로고침
2. 다른 브라우저에서 시도
3. URL 확인: `http://localhost:8000/admin` (정확한 경로)

### 데이터베이스 오류

```bash
# 데이터베이스 초기화
rm babba_local.db

# 서버 재시작
uvicorn main_local:app --reload
```

## ✅ 테스트 체크리스트

- [ ] Swagger UI 로드 (`/docs`)
- [ ] Admin 패널 로드 (`/admin`)
- [ ] Admin 로그인 성공
- [ ] User 생성 성공
- [ ] User 조회 성공
- [ ] User 수정 성공
- [ ] User 삭제 성공
- [ ] Partner 생성 성공
- [ ] Partner 조회 성공
- [ ] Partner 수정 성공
- [ ] Partner 삭제 성공
- [ ] API 검색 기능 정상 작동

## 📝 다음 단계

1. ✅ 로컬 테스트 완료
2. 🔄 Cloud SQL 인스턴스 설정
3. 🔄 `.env` 파일 업데이트
4. 🔄 `app/main.py`로 전환 (프로덕션)
5. 🔄 Docker 빌드 및 배포

---

**로컬 테스트를 통해 Admin 패널과 API를 검증한 후 프로덕션 배포를 진행하세요!** 🚀
