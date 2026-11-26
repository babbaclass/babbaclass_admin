# FastAPI Admin 패널 가이드

## 📊 Admin 패널 개요

FastAPI Admin을 사용하여 데이터베이스 모델(Users, Partners)을 시각적으로 관리할 수 있는 관리자 패널을 제공합니다.

## 🎯 주요 기능

### Users 관리
- ✅ 사용자 생성/조회/수정/삭제
- ✅ 이메일, 사용자명으로 검색
- ✅ 활성 상태 관리
- ✅ 생성/수정 시간 추적

### Partners 관리
- ✅ 파트너사 생성/조회/수정/삭제
- ✅ 파트너명으로 검색
- ✅ 설명 관리
- ✅ 활성 상태 관리

## 🚀 사용 방법

### 1단계: 로컬에서 테스트

```bash
# 패키지 설치
pip install -r requirements.txt

# 서버 실행
uvicorn app.main:app --reload
```

### 2단계: Admin 패널 접속

브라우저에서 다음 URL로 접속:
```
http://localhost:8000/admin
```

### 3단계: 로그인 (기본 설정)

기본 Admin 패널에서는 로그인이 필요합니다:
- **Username**: `admin`
- **Password**: `admin` (또는 설정된 비밀번호)

**주의**: 프로덕션 환경에서는 보안 설정을 필수로 변경해야 합니다!

## 📱 Admin 패널 기능

### Users 패널
| 기능 | 설명 |
|------|------|
| **생성** | 새 사용자 추가 |
| **조회** | 모든 사용자 목록 보기 |
| **수정** | 사용자 정보 편집 |
| **삭제** | 사용자 삭제 |
| **검색** | 이메일/사용자명으로 검색 |
| **정렬** | ID, 생성일로 정렬 |

### Partners 패널
| 기능 | 설명 |
|------|------|
| **생성** | 새 파트너사 추가 |
| **조회** | 모든 파트너사 목록 보기 |
| **수정** | 파트너 정보 편집 |
| **삭제** | 파트너사 삭제 |
| **검색** | 파트너명으로 검색 |
| **정렬** | ID, 생성일로 정렬 |

## 🔒 보안 설정 (프로덕션)

### 1. 비밀번호 변경

```python
# app/admin.py에서 기본 비밀번호 설정
admin = Admin(
    app=app,
    engine=engine,
    title="babba-api Admin",
    username="admin",
    password="your-secure-password",  # 변경 필수!
)
```

### 2. HTTPS 사용

프로덕션에서는 반드시 HTTPS를 사용하세요.

### 3. 접근 제제

Admin 패널을 특정 IP 주소에서만 접근 가능하도록 제한:

```python
# Middleware를 사용하여 IP 제한
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class AdminIPRestrict(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/admin"):
            client_ip = request.client.host
            allowed_ips = ["YOUR_IP"]  # 관리자 IP만 허용
            if client_ip not in allowed_ips:
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        return await call_next(request)

app.add_middleware(AdminIPRestrict)
```

## 📡 API vs Admin 패널

| 항목 | REST API | Admin 패널 |
|------|----------|-----------|
| **접근** | 프로그래밍 방식 | GUI 방식 |
| **권한** | API 토큰 기반 | 로그인 기반 |
| **성능** | JSON 기반 | HTML/웹 기반 |
| **용도** | 자동화/통합 | 수동 관리 |

## 🔗 관련 엔드포인트

### REST API (비 Admin)
- `GET /users` - 사용자 목록
- `POST /users` - 사용자 생성
- `GET /users/{user_id}` - 사용자 조회
- `DELETE /users/{user_id}` - 사용자 삭제

### Admin 패널
- `GET /admin` - Admin 대시보드
- `GET /admin/users` - 사용자 관리
- `GET /admin/partners` - 파트너 관리

## 📊 데이터 구조

### Users 테이블
```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### Partners 테이블
```sql
CREATE TABLE partners (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## 🆘 트러블슈팅

### Admin 패널에 접속할 수 없음
1. 서버가 실행 중인지 확인: `http://localhost:8000`
2. URL 확인: `http://localhost:8000/admin` (정확한 경로)
3. 브라우저 캐시 삭제 및 새로고침

### 로그인 실패
1. 기본 자격증명 확인: `admin` / `admin`
2. `app/admin.py`에서 설정한 비밀번호 확인
3. 데이터베이스 연결 상태 확인

### 데이터베이스 쿼리 오류
1. Cloud SQL 연결 확인
2. 테이블이 생성되었는지 확인
3. SQLAlchemy 모델이 정확히 정의되었는지 확인

## 📚 참고 자료

- [FastAPI Admin GitHub](https://github.com/aminalaee/fastapi-admin)
- [FastAPI 문서](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)

---

**Admin 패널을 통해 데이터베이스를 시각적으로 관리하세요!** 🎉






