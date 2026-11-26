# Babba API Cloud Run 배포 진행 상황# Babba API Cloud Run 배포 진행 상황# Babba API Cloud Run 배포 진행 상황



**마지막 업데이트**: 2025년 11월 1일 (2025-11-01T03:45:00Z)

**현재 Revision**: 00046-ck6

**Git Commit**: a74c12f - fix: Makeshop API 호출 방식 수정**마지막 업데이트**: 2025년 11월 1일 (2025-11-01T00:35:00Z)**마지막 업데이트**: 2025년 11월 1일



---**Git Commit**: 0aab6bd - feat: Cloud SQL Auth Proxy 적용 및 Makeshop API 통합



## 📊 현재 상태## 📋 현재 상태



### ✅ 완료 (100%)## 📊 현재 상태



1. **Cloud Run 배포** ✅### ✅ 완료된 항목

   - 서비스명: babba-api

   - 리전: asia-northeast3### ✅ 완료 (100%)

   - URL: https://babba-api-1024083500192.asia-northeast3.run.app

   - 현재 Revision: 00046-ck61. **Cloud Run 배포**

   - 상태: 🟢 정상 작동

1. **Cloud Run 배포** ✅   - 서비스명: babba-api

2. **VPC Connector 설정** ✅

   - 이름: babba-connector   - 서비스명: babba-api   - 리전: asia-northeast3

   - CIDR: 10.8.0.0/28

   - 상태: 🟢 READY   - 리전: asia-northeast3   - URL: https://babba-api-1024083500192.asia-northeast3.run.app



3. **Cloud SQL Private IP** ✅   - URL: https://babba-api-1024083500192.asia-northeast3.run.app   - 상태: 정상 작동 중

   - IP: 10.85.224.3

   - 인스턴스: babba-db (MySQL 8.0.41)   - 현재 Revision: 00045-8dr

   - 상태: 🟢 정상 작동

   - 상태: 🟢 정상 작동2. **VPC Connector 설정**

4. **Cloud SQL Auth Proxy** ✅

   - Dockerfile에 cloud-sql-proxy 통합   - 이름: babba-connector

   - 엔드포인트: localhost:3306 (127.0.0.1)

   - 상태: 🟢 작동 중2. **VPC Connector 설정** ✅   - CIDR: 10.8.0.0/28



5. **고정 외부 IP (NAT)** ✅   - 이름: babba-connector   - 상태: READY ✅

   - IP: 34.50.26.124 (고정)

   - 리소스: babba-nat-vm (e2-micro)   - CIDR: 10.8.0.0/28

   - 상태: 🟢 정상 작동

   - 비용: 월 ~$5-10 (Cloud NAT보다 60% 저렴)   - 상태: 🟢 READY3. **Cloud SQL Private IP 할당**



6. **데이터베이스** ✅   - IP: 10.85.224.3

   - 데이터베이스명: babba

   - 테이블 6개 자동 생성3. **Cloud SQL Private IP** ✅   - 인스턴스: babba-db (MySQL 8.0.41)

   - 상태: 🟢 정상 작동

   - IP: 10.85.224.3   - 리전: asia-northeast3

7. **API 엔드포인트** ✅

   - ✅ `/health` - 기본 상태 확인   - 인스턴스: babba-db (MySQL 8.0.41)

   - ✅ `/health/db` - DB 연결 확인

   - ✅ `/database/tables` - 테이블 목록 조회   - 상태: 🟢 정상 작동4. **Cloud SQL 데이터베이스 생성**

   - ✅ CRUD 엔드포인트

   - 데이터베이스명: `babba` ✅

8. **Makeshop API 통합** ✅

   - 인증 방식: Shopkey / Licensekey 헤더4. **Cloud SQL Auth Proxy** ✅   - 상태: 생성 완료

   - 엔드포인트: /list/open_api.html

   - 호출 형식: 올바르게 수정됨   - Dockerfile에 cloud-sql-proxy 통합

   - 상태: 🟡 응답 코드 9002 (상점 정보 재검증 필요)

   - 엔드포인트: localhost:3306 (127.0.0.1)5. **연결 문자열 특수문자 문제 해결**

## 🔄 진행 중 (추진 대기)

   - 상태: 🟢 작동 중   - 문제: 비밀번호의 `@` 특수문자로 인한 URL 파싱 오류

1. **Makeshop API 실제 데이터 동기화 테스트**

   - API 응답 형식 검증 필요   - 해결: `urllib.parse.quote()` 사용하여 비밀번호 URL 인코딩

   - 실제 데이터 동기화 테스트 필요

