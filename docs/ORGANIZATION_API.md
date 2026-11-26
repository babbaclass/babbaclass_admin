# 조직 구조 관리 API 문서

## 개요

조직의 계층 구조를 관리하기 위한 API 입니다. 본사(HQ)와 지사(BRANCH), 그리고 각 위치에 소속된 사용자들을 관리합니다.

## 핵심 엔티티

### 1. Company (회사/지사)
- **company_group**: 'HQ'(본사) 또는 'BRANCH'(지사)
- **name**: 위치명
- **address**: 주소
- **phone_number**: 대표 연락처
- **parent_company_id**: 상위 회사 (본사는 NULL)

### 2. Role (직책/역할)
- **role_name**: 역할명 (예: '본사 관리자', '지사장', '원장')
- **description**: 역할 설명

### 3. User (사용자/직원)
- **name**: 사용자명
- **email**: 이메일 (로그인 ID)
- **password_hash**: 비밀번호 해시
- **company_id**: 소속 회사
- **role_id**: 직책
- **reports_to_user_id**: 직속 상사 (NULL이면 최상위)

---

## API 엔드포인트

### Company (회사) 관리

#### 1. 회사 생성
```http
POST /api/v1/companies
Content-Type: application/json

{
  "company_group": "HQ",
  "name": "본사",
  "address": "서울시 강남구",
  "phone_number": "02-1234-5678",
  "parent_company_id": null
}
```

**응답:**
```json
{
  "company_id": 1,
  "company_group": "HQ",
  "name": "본사",
  "address": "서울시 강남구",
  "phone_number": "02-1234-5678",
  "parent_company_id": null,
  "is_active": true,
  "created_at": "2025-11-06T00:00:00",
  "updated_at": "2025-11-06T00:00:00"
}
```

#### 2. 지사 생성
```http
POST /api/v1/companies
Content-Type: application/json

{
  "company_group": "BRANCH",
  "name": "부산 지사",
  "address": "부산시 해운대구",
  "phone_number": "051-1234-5678",
  "parent_company_id": 1
}
```

#### 3. 회사 조회
```http
GET /api/v1/companies/{company_id}
```

**응답 (상세 정보):**
```json
{
  "company_id": 1,
  "company_group": "HQ",
  "name": "본사",
  "address": "서울시 강남구",
  "phone_number": "02-1234-5678",
  "parent_company_id": null,
  "is_active": true,
  "created_at": "2025-11-06T00:00:00",
  "updated_at": "2025-11-06T00:00:00",
  "branches": [
    {
      "company_id": 2,
      "company_group": "BRANCH",
      "name": "부산 지사",
      "address": "부산시 해운대구",
      "phone_number": "051-1234-5678",
      "parent_company_id": 1,
      "is_active": true,
      "created_at": "2025-11-06T00:00:00",
      "updated_at": "2025-11-06T00:00:00"
    }
  ],
  "users": [
    {
      "user_id": 1,
      "name": "홍길동",
      "email": "hong@babba.com",
      "company_id": 1,
      "role_id": 1,
      "reports_to_user_id": null,
      "is_active": true,
      "created_at": "2025-11-06T00:00:00",
      "updated_at": "2025-11-06T00:00:00"
    }
  ]
}
```

#### 4. 모든 회사 조회
```http
GET /api/v1/companies?skip=0&limit=100
GET /api/v1/companies?skip=0&limit=100&company_group=HQ
GET /api/v1/companies?skip=0&limit=100&company_group=BRANCH
```

#### 5. 지사 목록 조회
```http
GET /api/v1/companies/{company_id}/branches
```

#### 6. 회사 수정
```http
PUT /api/v1/companies/{company_id}
Content-Type: application/json

{
  "name": "새로운 본사",
  "address": "서울시 서초구",
  "phone_number": "02-9999-9999",
  "is_active": true
}
```

#### 7. 회사 삭제
```http
DELETE /api/v1/companies/{company_id}
```

