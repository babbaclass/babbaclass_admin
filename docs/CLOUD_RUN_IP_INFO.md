# Babba-API Cloud Run IP 주소 정보

## 🔍 Cloud Run 서비스 정보

### 서비스 URL
```
https://babba-api-kitlcurzpa-du.a.run.app
```

### 할당된 IP 주소 (동적)

Cloud Run은 **로드 밸런싱**을 위해 여러 개의 IP 주소를 사용합니다:

```
34.143.75.2
34.143.78.2
34.143.77.2
34.143.76.2
34.143.79.2
34.143.74.2
34.143.72.2
34.143.73.2
```

---

## ⚠️ 중요: Cloud Run IP 특성

### 1️⃣ **동적 IP 주소**
- Cloud Run은 서버리스 서비스로, IP 주소가 **동적으로 변할 수 있습니다**
- 언제든지 새로운 IP 주소로 변경될 수 있습니다
- **고정 IP 주소가 없습니다**

### 2️⃣ **로드 밸런싱**
- 여러 개의 IP 주소로 분산 처리
- 위에 나열된 8개 IP는 모두 babba-api를 가리킵니다

### 3️⃣ **DNS 사용 권장**
- IP 주소 대신 **도메인 네임 (URL)**을 사용하는 것이 안전합니다
- DNS는 자동으로 IP 변경을 추적합니다

---

## 🛡️ Makeshop API 허용 IP 등록 방법

### ✅ 권장: 도메인 등록

**Makeshop 관리자 페이지에서:**

```
설정 > API 보안 > 허용 도메인
─────────────────────────────
babba-api-kitlcurzpa-du.a.run.app
```

또는

```
https://babba-api-kitlcurzpa-du.a.run.app
```

### ❌ 비권장: IP 주소 등록

만약 IP 주소 등록이 필수라면, **모든 IP 주소를 등록**해야 합니다:

```
34.143.72.2
34.143.73.2
34.143.74.2
34.143.75.2
34.143.76.2
34.143.77.2
34.143.78.2
34.143.79.2
```

⚠️ **주의**: 이 IP들도 언제든 변경될 수 있습니다.

---

## 🔧 고정 IP 주소가 필요한 경우

### Cloud NAT 사용 (권장)

고정 IP가 필요하다면 **Cloud NAT**을 설정할 수 있습니다:

```bash
# 1. 예약된 정적 IP 생성
gcloud compute addresses create babba-api-ip \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9

# 2. Cloud NAT 게이트웨이 생성
gcloud compute routers create babba-router \
  --region=asia-northeast3 \
  --network=default \
  --project=astute-window-472313-g9

# 3. NAT 규칙 추가
gcloud compute routers nats create babba-nat \
  --router=babba-router \
  --region=asia-northeast3 \
  --nat-all-subnet-ip-ranges \
  --auto-allocate-nat-external-ips \
  --project=astute-window-472313-g9
```

### 생성된 정적 IP 확인

```bash
gcloud compute addresses list \
  --region=asia-northeast3 \
  --project=astute-window-472313-g9
```

---

## 📋 정보 요약

| 항목 | 값 |
|------|-----|
| **서비스 URL** | `https://babba-api-kitlcurzpa-du.a.run.app` |
| **리전** | `asia-northeast3` (서울) |
| **프로젝트** | `astute-window-472313-g9` |
| **IP 타입** | 동적 (로드 밸런싱) |
| **현재 IP 개수** | 8개 |

---

## 🎯 Makeshop API 허용 설정 체크리스트

- [ ] Makeshop 관리자 페이지 로그인
- [ ] API 보안 설정 접근
- [ ] 다음 중 하나 선택:
  - [ ] 도메인 등록: `babba-api-kitlcurzpa-du.a.run.app`
  - [ ] 또는 모든 IP 주소 등록 (위 8개)
- [ ] 설정 저장
- [ ] Makeshop API 테스트: `GET /makeshop/health`

---

## 🔗 참고 링크

- [Cloud Run 네트워킹 문서](https://cloud.google.com/run/docs/networking)
- [Cloud NAT 문서](https://cloud.google.com/nat/docs)
- [Makeshop API 보안 설정](https://developer.makeshop.co.kr/docs)

---

**생성일**: 2025년 10월 31일  
**상태**: ✅ 확인됨
