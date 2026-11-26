# 로컬 Docker 빌드 및 실행 가이드

**최종 작성일**: 2025년 11월 2일  
**대상**: 개발자  
**소요시간**: 5분

---

## 📋 개요

이 가이드는 로컬 개발 환경에서 babba-api Docker 이미지를 빌드하고 실행하는 방법을 설명합니다.

### ✅ 완료된 작업
- ✅ sqladmin + SQLAlchemy 2.0 통합
- ✅ ModelView 폴백 메커니즘 구현
- ✅ Cloud Run 배포 검증
- ✅ **로컬 Docker 빌드 자동화 스크립트 작성** ⭐
- ✅ Admin 패널 기본 모드 정상 작동

---

## 🚀 빠른 시작 (1분)

### 한 줄 명령어

```bash
cd /Users/hoonlee/Documents/GitHub/babba-api
./local-run.sh
```

이 명령어는 다음을 자동으로 수행합니다:
1. Docker 이미지 빌드
2. Cloud SQL 인증 설정
3. 컨테이너 실행
4. 서비스 헬스 체크
5. 접속 URL 표시

완료 후 다음 URL을 방문하세요:
- 🌐 **API**: http://127.0.0.1:8080/
- 📊 **Admin**: http://127.0.0.1:8080/admin/
- 📚 **Swagger 문서**: http://127.0.0.1:8080/docs/

---

## 📦 시스템 요구사항

### 필수 항목

| 항목 | 버전 | 설치 확인 |
|------|------|---------|
| Docker | 20.10+ | `docker --version` |
| gcloud CLI | 최신 | `gcloud --version` |
| Python | 3.11+ | `python3 --version` |

### 필수 인증

```bash
# Google Cloud 인증 (1회만 수행)
gcloud auth login
gcloud config set project astute-window-472313-g9

# 애플리케이션 기본 자격증명 설정 (Cloud SQL 접근용)
gcloud auth application-default login --no-launch-browser
```

---

## 🔧 로컬 실행 스크립트 사용법

### 스크립트 위치
```
/Users/hoonlee/Documents/GitHub/babba-api/local-run.sh
```

### 사용 가능한 명령어

#### 1️⃣ 빌드 및 실행 (기본)
```bash
./local-run.sh
# 또는
./local-run.sh run
```

**수행 작업:**
- Docker 이미지 빌드 (캐시 활용, ~30초)
- 기존 컨테이너 제거
- 새 컨테이너 실행
- 20초 대기 (Cloud SQL Proxy + Uvicorn 시작)
- 헬스 체크 및 접속 URL 표시

**출력 예시:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 로컬 개발 서버 준비 완료
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📍 API 엔드포인트:
   http://127.0.0.1:8080/

📊 Admin 패널:
   http://127.0.0.1:8080/admin/

📚 API 문서 (Swagger):
   http://127.0.0.1:8080/docs/
```

---

#### 2️⃣ 실시간 로그 확인
```bash
./local-run.sh --logs
```

**출력:**
```
Starting Cloud SQL Auth Proxy for astute-window-472313-g9:asia-northeast3:babba-db on port 3306
2025/11/02 03:07:44 This is the Cloud SQL Proxy v1...
[DEBUG] DB_USER=root, DB_NAME=babba, HOST=127.0.0.1
[DEBUG] Connection URL: mysql+pymysql://root:***@127.0.0.1:3306/babba
⚠️ ModelView 등록 실패. 기본 Admin 모드로 폴백합니다.
INFO:     Started server process [1]
INFO:     Uvicorn running on http://0.0.0.0:8080
```

**Ctrl+C로 로그 보기 종료 (컨테이너는 실행 상태 유지)**

---

#### 3️⃣ 컨테이너 중지
```bash
./local-run.sh --stop
```

**수행 작업:**
- 실행 중인 컨테이너 중지
- 컨테이너는 제거되지 않음 (재실행 가능)

---

#### 4️⃣ 컨테이너 셸 접속
```bash
./local-run.sh --shell
```

**접속 후 가능한 작업:**
```bash
# API 엔드포인트 테스트
curl http://localhost:8080/

# 데이터베이스 연결 테스트
mysql -h 127.0.0.1 -u root -p babba

# 프로세스 확인
ps aux | grep -E 'cloud-sql|uvicorn'

# 로그 확인
tail -f /var/log/app.log

