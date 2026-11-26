# 📚 babba-api Documentation Index

**최종 업데이트**: 2025년 11월 2일

---

## 🎯 문서 구조

babba-api 프로젝트의 모든 가이드 및 기술 문서를 한 곳에서 확인할 수 있습니다.

### 📁 docs/ 폴더 구조

```
docs/
├── INDEX.md                          # 이 파일 (문서 인덱스)
├── LOCAL_BUILD_GUIDE.md              # ⭐ 로컬 Docker 빌드 가이드
├── SQLADMIN_INTEGRATION.md           # ⭐ sqladmin + SA 2.0 통합 가이드
├── ADMIN_PANEL.md                    # Admin 패널 사용 가이드
├── DEPLOYMENT_GUIDE.md               # Cloud Run 배포 가이드
└── README_STRUCTURE.md               # 프로젝트 구조 설명
```

---

## 🚀 빠른 네비게이션

### 🟢 신규 사용자 (5분)

**시작하기 전에 필요한 것:**
- [ ] Docker 설치
- [ ] gcloud CLI 설치 및 인증

**따라할 가이드:**

1. **[LOCAL_BUILD_GUIDE.md](./LOCAL_BUILD_GUIDE.md)** (5분)
   - 로컬에서 바로 시작하기
   - `./local-run.sh` 한 줄 실행
   - 개발 환경 세팅

2. **[ADMIN_PANEL.md](./ADMIN_PANEL.md)** (3분)
   - Admin 패널 접근 및 사용
   - 주의: 현재 기본 모드 (ModelView 폴백)

---

### 🟡 배포 준비 (20분)

**진행 순서:**

1. 로컬 빌드 완료: [LOCAL_BUILD_GUIDE.md](./LOCAL_BUILD_GUIDE.md)
2. sqladmin 통합 이해: [SQLADMIN_INTEGRATION.md](./SQLADMIN_INTEGRATION.md)
3. Cloud Run 배포: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

**결과:**
- ✅ 로컬 개발 환경 구축
- ✅ Admin 패널 이해
- ✅ Cloud Run 배포 준비

---

### 🔴 전문가 (상세 내용)

**깊이 있는 이해:**

1. [SQLADMIN_INTEGRATION.md](./SQLADMIN_INTEGRATION.md)
   - sqladmin 0.21.0 + SQLAlchemy 2.0.35 통합
   - pk_columns 이슈 원인 분석
   - Graceful fallback 메커니즘

2. [LOCAL_BUILD_GUIDE.md](./LOCAL_BUILD_GUIDE.md)
   - 스크립트 내부 동작 원리
   - 캐시 최적화 전략
   - 고급 사용법