5. **데이터베이스** ✅   - 결과: 연결 문자열 정상 파싱 ✅

## 🚀 배포 현황

   - 데이터베이스명: babba

| 항목 | 상태 | 설명 |

|------|------|------|   - 테이블 6개 자동 생성:### ✅ 해결됨 - DB 연결 성공!

| Cloud Run | ✅ 배포 완료 | revision 00046-ck6, 정상 작동 |

| VPC 연결 | ✅ 완료 | 10.8.0.0/28 범위 구성 |     - users (6 columns)

| Cloud SQL | ✅ 연결 완료 | Private IP 10.85.224.3 |

| Auth Proxy | ✅ 작동 중 | localhost:3306 수신 |     - partners (6 columns)**문제**: MySQL 권한 문제 (`Access denied for user 'root'@'10.8.0.2'`)

| 데이터베이스 | ✅ 준비 완료 | 6개 테이블, 자동 생성 |

| API 엔드포인트 | ✅ 작동 중 | health, db, tables 확인됨 |     - products (15 columns)

| 고정 IP (NAT) | ✅ 설정 완료 | 34.50.26.124 (e2-micro VM) |

| Makeshop 연동 | 🔄 준비 중 | API 클라이언트 구현 완료 |     - categories (8 columns)**해결책**: Cloud SQL Auth Proxy 사용



## 🏗️ 인프라 구조     - orders (14 columns)- entrypoint에서 proxy와 uvicorn을 함께 실행



```     - order_items (9 columns)- `-instances=<INSTANCE_NAME>=tcp:127.0.0.1:3306` 파라미터로 인스턴스 지정

┌─────────────────────────────┐

│  고정 외부 IP: 34.50.26.124  │   - 상태: 🟢 정상 작동- localhost:3306으로 연결하여 권한 우회

│  (babba-nat-vm, e2-micro)   │

└────────────┬────────────────┘

             │

    ┌────────▼─────────┐6. **API 엔드포인트** ✅**현재 상태**: ✅ 모든 DB 엔드포인트 정상 작동

    │  Cloud Run        │

    │  babba-api        │   - ✅ `/health` - 기본 상태 확인

    └────────┬─────────┘

             │   - ✅ `/health/db` - DB 연결 확인## 🎯 현재 작업 - Makeshop API 통합

   ┌─────────┼──────────┐

   │                    │   - ✅ `/database/tables` - 테이블 목록 조회

┌──▼──┐      ┌────────▼─────┐

│VPC  │      │Cloud SQL      │   - ✅ `/users`, `/partners` 등 CRUD 엔드포인트### ✅ 완료

│Conn │      │10.85.224.3    │

└─────┘      └───────────────┘   - ✅ Makeshop 동기화 엔드포인트 구조1. Cloud SQL Auth Proxy 적용 - DB 연결 성공

```

2. 모든 기본 엔드포인트 정상 작동

## 🎯 전체 진행률

7. **Makeshop API 통합** ✅3. MakeshopAPIClient 구현

| 항목 | 진행률 | 상태 |

|------|--------|------|   - 인증 방식: Shopkey / Licensekey 헤더4. Makeshop 동기화 엔드포인트 구조 완성

| 인프라 구성 | 100% | ✅ |

| 데이터베이스 | 100% | ✅ |   - 엔드포인트: /list/open_api.html

| API 기본 기능 | 100% | ✅ |

| Makeshop 통합 | 50% | 🔄 |   - 구현 메서드:### 🔄 진행 중

| 자동화/스케줄링 | 0% | 📋 |

| 프로덕션 준비 | 60% | 🔄 |     - `get_products()` - 상품 조회1. Makeshop Open API 문서 검토 및 엔드포인트 확인



**전체 완료율: ~70% (7/10)**     - `get_categories()` - 카테고리 조회   - 참고: https://openapi.makeshop.co.kr/



## 📋 다음 단계     - `get_orders()` - 주문 조회2. API 키 및 Shop ID 검증



### 1️⃣ Makeshop API 실제 연동 확인 (우선순위: 높음)     - `health_check()` - API 헬스 체크3. 상품, 카테고리, 주문 동기화 테스트

- [ ] API 키 및 라이센스 키 유효성 검증

- [ ] API 응답 형식 분석   - 상태: 🟡 API 응답 검증 필요

- [ ] 실제 상품 데이터 동기화 테스트

