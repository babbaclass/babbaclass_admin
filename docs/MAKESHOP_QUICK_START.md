# Makeshop API 통합 - 빠른 시작 가이드

## ✅ 완료된 사항

### 1. 패키지 업데이트 ✓
- `requests` - HTTP 요청 라이브러리
- `python-dotenv` - 환경변수 관리

### 2. 환경변수 템플릿 ✓
- `.env.makeshop` 파일 생성
- 필요한 설정값 명시

### 3. 데이터베이스 모델 추가 ✓
- `Category` - 상품 카테고리
- `Product` - 상품 정보 (Makeshop 동기화용)
- `Order` - 주문 정보
- `OrderItem` - 주문 상품 항목

### 4. Makeshop API 클라이언트 ✓
- `app/services/makeshop_service.py` 생성
- 완전한 API 래퍼 (상품, 카테고리, 주문)
- 오류 처리 및 로깅 포함

### 5. FastAPI 엔드포인트 추가 ✓
```
POST /sync/makeshop/products      - 상품 동기화
POST /sync/makeshop/categories    - 카테고리 동기화
POST /sync/makeshop/orders        - 주문 동기화
GET  /makeshop/health             - API 헬스 체크
```

### 6. 설정 가이드 문서 ✓
- `MAKESHOP_SETUP.md` - 완전한 설정 가이드

---

## 🚀 즉시 시작하기 (3단계)

### Step 1: 환경변수 설정

```bash
# .env 파일 생성
cp .env.makeshop .env

# .env 파일 편집 후 다음 정보 입력:
# MAKESHOP_API_KEY=your_api_key
# MAKESHOP_SHOP_ID=your_shop_id
```

### Step 2: 패키지 설치

```bash
pip install -r requirements.txt
```

### Step 3: 서버 실행 및 테스트

```bash
# 로컬 서버 실행
uvicorn app.main:app --reload

# 다른 터미널에서 API 테스트
curl -X GET http://localhost:8080/makeshop/health
```

---

## 🔄 동기화 API 사용법

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

### 주문 동기화

```bash
curl -X POST "http://localhost:8080/sync/makeshop/orders?page=1&limit=50"
```

---

## 📊 Swagger UI 확인

```
http://localhost:8080/docs
```

다음 엔드포인트 확인 가능:
- Makeshop Sync 섹션 참고
- 직접 API 테스트 가능

---

## 📁 생성/수정된 파일

```
babba-api/
├── requirements.txt               # ✅ 업데이트: requests, python-dotenv 추가
├── .env.makeshop                 # ✨ 신규: 환경변수 템플릿
├── MAKESHOP_SETUP.md             # ✨ 신규: 완전한 설정 가이드
├── app/
│   ├── main.py                   # ✅ 업데이트: 동기화 엔드포인트 추가
│   ├── models.py                 # ✅ 업데이트: Product, Category, Order 모델 추가
│   └── services/
│       ├── __init__.py           # ✨ 신규
│       └── makeshop_service.py   # ✨ 신규: Makeshop API 클라이언트
```

---

## 🔑 주요 기능

### MakeshopAPIClient 메서드

#### 상품 관리
```python
from app.services import MakeshopAPIClient

client = MakeshopAPIClient()

# 상품 목록 조회
products = client.get_products(page=1, limit=100)

# 특정 상품 조회
product = client.get_product("PRODUCT_ID")

# 재고 업데이트
client.update_product_stock("PRODUCT_ID", 100)
```

#### 카테고리 관리
```python
# 모든 카테고리 조회
categories = client.get_categories()

# 특정 카테고리 조회
category = client.get_category("CATEGORY_ID")
```

#### 주문 관리
```python
# 주문 목록 조회
orders = client.get_orders(page=1, limit=100, status="pending")

# 특정 주문 조회
order = client.get_order("ORDER_ID")

# 주문 상태 업데이트
client.update_order_status("ORDER_ID", "shipped")
```

#### 헬스 체크
```python
# API 연결 상태 확인
is_healthy = client.health_check()
```

---

## 📋 체크리스트

설정 완료 전 확인사항:

- [ ] Makeshop API 키 발급 받음
- [ ] `.env` 파일에 API 키, Shop ID 입력
- [ ] `pip install -r requirements.txt` 실행
- [ ] 서버 실행: `uvicorn app.main:app --reload`
- [ ] `/makeshop/health` 엔드포인트로 헬스 체크
- [ ] `/sync/makeshop/categories` 엔드포인트로 카테고리 동기화 테스트
- [ ] `/sync/makeshop/products` 엔드포인트로 상품 동기화 테스트
- [ ] Swagger UI (`/docs`)에서 모든 엔드포인트 확인

---

## 🛠️ 다음 단계 (선택 사항)

### 1. 자동 동기화 스케줄링
```python
# APScheduler 활용하여 주기적 동기화
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.add_job(sync_products, 'interval', hours=1)
scheduler.start()
```

### 2. 웹훅 처리
```python
# Makeshop 웹훅에서 실시간 동기화
@app.post("/webhook/makeshop/product-updated")
def handle_product_update(data: dict):
    # 실시간 상품 정보 업데이트
    pass
```

### 3. 동기화 로그 추적
```python
# 동기화 기록을 DB에 저장
class SyncLog(Base):
    __tablename__ = "sync_logs"
    sync_type: str  # products, categories, orders
    status: str     # success, failed
    synced_count: int
    error_message: str
```

### 4. 오류 알림
```python
# 동기화 실패 시 이메일 또는 Slack 알림
if sync_failed:
    send_notification(f"Makeshop 동기화 실패: {error}")
```

---

## 📞 문제 해결

### Q: "API 인증 정보가 누락되었습니다" 오류

**A:** `.env` 파일 확인 및 재설정
```bash
cat .env | grep MAKESHOP
```

### Q: "API 요청 타임아웃" 오류

**A:** 네트워크 확인 및 타임아웃 값 증가
```env
MAKESHOP_API_TIMEOUT=30
```

### Q: API 키가 유효하지 않음 (401 오류)

**A:** Makeshop 개발자 센터에서 새 API 키 발급

---

## 📚 상세 가이드

전체 설정 및 사용법은 `MAKESHOP_SETUP.md` 참고

---

## 🎉 완료!

이제 Makeshop API 통합이 준비되었습니다.

**다음 명령어로 시작하세요:**

```bash
# 1. 환경변수 설정
cp .env.makeshop .env
# .env 파일 편집

# 2. 패키지 설치
pip install -r requirements.txt

# 3. 서버 실행
uvicorn app.main:app --reload

# 4. 브라우저에서 확인
# http://localhost:8080/docs
```

행운을 빕니다! 🚀