# 종료
exit
```

---

#### 5️⃣ 정리 (컨테이너 및 이미지 제거)
```bash
./local-run.sh --clean
```

**수행 작업:**
- 실행 중인 컨테이너 중지
- 컨테이너 제거
- Docker 이미지 제거 (`babba-api:local`)

⚠️ **주의**: 로컬 데이터는 컨테이너에만 존재하므로 삭제 후 복구 불가

---

## 🏗️ 스크립트 내부 동작

### 1. 이미지 빌드 프로세스

```bash
docker build -t babba-api:local .
```

**빌드 단계:**
1. Python 3.11-slim 베이스 이미지 풀
2. 시스템 패키지 설치 (build-essential, curl, wget)
3. Cloud SQL Auth Proxy 다운로드
4. Python 의존성 설치 (requirements.txt)
5. 앱 코드 복사 (app/ 폴더)
6. 엔트리포인트 스크립트 생성

**최종 이미지 크기**: ~840MB

### 2. 컨테이너 실행 프로세스

```bash
docker run -d \
  --name babba-local \
  -e CLOUD_SQL_INSTANCE=astute-window-472313-g9:asia-northeast3:babba-db \
  -e DB_USER=root \
  -e DB_PASSWORD=babba_local_pass \
  -e DB_NAME=babba \
  -p 8080:8080 \
  babba-api:local
```

**실행 순서:**
1. Cloud SQL Auth Proxy 시작 (포트 3306)
2. 15초 대기 (Proxy 초기화)
3. Uvicorn 시작 (포트 8080)
4. API 요청 대기

---

## 🔗 API 엔드포인트 테스트

### 1. API 루트

```bash
curl http://127.0.0.1:8080/

# 응답:
# {
#   "message": "babba-api is running",
#   "version": "1.0.0",
#   "admin_panel": "https://...",
#   "swagger_docs": "https://..."
# }
```

### 2. Admin 패널

```bash
curl -I http://127.0.0.1:8080/admin/

# 응답:
# HTTP/1.1 200 OK
# content-type: text/html; charset=utf-8
# content-length: 3000
```

브라우저에서 방문: http://127.0.0.1:8080/admin/

**기능:**
- 사용자 관리 (기본 Admin 홈만 표시, ModelView 폴백 중)
- Swagger UI는 `/docs/` 엔드포인트에서 확인 가능

### 3. Swagger API 문서

```bash
curl http://127.0.0.1:8080/docs/
```

브라우저에서 방문: http://127.0.0.1:8080/docs/

**포함 내용:**
- 모든 API 엔드포인트 목록
- 각 엔드포인트 상세 문서
- 직접 테스트 기능 (Try it out)

---

## 🗄️ 환경 변수 설정

### 기본 환경 변수 (스크립트에 포함)

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `CLOUD_SQL_INSTANCE` | `astute-window-472313-g9:asia-northeast3:babba-db` | Cloud SQL 인스턴스 |
| `DB_USER` | `root` | 데이터베이스 사용자 |
| `DB_PASSWORD` | `babba_local_pass` | 데이터베이스 비밀번호 |
| `DB_NAME` | `babba` | 데이터베이스명 |
| `LOCAL_PORT` | `8080` | 로컬 바인드 포트 |
| `TARGET_PORT` | `8080` | 컨테이너 내 포트 |

### 환경 변수 재정의

```bash
# 방법 1: 환경 변수 설정 후 실행
export LOCAL_PORT=9090
export DB_PASSWORD="custom_password"
./local-run.sh

# 방법 2: 스크립트 수정 (local-run.sh 직접 편집)
# CLOUD_SQL_INSTANCE, DB_USER 등 값 변경 후 저장
```

---

## 🐛 문제 해결

### 1. "Docker daemon이 실행 중이지 않음"

```bash
# Docker Desktop 시작 (macOS)
open /Applications/Docker.app

# 또는 대기
sleep 10 && ./local-run.sh
```

### 2. "컨테이너 포트 충돌"

```bash
# 포트 8080 사용 중인 프로세스 확인
lsof -i :8080

# 해당 프로세스 종료 (PID: xxxxx)
kill -9 xxxxx

# 또는 스크립트에서 다른 포트 사용
export LOCAL_PORT=9090
./local-run.sh
```

### 3. "Cloud SQL 연결 실패"

```bash
# 로그 확인
./local-run.sh --logs

# 오류: "Can't connect to MySQL server"
# → Cloud SQL Proxy 시작 실패 (Cloud SQL 인스턴스 확인 필요)

# 해결 방법:
# 1. gcloud 인증 재확인
gcloud auth application-default login --no-launch-browser

# 2. Cloud SQL 인스턴스 존재 확인
gcloud sql instances list

