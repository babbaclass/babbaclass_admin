# Cloud SQL 데이터베이스 테이블 목록

## 📊 생성된 테이블 조회 (최종 확인)

### 🎯 데이터베이스 위치

```
프로젝트:      astute-window-472313-g9
인스턴스:      babba-db (asia-northeast3)
데이터베이스:  babba
MySQL 버전:    8.0.41 (Enterprise Edition)
사용자:       babba_user
```

---

## 📋 테이블 목록 (총 6개)

### 1️⃣ **user** - 사용자 관리 테이블

```sql
테이블명: user
상태: ✅ 생성됨

컬럼 목록:
  🔑 id                INT          NOT NULL  PRIMARY KEY AUTO_INCREMENT
  • email              VARCHAR(255) NOT NULL  UNIQUE
  • username           VARCHAR(100) NOT NULL
  • is_active          BOOLEAN      DEFAULT TRUE
  • created_at         DATETIME     DEFAULT CURRENT_TIMESTAMP
  • updated_at         DATETIME     AUTO UPDATE CURRENT_TIMESTAMP

용도: 플랫폼 사용자 계정 관리
행 개수: 0 (비어있음)
```

---

### 2️⃣ **partner** - 파트너사 관리 테이블

```sql
테이블명: partner
상태: ✅ 생성됨

컬럼 목록:
  🔑 id                INT          NOT NULL  PRIMARY KEY AUTO_INCREMENT
  • name               VARCHAR(255) NOT NULL
  • description        TEXT         NULLABLE
  • is_active          BOOLEAN      DEFAULT TRUE
  • created_at         DATETIME     DEFAULT CURRENT_TIMESTAMP
  • updated_at         DATETIME     AUTO UPDATE CURRENT_TIMESTAMP

용도: 파트너 회사 정보 저장
행 개수: 0 (비어있음)
```

---

### 3️⃣ **category** - Makeshop 카테고리 테이블

```sql
테이블명: category
상태: ✅ 생성됨

컬럼 목록:
  🔑 id                        INT           NOT NULL  PRIMARY KEY AUTO_INCREMENT
  • makeshop_category_id      VARCHAR(50)   NULLABLE  UNIQUE
  • name                      VARCHAR(255)  NOT NULL
  • description               TEXT          NULLABLE
  • is_active                 BOOLEAN       DEFAULT TRUE
  • created_at                DATETIME      DEFAULT CURRENT_TIMESTAMP
  • updated_at                DATETIME      AUTO UPDATE CURRENT_TIMESTAMP

용도: Makeshop의 상품 카테고리 동기화
데이터 출처: POST /sync/makeshop/categories
행 개수: 0 (동기화 대기중)
```

---

### 4️⃣ **product** - Makeshop 상품 테이블

```sql
테이블명: product
상태: ✅ 생성됨

컬럼 목록:
  🔑 id                        INT           NOT NULL  PRIMARY KEY AUTO_INCREMENT
  • makeshop_product_id       VARCHAR(50)   NULLABLE  UNIQUE
  • name                      VARCHAR(255)  NOT NULL
  • price                     DECIMAL(10,2) NULLABLE
  • cost                      DECIMAL(10,2) NULLABLE
  • stock                     INT           DEFAULT 0
  • description               TEXT          NULLABLE
  • category_name             VARCHAR(255)  NULLABLE
  • image_url                 VARCHAR(500)  NULLABLE
  • status                    VARCHAR(50)   DEFAULT 'active'
  • synced_at                 DATETIME      NULLABLE
  • created_at                DATETIME      DEFAULT CURRENT_TIMESTAMP
  • updated_at                DATETIME      AUTO UPDATE CURRENT_TIMESTAMP

용도: Makeshop의 상품 정보 동기화
데이터 출처: POST /sync/makeshop/products
행 개수: 0 (동기화 대기중)

인덱스:
  • makeshop_product_id (UNIQUE)
```

---

### 5️⃣ **order** - Makeshop 주문 테이블

