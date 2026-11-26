# Copilot Instructions — babba-api

## Project Overview
FastAPI 기반 B2B 교육 플랫폼 관리 시스템. Makeshop(쇼핑몰) 주문 데이터를 동기화하고, 지사별 수수료를 정산하며, SQLAdmin 기반 관리자 패널을 제공합니다. Google Cloud Run + Cloud SQL(MySQL)에 배포됩니다.

## Architecture
```
app/main.py          ← FastAPI app, 미들웨어 등록, 라우터 포함
app/models.py        ← 모든 SQLAlchemy ORM 모델 (단일 파일)
app/schemas.py       ← Pydantic 요청/응답 스키마
app/database.py      ← Engine, SessionLocal, get_db dependency
app/admin.py         ← SQLAdmin ModelView 전체 (3000+ lines, 관리자 패널 핵심)
app/routers/         ← FastAPI 라우터 (batch, makeshop, organization, admin_*)
app/services/        ← 비즈니스 로직 (settlement, commission, makeshop, organization)
app/templates/       ← Jinja2 HTML 템플릿 (관리자 패널 커스텀 뷰)
alembic/versions/    ← DB 마이그레이션 (084개+, 순차 번호 접두사)
```

## Key Domain Concepts
- **Role 체계**: `role_id=1`(본사 관리자), `role_id=2`(지사장), `role_id=3`(원장/교사). 관리자 패널 접근은 1,2만 허용
- **Company 계층**: `HQ`(본사) → `BRANCH`(지사). `company_id`로 사용자-회사 연결
- **정산 흐름**: Makeshop 주문 → `Order`/`OrderItem` → `Settlement`(수수료 계산) → `Statement`(정산서) → 확인/지급
- **수수료 계산**: `CommissionType`(가입비, 바스클 교재 등) × `CommissionRateWindow`(기간/금액 티어별 수수료율)

## Coding Conventions
- **언어**: Python 3.11, 주석과 UI 텍스트는 한국어, 코드 식별자/변수명은 영어
- **ORM**: SQLAlchemy 2.0 스타일이지만 `db.query(Model)` 패턴 혼용. `Base`는 `app/database.py`에서 import
- **DB 세션**: FastAPI endpoint에서는 `Depends(get_db)` 사용, 서비스/배치에서는 `SessionLocal()` 직접 생성 후 `finally: db.close()`
- **Admin ModelView**: `class FooAdmin(RoleRestrictedModelView, model=Foo)` 패턴. `RoleRestrictedModelView`가 role 기반 visibility를 제어
- **커스텀 포매터**: `_format_currency`, `_fmt_company_type` 등 `admin.py` 상단에 helper 함수로 정의
- **스키마 매핑**: Pydantic `company_group` → DB `company_type` 변환은 서비스 레이어에서 처리 (`CompanyService.create`)

## Database & Migrations
- **DB**: MySQL (PyMySQL 드라이버), DB명 `babba`, 환경변수 `DB_USER`, `DB_PASSWORD`, `CLOUD_SQL_HOST`, `DB_NAME`
- **마이그레이션**: `alembic/versions/` 에 `NNN_description.py` 형식. 새 마이그레이션: `alembic revision --autogenerate -m "NNN_description"`
- **번호 규칙**: 기존 최대 번호 + 1 (현재 084). 파일명은 `085_add_feature.py` 형식으로 시작
- **주의**: `entrypoint.sh`에서 컨테이너 시작 시 자동 마이그레이션 실행. `AUTO_CREATE_TABLES=true`는 개발용만

## External Integrations
- **Makeshop API**: `app/services/makeshop_service.py` — 상품/주문/회원 동기화. 환경변수: `MAKESHOP_SHOPKEY`, `MAKESHOP_LICENSEKEY`, `MAKESHOP_API_URL`
- **Cloud Tasks**: 주문 동기화를 비동기 태스크로 처리 (`main.py`의 `create_sync_task`)
- **Cloud Scheduler**: `app/routers/batch.py`의 배치 엔드포인트를 주기적 호출 (월별 정산 집계 등)
- **Google Sheets**: `app/services/sheet_import_service.py` — Google Sheets에서 사용자/데이터 일괄 import

## Local Development
```bash
# Docker 기반 로컬 실행 (권장)
./local-run.sh          # 빌드 + 실행
./local-run.sh logs     # 로그 확인
./local-run.sh stop     # 중지

# 접속: http://127.0.0.1:8080/admin/ (관리자), http://127.0.0.1:8080/docs (Swagger)

# 배포
# github action 으로 배포
# ./build-and-deploy.sh   # Docker 빌드 → Artifact Registry 푸시 → Cloud Run 배포
```

