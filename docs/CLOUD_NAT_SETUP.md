# Cloud NAT 설정 완료

## 개요
서울 리전(asia-northeast3)에서 VM+NAT 사용 시 발생하는 과금 문제를 해결하기 위해 Cloud NAT으로 고정 IP를 설정했습니다.

## 생성된 리소스

### 1. Cloud Router
- **이름**: `babba-nat-router`
- **리전**: `asia-northeast3`
- **네트워크**: `default`

### 2. 고정 IP 주소
- **이름**: `babba-nat-ip-v2`
- **IP 주소**: `34.158.215.39`
- **상태**: `IN_USE`
- **목적**: Cloud NAT 사용

### 3. Cloud NAT
- **이름**: `babba-nat`
- **라우터**: `babba-nat-router`
- **고정 IP**: `babba-nat-ip-v2` (34.158.215.39)
- **서브넷 범위**: 모든 서브넷의 모든 IP 범위 (`ALL_SUBNETWORKS_ALL_IP_RANGES`)
- **NAT IP 할당 옵션**: `MANUAL_ONLY` (고정 IP만 사용)

### 4. VPC Connector
- **이름**: `babba-connector`
- **리전**: `asia-northeast3`
- **네트워크**: `default`
- **IP 범위**: `10.8.0.0/28`
- **상태**: `READY`

## Cloud Run 서비스 설정

### VPC Connector 활성화
Cloud Run 서비스 `babba-api`가 다음과 같이 구성되었습니다:

```
Metadata:
  run.googleapis.com/vpc-access-connector: "babba-connector"
  run.googleapis.com/vpc-access-egress: "private-ranges-only"
```

이를 통해 Cloud Run에서 나가는 모든 트래픽이 Cloud NAT의 고정 IP(`34.158.215.39`)를 통해 라우팅됩니다.

## 트래픽 흐름

```
Cloud Run (babba-api)
    ↓
VPC Connector (babba-connector) - 10.8.0.0/28
    ↓
Cloud NAT (babba-nat)
    ↓
고정 IP 주소 (34.158.215.39)
    ↓
외부 서비스/인터넷
```

## 비용 절감 효과

- **기존 방식**: VM 인스턴스 + NAT = 더 높은 과금
- **현재 방식**: Cloud NAT + 고정 IP = VM 과금 제거, NAT 과금만 존재

## 검증 명령어

### Cloud NAT 확인
```bash
gcloud compute routers nats describe babba-nat \
  --router=babba-nat-router \
  --region=asia-northeast3
```

### 고정 IP 주소 확인
```bash
gcloud compute addresses describe babba-nat-ip-v2 --region=asia-northeast3
```

### VPC Connector 확인
```bash
gcloud compute networks vpc-access connectors describe babba-connector \
  --region=asia-northeast3
```

### Cloud Run 서비스 VPC 설정 확인
```bash
gcloud run services describe babba-api \
  --region=asia-northeast3 \
  --format=json | grep -i vpc
```

## 외부 서비스에서 보는 IP

MakeShop API 등 외부 서비스에 대한 모든 아웃바운드 연결은 `34.158.215.39`에서 발생한 것으로 보입니다.

## 주의사항

1. Cloud Run은 VPC Connector를 통해서만 Private IP 범위의 리소스에 접근 가능합니다.
2. Cloud SQL은 Private IP로 설정되어 있어야 합니다. (현재 구성에서 VPC Connector를 통해 접근)
3. VPC Connector 자체도 월 과금이 발생하지만, VM 인스턴스 비용 절감으로 인한 이득이 더 큽니다.

## 관련 파일
- `.github/workflows/deploy.yml` - VPC Connector 설정은 자동으로 적용됨
- `.env` - VPC 관련 환경변수 불필요 (gcloud 설정으로 관리)
