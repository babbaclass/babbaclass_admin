# Cloud Run 고정 IP 주소 설정 가이드

## 🔍 개요

Cloud Run은 기본적으로 **동적 IP**를 사용합니다. 하지만 **Cloud NAT**을 사용하면 **고정 IP**로 나가는 아웃바운드 트래픽을 설정할 수 있습니다.

---

## 📊 Cloud Run IP 옵션 비교

| 항목 | 기본 (동적) | Cloud NAT (고정) |
|------|-----------|-----------------|
| **인바운드 IP** | 동적 (변함) | 동적 (변함) |
| **아웃바운드 IP** | 동적 (변함) | 고정 (안정적) |
| **Makeshop API 호출** | 동적 IP로 나감 | 고정 IP로 나감 |
| **비용** | 무료 | ~$32/월 (정적 IP + NAT) |
| **설정 복잡도** | 간단 | 중간 |

---

## 🎯 고정 IP가 필요한 이유

Makeshop API에서 **발신 IP를 화이트리스트**로 관리할 때:

```
현재 문제:
┌─────────────────┐
│ Cloud Run       │
│ (동적 IP)       │ ──→ Makeshop API
│ 34.143.72.2     │     (매번 다른 IP로 요청)
│ 34.143.73.2     │
│ 34.143.74.2     │
└─────────────────┘

해결책 (Cloud NAT):
┌─────────────────┐
│ Cloud Run       │
│ (고정 IP로)     │ ──→ Makeshop API
│ 203.0.113.10    │     (항상 같은 IP로 요청)
└─────────────────┘
```

---

## 🚀 Cloud NAT으로 고정 IP 설정하기

### 📋 전제 조건

- VPC (Virtual Private Cloud) - 기본값: `default`
- Cloud Router 생성 권한
- Compute Engine API 활성화

### ✅ Step 1: Compute Engine API 활성화

```bash
gcloud services enable compute.googleapis.com \
  --project=astute-window-472313-g9
```

### ✅ Step 2: 정적 IP 주소 예약

```bash
# 정적 IP 생성
gcloud compute addresses create babba-api-static-ip \
  --region=asia-northeast3 \
  --address-type=EXTERNAL \
  --project=astute-window-472313-g9

# 생성된 IP 확인
gcloud compute addresses describe babba-api-static-ip \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --format='value(address)'
```

**예상 출력:**
```
203.0.113.10
```

### ✅ Step 3: Cloud Router 생성

```bash
# Cloud Router 생성
gcloud compute routers create babba-router \
  --region=asia-northeast3 \
  --network=default \
  --project=astute-window-472313-g9
```

### ✅ Step 4: Cloud NAT 게이트웨이 설정

```bash
# NAT 규칙 추가
gcloud compute routers nats create babba-nat \
  --router=babba-router \
  --region=asia-northeast3 \
  --nat-all-subnet-ip-ranges \
  --auto-allocate-nat-external-ips \
  --project=astute-window-472313-g9
```

**또는 정적 IP 지정:**

```bash
# 예약한 정적 IP로 NAT 설정
gcloud compute routers nats create babba-nat \
  --router=babba-router \
  --region=asia-northeast3 \
  --nat-all-subnet-ip-ranges \
  --nat-external-ip-pool=babba-api-static-ip \
  --project=astute-window-472313-g9
```

### ✅ Step 5: Cloud Run을 VPC 커넥터에 연결

```bash
# VPC 커넥터 생성
gcloud compute networks vpc-access connectors create babba-connector \
  --region=asia-northeast3 \
  --subnet=default \
  --project=astute-window-472313-g9

# Cloud Run 서비스 업데이트
gcloud run services update babba-api \
  --vpc-connector=babba-connector \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --update-env-vars="VPC_ENABLED=true"
```

### ✅ Step 6: 고정 IP 확인

```bash
# 정적 IP 확인
gcloud compute addresses list \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9

# NAT 상태 확인
gcloud compute routers describe babba-router \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9
```

---

## 🔄 Cloud Run 아웃바운드 트래픽 흐름

### 설정 후 동작

```
Cloud Run (babba-api)
    ↓
VPC 커넥터 (babba-connector)
    ↓
Cloud Router (babba-router)
    ↓
Cloud NAT
    ↓
정적 IP로 나감 (203.0.113.10)
    ↓
Makeshop API
```

---

## 📝 Makeshop API 허용 IP 등록

고정 IP 설정 후:

### Makeshop 관리자 페이지

```
설정 > API 보안 > 허용 IP
─────────────────────────
203.0.113.10
```

**단 1개 IP만 등록하면 됩니다!** ✅

---

## 💰 비용 분석

### 월간 비용 추정

```
Cloud NAT 비용:
┌─────────────────────────────────────────┐
│ 정적 IP 예약: $2.50/월                  │
│ NAT 게이트웨이: $0.045/시간             │
│   = 0.045 × 730 = $32.85/월             │
│ 아웃바운드 트래픽: $0.12/GB             │
├─────────────────────────────────────────┤
│ 최소 월간 비용: ~$35/월                 │
│ (정적 IP + NAT 기본)                    │
│                                          │
│ 추가 아웃바운드 트래픽 기준:            │
│ 1GB/일 = 30GB/월 = +$3.60               │
│ 10GB/일 = 300GB/월 = +$36               │
└─────────────────────────────────────────┘

기존 비용:
┌─────────────────────────────────────────┐
│ babba-api (db-f1-micro): $12.50/월      │
│ 추가 NAT 비용: ~$35/월                  │
├─────────────────────────────────────────┤
│ 총 예상 월간 비용: ~$47.50/월           │
└─────────────────────────────────────────┘
```

