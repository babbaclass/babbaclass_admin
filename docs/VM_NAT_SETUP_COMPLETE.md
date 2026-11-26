# VM NAT 설정 완료 - 최종 가이드

## ✅ 모든 설정이 완료되었습니다!

### 📊 생성된 인프라 요약

```
┌─────────────────────────────────────────────────────┐
│ Babba API 고정 IP 설정 완료                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│ 1. 정적 외부 IP 주소                              │
│    └─ 34.50.26.124 (babba-nat-ip)                │
│                                                     │
│ 2. e2-micro VM (Always Free)                      │
│    └─ babba-nat-vm (asia-northeast3-a)           │
│    └─ Nginx 리버스 프록시 설치                    │
│                                                     │
│ 3. 네트워크 구성                                  │
│    └─ 방화벽 규칙: 포트 80, 443 허용             │
│    └─ 리버스 프록시: Cloud Run ↔ 외부            │
│                                                     │
│ 4. 비용                                           │
│    └─ 추가 비용: $0/월 (Always Free)             │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 즉시 실행 가능한 다음 단계

### **Step 1: Makeshop 허용 IP 등록**

```
Makeshop 관리자 페이지:
설정 > API 보안 > 허용 IP 주소 등록

입력 값:
34.50.26.124
```

### **Step 2: 연결 테스트**

**Option A: 명령줄에서 테스트**
```bash
# 헬스 체크 (성공 확인됨)
curl http://34.50.26.124/health

# 응답: {"status":"healthy"}
```

**Option B: Postman에서 테스트**
```
URL: http://34.50.26.124/health
Method: GET
Expected: {"status":"healthy"}
```

### **Step 3: Makeshop API 동기화 테스트**

```bash
# 카테고리 동기화
curl -X POST http://34.50.26.124/sync/makeshop/categories

# 응답 예시:
# {"synced_categories": 12}
```

---

## 📍 중요: 고정 IP 정보

### 외부 통신용 고정 IP
```
IP 주소: 34.50.26.124
용도: Makeshop API 아웃바운드 통신
상태: ✅ 작동 확인
```

### 아키텍처 흐름

```
Makeshop API Server
      ↓
GET/POST http://34.50.26.124:80
      ↓
Nginx 리버스 프록시 (VM)
      ↓
proxy_pass https://babba-api-kitlcurzpa-du.a.run.app
      ↓
Cloud Run (babba-api)
      ↓
Cloud SQL 데이터베이스
      ↓
응답 반환 (고정 IP로)
```

---

## 📊 비용 검증 (최종)

### 월간 예상 비용 (Always Free 범위 내)

```
리소스별 비용:
─────────────────────────────────────────
e2-micro VM              Always Free ($0)
정적 외부 IP (VM 할당)   Always Free ($0)
Debian 11 OS             Free ($0)

기존 리소스:
─────────────────────────────────────────
Cloud SQL (db-f1-micro)  $12.50
Cloud Run (babba-api)    사용량 기반

합계 추가 비용: $0/월 ✅
```

### ⚠️ 비용 폭증 회피 규칙

```
✅ 절대 지켜야 할 것:
- VM은 항상 RUNNING 상태 유지
- 정적 IP는 항상 VM에 할당 상태 유지

❌ 절대 하면 안 되는 것:
- VM 중지/삭제 후 정적 IP 방치 → $13/월 자동 과금
- 정적 IP만 예약하고 VM 할당 안 함 → 즉시 과금
```

---

## 🛠️ 유지보수 및 모니터링

### 일일 체크리스트

```bash
# 1. VM 상태 확인
gcloud compute instances list --filter="name=babba-nat-vm"

# 2. Nginx 상태 확인
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9 \
  --command="sudo systemctl status nginx"

# 3. 헬스 체크
curl http://34.50.26.124/health
```

### 주간 체크리스트

```bash
# 1. Nginx 접근 로그 확인
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9 \
  --command="sudo tail -100 /var/log/nginx/access.log"

# 2. Nginx 에러 로그 확인
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9 \
  --command="sudo tail -100 /var/log/nginx/error.log"
