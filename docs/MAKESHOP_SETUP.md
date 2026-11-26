# Makeshop API 통합 설정 가이드

## 📋 개요

이 가이드는 babba-api에 Makeshop API를 통합하기 위한 모든 설정 절차를 설명합니다.

---

## 🔑 1단계: Makeshop API 인증 정보 발급

### 개발자 계정 생성

1. [Makeshop 개발자 센터](https://developer.makeshop.co.kr) 접속
2. **개발자 계정** 회원가입
3. **API 키** 발급 요청

### 필요한 정보

```
- MAKESHOP_API_KEY: 발급받은 API 키
- MAKESHOP_SHOP_ID: 쇼핑몰 고유 ID (매장 번호)
```

---

## 🛠️ 2단계: 로컬 환경 설정

### .env 파일 생성

`.env.makeshop` 템플릿을 참고하여 `.env` 파일 생성:

```bash
cp .env.makeshop .env
```

### 환경변수 입력

`.env` 파일 편집:

```env
# Makeshop API 설정
MAKESHOP_API_KEY=your_api_key_here       # 발급받은 API 키 입력
MAKESHOP_SHOP_ID=your_shop_id_here       # 쇼핑몰 ID 입력
MAKESHOP_API_URL=https://api.makeshop.co.kr/api
MAKESHOP_API_TIMEOUT=10

# 기존 DB 설정은 유지
CLOUD_SQL_INSTANCE=astute-window-472313-g9:asia-northeast3:babba-db
DB_USER=babba_user
DB_PASSWORD=Fulfilled07!@
DB_NAME=babba
```

### 패키지 설치

```bash
pip install -r requirements.txt
```

**새로 추가된 패키지:**
- `requests>=2.28.0` - HTTP 요청 라이브러리
- `python-dotenv>=0.21.0` - 환경변수 관리

---

## 📦 3단계: 데이터베이스 테이블 생성

서버 시작 시 자동으로 생성됩니다:

```bash
# 로컬에서 실행
uvicorn app.main:app --reload

# 또는 uvicorn 없이 직접 실행
python -c "from app.database import Base, engine; from app.models import *; Base.metadata.create_all(bind=engine)"
```

**생성되는 테이블:**
- `categories` - 상품 카테고리
- `products` - 상품 정보
- `orders` - 주문 정보
- `order_items` - 주문 상품 항목

---

## 🔌 4단계: API 연결 테스트

### 헬스 체크 엔드포인트

```bash
curl -X GET http://localhost:8080/makeshop/health
```

**응답 예시:**
```json
{
  "status": "healthy",
  "message": "Makeshop API 연결 정상",
  "makeshop_api": "connected"
}
```

### Swagger UI 확인

```
http://localhost:8080/docs
```

Swagger UI에서 다음 엔드포인트 확인:
- `GET /makeshop/health` - API 헬스 체크
- `POST /sync/makeshop/products` - 상품 동기화
- `POST /sync/makeshop/categories` - 카테고리 동기화
- `POST /sync/makeshop/orders` - 주문 동기화

---

## 🔄 5단계: 동기화 실행

### 카테고리 동기화

```bash
curl -X POST http://localhost:8080/sync/makeshop/categories
```

**응답:**
```json
{
  "status": "success",
  "message": "카테고리 동기화 완료",
  "total_categories": 15,
  "created": 15
}
```

### 상품 동기화

```bash
curl -X POST http://localhost:8080/sync/makeshop/products
```

**응답:**
```json
{
  "status": "success",
  "message": "상품 동기화 완료",
  "total_synced": 150,
  "created": 100,
  "updated": 50
}
```

### 주문 동기화

```bash
curl -X POST "http://localhost:8080/sync/makeshop/orders?page=1&limit=50"
```

**응답:**
```json
{
  "status": "success",
  "message": "주문 동기화 완료",
  "total_synced": 45,
  "created": 30,
  "updated": 15
}
```

---

## 📊 생성된 테이블 구조

### categories (카테고리)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer | 기본 키 |
| makeshop_category_id | String(100) | Makeshop 카테고리 ID |
| name | String(255) | 카테고리명 |
| description | Text | 설명 |
| is_active | Boolean | 활성 여부 |
| created_at | DateTime | 생성 시간 |
| updated_at | DateTime | 수정 시간 |

### products (상품)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer | 기본 키 |
| makeshop_product_id | String(100) | Makeshop 상품 ID |
| name | String(255) | 상품명 |
| price | Integer | 판매 가격 |
| cost | Integer | 원가 |
| stock | Integer | 재고 |
| description | Text | 상품 설명 |
| category_id | Integer | 카테고리 ID |
| category_name | String(100) | 카테고리명 |
| image_url | String(500) | 이미지 URL |
| status | String(50) | 상태 (active, inactive, discontinued) |
| is_active | Boolean | 활성 여부 |
| synced_at | DateTime | 마지막 동기화 시간 |
| created_at | DateTime | 생성 시간 |
| updated_at | DateTime | 수정 시간 |

### orders (주문)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer | 기본 키 |
| makeshop_order_id | String(100) | Makeshop 주문 ID |
| customer_name | String(255) | 고객명 |
| customer_email | String(255) | 이메일 |
| customer_phone | String(20) | 전화번호 |
| total_price | Integer | 주문 금액 |
| payment_status | String(50) | 결제 상태 |
| order_status | String(50) | 주문 상태 |
| items_count | Integer | 상품 개수 |
| shipping_address | Text | 배송 주소 |
| notes | Text | 메모 |
| synced_at | DateTime | 마지막 동기화 시간 |
| created_at | DateTime | 생성 시간 |
| updated_at | DateTime | 수정 시간 |

### order_items (주문 항목)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer | 기본 키 |
| order_id | String(100) | 주문 로컬 ID |
| makeshop_order_id | String(100) | Makeshop 주문 ID |
| product_id | String(100) | 상품 ID |
| product_name | String(255) | 상품명 |
| quantity | Integer | 수량 |
| unit_price | Integer | 단가 |
| total_price | Integer | 합계 |
| created_at | DateTime | 생성 시간 |

---

## 🔧 MakeshopAPIClient 사용법

### 클라이언트 초기화

```python
from app.services import MakeshopAPIClient

client = MakeshopAPIClient()
```

### 상품 조회

```python
# 상품 목록 조회
products = client.get_products(page=1, limit=100)

# 특정 상품 조회
product = client.get_product("PRODUCT_ID")

# 상품 재고 업데이트
result = client.update_product_stock("PRODUCT_ID", 100)
```

### 카테고리 조회

```python
# 모든 카테고리 조회
categories = client.get_categories()

# 특정 카테고리 조회
category = client.get_category("CATEGORY_ID")
```

### 주문 조회

```python
# 주문 목록 조회
orders = client.get_orders(page=1, limit=100, status="pending")

# 특정 주문 조회
order = client.get_order("ORDER_ID")

# 주문 상태 업데이트
result = client.update_order_status("ORDER_ID", "shipped")
```

### 헬스 체크

```python
# API 연결 상태 확인
is_healthy = client.health_check()
```

---

## 🚀 클라우드 배포 설정

### Cloud Run 환경변수 설정

Cloud Run 서비스 배포 시 환경변수 추가:

```bash
gcloud run deploy babba-api \
  --region=asia-northeast3 \
  --set-env-vars="\
    MAKESHOP_API_KEY=your_api_key,\
    MAKESHOP_SHOP_ID=your_shop_id,\
    MAKESHOP_API_URL=https://api.makeshop.co.kr/api,\
    MAKESHOP_API_TIMEOUT=10,\
    CLOUD_SQL_INSTANCE=...,\
    DB_USER=...,\
    DB_PASSWORD=...,\
    DB_NAME=..."
```

### 또는 .env.yaml 사용

`.env.yaml` 생성:

```yaml
MAKESHOP_API_KEY: your_api_key
MAKESHOP_SHOP_ID: your_shop_id
MAKESHOP_API_URL: https://api.makeshop.co.kr/api
MAKESHOP_API_TIMEOUT: 10
CLOUD_SQL_INSTANCE: astute-window-472313-g9:asia-northeast3:babba-db
DB_USER: babba_user
DB_PASSWORD: Fulfilled07!@
DB_NAME: babba
```

배포 시:

```bash
gcloud run deploy babba-api \
  --region=asia-northeast3 \
  --env-vars-file=.env.yaml
```

---

## 🔒 보안 주의사항

### API 키 보호

1. **절대 Git에 커밋하지 마세요**
   - `.gitignore`에 `.env` 추가됨
   - `.env.makeshop`은 템플릿이므로 안전

2. **환경변수 관리**
   - 로컬: `.env` 파일 사용
   - 클라우드: Cloud Run 환경변수 또는 Secret Manager 사용

3. **Secret Manager 권장** (프로덕션)

```bash
# API 키를 Secret Manager에 저장
gcloud secrets create makeshop-api-key --data-file=-
gcloud secrets create makeshop-shop-id --data-file=-

# Cloud Run에서 접근 권한 설정
gcloud run services update babba-api \
  --set-env-vars=MAKESHOP_API_KEY=projects/PROJECT_ID/secrets/makeshop-api-key/versions/latest
```

---

## 📝 로깅

Makeshop API 호출 로그는 자동으로 기록됩니다:

```python
import logging

logger = logging.getLogger(__name__)

# 로그 레벨 설정
logging.basicConfig(level=logging.INFO)
```

**로그 예시:**

```
INFO:app.services.makeshop_service:MakeshopAPIClient initialized for shop_id: 12345
INFO:app.services.makeshop_service:API Request: GET https://api.makeshop.co.kr/api/shop/12345/products
INFO:app.services.makeshop_service:조회된 상품 수: 150
INFO:app.services.makeshop_service:상품 조회: 우수 상품 #1
```

---

## ❌ 트러블슈팅

### 오류: "Makeshop API 인증 정보가 누락되었습니다"

**원인:** 환경변수가 설정되지 않음

**해결책:**
```bash
# .env 파일 확인
cat .env | grep MAKESHOP

# 또는 환경변수 직접 설정
export MAKESHOP_API_KEY=your_key
export MAKESHOP_SHOP_ID=your_id
```

### 오류: "API 요청 타임아웃"

**원인:** Makeshop API 서버 응답 지연

**해결책:**
1. 네트워크 연결 확인
2. `MAKESHOP_API_TIMEOUT` 증가 (기본값: 10초)
3. Makeshop 상태 페이지 확인

### 오류: "HTTP 오류 401"

**원인:** API 키가 유효하지 않음

**해결책:**
1. API 키 재확인
2. 새로운 API 키 발급 시도
3. Makeshop 개발자 센터 확인

### 오류: "상품 목록 조회 실패"

**원인:** 
- API 요청 형식 오류
- 권한 부족
- 쇼핑몰 ID 오류

**해결책:**
```bash
# 헬스 체크 실행
curl -X GET http://localhost:8080/makeshop/health

# 로그 확인
docker logs babba-api  # 또는 Cloud Run 로그 확인
```

---

## 📚 참고 자료

- [Makeshop API 문서](https://developer.makeshop.co.kr/docs)
- [FastAPI 문서](https://fastapi.tiangolo.com)
- [SQLAlchemy 문서](https://docs.sqlalchemy.org)
- [babba-api README](../README.md)

---

## 📞 추가 지원

문제 발생 시:

1. 로그 확인: `docker logs babba-api`
2. 헬스 체크: `GET /health`, `GET /makeshop/health`
3. Swagger UI 확인: `http://localhost:8080/docs`