## Important Patterns
- **정산 서비스** (`settlement_service.py`): `aggregate_completed_orders_to_settlement()` — 주문 데이터를 정산으로 변환하는 핵심 메서드
- **수수료율 조회** (`commission_service.py`): `get_commission_rate(db, type_code, target_date, amount)` — 기간 윈도우 + 금액 티어 매칭
- **Admin 인증**: `AdminAuthenticationBackend` (session 기반) — `login_id`로 로그인, `role_id`를 세션에 저장, 5회 실패 시 15분 잠금
- **주문 upsert**: `makeshop_order_import_service.py`의 `upsert_order_from_payload()` — Makeshop API JSON을 Order/OrderItem으로 변환
- **스킵 기록**: 정산 실패 건은 `SettlementSkipRecord`에 사유와 함께 기록 (디버깅용)

## Settlement & Scheduling Architecture

### 현재 스케줄 흐름
```
[매일 09:50, 13:50 KST]  Cloud Scheduler (babba-sync-makeshop)
  → POST /tasks/sync/makeshop/trigger → Cloud Tasks 큐
  → POST /tasks/sync/makeshop/run     → _run_makeshop_sync()
  → 상품(Product), 주문(Order/OrderItem), 회원(Member) 동기화

[매월 10일 09:00 KST]  Cloud Scheduler (babba-settlement-monthly-aggregation)
  → POST /api/batch/settlement-monthly-aggregation
  → SettlementService.aggregate_completed_orders_to_settlement()
  → Settlement, Statement, SettlementCompanyMonthlyAggregate 생성
```

### 정산 실패(스킵) 원인과 사전 검증 전략
정산은 월 1회 실행되므로, 실패 원인이 10일까지 축적됨. **매일 주문 동기화 직후** 정산 가능 여부를 사전 검증하면 문제를 조기 발견 가능.

| skip_reason | 원인 | 사전 검증 방법 |
|---|---|---|
| `USER_NOT_FOUND` | `Order.member_id` → `User.login_id` 매핑 실패 | 동기화 후 매핑 불가 주문 즉시 집계 |
| `INVALID_COMPANY_ID` | 사용자의 `company_id`가 `companies`에 없음 | User 테이블의 FK 정합성 체크 |
| `NO_ORDER_ITEMS` | 주문번호에 `OrderItem`이 없음 | 동기화 후 아이템 없는 주문 탐지 |
| `NO_COMMISSION_TYPE` | 상품 `cate1`에 매칭 `CommissionType` 없음 | 신규 cate1 코드 등장 시 알림 |
| `NO_PRODUCT` | `product_uid`에 해당 `Product` 없음 | OrderItem.product_uid ↔ Product.uid 정합성 |

### 구현 완료: 주문 동기화 후 정산 사전 검증 시스템
매일 주문 동기화(`/tasks/sync/makeshop/run`) 완료 후 자동으로 사전 검증이 실행됨.

#### 구현 파일 및 위치
| 파일 | 변경 내용 |
|---|---|
| `app/services/settlement_service.py` | `SettlementService.pre_validate_orders(db, year, month)` 정적 메서드 |
| `app/routers/batch.py` | `POST /api/batch/settlement-pre-validate` 수동 실행 엔드포인트 |
| `app/main.py` | `_run_makeshop_sync()` Step 5에서 동기화 후 자동 호출 |
| `app/admin.py` | `HomeDashboardView.index()`에서 사전 검증 데이터 조회 → 템플릿 전달 |
| `app/templates/home_dashboard.html` | 정산 불가 주문 경고 배너 (issue 있으면 warning, 없으면 success) |

#### 동작 흐름
```
_run_makeshop_sync()
  Step 1: 상품 동기화
  Step 2: 회원 동기화
  Step 3: 주문 동기화
  Step 4: 최근 29일 주문 업데이트
  Step 5: SettlementService.pre_validate_orders(db)  ← 신규 추가
    → 별도 DB 세션으로 실행 (동기화 트랜잭션 분리)
    → 실패해도 동기화 결과에 영향 없음 (try/except)
    → 로그에 사유별 건수 출력
```

#### `pre_validate_orders()` 반환 구조
```python
{
    "status": "success",
    "year": 2025, "month": 1,
    "total_completed_orders": 150,
    "settleable_count": 142,
    "issue_count": 8,
    "issues": [
        {"order_id": 123, "ordernum": "ORD001", "reason": "USER_NOT_FOUND", "detail": "..."},
        ...
    ],
    "summary_by_reason": {
        "USER_NOT_FOUND": 3,
        "NO_COMMISSION_TYPE": 5
    }
}
```

#### 관리자 대시보드 표시
- **issue_count > 0**: 경고(warning) 배너 — 사유별 badge + "정산 안된 내역 보기" 링크
- **issue_count == 0**: 성공(success) 배너 — "모두 정산 가능합니다"
- **pre_validation == None**: 표시 없음 (에러 발생 시)