```sql
테이블명: order
상태: ✅ 생성됨

컬럼 목록:
  🔑 id                        INT           NOT NULL  PRIMARY KEY AUTO_INCREMENT
  • makeshop_order_id         VARCHAR(50)   NULLABLE  UNIQUE
  • customer_name             VARCHAR(255)  NULLABLE
  • customer_email            VARCHAR(255)  NULLABLE
  • customer_phone            VARCHAR(20)   NULLABLE
  • total_price               DECIMAL(10,2) DEFAULT 0
  • payment_status            VARCHAR(50)   DEFAULT 'pending'
  • order_status              VARCHAR(50)   DEFAULT 'pending'
  • items_count               INT           DEFAULT 0
  • shipping_address          TEXT          NULLABLE
  • notes                     TEXT          NULLABLE
  • created_at                DATETIME      DEFAULT CURRENT_TIMESTAMP
  • updated_at                DATETIME      AUTO UPDATE CURRENT_TIMESTAMP

용도: Makeshop의 주문 정보 동기화
데이터 출처: POST /sync/makeshop/orders
행 개수: 0 (동기화 대기중)

인덱스:
  • makeshop_order_id (UNIQUE)
```

---

### 6️⃣ **orderitem** - Makeshop 주문 항목 테이블

```sql
테이블명: orderitem
상태: ✅ 생성됨

컬럼 목록:
  🔑 id                INT           NOT NULL  PRIMARY KEY AUTO_INCREMENT
  • order_id          INT           NOT NULL  FOREIGN KEY → order(id)
  • product_id        INT           NULLABLE
  • quantity          INT           DEFAULT 1
  • price             DECIMAL(10,2) NULLABLE
  • created_at        DATETIME      DEFAULT CURRENT_TIMESTAMP
  • updated_at        DATETIME      AUTO UPDATE CURRENT_TIMESTAMP

용도: 각 주문에 포함된 상품 항목 저장
데이터 출처: POST /sync/makeshop/orders
행 개수: 0 (동기화 대기중)

관계:
  • 1:N 관계 (order_id 기준)
  • ON DELETE CASCADE (주문 삭제시 항목도 함께 삭제)
```

---

## 📊 테이블 데이터 현황

```
┌─────────────┬───────────┬──────────────┐
│ 테이블 명   │ 컬럼 수   │ 행 개수      │
├─────────────┼───────────┼──────────────┤
│ user        │ 6         │ 0 ⚪         │
│ partner     │ 6         │ 0 ⚪         │
│ category    │ 7         │ 0 ⚪         │
│ product     │ 13        │ 0 ⚪         │
│ order       │ 12        │ 0 ⚪         │
│ orderitem   │ 7         │ 0 ⚪         │
├─────────────┼───────────┼──────────────┤
│ 합계        │ 51        │ 0 ⚪         │
└─────────────┴───────────┴──────────────┘
```

---

## 🔄 테이블 생성 프로세스

### 자동 생성 방식

```
1. Cloud Run에 babba-api 배포
                ↓
2. FastAPI 애플리케이션 시작 (app/main.py)
                ↓
3. 다음 코드 자동 실행:
   Base.metadata.create_all(bind=engine)
                ↓
4. SQLAlchemy가 app/models.py의 모든 모델 검사
                ↓
5. 각 모델에 해당하는 테이블 생성
   ✅ User → user 테이블
   ✅ Partner → partner 테이블
   ✅ Category → category 테이블
   ✅ Product → product 테이블
   ✅ Order → order 테이블
   ✅ OrderItem → orderitem 테이블
                ↓
6. FastAdmin 설정 (app/admin.py)
   - 모든 모델 등록
                ↓
7. 준비 완료!
```

---

## ✅ 테이블 생성 확인 방법

### **방법 1️⃣: API 엔드포인트 호출**

```bash
# ✅ 곧 추가될 예정:
curl https://babba-api-kitlcurzpa-du.a.run.app/database/tables

# 응답 예시:
{
  "status": "success",
  "total": 6,
  "tables": [
    {
      "name": "user",
      "column_count": 6,
      "row_count": 0,
      "columns": [...]
    },
    ...
  ]
}
```

### **방법 2️⃣: FastAdmin 웹 UI**

```
https://babba-api-kitlcurzpa-du.a.run.app/admin

시각적으로 모든 테이블 확인 가능:
✅ Users 탭
✅ Partners 탭
✅ Categories 탭
✅ Products 탭
✅ Orders 탭
✅ OrderItems 탭
```

### **방법 3️⃣: 헬스 체크 (DB 연결 확인)**

```bash
curl https://babba-api-kitlcurzpa-du.a.run.app/health

# 응답:
{
  "status": "healthy",
  "database": "connected"
}
```

---

## 🎯 다음 단계: 데이터 추가

### **Step 1: 사용자 추가 (user 테이블)**