---

### Role (직책) 관리

#### 1. 직책 생성
```http
POST /api/v1/roles
Content-Type: application/json

{
  "role_name": "본사 관리자",
  "description": "본사에서 전체 업무를 관리하는 역할"
}
```

#### 2. 직책 조회
```http
GET /api/v1/roles/{role_id}
```

#### 3. 모든 직책 조회
```http
GET /api/v1/roles?skip=0&limit=100
```

#### 4. 직책 수정
```http
PUT /api/v1/roles/{role_id}
Content-Type: application/json

{
  "role_name": "본사 관리자 (수정)",
  "description": "수정된 설명",
  "is_active": true
}
```

#### 5. 직책 삭제
```http
DELETE /api/v1/roles/{role_id}
```

---

### User (사용자) 관리

#### 1. 사용자 생성
```http
POST /api/v1/users
Content-Type: application/json

{
  "name": "홍길동",
  "email": "hong@babba.com",
  "password": "securePassword123",
  "company_id": 1,
  "role_id": 1,
  "reports_to_user_id": null
}
```

#### 2. 사용자 조회
```http
GET /api/v1/users/{user_id}
```

**응답 (상세 정보):**
```json
{
  "user_id": 1,
  "name": "홍길동",
  "email": "hong@babba.com",
  "company_id": 1,
  "role_id": 1,
  "reports_to_user_id": null,
  "is_active": true,
  "created_at": "2025-11-06T00:00:00",
  "updated_at": "2025-11-06T00:00:00",
  "company_name": "본사",
  "role_name": "본사 관리자",
  "reports_to_name": null,
  "direct_reports": [
    {
      "user_id": 2,
      "name": "김영희",
      "email": "kim@babba.com",
      "company_id": 1,
      "role_id": 2,
      "reports_to_user_id": 1,
      "is_active": true,
      "created_at": "2025-11-06T00:00:00",
      "updated_at": "2025-11-06T00:00:00"
    }
  ]
}
```

#### 3. 모든 사용자 조회
```http
GET /api/v1/users?skip=0&limit=100
GET /api/v1/users?skip=0&limit=100&company_id=1
GET /api/v1/users?skip=0&limit=100&role_id=1
```

#### 4. 직속 부하 직원 조회
```http
GET /api/v1/users/{user_id}/subordinates
```

#### 5. 사용자 수정
```http
PUT /api/v1/users/{user_id}
Content-Type: application/json

{
  "name": "홍길동 (수정)",
  "email": "hong.new@babba.com",
  "company_id": 1,
  "role_id": 2,
  "reports_to_user_id": null,
  "is_active": true,
  "password": "newPassword123"
}
```

#### 6. 사용자 삭제
```http
DELETE /api/v1/users/{user_id}
```

---

### Authentication (인증)

#### 사용자 로그인
```http
POST /api/v1/auth/login?email=hong@babba.com&password=securePassword123
```

**응답:**
```json
{
  "user_id": 1,
  "email": "hong@babba.com",
  "name": "홍길동",
  "company_id": 1,
  "role_id": 1,
  "message": "로그인 성공"
}
```

---

## 사용 사례 (Use Cases)

### 시나리오: 본사-지사 구조 구축

#### 1단계: 역할(Role) 생성
```http
POST /api/v1/roles
{
  "role_name": "본사 관리자",
  "description": "본사 전체 관리"
}

POST /api/v1/roles
{
  "role_name": "지사장",
  "description": "지사 운영 책임"
}

POST /api/v1/roles
{
  "role_name": "원장",
  "description": "지사 내 팀 관리"
}
```

#### 2단계: 회사(Company) 생성
```http
POST /api/v1/companies
{
  "company_group": "HQ",
  "name": "본사",
  "address": "서울시 강남구",
  "phone_number": "02-1234-5678",
  "parent_company_id": null
}

POST /api/v1/companies
{
  "company_group": "BRANCH",
  "name": "부산 지사",
  "address": "부산시 해운대구",
  "phone_number": "051-1234-5678",
  "parent_company_id": 1
}
```

