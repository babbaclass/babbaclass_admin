# Cloud Run 고정 IP 최저 비용 설정 가이드

## 💰 비용 비교

### 옵션 비교표

| 옵션 | 월간 비용 | 복잡도 | 설정시간 |
|------|---------|--------|---------|
| **1. Makeshop 도메인 허용** | **$0** | 매우 낮음 | 5분 |
| **2. Makeshop IP 목록 허용** | **$0** | 낮음 | 5분 |
| **3. Cloud NAT + 정적 IP** | **$35/월** | 중간 | 30분 |
| **4. Compute Engine VM NAT** | **$3-5/월** | 높음 | 1시간 |

---

## 🟢 최저 비용 방법: **VM 기반 NAT** ($3-5/월)

현재 Cloud NAT($35/월)보다 **7배 저렴합니다!**

### 📊 비용 상세 분석

```
VM 기반 NAT 구성:
┌─────────────────────────────┐
│ Compute Engine VM (e2-micro) │ $3-5/월
│ - Always Free 범위 내        │
│ - 고정 IP 1개               │
├─────────────────────────────┤
│ NAT 게이트웨이 역할          │
│ - Cloud Run을 프록시        │
│ - 고정 IP로 아웃바운드      │
└─────────────────────────────┘

vs Cloud NAT: $35/월 (7배 비쌈!)
```

---

## 🚀 가장 저렴한 방법 구현: VM NAT ($3-5/월)

### ✅ Step 1: 정적 IP 주소 예약

```bash
# 정적 외부 IP 생성
gcloud compute addresses create babba-nat-ip \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9

# 생성된 IP 확인
gcloud compute addresses describe babba-nat-ip \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --format='value(address)'
```

**출력 예시:**
```
203.0.113.10
```

### ✅ Step 2: e2-micro VM 생성 (Always Free)

```bash
# e2-micro 인스턴스 생성
gcloud compute instances create babba-nat-vm \
  --zone=asia-northeast3-a \
  --machine-type=e2-micro \
  --network-interface=network-tier=PREMIUM,subnet=default,address=babba-nat-ip \
  --image-family=debian-11 \
  --image-project=debian-cloud \
  --metadata=enable-oslogin=true \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --project=astute-window-472313-g9
```

### ✅ Step 3: VM에 NAT 소프트웨어 설치

```bash
# VM에 SSH 접속
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9

# 다음 명령어를 VM에서 실행
cat << 'EOF' | sudo bash
#!/bin/bash

# 필요한 패키지 설치
apt-get update
apt-get install -y tinyproxy

# tinyproxy 설정
cat > /etc/tinyproxy/tinyproxy.conf << 'PROXY_CONFIG'
Port 8080
Listen 0.0.0.0
Timeout 600
DefaultErrorFile "/usr/share/tinyproxy/default.html"
StatFile "/usr/share/tinyproxy/stats.html"
LogFile "/var/log/tinyproxy/tinyproxy.log"
LogLevel Connect
MaxClients 100
MaxSpareServers 20
MinSpareServers 5
StartServers 10
ConnectPort 443
ConnectPort 80
PROXY_CONFIG

# tinyproxy 시작
systemctl restart tinyproxy
systemctl enable tinyproxy

echo "✅ NAT 프록시 설정 완료"
EOF
```

### ✅ Step 4: Cloud Run에서 VM 프록시 사용하도록 설정

Cloud Run의 환경변수에서 프록시 설정:

```bash
# VM의 IP 확인
VM_IP=$(gcloud compute addresses describe babba-nat-ip \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9 \
  --format='value(address)')

echo "프록시 IP: $VM_IP:8080"

# Cloud Run 환경변수 설정
gcloud run services update babba-api \
  --update-env-vars=HTTP_PROXY=http://${VM_IP}:8080,HTTPS_PROXY=http://${VM_IP}:8080 \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9
```

### ✅ Step 5: Makeshop API 허용 IP 등록

```
Makeshop 관리자 페이지:
설정 > API 보안 > 허용 IP
${VM_IP}  (예: 203.0.113.10)
```

---

## 🎯 또 다른 저렴한 방법: **Always Free 범위 최대 활용**

### 월간 예상 비용: **$0 (무료!)**

Google Cloud Always Free 범위:
- Compute Engine: 1개 e2-micro VM (월 730시간)
- 정적 외부 IP: 1개 (사용 중일 때만 무료)

### 제약사항

```
Always Free 범위:
✅ e2-micro: 월 730시간 (항상 켜야 함)
✅ 정적 IP: 1개 (VM에 할당되어 있을 때)
❌ 고정 비용 없음

주의:
- VM을 항상 실행 상태로 유지해야 함
- e2-micro 범위를 초과하면 과금 시작
```

---

## 📋 최저 비용 방법 비교

### 🥇 **1순위: Makeshop 도메인 허용** (추천)

```
월간 비용: $0
복잡도: 매우 낮음

구성:
Cloud Run (동적 IP) → Makeshop API
  └─ 도메인으로 허용

장점:
✅ 무료
✅ 가장 간단
✅ 설정 5분
✅ 유지보수 없음
```

**먼저 이 방법 시도를 강력 권장합니다!**

### 🥈 **2순위: VM NAT** ($3-5/월)

```
월간 비용: $3-5
복잡도: 중간

구성:
Cloud Run → e2-micro VM (고정 IP) → Makeshop API

장점:
✅ 매우 저렴
✅ 진정한 고정 IP
✅ 유연함

단점:
❌ VM 관리 필요
❌ 설정 복잡
❌ 모니터링 필요
```

### 🥉 **3순위: Cloud NAT** ($35/월)

