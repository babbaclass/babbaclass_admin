# 위시켓 포트폴리오 등록 가이드 — babba-api

> 아래 내용을 위시켓 포트폴리오 등록 폼에 각 항목별로 복사하여 입력하세요.

---

## 1. 프로젝트명
```
B2B 교육 프랜차이즈 통합 관리 시스템 (주문 동기화·수수료 정산·관리자 패널)
```

## 2. 업무 범위
```
개발 · 기획
```

## 3. 카테고리
```
웹
```

## 4. 프로젝트 분야
```
ERP·CRM, 커머스·쇼핑몰, 통계·대시보드
```

---

## 5. 프로젝트 배경

```
교육 프랜차이즈 본사가 Makeshop 쇼핑몰을 통해 교재·교구를 판매하고 있었으나, 전국 지사별 주문 현황 파악과 수수료 정산을 수작업(엑셀)으로 처리하고 있었습니다.

기존 문제점:
- 매월 수백 건의 주문을 수동으로 지사별 분류 후 엑셀 정산 → 인적 오류 및 정산 지연 발생
- Makeshop 주문 데이터와 내부 사용자·지사 정보가 분리되어 실시간 현황 파악 불가
- 지사장이 자기 지사의 주문·정산 내역을 직접 확인할 수 없어 본사 문의 빈번
- 수수료율이 상품 유형·기간·금액 티어별로 상이하여 계산 복잡도가 높음

프로젝트 목표:
- Makeshop API 연동으로 상품·주문·회원 데이터 자동 동기화 (1일 2회)
- 복잡한 수수료율 체계(상품 유형 × 기간 윈도우 × 금액 티어)를 시스템화하여 월별 자동 정산
- 역할 기반 관리자 패널로 본사 관리자와 지사장이 각자 권한에 맞는 데이터 조회
- Google Cloud Run 서버리스 배포로 운영 비용 최소화
```

---

## 6. 프로젝트 성과

### 성과 1
```
정산 업무 자동화로 월 40시간 이상 업무 시간 절감
```
```
기존 수작업 엑셀 정산을 완전 자동화하여, 매월 10일 Cloud Scheduler가 자동으로 정산을 집계합니다. 수백 건의 주문을 지사별·상품별로 분류하고 수수료를 계산하는 과정이 수 초 내에 완료됩니다.
```

### 성과 2
```
실시간 데이터 동기화로 운영 가시성 확보
```
```
Makeshop API와 Cloud Tasks 비동기 큐를 결합하여 매일 2회(09:50, 13:50) 상품·주문·회원 데이터를 자동 동기화합니다. 정산 사전 검증 시스템으로 동기화 직후 정산 불가 건을 사전 탐지하여 월말 정산 실패를 예방합니다.
```

### 성과 3
```
서버리스 아키텍처로 월 운영비 최소화
```
```
Google Cloud Run(min 0, max 2 인스턴스) + Cloud SQL 조합으로 트래픽이 없을 때 비용이 0에 수렴하는 서버리스 구조를 구현했습니다. Docker 컨테이너 기반 CI/CD 파이프라인으로 빌드부터 배포까지 자동화되어 있습니다.
```

---

## 7. 핵심 기능

### 기능 1: Makeshop 쇼핑몰 주문 자동 동기화
```
Makeshop REST API와 연동하여 상품(Product), 주문(Order/OrderItem), 회원(Member) 데이터를 자동 동기화합니다. Cloud Scheduler → Cloud Tasks 비동기 큐 구조로 장시간 동기화에도 타임아웃 없이 안정적으로 처리합니다. Upsert 방식으로 중복 데이터 없이 증분 동기화되며, 최근 29일 주문의 상태 변경(결제 완료, 배송 등)도 자동 업데이트됩니다.
```

### 기능 2: 다층 수수료율 기반 자동 정산 시스템
```
상품 유형(가입비, 교재비 등) × 기간 윈도우(연/월 단위) × 금액 티어(구간별 요율) × 지사별 특수 요율을 조합한 복잡한 수수료 체계를 시스템화했습니다. 매월 자동으로 완료된 주문을 집계하여 지사별 Settlement(정산 레코드) → Statement(정산서)를 생성하고, 정산 불가 건은 사유(USER_NOT_FOUND, NO_COMMISSION_TYPE 등)와 함께 SkipRecord에 기록하여 추적이 가능합니다.
```