### 📋 Makeshop API 엔드포인트 (예정)

### 2️⃣ 데이터 동기화 로직 구현 (우선순위: 높음)

- [ ] 초기 상품 동기화## 🔄 진행 중 (추진 대기)- `GET /sync/makeshop/products` - 상품 동기화

- [ ] 초기 카테고리 동기화

- [ ] 초기 주문 동기화- `GET /sync/makeshop/categories` - 카테고리 동기화

- [ ] 변경사항 감지 및 증분 동기화

1. **Makeshop API 실제 연동 테스트**- `GET /sync/makeshop/orders` - 주문 동기화

### 3️⃣ 자동화 및 모니터링 (우선순위: 중간)

- [ ] 동기화 작업 스케줄링 (APScheduler)   - API 응답 형식 검증 필요- `GET /makeshop/health` - API 헬스 체크

- [ ] 에러 처리 및 재시도 로직

- [ ] 로깅 및 모니터링   - 실제 데이터 동기화 테스트 필요

- [ ] 알림 설정

   - 요청 예시: `curl -H 'Shopkey: {key}' -H 'Licensekey: {license}' 'http://{domain}/list/open_api.html?mode=search&type=product'`## 📁 코드 현재 상태

### 4️⃣ 프로덕션 배포 준비 (우선순위: 중간)

- [ ] 환경 변수 보안화 (Secret Manager)

- [ ] CloudSQL IAM 권한 최적화

- [ ] Cloud Logging 구성## 📈 배포 현황### database.py

- [ ] Cloud Monitoring 알림 설정

- **상태**: IAM 인증 시도, password 인증 fallback 구현

---

| 항목 | 상태 | 설명 |- **문제**: cloud-sql-python-connector가 Docker에서 import 실패

**상태**: ✅ 최신 (2025-11-01)

**버전**: 2.0|------|------|------|- **다음**: Auth Proxy 또는 IAM 설정 필요


| Cloud Run | ✅ 배포 완료 | revision 00045, 정상 작동 |

| VPC 연결 | ✅ 완료 | 10.8.0.0/28 범위 구성 |### requirements.txt

| Cloud SQL | ✅ 연결 완료 | Private IP 10.85.224.3 |```

| Auth Proxy | ✅ 작동 중 | localhost:3306 수신 |fastapi==0.115.5

| 데이터베이스 | ✅ 준비 완료 | 6개 테이블, 자동 생성 |uvicorn[standard]==0.30.0

| API 엔드포인트 | ✅ 작동 중 | health, db, tables 확인됨 |sqlalchemy>=2.0

| Makeshop 연동 | 🔄 준비 중 | API 클라이언트 구현 완료 |pymysql==1.1.1

cloud-sql-python-connector[pymysql]>=1.6.0  # 추가됨

## 🚀 다음 단계pydantic-settings==2.5.0

email-validator==2.2.0

### 1️⃣ Makeshop API 실제 연동 확인requests==2.32.3

- [ ] API 키 및 라이센스 키 유효성 검증python-dotenv==1.0.1

- [ ] API 응답 형식 분석 (JSON vs HTML)```

- [ ] 실제 상품 데이터 동기화 테스트

### Dockerfile

### 2️⃣ 데이터 동기화 로직 구현- **상태**: cloud-sql-proxy 미설정

- [ ] 초기 상품 동기화 (`POST /sync/makeshop/products`)- **필요**: 다음 수정 사항 적용

- [ ] 초기 카테고리 동기화 (`POST /sync/makeshop/categories`)  ```dockerfile

- [ ] 초기 주문 동기화 (`POST /sync/makeshop/orders`)  # cloud-sql-proxy 다운로드 추가

- [ ] 변경사항 감지 및 증분 동기화  RUN curl -o /cloud-sql-proxy https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64

  RUN chmod +x /cloud-sql-proxy

### 3️⃣ 성능 및 안정성 개선  

- [ ] 동기화 작업 스케줄링 (APScheduler)  # entrypoint 수정하여 proxy와 uvicorn 함께 실행

- [ ] 에러 처리 및 재시도 로직  ```

- [ ] 로깅 및 모니터링

- [ ] 단위 테스트 및 통합 테스트## 🔗 관련 리소스



### 4️⃣ 프로덕션 배포 준비- **Cloud Run Service**: babba-api (asia-northeast3)

- [ ] 환경 변수 보안화 (Secret Manager)- **Cloud SQL Instance**: babba-db

- [ ] CloudSQL IAM 권한 최적화  - Private IP: 10.85.224.3