```
월간 비용: $35
복잡도: 중간

장점:
✅ 관리형 서비스
✅ 고가용성

단점:
❌ 매우 비쌈 (7배)
```

---

## 🚀 권장 실행 순서

### **Step 1: Makeshop 도메인 허용 확인 (5분)**

```bash
# Makeshop 관리자 페이지 접속
# 설정 > API 보안 > 허용 규칙
# "도메인" 옵션이 있는지 확인
```

✅ **도메인 허용 가능** → 여기서 종료 (무료!)  
❌ **IP만 가능** → Step 2로 진행

### **Step 2: 현재 동적 IP 목록 등록 시도 (5분)**

```
Makeshop API 설정:
허용 IP: 34.143.72.2 ~ 34.143.79.2 (8개)
```

✅ **작동함** → 이대로 사용 (무료!)  
❌ **작동 안 함** → Step 3로 진행

### **Step 3: VM NAT 설정** ($3-5/월)

위의 "Step 1-5" 실행

---

## 🛠️ 빠른 설정: VM NAT 한 번에 하기

### 완전 자동화 스크립트

```bash
#!/bin/bash

PROJECT_ID="astute-window-472313-g9"
REGION="asia-northeast3"
ZONE="asia-northeast3-a"

echo "🚀 Cloud Run 고정 IP 설정 시작 (VM NAT 방식)"

# 1. 정적 IP 생성
echo "1️⃣ 정적 IP 생성..."
gcloud compute addresses create babba-nat-ip \
  --region=$REGION \
  --project=$PROJECT_ID

# IP 확인
NAT_IP=$(gcloud compute addresses describe babba-nat-ip \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format='value(address)')

echo "생성된 IP: $NAT_IP"

# 2. VM 생성
echo "2️⃣ e2-micro VM 생성..."
gcloud compute instances create babba-nat-vm \
  --zone=$ZONE \
  --machine-type=e2-micro \
  --network-interface=network-tier=PREMIUM,subnet=default,address=babba-nat-ip \
  --image-family=debian-11 \
  --image-project=debian-cloud \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --project=$PROJECT_ID

# 3. 시작 스크립트로 NAT 소프트웨어 설치
echo "3️⃣ NAT 소프트웨어 설치..."

STARTUP_SCRIPT=$(cat << 'SCRIPT'
#!/bin/bash
apt-get update
apt-get install -y tinyproxy
systemctl restart tinyproxy
systemctl enable tinyproxy
SCRIPT
)

gcloud compute instances add-metadata babba-nat-vm \
  --zone=$ZONE \
  --metadata=startup-script="$STARTUP_SCRIPT" \
  --project=$PROJECT_ID

# 4. Cloud Run 환경변수 설정
echo "4️⃣ Cloud Run 프록시 설정..."
gcloud run services update babba-api \
  --update-env-vars=HTTP_PROXY=http://${NAT_IP}:8080,HTTPS_PROXY=http://${NAT_IP}:8080 \
  --region=$REGION \
  --project=$PROJECT_ID

echo "✅ 설정 완료!"
echo "고정 IP: $NAT_IP"
echo "Makeshop에 이 IP를 허용 IP로 등록하세요."
```

### 스크립트 실행

```bash
# 스크립트 저장
cat > setup_vm_nat.sh << 'SCRIPT'
[위의 완전 자동화 스크립트 내용]
SCRIPT

# 실행 권한 부여
chmod +x setup_vm_nat.sh

# 실행
./setup_vm_nat.sh
```

---

## 📊 설정 후 상태 확인

### 정적 IP 확인

```bash
gcloud compute addresses list \
  --filter="name=babba-nat-ip" \
  --project=astute-window-472313-g9
```

### VM 상태 확인

```bash
gcloud compute instances list \
  --filter="name=babba-nat-vm" \
  --project=astute-window-472313-g9
```

### 프록시 작동 확인

```bash
# VM에 SSH 접속
gcloud compute ssh babba-nat-vm \
  --zone=asia-northeast3-a \
  --project=astute-window-472313-g9

# VM에서 프록시 상태 확인
sudo systemctl status tinyproxy
sudo tail -f /var/log/tinyproxy/tinyproxy.log
```

---

## 🧹 정리: 비용 최종 요약

### 총 월간 비용

```
이전 (동적 IP): $12.50
  babba-api (db-f1-micro): $12.50

VM NAT 설정 후:
  babba-api (db-f1-micro): $12.50
  e2-micro VM (정적 IP): Always Free ($0)
  ────────────────────────────
  총계: $12.50/월 (변화 없음!)
```

**VM이 Always Free 범위 내이면 추가 비용 0입니다!** 🎉

---

## 💡 최종 권장안

### 🟢 **최우선 순위:**

```
1. Makeshop에서 도메인 허용 가능한지 확인
   ✅ 가능 → 끝! (무료, 5분)
   ❌ 불가능 → 2번 진행
```

### 🟡 **차선책:**

```
2. VM NAT 설정 ($0, Always Free 범위)
   ✅ 고정 IP 확보
   ✅ 추가 비용 없음
   ✅ 설정 30분
```

### 🔴 **마지막 수단:**

```
3. Cloud NAT ($35/월)
   - 관리형이지만 매우 비쌈
```

---

## 📝 실행 체크리스트

### VM NAT 설정

- [ ] Compute Engine API 활성화
- [ ] 정적 IP 생성
- [ ] e2-micro VM 생성
- [ ] tinyproxy 설치 및 시작
- [ ] Cloud Run 프록시 환경변수 설정
- [ ] Makeshop 허용 IP 등록
- [ ] 동작 확인

---

**비용 최적화 완료!** 🚀  
**권장 방법**: Makeshop 도메인 허용 (무료) → VM NAT ($0 Always Free)