3. [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
   - Cloud Run 설정 상세
   - 비용 최적화
   - 모니터링 설정

---

## 📖 전체 문서 목록

### 🆕 최신 추가 문서 (2025-11-02)

| 문서 | 설명 | 소요시간 | 링크 |
|------|------|---------|------|
| **LOCAL_BUILD_GUIDE.md** | 로컬 Docker 빌드 및 실행 가이드 (스크립트 포함) | 5분 | [📄](./LOCAL_BUILD_GUIDE.md) |
| **SQLADMIN_INTEGRATION.md** | sqladmin + SQLAlchemy 2.0 통합 상세 가이드 | 10분 | [📄](./SQLADMIN_INTEGRATION.md) |

### 🔧 개발 가이드

| 문서 | 설명 | 상태 |
|------|------|------|
| LOCAL_BUILD_GUIDE.md | 로컬 환경 구축 및 Docker 빌드 | ✅ Active |
| ADMIN_PANEL.md | Admin 패널 사용 및 관리 | ✅ Active |
| DEPLOYMENT_GUIDE.md | Cloud Run 배포 절차 | ✅ Active |
| SQLADMIN_INTEGRATION.md | sqladmin 통합 및 이슈 해결 | ✅ Active |

---

## 🎓 주제별 학습 경로

### 경로 1: 로컬 개발 시작

```
시작
  ↓
Docker & gcloud 설치
  ↓
LOCAL_BUILD_GUIDE.md (로컬 빌드 및 실행)
  ↓
./local-run.sh 실행
  ↓
http://127.0.0.1:8080/ 접근
  ↓
API & Admin 패널 탐색
```

**예상 시간**: 5분  
**결과**: 로컬 개발 환경 준비 완료

---

### 경로 2: sqladmin 이해

```
시작
  ↓
SQLADMIN_INTEGRATION.md 읽기
  ├─ sqladmin + SQLAlchemy 2.0 호환성
  ├─ ModelView 클래스 7개 구현
  ├─ pk_columns 이슈 분석
  └─ Graceful fallback 메커니즘
  ↓
app/admin.py 코드 검토
  ↓
LOCAL_BUILD_GUIDE.md 로그 확인
```

**예상 시간**: 10분  
**결과**: sqladmin 통합 이해

---

### 경로 3: Cloud Run 배포

```
시작
  ↓
로컬 빌드 확인 (LOCAL_BUILD_GUIDE.md)
  ↓
SQLADMIN_INTEGRATION.md 이해
  ↓
DEPLOYMENT_GUIDE.md 실행
  ├─ Docker 빌드
  ├─ Artifact Registry 푸시
  └─ Cloud Run 배포
  ↓
https://babba-api-*.run.app 접근
```

**예상 시간**: 20분  
**결과**: Cloud Run 배포 완료

---

### 경로 4: Cloud Scheduler & Cloud Tasks 이해

```
시작
  ↓
CLOUD_SCHEDULER_CLOUD_TASKS_FLOW.md 읽기
  ├─ Cloud Scheduler: 시간 기반 작업 스케줄
  ├─ Cloud Tasks: 비동기 작업 큐
  ├─ 통합 아키텍처
  └─ Makeshop 동기화 실제 동작
  ↓
setup-cloud-scheduler.sh 이해
  ↓
Cloud Scheduler Job 생성 (선택사항)
```

**예상 시간**: 15분  
**결과**: 자동화된 배경 작업 이해

---

## 🔍 자주 찾는 질문별 문서

### Q: 어디서 시작해야 하나?
**A**: [LOCAL_BUILD_GUIDE.md](./LOCAL_BUILD_GUIDE.md) 참고  
→ `./local-run.sh` 명령어로 바로 시작

### Q: Admin 패널이 작동하지 않는다
**A**: [ADMIN_PANEL.md](./ADMIN_PANEL.md) 참고  
→ 현재 기본 모드 (ModelView 폴백) - 정상 동작

### Q: ModelView가 안 나타난다
**A**: [SQLADMIN_INTEGRATION.md](./SQLADMIN_INTEGRATION.md) 참고  
→ sqladmin 0.21.0의 알려진 이슈 (0.22.0 대기 중)

### Q: 로컬 빌드는 어떻게?
**A**: [LOCAL_BUILD_GUIDE.md](./LOCAL_BUILD_GUIDE.md) 참고  
→ `./local-run.sh` 스크립트 사용

### Q: Cloud Run 배포는?
**A**: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) 참고  
→ `./deploy.sh` 또는 `./build-and-deploy.sh` 사용

### Q: Cloud Scheduler와 Cloud Tasks의 차이?
**A**: [CLOUD_SCHEDULER_CLOUD_TASKS_FLOW.md](./CLOUD_SCHEDULER_CLOUD_TASKS_FLOW.md) 참고  
→ Scheduler는 시간 관리, Tasks는 작업 큐 관리

### Q: Makeshop 동기화는 어떻게 작동하나?
**A**: [CLOUD_SCHEDULER_CLOUD_TASKS_FLOW.md](./CLOUD_SCHEDULER_CLOUD_TASKS_FLOW.md) 참고  
→ 매일 09:50, 13:50 KST에 자동 실행