- [ ] Cloud Logging 구성  - Public IP: 34.22.93.96 (임시 활성화됨)

- [ ] Cloud Monitoring 알림 설정- **GCP Project**: astute-window-472313-g9

- **VPC Connector**: babba-connector

## 🔐 환경 변수

## 📊 아키텍처 다이어그램

```bash

# Cloud SQL```

CLOUD_SQL_INSTANCE=astute-window-472313-g9:asia-northeast3:babba-db┌─────────────────────────────────────────┐

DB_USER=root│         Cloud Run                       │

DB_PASSWORD=*** (설정됨)│     (babba-api service)                 │

DB_NAME=babba│  ┌─────────────────────────────────┐   │

│  │  FastAPI Application            │   │

# Makeshop│  │  - /health                      │   │

MAKESHOP_API_KEY=Yzg3MGRmM2ZiYzRhNmU2MmE1MTU0NzAyNjlmZGY4MTQ=│  │  - /health/db                   │   │

MAKESHOP_SHOP_ID=ba9e9e655550c14ab3fc6d778bcba33b│  │  - /sync/makeshop/*             │   │

MAKESHOP_API_URL=https://api.makeshop.co.kr│  └─────────────────────────────────┘   │

MAKESHOP_API_TIMEOUT=10└──────────────┬──────────────────────────┘

```               │

        ┌──────▼──────┐

## 📝 주요 변경사항        │ VPC         │

        │ Connector   │

### Dockerfile        │10.8.0.0/28  │

- Cloud SQL Auth Proxy 바이너리 추가        └──────┬──────┘

- entrypoint에서 proxy와 uvicorn을 함께 실행               │

- `-instances=<INSTANCE>:tcp:127.0.0.1:3306` 파라미터 사용               │ Private IP

               │ 10.85.224.3

### database.py      ┌────────▼────────────────┐

- 연결 host를 127.0.0.1 (localhost)로 설정      │   Cloud SQL (MySQL)     │

- Auth Proxy 통해 Cloud SQL 접근      │   - babba (database)    │

      │   - root user (권한설정필요) │

### makeshop_service.py      └─────────────────────────┘

- Shopkey/Licensekey 헤더 기반 인증```

- /list/open_api.html 엔드포인트 사용

- JSON 및 텍스트 응답 처리## ✅ 체크리스트 (내일)



## ✅ 테스트 결과- [ ] Cloud SQL Auth Proxy 설치 (Dockerfile)

- [ ] database.py 수정 (localhost:3306 연결)

### DB 연결 테스트- [ ] Docker 빌드 (--no-cache)

```bash- [ ] Docker push

$ curl https://babba-api-1024083500192.asia-northeast3.run.app/health/db- [ ] Cloud Run 배포

{"status":"healthy","database":"connected"}- [ ] /health/db 엔드포인트 테스트

```- [ ] /database/tables 엔드포인트 테스트



### 테이블 조회 테스트## 💡 참고 사항

```bash

$ curl https://babba-api-1024083500192.asia-northeast3.run.app/database/tables1. **현재 배포 revision**: babba-api-00036-flg

{2. **이전 시도**:

  "status": "success",   - root@% 비밀번호 설정 ✓

  "tables": [   - vpc_user 생성 ✓

    {"name": "categories", ...},   - URL 인코딩 적용 ✓

    {"name": "order_items", ...},3. **정상 작동 확인**:

    {"name": "orders", ...},   - /health 엔드포인트: ✅ 작동

    {"name": "partners", ...},   - /health/db 엔드포인트: ❌ DB 연결 실패

    {"name": "products", ...},

    {"name": "users", ...}## 🚀 최종 목표

  ],

  "total": 61. DB 연결 성공 (`/health/db` 통과)

}2. Makeshop API 동기화 엔드포인트 테스트

```3. 프로덕션 배포


## 📦 배포 정보

- **Docker Image**: asia-northeast3-docker.pkg.dev/.../babba-api:latest
- **Digest**: sha256:f33fc3912bd...
- **Region**: asia-northeast3
- **Memory**: 256Mi
- **CPU**: 1 vCPU
- **Max Instances**: 100

## 🎯 전체 진행률

- 인프라 구성: **100%** ✅
- 데이터베이스: **100%** ✅
- API 기본 기능: **100%** ✅
- Makeshop 통합: **50%** 🔄
- 프로덕션 준비: **20%** 📋

**전체 완료율: ~67% (2/3)**
