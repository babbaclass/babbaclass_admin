# Babba API - 인프라 구조 및 설정 문서

**마지막 업데이트**: 2025년 11월 5일
**프로젝트**: babba-api (Fulfilled Inc.)
**상태**: ✅ 프로덕션 배포 완료 (Cloud NAT 최적화됨)

---

## 📋 목차

1. [전체 아키텍처](#전체-아키텍처)
2. [컴포넌트 상세](#컴포넌트-상세)
3. [네트워크 구성](#네트워크-구성)
4. [데이터베이스](#데이터베이스)
5. [API 통합](#api-통합)
6. [배포 및 접근](#배포-및-접근)
7. [비용 최적화](#비용-최적화)

---

## 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        인터넷 (외부)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────▼────────────┐
        │  고정 외부 IP              │
        │  34.158.215.39           │ (Cloud NAT)
        └────────────┬─────────────┘
                     │
        ┌────────────▼────────────────────────┐
        │    Cloud NAT + Cloud Router          │
        │    babba-nat-router                  │
        │    (asia-northeast3)                 │
        └────────────┬──────────────────────────┘
                     │
                     │ VPC (default network)
                     │
        ┌────────────▼────────────────────┐
        │    Cloud Run                     │
        │    babba-api                     │
        │    - Public URL                  │
        │    - VPC Connector 연결          │
        └────────┬───────────────┬─────────┘
                 │               │
         ┌───────▼──────┐  ┌────▼──────────┐
         │ VPC Connector │  │ Cloud SQL     │
         │ 10.8.0.0/28  │  │ Private IP    │
         │ babba-conn   │  │ 10.85.224.3   │
         └──────────────┘  └───────────────┘
```

---

## 컴포넌트 상세

### 1️⃣ Cloud Run 서비스

| 항목 | 값 |
|------|-----|
| **서비스명** | babba-api |
| **리전** | asia-northeast3 |
| **URL** | https://babba-api-1024083500192.asia-northeast3.run.app |
| **현재 Revision** | 00046-ck6 |
| **메모리** | 256Mi |
| **CPU** | 1 vCPU |
| **최대 인스턴스** | 2 |
| **상태** | 🟢 정상 작동 |

**특징:**
- ✅ VPC Connector를 통해 Cloud SQL 접근
- ✅ Cloud SQL Auth Proxy 사이드카 컨테이너 실행
- ✅ 자동 스케일링 지원
- ✅ 트래픽 100% 라우팅

### 2️⃣ Cloud NAT (비용 최적화) ⭐ NEW

| 항목 | 값 |
|------|-----|
| **라우터명** | babba-nat-router |
| **NAT명** | babba-nat |
| **고정 IP 주소** | 34.158.215.39 |
| **IP 할당 옵션** | MANUAL_ONLY (고정 IP만 사용) |
| **서브넷 범위** | 모든 서브넷의 모든 IP 범위 |
| **리전** | asia-northeast3 |
| **상태** | 🟢 활성화 |

**특징:**
- ✅ Cloud Run의 모든 아웃바운드 트래픽이 고정 IP `34.158.215.39`를 사용
- ✅ 외부 서비스(MakeShop 등)에서 예측 가능한 IP로 인식
- ✅ VM 기반 NAT 대비 비용 절감 (월 $5-10 수준)
- ✅ Private IP 범위(10.8.0.0/28)로 자동 라우팅

**이점:**
- 📊 비용 최적화: VM 인스턴스 제거로 월 과금 절감
- 🔒 보안: VPC Connector를 통한 격리된 네트워크
- 📍 추적성: 모든 외부 요청이 동일 IP에서 발생
- ⚡ 성능: 직접 경로로 지연시간 최소화

### 3️⃣ Cloud SQL 인스턴스

| 항목 | 값 |
|------|-----|
| **인스턴스명** | babba-db |
| **데이터베이스 엔진** | MySQL 8.0.41 (Enterprise) |
| **리전** | asia-northeast3 |
| **Public IP** | 34.22.93.96 (비활성화) |
| **Private IP** | 10.85.224.3 ✅ |
| **데이터베이스** | babba |
| **상태** | 🟢 정상 작동 |

**데이터베이스 테이블 (6개):**
```sql
1. users        - 사용자 정보 (6 columns)
2. partners     - 파트너 정보 (6 columns)
3. products     - 상품 정보 (15 columns)
4. categories   - 카테고리 (8 columns)
5. orders       - 주문 정보 (14 columns)
6. order_items  - 주문 상세 (9 columns)
```

---

## 네트워크 구성

### VPC 설정

| 항목 | 설정값 |
|------|--------|
| **VPC 이름** | default |
| **Subnet** | default (10.128.0.0/9) |

### VPC Connector

| 항목 | 설정값 |
|------|--------|
| **Connector명** | babba-connector |
| **상태** | 🟢 READY |
| **CIDR 범위** | 10.8.0.0/28 (16 IP) |
| **머신 타입** | e2-micro |
| **최소 인스턴스** | 2 |
| **최대 인스턴스** | 10 |
| **리전** | asia-northeast3 |

**용도:**
- Cloud Run ↔ Cloud SQL 통신
- Private IP를 통한 안전한 연결

### 외부 IP (주소 관리)

| 항목 | 설정값 |
|------|--------|
| **IP명** | babba-nat-ip-v2 |
| **주소** | 34.158.215.39 (고정) |
| **타입** | EXTERNAL |
| **상태** | IN_USE |
| **할당처** | babba-nat (Cloud NAT) |
| **목적** | Cloud Run 아웃바운드 트래픽 라우팅 |

---

## 데이터베이스

### 연결 방식

```
Cloud Run
    ↓
Cloud SQL Auth Proxy (localhost:3306)
    ↓
Cloud SQL Private IP (10.85.224.3:3306)
```

### 인증 정보

```
사용자: root
비밀번호: Fulfilled07!@  (환경변수: DB_PASSWORD)
데이터베이스: babba
인증 방식: 비밀번호 기반
```

### 스키마

#### users 테이블
```sql
- id (PK)
- email (UNIQUE)
- password_hash
- name
- created_at
- updated_at
```

#### products 테이블
```sql
- id (PK)
- makeshop_id
- name
- description
- price
- cost
- stock
- category_id (FK)
- status
- sku
- barcode
- weight
- dimensions
- created_at
- updated_at
```

#### orders 테이블
```sql
- id (PK)
- makeshop_order_id (UNIQUE)
- customer_id (FK)
- status
- total_price
- shipping_address
- payment_method
- payment_status
- shipped_at
- delivered_at
- created_at
- updated_at
```

---

## API 통합

### Makeshop API

**설정 현황:**

| 항목 | 값 |
|------|-----|
| **상점 도메인** | www.babbasmartclass.com |
| **API 엔드포인트** | http://www.babbasmartclass.com/list/open_api.html |
| **인증 방식** | Shopkey / Licensekey 헤더 |
| **Shopkey** | Yzg3MGRmM2ZiYzRhNmU2MmE1MTU0NzAyNjlmZGY4MTQ= |
| **Licensekey** | ba9e9e655550c14ab3fc6d778bcba33b |

**구현된 메서드:**

```python
# 상품 조회
GET /list/open_api.html?mode=search&type=product&page=1&limit=100

# 카테고리 조회
GET /list/open_api.html?mode=search&type=category

# 주문 조회
GET /list/open_api.html?mode=search&type=order&page=1&limit=100

# 사용자 조회
GET /list/open_api.html?mode=search&type=user&page=1&limit=1
```

**상태:**
- 🟡 호출 형식 정상 (9002 오류: 상점 정보 재검증 필요)

---

## 배포 및 접근

### 배포 구성

| 항목 | 설정값 |
|------|--------|
| **Container Registry** | asia-northeast3-docker.pkg.dev |
| **Repository** | babba |
| **이미지** | babba-api:latest |
| **빌드 도구** | Docker |
| **배포 도구** | gcloud CLI |

### Public 접근

```
URL: https://babba-api-1024083500192.asia-northeast3.run.app
타입: HTTPS만 지원
상태: ✅ 온라인
```

### API 엔드포인트

```bash
# 헬스 체크
GET /health
응답: {"status":"healthy"}

# DB 연결 확인
GET /health/db
응답: {"status":"healthy","database":"connected"}

# 데이터베이스 테이블 조회
GET /database/tables
응답: 6개 테이블 목록 및 스키마

# CRUD 엔드포인트
GET/POST/PUT/DELETE /users
GET/POST/PUT/DELETE /partners
GET/POST/PUT/DELETE /products
...

# Makeshop 동기화 (준비 중)
POST /sync/makeshop/products
POST /sync/makeshop/categories
POST /sync/makeshop/orders
```

---

## 비용 최적화

### 현재 전략 (Cloud NAT 기반) ⭐ 개선됨

| 컴포넌트 | 비용 효율화 방법 |
|---------|-----------------|
| **아웃바운드 IP** | Cloud NAT (고정 IP) - VM 제거로 비용 절감 |
| **데이터베이스** | MySQL (Private IP 사용) |
| **컴퓨팅** | Cloud Run 자동 스케일 |
| **네트워크** | VPC Connector (효율적 라우팅) |

### 월 예상 비용 (개략)

```
Cloud Run (512Mi, 1 CPU):      ~$15-20
Cloud SQL (db-f1-micro):        ~$15-20
Cloud NAT:                       ~$3-5
VPC Connector:                   ~$10-15
─────────────────────────────────────
합계:                            ~$43-60/월

이전 비용 (NAT VM 방식):         ~$50-70/월
절감액:                          ~$7-10/월 (약 15-20% 절감)
```

**개선사항:**
- ✅ VM 인스턴스 제거로 운영 복잡도 감소
- ✅ Cloud NAT는 Pay-per-use 모델로 사용량 기반 과금
- ✅ 관리 오버헤드 제거 (자동 스케일, 패치 관리 불필요)
- ✅ 가용성 향상 (Google 관리 서비스)

---

### 보안 설정

### 데이터베이스

- ✅ Private IP 사용 (외부 직접 접근 불가)
- ✅ Public IP 비활성화
- ✅ Cloud SQL Auth Proxy를 통한 안전한 연결
- ✅ VPC Connector를 통한 격리

### 네트워크

- ✅ Cloud NAT을 통한 보안된 아웃바운드 연결
- ✅ VPC 내부 격리 네트워크
- ✅ 고정 외부 IP(`34.158.215.39`)로 아웃바운드 추적 가능
- ✅ IAM 권한 설정 (별도 문서 참조)

### API

- ✅ HTTPS만 사용
- ✅ 환경 변수로 민감 정보 관리
- ✅ Cloud Secret Manager 통합 (선택사항)

---

## 모니터링 및 로깅

### Cloud Logging

```bash
# Cloud Run 로그 조회
gcloud run services logs read babba-api --limit=50 --region=asia-northeast3

# 특정 키워드 검색
gcloud run services logs read babba-api --limit=100 --grep="makeshop"
```

### Cloud Monitoring

**주요 메트릭:**
- Request count
- Error rate
- Latency (p50, p95, p99)
- Instance count
- CPU utilization
- Memory utilization

---

## 트러블슈팅

### 🔴 Makeshop API 연결 오류 (9002)

**원인**: 잘못된 상점 정보
**해결책**:
1. Shopkey와 Licensekey 재확인
2. 상점 도메인 정확성 확인
3. Makeshop 관리자 페이지 API 설정 검증

### 🔴 Cloud Run 시간 초과

**원인**: VPC Connector 문제 또는 네트워크 지연
**해결책**:
1. VPC Connector 상태 확인: `gcloud compute networks vpc-access connectors describe babba-connector --region=asia-northeast3`
2. Cloud SQL 접근성 테스트
3. 타임아웃 값 증가

### 🔴 데이터베이스 연결 거부

**원인**: Auth Proxy 미실행 또는 권한 문제
**해결책**:
1. Cloud Run 로그 확인: `/cloud-sql-proxy` 시작 메시지
2. Docker 이미지 빌드 재확인
3. 환경 변수 `CLOUD_SQL_INSTANCE` 확인

---

## 다음 단계

### 🔄 진행 중

- [x] Cloud NAT 설정 완료 (2025-11-05)
- [x] 고정 IP 할당 및 구성 완료
- [x] VPC Connector 적용 완료
- [ ] Makeshop API 실제 데이터 동기화 테스트
- [ ] 응답 코드 9002 해결
- [ ] 상품/주문 데이터 초기 동기화

### 📋 계획 중

- [ ] 자동 동기화 스케줄 구성 (APScheduler)
- [ ] 에러 알림 설정 (Cloud Alerting)
- [ ] CloudSQL 백업 정책 수립
- [ ] 성능 모니터링 대시보드 구축

### 🚀 장기 목표

- [ ] 데이터 파이프라인 자동화
- [ ] 다중 샤드 지원
- [ ] 글로벌 확장성 검증
- [ ] 재해 복구 계획 수립

---

## 관련 문서

- [PROGRESS.md](./PROGRESS.md) - 배포 진행 상황
- [MAKESHOP_API_FIX.md](./MAKESHOP_API_FIX.md) - API 호출 방식 수정
- [requirements.txt](./requirements.txt) - Python 의존성
- [.env.makeshop](./.env.makeshop) - Makeshop 설정

---

## 담당자

- **프로젝트**: Babba API (Fulfilled Inc.)
- **배포 담당**: DevOps Team
- **마지막 업데이트**: 2025-11-01

---

## 변경 이력

| 날짜 | 변경사항 | 커밋 |
|------|---------|------|
| 2025-11-05 | Cloud NAT 설정 완료 (NAT VM에서 Cloud NAT으로 마이그레이션) | 39cf504 |
| 2025-11-04 | Cloud NAT 구성 문서 추가 (CLOUD_NAT_SETUP.md) | 336e116 |
| 2025-11-04 | 모든 logger 호출을 print()로 변환 (Cloud Run 로그 가시성 개선) | 336e116 |
| 2025-11-01 | Cloud NAT 대신 e2-micro NAT VM으로 비용 최적화 | - |
| 2025-11-01 | Makeshop API 호출 방식 수정 | a74c12f |
| 2025-11-01 | Cloud SQL Auth Proxy 적용 | 0aab6bd |
| 2025-11-01 | Cloud Run 배포 및 VPC 구성 | - |

---

**문서 작성일**: 2025년 11월 1일
**마지막 업데이트**: 2025년 11월 5일
**버전**: 2.0 (Cloud NAT 기반 최적화)
**상태**: ✅ 최신