```bash
curl -X POST https://babba-api-kitlcurzpa-du.a.run.app/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "john_doe"
  }'

# user 테이블에 새 행 추가
```

### **Step 2: Makeshop 동기화**

```bash
# 카테고리 동기화
curl -X POST https://babba-api-kitlcurzpa-du.a.run.app/sync/makeshop/categories
# → category 테이블에 데이터 추가

# 상품 동기화
curl -X POST https://babba-api-kitlcurzpa-du.a.run.app/sync/makeshop/products
# → product 테이블에 데이터 추가

# 주문 동기화
curl -X POST https://babba-api-kitlcurzpa-du.a.run.app/sync/makeshop/orders
# → order, orderitem 테이블에 데이터 추가
```

### **Step 3: FastAdmin에서 확인**

```
https://babba-api-kitlcurzpa-du.a.run.app/admin

→ 각 탭에서 새로 추가된 데이터 확인
```

---

## 📊 테이블 관계도 (ER Diagram)

```
┌──────────────┐
│    user      │
├──────────────┤
│ 🔑 id        │
│   email      │
│   username   │
│   is_active  │
└──────────────┘

┌──────────────┐
│   partner    │
├──────────────┤
│ 🔑 id        │
│   name       │
│   description│
│   is_active  │
└──────────────┘

┌──────────────────┐
│    category      │ (Makeshop)
├──────────────────┤
│ 🔑 id            │
│   makeshop_id    │
│   name           │
│   description    │
└──────────────────┘
         △
         │
         │ 1:N
         │
         │
┌──────────────────┐
│    product       │ (Makeshop)
├──────────────────┤
│ 🔑 id            │
│   makeshop_id    │
│   name           │
│   price          │
│   stock          │
│   category_name  │
└──────────────────┘

┌──────────────────┐
│     order        │ (Makeshop)
├──────────────────┤
│ 🔑 id            │
│   makeshop_id    │
│   customer_name  │
│   total_price    │
│   order_status   │
└──────────────────┘
         △
         │
         │ 1:N
         │
         │
┌──────────────────┐
│   orderitem      │ (Makeshop)
├──────────────────┤
│ 🔑 id            │
│  🔗 order_id     │
│    product_id    │
│    quantity      │
│    price         │
└──────────────────┘
```

---

## 🔍 상세 테이블 정보 조회

### 로컬 스크립트로 확인

```bash
# 테이블 상태 확인 스크립트 실행
python3 create_tables.py

# 또는
python3 check_tables.py
```

### SQL 쿼리로 확인 (Cloud SQL 콘솔)

```sql
-- 모든 테이블 목록
SHOW TABLES;

-- 특정 테이블 스키마 확인
DESC user;
DESC product;
DESC order;
```

---

## 💾 백업 및 관리

### 자동 백업

```
GCP Cloud SQL 자동 백업 정책:
✅ 일일 자동 백업 (7일 보관)
✅ 트랜잭션 로그 (필요시 Point-in-time 복구)
```

### 수동 백업

```bash
# 스냅샷 생성
gcloud sql backups create \
  --instance=babba-db \
  --project=astute-window-472313-g9
```

---

## 🎯 체크리스트

### 테이블 확인

- [x] user 테이블 생성됨
- [x] partner 테이블 생성됨
- [x] category 테이블 생성됨
- [x] product 테이블 생성됨
- [x] order 테이블 생성됨
- [x] orderitem 테이블 생성됨

### 데이터 입력

- [ ] user 테이블에 데이터 추가
- [ ] Makeshop 카테고리 동기화
- [ ] Makeshop 상품 동기화
- [ ] Makeshop 주문 동기화

### 검증

- [ ] FastAdmin에서 모든 테이블 확인
- [ ] API 엔드포인트로 데이터 조회 테스트
- [ ] 월간 모니터링

---

## 📝 요약

```
✅ 테이블 생성 상태: 완료
✅ 총 테이블 수: 6개
✅ 총 컬럼 수: 51개
✅ 현재 데이터: 0 행 (초기 상태)

위치:
  프로젝트: astute-window-472313-g9
  인스턴스: babba-db (asia-northeast3)
  데이터베이스: babba

접근 방법:
  • FastAdmin: https://babba-api-kitlcurzpa-du.a.run.app/admin
  • API: https://babba-api-kitlcurzpa-du.a.run.app/users
  • 헬스체크: https://babba-api-kitlcurzpa-du.a.run.app/health
```

---

**모든 Cloud SQL 테이블이 준비되었습니다!** ✨
