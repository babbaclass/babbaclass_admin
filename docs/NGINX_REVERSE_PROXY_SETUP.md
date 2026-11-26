# Nginx 리버스 프록시를 통한 Cloud Run 고정 IP 설정

## 📋 설정 완료 상태

### ✅ 생성된 리소스

```
1. 정적 외부 IP: 34.50.26.124
   - 주소 이름: babba-nat-ip
   - 상태: IN_USE (VM에 할당됨)
   - 비용: Always Free (VM 할당 상태)

2. e2-micro VM: babba-nat-vm
   - 머신 타입: e2-micro (Always Free)
   - 상태: RUNNING
   - OS: Debian 11
   - 외부 IP: 34.50.26.124 (고정)
   - 내부 IP: 10.178.0.2
   - 영역: asia-northeast3-a
   - 비용: Always Free (월 730시간)

3. Nginx 리버스 프록시
   - 상태: running (active)
   - 포트: 80 (HTTP), 443 (HTTPS)
   - 용도: Cloud Run → 외부 통신 프록시
```

---

## 🔄 작동 원리

### 네트워크 흐름

```
┌─────────────────────────────────────────────────────┐
│ Makeshop API                                        │
│ (babba-nat-ip: 34.50.26.124로 요청)                │
└────────────────────────┬────────────────────────────┘
                         │
                         ▼
         ┌───────────────────────────────┐
         │ Nginx 리버스 프록시           │
         │ (VM: 34.50.26.124:80/443)    │
         │ - 요청 수신                   │
         │ - Cloud Run으로 포워드        │
         │ - 응답 수신 후 반환          │
         └────────────┬──────────────────┘
                      │
                      ▼
      ┌──────────────────────────────┐
      │ Cloud Run                    │
      │ babba-api-kitlcurzpa-du.a   │
      │ .run.app (동적 IP)           │
      └──────────────────────────────┘
                      ▼
      ┌──────────────────────────────┐
      │ Cloud SQL Database           │
      │ (MySQL 8.0.41)               │
      └──────────────────────────────┘
```

### 요청 흐름 (예시: /sync/makeshop/products)

```
1. Makeshop API 서버
   → POST http://34.50.26.124/sync/makeshop/products
   
2. Nginx 리버스 프록시 (VM 수신)
   → proxy_pass https://babba-api-kitlcurzpa-du.a.run.app
   
3. Cloud Run 처리
   → Database에서 제품 데이터 동기화
   
4. Nginx 응답 반환
   → {"synced_products": 45, ...}
   
5. Makeshop API 수신 완료
```

---

## ✅ 동작 확인

### 헬스 체크 테스트 (성공)

```bash
$ curl -s http://34.50.26.124/health
{"status":"healthy"}
```

✅ **Nginx 프록시가 정상 작동합니다!**

---

## 🛠️ VM 및 Nginx 관리

### 로그 확인

```bash
# Nginx 접근 로그
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9 \
  --command="sudo tail -f /var/log/nginx/access.log"

# Nginx 에러 로그
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9 \
  --command="sudo tail -f /var/log/nginx/error.log"
```

### 상태 확인

```bash
# Nginx 상태
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9 \
  --command="sudo systemctl status nginx"

# 포트 확인
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9 \
  --command="sudo ss -tlnp | grep nginx"
```

### Nginx 설정 재로드

```bash
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9 \
  --command="sudo nginx -t && sudo systemctl reload nginx"
```

---

## 📊 비용 분석

### 월간 예상 비용 (최저)

```
구성:
┌──────────────────────────────┐
│ e2-micro VM (Always Free)    │ $0/월
│ + 정적 외부 IP (VM 할당)     │ $0/월
│ + 기존 Cloud SQL (db-f1)     │ $12.50/월
│ + 기존 Cloud Run (babba-api) │ 사용량 기반
├──────────────────────────────┤
│ 합계 추가 비용               │ $0/월
│ 총 월간 예상 비용            │ $12.50+
└──────────────────────────────┘
```

**추가 과금 없음! 모두 Always Free 범위 내입니다.** ✅

---

## 🎯 다음 단계: Makeshop 허용 IP 등록

### 1️⃣ Makeshop 관리자 페이지 접속

```
https://[makeshop-domain]/admin/
```

### 2️⃣ API 보안 설정

```
설정 > API 보안 > 허용 IP 등록
```

### 3️⃣ 고정 IP 등록

```
허용 IP 주소: 34.50.26.124
```

### 4️⃣ 저장 및 테스트

- Makeshop에서 babba-api 호출 테스트
- Cloud Run에서 `/makeshop/health` 응답 확인

---

## 🔧 Nginx 설정 파일 상세

### 위치
```
/etc/nginx/nginx.conf
```

### 주요 설정 항목

```nginx
# Cloud Run으로의 리버스 프록시
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    location / {
        # Cloud Run 대상
        proxy_pass https://babba-api-kitlcurzpa-du.a.run.app;
        
        # 헤더 설정
        proxy_set_header Host babba-api-kitlcurzpa-du.a.run.app;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 버퍼링 비활성화 (실시간 응답)
        proxy_buffering off;
        proxy_request_buffering off;
        
        # SSL 검증 비활성화
        proxy_ssl_verify off;
    }
}
```

---

## 🧹 정리: 리소스 삭제 (필요시)

### 안전하게 삭제하는 방법

```bash
# 1. Nginx 서비스 중지
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9 \
  --command="sudo systemctl stop nginx"

# 2. VM 삭제 (⚠️ 중요: 먼저 VM을 삭제해야 정적 IP도 함께 삭제됨)
gcloud compute instances delete babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9

# 3. 정적 IP 주소 삭제
gcloud compute addresses delete babba-nat-ip \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9

# 4. 방화벽 규칙 삭제
gcloud compute firewall-rules delete allow-nginx-from-external \
  --project=astute-window-472313-g9
```

⚠️ **주의**: 정적 IP를 VM 없이 방치하면 $13/월의 과금이 발생합니다!

---

## 📝 최종 체크리스트

### 설정 확인

- [x] e2-micro VM 생성 (Always Free)
- [x] 정적 IP 할당 (34.50.26.124)
- [x] Nginx 리버스 프록시 설치
- [x] Nginx 설정 파일 적용
- [x] 방화벽 규칙 추가
- [x] 헬스 체크 테스트 성공

### 사용 단계

- [ ] Makeshop 관리자에서 허용 IP 등록 (34.50.26.124)
- [ ] Makeshop에서 Babba API 호출 테스트
- [ ] 동기화 엔드포인트 테스트 (/sync/makeshop/*)
- [ ] 에러 로그 모니터링

### 유지보수

- [ ] 월 1회 비용 확인 (GCP 콘솔)
- [ ] 월 1회 Nginx 로그 확인
- [ ] 필요시 VM 업데이트 실행

---

## 🚀 완료!

**Nginx 리버스 프록시 기반 고정 IP 설정이 완료되었습니다!**

- 📍 **고정 IP**: 34.50.26.124
- 📊 **추가 비용**: $0/월 (Always Free)
- ⚡ **성능**: Nginx 리버스 프록시로 안정적 통신
- 🔒 **보안**: 방화벽 규칙으로 제한된 접근

**다음**: Makeshop에 위 고정 IP를 허용 IP로 등록하세요!