---

## 🔧 고정 IP 설정 체크리스트

### 사전 점검
- [ ] Compute Engine API 활성화 확인
- [ ] gcloud CLI 설치 및 인증 완료

### 설정 단계
- [ ] 정적 IP 주소 예약 (`babba-api-static-ip`)
- [ ] Cloud Router 생성 (`babba-router`)
- [ ] Cloud NAT 게이트웨이 설정 (`babba-nat`)
- [ ] VPC 커넥터 생성 (`babba-connector`)
- [ ] Cloud Run 서비스 VPC 연결 (`--vpc-connector`)

### 검증
- [ ] 정적 IP 확인: `gcloud compute addresses list`
- [ ] NAT 상태 확인: `gcloud compute routers describe`
- [ ] Cloud Run 로그에서 VPC 연결 확인

### Makeshop 설정
- [ ] 허용 IP 등록 (정적 IP 주소)
- [ ] Makeshop API 테스트

---

## 🚨 주의사항

### 1️⃣ VPC 커넥터 생성 시간
- **첫 생성**: 10-15분 소요
- 생성 중 Cloud Run이 일시적으로 응답하지 않을 수 있음

### 2️⃣ 비용 증가
- 기존 $12.50/월 → 약 $47.50/월 (약 4배)
- 정적 IP가 정말 필요한지 검토 필수

### 3️⃣ 대체 방안 검토

**Cloud NAT 없이 고정 IP 효과 얻기:**

```
Makeshop API 측에서 도메인 허용:
─────────────────────────────────
babba-api-kitlcurzpa-du.a.run.app
```

이 방법이 더 저렴하고 간단합니다! ✅

---

## 📋 명령어 빠른 참조

### 모든 설정을 한 번에 하기

```bash
#!/bin/bash
PROJECT_ID="astute-window-472313-g9"
REGION="asia-northeast3"

# 1. 정적 IP 생성
gcloud compute addresses create babba-api-static-ip \
  --region=$REGION --project=$PROJECT_ID

# 2. Cloud Router 생성
gcloud compute routers create babba-router \
  --region=$REGION --network=default --project=$PROJECT_ID

# 3. Cloud NAT 생성
gcloud compute routers nats create babba-nat \
  --router=babba-router --region=$REGION \
  --nat-all-subnet-ip-ranges \
  --nat-external-ip-pool=babba-api-static-ip \
  --project=$PROJECT_ID

# 4. VPC 커넥터 생성
gcloud compute networks vpc-access connectors create babba-connector \
  --region=$REGION --subnet=default --project=$PROJECT_ID

# 5. Cloud Run 업데이트
gcloud run services update babba-api \
  --vpc-connector=babba-connector \
  --region=$REGION --project=$PROJECT_ID

echo "✅ 고정 IP 설정 완료"
```

### 정적 IP 확인

```bash
gcloud compute addresses describe babba-api-static-ip \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --format='value(address)'
```

### 설정 삭제 (되돌리기)

```bash
# VPC 커넥터 연결 해제
gcloud run services update babba-api \
  --no-vpc-connector \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9

# 리소스 삭제
gcloud compute routers nats delete babba-nat \
  --router=babba-router --region=asia-northeast3 --project=astute-window-472313-g9

gcloud compute routers delete babba-router \
  --region=asia-northeast3 --project=astute-window-472313-g9

gcloud compute networks vpc-access connectors delete babba-connector \
  --region=asia-northeast3 --project=astute-window-472313-g9

gcloud compute addresses delete babba-api-static-ip \
  --region=asia-northeast3 --project=astute-window-472313-g9
```

---

## 💡 권장 방향

### 🟢 가능한 경우: Makeshop 도메인 허용

```
Makeshop API 설정:
설정 > API 보안 > 허용 도메인
babba-api-kitlcurzpa-du.a.run.app
```

**장점:**
- 비용 증가 없음
- 설정 간단
- 유연한 IP 변경 대응

### 🟡 필수인 경우: Cloud NAT 설정

```
월간 비용: +$35
설정 시간: 20분
복잡도: 중간
```

---

## 🔗 참고 문서

- [Cloud NAT 문서](https://cloud.google.com/nat/docs)
- [VPC 커넥터 문서](https://cloud.google.com/run/docs/configuring/connecting-vpc)
- [Cloud Run 네트워킹](https://cloud.google.com/run/docs/networking)
- [정적 IP 예약](https://cloud.google.com/compute/docs/ip-addresses/reserve-static-external-ip-address)

---

## ❓ FAQ

**Q: Cloud NAT 설정 후 즉시 적용되나요?**  
A: 아니오, VPC 커넥터 생성에 10-15분 소요됩니다.

**Q: 정적 IP가 정말 고정되나요?**  
A: 예, 명시적으로 삭제하기 전까지 유지됩니다.

**Q: 비용을 절감할 수 있나요?**  
A: 네, Makeshop에서 도메인 허용이 가능하면 NAT 없이 진행하세요.

**Q: 기존 Cloud Run은 영향을 받나요?**  
A: VPC 커넥터 생성 중 brief하게 응답 지연이 있을 수 있습니다.

---

**작성일**: 2025년 10월 31일  
**상태**: ✅ 실행 가능