### 기능 3: 역할 기반 관리자 대시보드
```
SQLAdmin 기반 웹 관리자 패널에 역할 기반 접근 제어(RBAC)를 구현했습니다. 본사 관리자(role_id=1)는 전체 데이터에 접근 가능하고, 지사장(role_id=2)은 자신의 지사 데이터만 조회할 수 있습니다. 대시보드에는 정산 현황, 사전 검증 경고 배너, 지사별 월간 집계 등이 표시되며, 17개 모델에 대한 CRUD 인터페이스를 제공합니다.
```

### 기능 4: 정산 사전 검증 시스템
```
매일 주문 동기화 직후 자동으로 정산 가능 여부를 사전 검증합니다. 사용자 매핑 실패, 회사 ID 불일치, 주문 아이템 누락, 수수료 타입 미매핑, 상품 미존재 등 5가지 실패 사유를 사전에 탐지하여 관리자 대시보드에 경고 배너로 표시합니다. 월 1회 정산 실행 전에 문제를 조기 발견하여 정산 누락을 방지합니다.
```

### 기능 5: 조직 계층 및 계약 관리
```
본사(HQ) → 지사(BRANCH) 2단계 조직 구조와 관리자 → 지사장 → 원장/교사 3단계 역할 체계를 구현했습니다. 지사별 등급(새싹/활성화/우수/최우수), 계약 시작·종료일 관리, 지사장 비밀번호 관리 등 프랜차이즈 운영에 필요한 조직 관리 기능을 제공합니다.
```

---

## 8. 진행 단계

### 단계 1: 요구사항 분석 및 DB 설계
```
교육 프랜차이즈 비즈니스 도메인 분석, Makeshop API 연동 규격 파악, 수수료 정산 로직 정의. 17개 테이블 ERD 설계 및 Alembic 마이그레이션 체계 수립.
```

### 단계 2: 핵심 백엔드 개발
```
FastAPI 기반 REST API 서버 구축. SQLAlchemy ORM 모델 정의, Makeshop API 클라이언트 개발, 주문 Upsert 로직, 수수료율 조회 엔진, 정산 집계 서비스 구현.
```

### 단계 3: 관리자 패널 구축
```
SQLAdmin 기반 15개 이상의 ModelView 구현. 역할 기반 접근 제어, 커스텀 대시보드, 정산서 조회/확인 뷰, 사용자 생성 폼, 로그인 보안(5회 실패 시 15분 잠금) 구현.
```

### 단계 4: 클라우드 인프라 구축 및 배포
```
Docker 컨테이너화, Google Cloud Run 배포 자동화(build-and-deploy.sh), Cloud SQL(MySQL) 연결(Unix Socket Proxy), Cloud Scheduler + Cloud Tasks 배치 아키텍처 구축, 자동 마이그레이션 entrypoint 설정.
```

### 단계 5: 정산 고도화 및 사전 검증
```
정산 실패 원인 분석 후 SettlementSkipRecord 추적 시스템 도입. 주문 동기화 후 자동 사전 검증 파이프라인 구축. 관리자 대시보드에 정산 불가 주문 경고 배너 추가. 85회 이상의 DB 마이그레이션을 통한 점진적 스키마 개선.
```

---

## 9. 프로젝트 상세