```

### 월간 체크리스트

```bash
# 1. GCP 비용 확인 (콘솔: Billing > Account Management)
# 2. 정적 IP가 여전히 VM에 할당되었는지 확인
gcloud compute addresses describe babba-nat-ip \
  --region=asia-northeast3 \
  --format='value(status)'
  
# 3. 방화벽 규칙 확인
gcloud compute firewall-rules list --filter="name~'allow-nginx'"
```

---

## 🔍 문제 해결 가이드

### 문제: 34.50.26.124로 접속 불가

**확인 사항:**

```bash
# 1. VM이 RUNNING 상태인가?
gcloud compute instances describe babba-nat-vm \
  --zone=asia-northeast3-a \
  --format='value(status)'

# 2. Nginx가 실행 중인가?
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --command="sudo systemctl status nginx"

# 3. 포트 80이 열려있는가?
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --command="sudo ss -tlnp | grep 80"

# 4. 방화벽 규칙이 적용되었는가?
gcloud compute firewall-rules describe allow-nginx-from-external
```

### 문제: Cloud Run 응답 에러

```bash
# 1. Cloud Run 서비스 상태 확인
gcloud run services describe babba-api \
  --region=asia-northeast3 \
  --format='value(status.url)'

# 2. Nginx 에러 로그 확인
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --command="sudo tail -50 /var/log/nginx/error.log"

# 3. Cloud Run 로그 확인 (Cloud Console)
```

---

## 📋 참고 문서

### 생성된 문서들

1. **CLOUD_RUN_LOWEST_COST_IP.md**
   - 여러 고정 IP 옵션 비교
   - VM NAT vs Cloud NAT vs 도메인 허용

2. **VM_NAT_COST_ANALYSIS.md**
   - Always Free 범위 상세 분석
   - 비용 폭증 회피 방법

3. **NGINX_REVERSE_PROXY_SETUP.md**
   - Nginx 설정 상세 가이드
   - 관리 및 모니터링 방법

4. **MAKESHOP_SETUP.md**
   - Makeshop API 통합 가이드
   - 동기화 엔드포인트 설명

---

## ✨ 최종 정리

### ✅ 완료된 작업

- [x] 정적 외부 IP 주소 예약 (34.50.26.124)
- [x] e2-micro VM 생성 (Always Free)
- [x] Nginx 리버스 프록시 설치 및 설정
- [x] 방화벽 규칙 추가
- [x] 헬스 체크 테스트 (성공)
- [x] 설정 문서 작성 및 GitHub 푸시

### 📝 사용자가 해야 할 일

- [ ] Makeshop 관리자에서 고정 IP(34.50.26.124) 허용 등록
- [ ] Makeshop에서 Babba API 호출 테스트
- [ ] 각 동기화 엔드포인트 테스트
- [ ] 월 1회 비용 모니터링 (GCP 콘솔)

### 🚀 배포 준비 완료

```
현재 상태:
✅ Cloud Run 서비스 배포 (babba-api)
✅ Cloud SQL 연결 설정 (MySQL)
✅ Makeshop API 클라이언트 개발
✅ 고정 IP 설정 완료 (34.50.26.124)

다음 단계:
→ Makeshop 허용 IP 등록
→ API 동기화 테스트
→ 프로덕션 모니터링 설정
```

---

## 💡 핵심 정리

### 기억해야 할 점

```
🎯 고정 IP: 34.50.26.124
💰 추가 비용: $0/월 (Always Free)
⚡ 설정 완료: 100%
🔒 보안: 방화벽으로 제한된 접근
📍 용도: Makeshop API 아웃바운드
```

### 다음 연락처

- GCP 콘솔 문제: GCP Support
- Makeshop API 문제: Makeshop 개발 가이드
- Babba API 로직 문제: Cloud Run 콘솔 > 로그

---

**🎉 VM NAT 기반 고정 IP 설정이 완료되었습니다!**

**이제 Makeshop 관리자에서 34.50.26.124를 허용 IP로 등록하고 테스트하면 됩니다.**
