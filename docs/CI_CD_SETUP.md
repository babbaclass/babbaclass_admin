# CI/CD 설정 문서

## 현재 설정: GitHub Actions + Google Cloud Run

### 📋 배포 파이프라인

```
Git Push (main branch)
    ↓
GitHub Actions Workflow (.github/workflows/deploy.yml)
    ↓
1. Code Checkout
    ↓
2. WIF 인증 (Workload Identity Federation)
    ↓
3. Docker 이미지 빌드
    ↓
4. Artifact Registry에 푸시
    ↓
5. Cloud Run 서비스 배포
    ↓
✅ 서비스 업데이트 완료
```

## 🔑 주요 구성 요소

### 1. GitHub Actions (`.github/workflows/deploy.yml`)
- **트리거**: main 브랜치에 push 또는 수동 실행
- **인증**: Workload Identity Federation (WIF)
- **단계**:
  1. 코드 체크아웃
  2. GCP WIF 인증
  3. Docker 이미지 빌드
  4. Artifact Registry 인증
  5. Docker 이미지 푸시
  6. Cloud Run 서비스 배포

### 2. Workload Identity Federation (WIF)
- **WIF Pool**: `github-pool`
- **OIDC Provider**: `github-actions-provider`
- **조건**: `assertion.repository_owner == 'Fulfilled-Inc'`
- **장점**: 
  - 서비스 계정 키 불필요
  - 조직 정책 준수 (key 생성 제약 회피)
  - 더 안전한 인증 방식

### 3. Google Cloud Resources
- **Service Account**: `github-actions@PROJECT_ID.iam.gserviceaccount.com`
- **IAM 역할**:
  - `roles/iam.workloadIdentityUser` (WIF 사용)
  - `roles/run.admin` (Cloud Run 배포)
  - `roles/artifactregistry.writer` (이미지 푸시)
- **Artifact Registry**: `asia-northeast3-docker.pkg.dev/PROJECT_ID/babba-registry`
- **Cloud Run Service**: `babba-api` (asia-northeast3)

## 🚀 배포 프로세스

### 자동 배포 (Git Push)
```bash
git add -A
git commit -m "Your changes"
git push origin main
```
→ GitHub Actions가 자동으로 실행됨

### 수동 배포 (GitHub UI)
1. GitHub Repository → Actions 탭
2. "Deploy to Cloud Run" 워크플로우 선택
3. "Run workflow" 클릭

## 📊 배포 모니터링

### GitHub Actions 로그 확인
- URL: `https://github.com/Fulfilled-Inc/babba-api/actions`
- 각 단계의 로그와 에러 메시지 확인 가능

### Cloud Run 로그 확인
```bash
gcloud run services logs read babba-api --region=asia-northeast3 --limit=100
```

### 배포 상태 확인
```bash
gcloud run services describe babba-api --region=asia-northeast3
```

## 🔧 주요 설정 파일

| 파일 | 목적 | 수정 시 주의사항 |
|------|------|-----------------|
| `.github/workflows/deploy.yml` | GitHub Actions 워크플로우 | WIF 제공자 이름, SA 이메일, 이미지 경로 |
| `Dockerfile` | 서비스 컨테이너 이미지 | Python 버전, 의존성 변경 시 |
| `entrypoint.sh` | 컨테이너 시작 스크립트 | 환경 변수 설정 시 |
| `requirements.txt` | Python 의존성 | 패키지 추가/제거 시 |

## 🔐 GitHub Secrets 설정

GitHub Repository → Settings → Secrets and variables → Actions에서 다음을 설정해야 함:

| Secret | 값 | 설명 |
|--------|-----|------|
| `CLOUD_SQL_INSTANCE` | `astute-window-472313-g9:asia-northeast3:babba-db` | Cloud SQL 인스턴스 |
| `DB_USER` | `root` | 데이터베이스 사용자 |
| `DB_PASSWORD` | `[비밀번호]` | 데이터베이스 비밀번호 |
| `DB_NAME` | `babba` | 데이터베이스 이름 |

**참고**: `GCP_SA_KEY` 또는 다른 GCP 키는 필요하지 않음 (WIF 사용)

## 📝 서비스 환경 변수

Cloud Run에서 설정되는 환경 변수:
- `CLOUD_SQL_INSTANCE`: Cloud SQL 연결 문자열
- `DB_USER`: 데이터베이스 사용자
- `DB_PASSWORD`: 데이터베이스 비밀번호
- `DB_NAME`: 데이터베이스 이름

## ✅ 배포 체크리스트

배포 전 확인:
- [ ] GitHub Repository에 모든 Secret 설정됨
- [ ] Dockerfile과 requirements.txt 최신 상태
- [ ] entrypoint.sh 실행 가능 상태
- [ ] main 브랜치에 모든 변경사항 커밋됨

배포 후 확인:
- [ ] GitHub Actions 워크플로우 성공
- [ ] Cloud Run 서비스 상태 Ready
- [ ] `/health` 엔드포인트 응답 확인
- [ ] 필요한 데이터베이스 마이그레이션 수행됨 (따로 진행)

## 🛠️ 트러블슈팅

### WIF 인증 실패
**오류**: `unauthorized_client`
**원인**: GitHub OIDC 토큰이 attribute condition을 만족하지 못함
**해결**:
- WIF 제공자의 attribute condition 확인
- Service Account의 IAM 바인딩 확인

```bash
gcloud iam workload-identity-pools providers describe github-actions-provider \
  --location=global \
  --workload-identity-pool=github-pool \
  --project=astute-window-472313-g9
```

### Docker 빌드 실패
**해결**: 로컬에서 Docker 빌드 테스트
```bash
docker build -t babba-api:test .
docker run -e CLOUD_SQL_INSTANCE=... babba-api:test
```

### Cloud Run 배포 실패
**해결**: Service Account 권한 확인
```bash
gcloud projects get-iam-policy astute-window-472313-g9 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:github-actions*"
```

## 📚 참고 자료

- [Google Cloud Workload Identity Federation](https://cloud.google.com/docs/authentication/federation)
- [GitHub Actions with Google Cloud](https://github.com/google-github-actions/auth)
- [Cloud Run 배포 가이드](https://cloud.google.com/run/docs/deploying)
- [Artifact Registry](https://cloud.google.com/artifact-registry)