#### 3단계: 사용자(User) 생성 및 계층 설정
```http
# 본사 관리자
POST /api/v1/users
{
  "name": "홍길동",
  "email": "hong@babba.com",
  "password": "password123",
  "company_id": 1,
  "role_id": 1,
  "reports_to_user_id": null
}

# 지사장 (본사 관리자 아래)
POST /api/v1/users
{
  "name": "이순신",
  "email": "lee@babba.com",
  "password": "password123",
  "company_id": 2,
  "role_id": 2,
  "reports_to_user_id": 1
}

# 원장 (지사장 아래)
POST /api/v1/users
{
  "name": "김영희",
  "email": "kim@babba.com",
  "password": "password123",
  "company_id": 2,
  "role_id": 3,
  "reports_to_user_id": 2
}
```

#### 4단계: 조직도 조회
```http
# 본사 관리자와 직속 부하 직원 조회
GET /api/v1/users/1/subordinates

# 지사 및 소속 직원 조회
GET /api/v1/companies/2

# 지사장의 직속 부하 조회
GET /api/v1/users/2/subordinates
```

---

## 에러 처리

### 400 Bad Request
```json
{
  "detail": "유효하지 않은 요청 데이터"
}
```

### 404 Not Found
```json
{
  "detail": "회사를 찾을 수 없습니다."
}
```

### 409 Conflict
```json
{
  "detail": "이미 존재하는 이메일입니다."
}
```

### 500 Internal Server Error
```json
{
  "detail": "서버 내부 오류"
}
```

---

## 데이터베이스 테이블 관계도

```
companies (회사/지사)
├── company_id (PK)
├── company_group (HQ, BRANCH)
├── name
├── parent_company_id (FK) → companies.company_id

roles (직책)
├── role_id (PK)
├── role_name (UNIQUE)
├── description

users (사용자)
├── user_id (PK)
├── name
├── email (UNIQUE)
├── password_hash
├── company_id (FK) → companies.company_id
├── role_id (FK) → roles.role_id
├── reports_to_user_id (FK) → users.user_id
```

---

## 주의사항

1. **비밀번호**: 최소 8자 이상이어야 합니다.
2. **이메일**: 유일해야 하며 valid email 형식이어야 합니다.
3. **계층 구조**: `reports_to_user_id`는 NULL 또는 기존 사용자 ID여야 합니다.
4. **회사 타입**: 'HQ' 또는 'BRANCH'만 허용됩니다.
5. **삭제 연쇄**: 회사나 역할 삭제 시 관련된 사용자도 영향을 받을 수 있습니다.

---

## 예제 코드 (Python requests)

```python
import requests

BASE_URL = "https://babba-api.example.com/api/v1"

# 1. 역할 생성
response = requests.post(
    f"{BASE_URL}/roles",
    json={
        "role_name": "지사장",
        "description": "지사 운영 책임"
    }
)
print(response.json())

# 2. 회사 생성
response = requests.post(
    f"{BASE_URL}/companies",
    json={
        "company_group": "HQ",
        "name": "본사",
        "address": "서울시 강남구",
        "phone_number": "02-1234-5678"
    }
)
hq_id = response.json()["company_id"]

# 3. 사용자 생성
response = requests.post(
    f"{BASE_URL}/users",
    json={
        "name": "홍길동",
        "email": "hong@babba.com",
        "password": "securePassword123",
        "company_id": hq_id,
        "role_id": 1
    }
)
print(response.json())

# 4. 사용자 조회
response = requests.get(f"{BASE_URL}/users/1")
print(response.json())

# 5. 로그인
response = requests.post(
    f"{BASE_URL}/auth/login?email=hong@babba.com&password=securePassword123"
)
print(response.json())
```

---

**API 버전**: v1  
**최종 업데이트**: 2025년 11월 6일  
**담당자**: 개발팀
