# GitHub Actions CI/CD 설정 가이드

## 개요

GitHub Actions는 **Workload Identity Federation (WIF)**을 사용하여 Google Cloud Platform과 연동합니다. 이 방법은:

- ✅ 장기 유효한 Service Account 키가 불필요
- ✅ 조직의 IAM 정책 제약 우회 가능
- ✅ OIDC를 통한 안전한 인증

## 설정 단계

### 1. GitHub Repository Secrets 추가

GitHub Repository 페이지 → Settings → Secrets and variables → Actions에서 다음 시크릿을 추가하세요:

| Secret 이름 | 값 | 설명 |
|-----------|-----|-----|
| `CLOUD_SQL_INSTANCE` | `astute-window-472313-g9:asia-northeast3:babba-db` | Cloud SQL 인스턴스 연결 문자열 |
| `DB_USER` | `root` | 데이터베이스 사용자명 |
| `DB_PASSWORD` | `[실제 비밀번호]` | 데이터베이스 비밀번호 |
| `DB_NAME` | `babba` | 데이터베이스 이름 |

**참고**: 기존 `GCP_SA_KEY` 시크릿은 더 이상 필요하지 않습니다.

### 2. GCP 설정 (이미 완료됨)

다음 항목들이 이미 GCP에 설정되어 있습니다:

- ✅ Workload Identity Pool: `projects/1024083500192/locations/global/workloadIdentityPools/github-pool`
- ✅ OIDC Provider: `projects/1024083500192/locations/global/workloadIdentityPools/github-pool/providers/github-provider`
- ✅ Service Account: `github-actions@astute-window-472313-g9.iam.gserviceaccount.com`
- ✅ IAM 바인딩: Workload Identity User 역할 할당

## GitHub Actions 워크플로우 설명

`.github/workflows/deploy.yml`의 파이프라인:

```
Git Push (main branch)
    ↓
1. Code Checkout
    ↓
2. WIF를 통한 GCP 인증 (키 불필요)
    ↓
3. Docker 이미지 빌드 (migration + service)
    ↓
4. Artifact Registry에 푸시
    ↓
5. Cloud Run Job 실행 (데이터베이스 마이그레이션)
    ↓
6. Cloud Run 서비스 배포
    ↓
✅ 서비스 배포 완료
```

## 테스트하기

### 방법 1: Git 커밋 푸시 (자동)

```bash
cd /Users/hoonlee/Documents/GitHub/babba-api
git add -A
git commit -m "Enable GitHub Actions CI/CD with WIF"
git push origin main
```

GitHub Repository → Actions 탭에서 워크플로우 실행 상황을 모니터링하세요.

### 방법 2: 수동 실행

GitHub Repository → Actions → "Deploy to Cloud Run" 워크플로우 → "Run workflow" 버튼 클릭

## 문제 해결

### WIF 인증 실패

**증상**: `error: unable to authenticate to Google Cloud`

**해결**:
1. WIF 제공자가 올바른 GitHub 저장소를 신뢰하고 있는지 확인
2. Service Account에 올바른 IAM 역할이 할당되어 있는지 확인
3. 다음 명령어로 확인:

```bash
gcloud iam workload-identity-pools providers describe "github-provider" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --project="astute-window-472313-g9"
```

### Docker 빌드 실패

**증상**: `permission denied while trying to connect to Docker daemon`

**해결**: GitHub Actions는 자동으로 Docker 환경을 제공합니다. 로컬에서 테스트하려면:

```bash
docker build -f Dockerfile.migration -t babba-api-migration .
docker build -t babba-api .
```

### Cloud Run 배포 실패

**증상**: 배포는 성공하지만 서비스가 응답하지 않음

**해결**:
1. Cloud Run 서비스 로그 확인: `gcloud run services describe babba-api --region=asia-northeast3`
2. 환경 변수 확인: Cloud Run 서비스 설정에서 `CLOUD_SQL_INSTANCE`, `DB_USER` 등이 설정되어 있는지 확인
3. Cloud SQL Proxy 연결 확인: 서비스 계정(github-actions)이 Cloud SQL에 접근할 수 있는지 확인

## 다음 단계

1. **GitHub Repository에 Secrets 추가** (위의 "GitHub Repository Secrets 추가" 참조)
2. **메인 브랜치에 커밋**: 워크플로우가 자동으로 실행됩니다
3. **Cloud Run 서비스 테스트**: https://babba-api-*.run.app/health 접속
4. **Admin 계정 생성**: 데이터베이스에 admin 사용자 추가 후 /admin/ 로그인 테스트

## 참고 자료

- [Google Cloud Workload Identity Federation](https://cloud.google.com/docs/authentication/federation)
- [GitHub Actions Google Cloud Authentication](https://github.com/google-github-actions/auth#workload-identity-federation)
- [Cloud Run 배포 가이드](https://cloud.google.com/run/docs/deploying)
