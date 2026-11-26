# Cloud SQL 테이블 생성 완료 - 상태 확인

## ✅ 테이블 생성 상태

### 📍 테이블 생성 위치

```
GCP Project: astute-window-472313-g9
Cloud SQL 인스턴스: babba-db
지역: asia-northeast3
데이터베이스: babba
서버: MySQL 8.0.41 (Enterprise)
```

---

## 📊 생성된 테이블 목록 (6개)

### 1️⃣ **user** - 사용자 관리

```sql
CREATE TABLE user (
  id INT PRIMARY KEY AUTO_INCREMENT,
  email VARCHAR(255) UNIQUE NOT NULL,
  username VARCHAR(100) NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**용도**: 플랫폼 사용자 관리
**컬럼**: id, email, username, is_active, created_at, updated_at

---

### 2️⃣ **partner** - 파트너사 관리

```sql
CREATE TABLE partner (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**용도**: 파트너사 정보 관리
**컬럼**: id, name, description, is_active, created_at, updated_at

---

### 3️⃣ **category** - 카테고리 (Makeshop)

```sql
CREATE TABLE category (
  id INT PRIMARY KEY AUTO_INCREMENT,
  makeshop_category_id VARCHAR(50) UNIQUE,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  is_active BOOLEAN DEFAULT TRUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**용도**: Makeshop 카테고리 동기화
**컬럼**: id, makeshop_category_id, name, description, is_active, created_at, updated_at

**데이터 출처**: POST /sync/makeshop/categories 엔드포인트

---

### 4️⃣ **product** - 상품 (Makeshop)

```sql
CREATE TABLE product (
  id INT PRIMARY KEY AUTO_INCREMENT,
  makeshop_product_id VARCHAR(50) UNIQUE,
  name VARCHAR(255) NOT NULL,
  price DECIMAL(10, 2),
  cost DECIMAL(10, 2),
  stock INT DEFAULT 0,
  description TEXT,
  category_name VARCHAR(255),
  image_url VARCHAR(500),
  status VARCHAR(50) DEFAULT 'active',
  synced_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**용도**: Makeshop 상품 동기화
**컬럼**: id, makeshop_product_id, name, price, cost, stock, description, category_name, image_url, status, synced_at, created_at, updated_at

**데이터 출처**: POST /sync/makeshop/products 엔드포인트

---

### 5️⃣ **order** - 주문 (Makeshop)

```sql
CREATE TABLE order (
  id INT PRIMARY KEY AUTO_INCREMENT,
  makeshop_order_id VARCHAR(50) UNIQUE,
  customer_name VARCHAR(255),
  customer_email VARCHAR(255),
  customer_phone VARCHAR(20),
  total_price DECIMAL(10, 2) DEFAULT 0,
  payment_status VARCHAR(50) DEFAULT 'pending',
  order_status VARCHAR(50) DEFAULT 'pending',
  items_count INT DEFAULT 0,
  shipping_address TEXT,
  notes TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

**용도**: Makeshop 주문 동기화
**컬럼**: id, makeshop_order_id, customer_name, customer_email, customer_phone, total_price, payment_status, order_status, items_count, shipping_address, notes, created_at, updated_at

**데이터 출처**: POST /sync/makeshop/orders 엔드포인트

---

### 6️⃣ **orderitem** - 주문 품목 (Makeshop)

```sql
CREATE TABLE orderitem (
  id INT PRIMARY KEY AUTO_INCREMENT,
  order_id INT NOT NULL,
  product_id INT,
  quantity INT DEFAULT 1,
  price DECIMAL(10, 2),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES order(id) ON DELETE CASCADE
);
```

**용도**: Makeshop 주문 품목 관리
**컬럼**: id, order_id, product_id, quantity, price, created_at, updated_at
**관계**: order 테이블과 1:N 관계

---

## 🔄 테이블 생성 프로세스

### **자동 생성 시점**

```
1. Cloud Run에 babba-api 배포
   ↓
2. FastAPI 애플리케이션 시작
   ↓
3. app/main.py 실행
   ├─ Base.metadata.create_all(bind=engine)
   │  └─ 모든 테이블 자동 생성
   ├─ FastAdmin 설정 (setup_admin)
   └─ 애플리케이션 준비 완료
   ↓
4. /health 엔드포인트 호출 가능
```

### **테이블 생성 확인 방법**

#### **방법 1️⃣: /health 엔드포인트 호출**

```bash
curl https://babba-api-kitlcurzpa-du.a.run.app/health
```

**응답 (테이블 생성됨)**:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

#### **방법 2️⃣: API 엔드포인트 호출**

```bash
# 사용자 목록 조회 (user 테이블 확인)
curl https://babba-api-kitlcurzpa-du.a.run.app/users

# 파트너사 목록 조회 (partner 테이블 확인)
curl https://babba-api-kitlcurzpa-du.a.run.app/partners
```

#### **방법 3️⃣: FastAdmin 접속**

```
https://babba-api-kitlcurzpa-du.a.run.app/admin
```

→ 모든 테이블이 시각적으로 표시됨

---

## 📈 현재 데이터 상태

### **초기 상태 (배포 후)**

```
user:        0 행 (비어있음)
partner:     0 행 (비어있음)
category:    0 행 (Makeshop 동기화 대기)
product:     0 행 (Makeshop 동기화 대기)
order:       0 행 (Makeshop 동기화 대기)
orderitem:   0 행 (주문 항목 추가 대기)
```

### **Makeshop 동기화 후**

```bash
# Step 1: 카테고리 동기화
POST /sync/makeshop/categories
→ category 테이블에 데이터 추가

# Step 2: 상품 동기화
POST /sync/makeshop/products
→ product 테이블에 데이터 추가

# Step 3: 주문 동기화
POST /sync/makeshop/orders
→ order 테이블에 데이터 추가
→ orderitem 테이블에 품목 추가
```

---

## 🔍 테이블 구조 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│                   babba 데이터베이스                    │
└─────────────────────────────────────────────────────────┘
         │
         ├─ user (사용자)
         │   └─ id, email, username, ...
         │
         ├─ partner (파트너사)
         │   └─ id, name, description, ...
         │
         ├─ category (카테고리 - Makeshop)
         │   └─ id, makeshop_category_id, name, ...
         │
         ├─ product (상품 - Makeshop)
         │   └─ id, makeshop_product_id, name, price, stock, ...
         │
         ├─ order (주문 - Makeshop)
         │   └─ id, makeshop_order_id, customer_name, total_price, ...
         │       └─ OrderItem N:1 관계
         │
         └─ orderitem (주문 품목 - Makeshop)
             └─ id, order_id, product_id, quantity, price, ...
                 └─ Order 1:N 관계
```

---

## 🛠️ 테이블 관리

### **데이터 확인 (FastAdmin)**

```
1. https://babba-api-kitlcurzpa-du.a.run.app/admin 접속
2. 각 탭 클릭하여 테이블 데이터 확인
3. 필요시 데이터 추가/수정/삭제
```

### **데이터 추가 (API)**

```bash
# 새 사용자 추가
curl -X POST https://babba-api-kitlcurzpa-du.a.run.app/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "john_doe"
  }'

# Makeshop 카테고리 동기화
curl -X POST https://babba-api-kitlcurzpa-du.a.run.app/sync/makeshop/categories

# Makeshop 상품 동기화
curl -X POST https://babba-api-kitlcurzpa-du.a.run.app/sync/makeshop/products

# Makeshop 주문 동기화
curl -X POST https://babba-api-kitlcurzpa-du.a.run.app/sync/makeshop/orders
```

---

## 🧪 테이블 검증 스크립트

### **로컬에서 테이블 구조 확인**

```bash
# 스크립트 실행 (요구: Cloud SQL Proxy 실행 또는 Cloud Run API 호출)
python3 create_tables.py
```

**출력 예시**:
```
🔍 Cloud SQL 데이터베이스 테이블 상태 확인 및 생성

1️⃣ 데이터베이스 연결 테스트...
   ✅ Cloud SQL 연결 성공

2️⃣ 기존 테이블 확인...
   ✅ 6개의 테이블이 있습니다:
      • user
      • partner
      • category
      • product
      • order
      • orderitem

📊 최종 테이블 목록 (6개)
...
```

---

## ⚠️ 주의사항

### **테이블 삭제 방지**

```
주의: 프로덕션 환경에서 테이블을 삭제하면 안 됨!
→ Cloud SQL 백업 사용: gcloud sql backups
```

### **테이블 수정 (Migration)**

```
향후 스키마 변경 시:
1. Alembic 마이그레이션 도구 사용
2. app/models.py에서 모델 정의 수정
3. 마이그레이션 스크립트 생성 및 실행
```

---

## 📋 체크리스트

### **테이블 생성 및 검증**

- [x] Cloud SQL 인스턴스 생성 (babba-db)
- [x] babba 데이터베이스 생성
- [x] babba_user 계정 생성
- [x] SQLAlchemy ORM 모델 정의
- [x] FastAPI 애플리케이션에서 Base.metadata.create_all() 자동 실행
- [x] 모든 테이블 자동 생성
- [x] FastAdmin에 모든 모델 등록
- [x] /health 엔드포인트 테스트 성공

### **다음 단계**

- [ ] Makeshop 동기화 실행
- [ ] 실시간 데이터 확인 (FastAdmin)
- [ ] 프로덕션 모니터링 설정
- [ ] 백업 자동화 (Cloud SQL)

---

## 🎯 요약

```
✅ 상태: 모든 테이블 생성 완료
✅ 위치: Cloud SQL (babba-db, asia-northeast3)
✅ 테이블 수: 6개
✅ 접근 방법: 
   - API: https://babba-api-kitlcurzpa-du.a.run.app/
   - FastAdmin: https://babba-api-kitlcurzpa-du.a.run.app/admin
   - 건강도: https://babba-api-kitlcurzpa-du.a.run.app/health
```

---

**모든 테이블이 준비되었습니다! 이제 Makeshop 데이터를 동기화할 수 있습니다.** 🚀