### Q: 성능 최적화?
**A**: [LOCAL_BUILD_GUIDE.md - 캐시 최적화](./LOCAL_BUILD_GUIDE.md#🔄-빌드-캐시-최적화) 참고

---

## 📊 상태 대시보드

### 기능 현황

| 기능 | 상태 | 참고 |
|------|------|------|
| ✅ FastAPI 기본 | Active | |
| ✅ SQLAlchemy 2.0 | Active | |
| ✅ Cloud SQL 연결 | Active | |
| ✅ Admin 기본 모드 | Active | |
| ⚠️ ModelView | Fallback | sqladmin 0.22.0 대기 |
| ✅ API 엔드포인트 | Active | |
| ✅ Swagger 문서 | Active | /docs/ |
| ✅ Cloud Run 배포 | Active | |
| ✅ 로컬 Docker 빌드 | Active | local-run.sh |
| ✅ Cloud Scheduler | Active | 매일 09:50, 13:50 KST |
| ✅ Cloud Tasks | Active | Makeshop 동기화 큐 |

### 배포 상태

| 환경 | 상태 | URL | 버전 |
|------|------|-----|------|
| Local | ✅ Running | http://127.0.0.1:8080 | Latest |
| Cloud Run | ✅ Running | https://babba-api-*.run.app | Latest |

---

## 🛠️ 도구 및 스크립트

### 주요 스크립트

| 스크립트 | 목적 | 사용법 |
|---------|------|--------|
| `local-run.sh` | 로컬 빌드 및 실행 | `./local-run.sh` |
| `deploy.sh` | Cloud Run 배포 | `./deploy.sh` |
| `build-and-deploy.sh` | 빌드 및 배포 (권장) | `./build-and-deploy.sh` |

### 개발 환경 변수

```bash
# .env (권장)
CLOUD_SQL_INSTANCE=astute-window-472313-g9:asia-northeast3:babba-db
DB_USER=root
DB_PASSWORD=***
DB_NAME=babba
LOCAL_PORT=8080
```

---

## 📝 최근 변경사항

### 2025-11-02

#### ✅ 추가됨
- `local-run.sh` 스크립트 작성
- 로컬 Docker 빌드 자동화
- `LOCAL_BUILD_GUIDE.md` 문서 생성
- `SQLADMIN_INTEGRATION.md` 문서 생성
- `INDEX.md` (이 파일) 생성

#### 📋 개선됨
- README.md 로컬 빌드 섹션 확장
- 문서 구조 정리

#### 🐛 수정됨
- 없음

---

## 🔗 문서 간 링크

### 빠른 참조

- 🏠 [README.md](../README.md) - 프로젝트 개요
- 🚀 [LOCAL_BUILD_GUIDE.md](./LOCAL_BUILD_GUIDE.md) - 로컬 빌드
- 🔧 [SQLADMIN_INTEGRATION.md](./SQLADMIN_INTEGRATION.md) - sqladmin 통합
- 📊 [ADMIN_PANEL.md](./ADMIN_PANEL.md) - Admin 사용법
- 🌐 [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - 배포
- ⏰ [CLOUD_SCHEDULER_CLOUD_TASKS_QUICK.md](./CLOUD_SCHEDULER_CLOUD_TASKS_QUICK.md) - 자동화 빠른 가이드 (5분)
- 📋 [CLOUD_SCHEDULER_CLOUD_TASKS_FLOW.md](./CLOUD_SCHEDULER_CLOUD_TASKS_FLOW.md) - 상세 기술 문서

---

## 💡 팁 및 트러블슈팅

### 빠른 해결책

**문제**: Docker 포트 충돌
```bash
# 해결
export LOCAL_PORT=9090
./local-run.sh
```

**문제**: Cloud SQL 연결 실패
```bash
# 해결
gcloud auth application-default login --no-launch-browser
./local-run.sh
```

**문제**: 빌드가 느림
```bash
# 해결: 캐시 활용 (첫 빌드 후 30초)
./local-run.sh
```

더 자세한 해결책은 [LOCAL_BUILD_GUIDE.md](./LOCAL_BUILD_GUIDE.md#🐛-문제-해결) 참고

---

## 📞 지원 및 문의

### 문서 오류 또는 개선 사항
1. 해당 문서 파일 수정 요청
2. Git commit으로 변경사항 기록

### 기술 지원
- sqladmin 이슈: [SQLADMIN_INTEGRATION.md](./SQLADMIN_INTEGRATION.md) 참고
- 배포 문제: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) 참고
- 로컬 빌드 문제: [LOCAL_BUILD_GUIDE.md](./LOCAL_BUILD_GUIDE.md) 참고

---

## 📈 다음 단계

1. **로컬 빌드 시작** → [LOCAL_BUILD_GUIDE.md](./LOCAL_BUILD_GUIDE.md)
2. **Admin 패널 탐색** → [ADMIN_PANEL.md](./ADMIN_PANEL.md)
3. **sqladmin 이해** → [SQLADMIN_INTEGRATION.md](./SQLADMIN_INTEGRATION.md)
4. **배포 준비** → [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)

---

**작성일**: 2025년 11월 2일  
**최종 업데이트**: 2025년 11월 2일  
**상태**: ✅ Active  
**관리자**: Development Team