```
1) 포트폴리오 소개
本 프로젝트는 B2B 교육 프랜차이즈를 위한 통합 관리 시스템입니다. Makeshop 쇼핑몰의 주문 데이터를 자동 동기화하고, 전국 지사별 수수료를 자동으로 정산하며, 역할 기반 관리자 패널을 제공합니다. Python/FastAPI 백엔드 + SQLAdmin 관리자 패널 + Google Cloud 서버리스 인프라로 구성되어 있습니다.

2) 작업 범위
- 백엔드 API 설계 및 개발 (FastAPI, 50개 이상 REST 엔드포인트)
- 데이터베이스 설계 (MySQL, 25개 이상 테이블, 85회 마이그레이션)
- 관리자 패널 UI 구축 (SQLAdmin + Jinja2 커스텀 템플릿 19개)
- 외부 API 연동 (Makeshop REST API — 상품/주문/회원 동기화)
- 배치 처리 시스템 (Cloud Scheduler + Cloud Tasks 비동기 큐)
- 클라우드 인프라 (Cloud Run + Cloud SQL + Artifact Registry)
- CI/CD 파이프라인 (Docker 빌드 → Artifact Registry → Cloud Run 자동 배포)

3) 기술적 챌린지 및 해결 방법

[수수료 정산 복잡도]
상품 유형 × 기간 윈도우 × 금액 티어 × 지사별 특수 요율이라는 4차원 수수료율 매칭 로직이 핵심 난점이었습니다. CommissionType과 CommissionRateWindow 2개 테이블을 설계하여, 기간(start_year/month ~ end_year/month)과 금액 구간(min_amount ~ max_amount)을 조합한 유연한 요율 조회 엔진을 구현했습니다.

[Makeshop API 동기화 안정성]
Cloud Scheduler의 15분 타임아웃 제약을 Cloud Tasks 비동기 큐로 우회했습니다. OIDC 서비스 계정 토큰 인증으로 보안을 확보하고, Upsert 패턴으로 동기화 중복을 방지했습니다. 동기화 실패 시에도 기존 데이터에 영향이 없도록 별도 세션으로 트랜잭션을 분리했습니다.

[정산 실패 추적 및 사전 검증]
월 1회 정산 실행 시 실패 원인이 누적되는 문제를 해결하기 위해, 매일 동기화 직후 자동 사전 검증 파이프라인을 도입했습니다. 5가지 실패 사유(USER_NOT_FOUND, INVALID_COMPANY_ID, NO_ORDER_ITEMS, NO_COMMISSION_TYPE, NO_PRODUCT)를 실시간 탐지하여 관리자 대시보드에 경고합니다.

4) 시스템 아키텍처

┌─────────────────────────────────────────────┐
│              Google Cloud                    │
├──────────────┬──────────────────────────────┤
│  Cloud Run   │  Cloud Scheduler (Cron)      │
│  (FastAPI)   │  ├ 주문동기화: 매일 2회       │
│  Port: 8080  │  └ 정산집계: 매월 10일        │
│  0~2 인스턴스 │                              │
└──────┬───────┴──────────────────────────────┘
       │ Cloud SQL Proxy (Unix Socket)
       ▼
┌──────────────────┐    ┌──────────────────┐
│  Cloud SQL       │    │  Cloud Tasks     │
│  MySQL 8.0       │    │  비동기 큐        │
│  25+ Tables      │    │  Makeshop 동기화  │
└──────────────────┘    └──────────────────┘

5) 주요 ORM 모델 (17개)
- 조직: Company(HQ/BRANCH), Grade, Role, User
- Makeshop: Product, Order, OrderItem, Member
- 수수료: CommissionType, CommissionRateWindow
- 정산: Settlement, Statement, SettlementCompanyMonthlyAggregate, SettlementStatementConfirmation, SettlementSkipRecord
- 감사: LoginHistory, ContractEnd
```

---

## 10. 관련 기술 (태그)

```
FastAPI, Python, SQLAlchemy, MySQL, SQLAdmin, Alembic, Docker, Google Cloud Run, Cloud SQL, Cloud Tasks, Cloud Scheduler, Pydantic, Jinja2, REST API, Makeshop API
```

---

## 11. 프로젝트 정보

| 항목 | 입력값 |
|------|--------|
| **참여 기간** | 2024.06 ~ 현재 (운영 중) |
| **참여율** | 100% |
| **고객사** | 교육 프랜차이즈 기업 (B2B) |
| **역할** | 시스템 설계 및 풀스택 개발 (기획·백엔드·인프라·관리자 패널) |
| **결과물 URL** | (관리자 전용 시스템으로 외부 공개 URL 없음 — 스크린샷 첨부 권장) |

---

## 12. 기술 태그 (위시켓 검색 최적화용)

위시켓에서 검색될 수 있도록 아래 기술 태그를 모두 등록하세요:

| 카테고리 | 태그 |
|----------|------|
| **언어** | Python |
| **프레임워크** | FastAPI, SQLAlchemy, SQLAdmin, Pydantic, Alembic, Jinja2 |
| **데이터베이스** | MySQL, Cloud SQL |
| **인프라** | Docker, Google Cloud Run, Cloud Tasks, Cloud Scheduler, Artifact Registry |
| **기타** | REST API, Makeshop API, RBAC, Bcrypt, Session Auth |

---

## 참고: 스크린샷 촬영 권장 목록

위시켓 포트폴리오에 이미지를 첨부하면 노출도가 높아집니다. 아래 화면을 캡처하여 첨부하세요:

1. **관리자 대시보드** — 정산 현황 + 사전 검증 경고 배너가 보이는 메인 화면
2. **정산서 목록/상세** — 월별 정산서가 표시된 화면
3. **주문 관리 화면** — OrderAdmin 목록 (Makeshop 동기화 데이터)
4. **수수료율 관리** — CommissionRateWindow 설정 화면
5. **시스템 아키텍처 다이어그램** — 위 ASCII 아트를 비주얼 도구로 변환
6. **Swagger API 문서** — `/docs` 엔드포인트 스크린샷