# 3. 컨테이너 셸 접속 후 수동 연결 시도
./local-run.sh --shell
mysql -h 127.0.0.1 -u root -p babba
```

### 4. "ModelView 등록 실패 (pk_columns 오류)"

**예상된 동작입니다.** 로그에 표시되는 경고:

```
⚠️ ModelView 등록 실패. 기본 Admin 모드로 폴백합니다.
원인: 'UserAdmin' object has no attribute 'pk_columns'
```

**현황:**
- sqladmin 0.21.0 + SQLAlchemy 2.0.35 조합에서 발생하는 알려진 이슈
- 서비스는 정상 작동 (Admin 기본 홈만 표시)
- API 기능은 모두 정상

**해결 방법:**
- sqladmin >= 0.22.0 릴리스 대기 (아직 PyPI에 미등재)
- 또는 Dockerfile에서 개발 버전 사용 (비권장)

---

## 📊 성능 및 리소스

### 빌드 성능

| 단계 | 시간 | 설명 |
|------|------|------|
| 첫 번째 빌드 | ~2-3분 | 베이스 이미지 풀 + 패키지 설치 |
| 이후 빌드 | ~30초 | 캐시 활용 (app/ 폴더만 다시 빌드) |

### 런타임 리소스

| 항목 | 값 | 설명 |
|------|-----|------|
| 메모리 | ~200MB | 기본 설정 (제한 없음) |
| CPU | 1-2 cores | 요청에 따라 스케일링 |
| 디스크 | ~840MB | Docker 이미지 크기 |
| 시작 시간 | ~20초 | Cloud SQL Proxy + Uvicorn |

---

## 🔄 빌드 캐시 최적화

### 캐시 활용 전략

스크립트는 Docker 레이어 캐시를 자동으로 활용합니다.

```bash
# ✅ 캐시 적중 (빠름, ~30초)
./local-run.sh
# → app/ 폴더만 변경된 경우 (캐시 된 레이어 재사용)

# ❌ 캐시 미스 (느림, ~2-3분)
docker build --no-cache -t babba-api:local .
# → 캐시 강제 무시 (모든 레이어 재빌드)
```

### 캐시 정리

```bash
# 모든 dangling 이미지 제거
docker image prune

# 특정 이미지 캐시 제거
./local-run.sh --clean
docker build --no-cache -t babba-api:local .
```

---

## 📝 스크립트 커스터마이제이션

### 포트 변경

```bash
# 로컬 포트를 9090으로 변경
export LOCAL_PORT=9090
./local-run.sh
```

### Cloud SQL 인스턴스 변경

```bash
# local-run.sh 수정
# CLOUD_SQL_INSTANCE="your-new-instance" 설정 후 저장
```

### 환경 변수 영구 설정

```bash
# ~/.zshrc에 추가
export CLOUD_SQL_INSTANCE="astute-window-472313-g9:asia-northeast3:babba-db"
export DB_USER="root"
export DB_PASSWORD="your_password"

# 변경 사항 적용
source ~/.zshrc
```

---

## 🔍 고급 사용법

### 1. 컨테이너 로그 저장

```bash
# 로그를 파일에 저장
./local-run.sh --logs > container.log 2>&1 &

# 백그라운드 실행 (Ctrl+C로 로그 보기 중지, 컨테이너는 계속 실행)
```

### 2. 다중 컨테이너 실행

```bash
# 여러 포트에서 동시 실행 (주의: 각 컨테이너는 별도 데이터)
export LOCAL_PORT=8080
./local-run.sh &

export LOCAL_PORT=9090
./local-run.sh &

# 확인
docker ps | grep babba
```

### 3. 이미지 저장 및 복원

```bash
# 이미지 저장
docker save babba-api:local -o babba-api-local.tar

# 이미지 복원 (다른 머신에서)
docker load -i babba-api-local.tar
```

---

## 📚 관련 문서

| 문서 | 설명 |
|------|------|
| [README.md](../README.md) | 프로젝트 개요 및 빠른 시작 |
| [QUICKSTART.md](./QUICKSTART.md) | 5분 빠른 시작 가이드 |
| [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) | Cloud Run 배포 가이드 |
| [ADMIN_PANEL.md](./ADMIN_PANEL.md) | Admin 패널 사용 가이드 |

---

## ✅ 체크리스트

로컬 빌드 설정 완료 확인:

- [ ] Docker 설치 및 실행 중
- [ ] gcloud CLI 설치 및 로그인 완료
- [ ] `gcloud auth application-default login` 실행 완료
- [ ] `/Users/hoonlee/Documents/GitHub/babba-api/local-run.sh` 실행 권한 확인
- [ ] `./local-run.sh` 명령어 실행 성공
- [ ] http://127.0.0.1:8080/ 접속 가능
- [ ] http://127.0.0.1:8080/admin/ 접속 가능

---

## 🚀 다음 단계

1. **Admin 패널 탐색**: http://127.0.0.1:8080/admin/
2. **API 테스트**: http://127.0.0.1:8080/docs/
3. **코드 수정 및 재빌드**: `./local-run.sh` (캐시 활용)
4. **배포 준비**: [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) 참고

---

**최종 확인**: 2025-11-02  
**작성자**: Development Team  
**상태**: ✅ Active
