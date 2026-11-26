# Cloud SQL 에디션 변경 가이드

## 📋 현재 상태

**프로젝트**: `astute-window-472313-g9`  
**현재 에디션**: ENTERPRISE_PLUS  
**문제**: `db-f1-micro` 같은 저렴한 티어 사용 불가

---

## 🔄 에디션 변경 방법

### 방법 1: GCP 콘솔에서 변경 (권장 - GUI)

#### 단계 1: GCP 콘솔 접속
```
https://console.cloud.google.com/sql/instances
```

#### 단계 2: 프로젝트 선택
- 프로젝트: `astute-window-472313-g9` 선택

#### 단계 3: 설정 확인
1. 좌측 메뉴에서 **"설정"** 클릭
2. **"SQL 에디션"** 섹션 확인
3. 현재 ENTERPRISE_PLUS로 설정되어 있음

#### 단계 4: 에디션 변경
1. **"에디션 변경"** 또는 **"수정"** 클릭
2. **"Standard"** 선택
3. **"저장"** 또는 **"업데이트"** 클릭

> **주의**: 에디션 변경에는 시간이 걸릴 수 있습니다 (5-10분)

---

### 방법 2: CLI를 통한 변경 (커맨드 라인)

#### 현재 설정 확인
```bash
gcloud sql instances describe babba-db \
  --project=astute-window-472313-g9 \
  --format='value(databaseVersion,settings.edition)'
```

#### 에디션 변경 (Standard로)
```bash
gcloud sql instances patch babba-db \
  --edition=STANDARD \
  --project=astute-window-472313-g9
```

**출력 예시**:
```
Instance patch request accepted.
Operation ID: <operation-id>
```

#### 변경 상태 확인
```bash
gcloud sql instances describe babba-db \
  --project=astute-window-472313-g9 \
  --format='value(databaseVersion,settings.edition,state)'
```

---

## 📊 에디션 비교

| 구분 | Standard | Enterprise | Enterprise Plus |
|------|----------|-----------|-----------------|
| **최소 티어** | db-f1-micro | db-perf-optimized-N-2 | db-perf-optimized-N-2 |
| **최소 비용** | ~$10-20/월 | ~$200-300/월 | ~$300+/월 |
| **자동 백업** | ✅ | ✅ | ✅ |
| **고가용성** | ❌ | ✅ (옵션) | ✅ (옵션) |
| **복제** | ❌ | ✅ | ✅ |
| **용도** | 개발/테스트 | 프로덕션 | 미션 크리티컬 |

---

## ✅ Standard 에디션으로 변경 후 실행

### 1. 에디션 변경 확인
```bash
gcloud sql instances describe babba-db \
  --project=astute-window-472313-g9 \
  --format='value(settings.edition)'
# 출력: STANDARD
```

### 2. 저렴한 티어로 새 인스턴스 생성
```bash
gcloud sql instances create babba-db-dev \
  --database-version=MYSQL_8_4 \
  --region=asia-northeast3 \
  --tier=db-f1-micro \
  --project=astute-window-472313-g9 \
  --no-backup \
  --backup-start-time=NONE
```

### 3. 생성 확인
```bash
gcloud sql instances describe babba-db-dev \
  --project=astute-window-472313-g9 \
  --format='value(name,tier,state)'
```

---

## ⚠️ 주의사항

1. **에디션 변경 제약**
   - ❌ 에디션을 바꾸려면 **새 인스턴스 생성** 필요
   - ✅ 기존 인스턴스는 ENTERPRISE_PLUS로 유지

2. **데이터 마이그레이션**
   - 기존 인스턴스의 데이터를 새 인스턴스로 이동 필요
   - `mysqldump` 사용 권장

3. **비용 최적화**
   - 개발: db-f1-micro (Standard)
   - 프로덕션: db-perf-optimized-N-2 (Enterprise)

---

## 🚀 권장 절차

### 현재 상황 (가장 저렴한 방법)

1. **로컬 개발 계속** (현재 상태)
   ```bash
   uvicorn main_local:app --reload
   # SQLite 사용 (무료)
   ```

2. **프로덕션 배포 시점에 선택**
   - **옵션 A**: 새 프로젝트 생성 (Standard 에디션)
   - **옵션 B**: 조직 정책 변경 요청 (IT 관리자)
   - **옵션 C**: Enterprise 에디션 사용 ($200+/월)

---

## 📞 조직 정책 변경 요청

### 누가 할 수 있나?
- **GCP 조직 관리자** (Organization Admin)
- **GCP 정책 관리자** (Policy Administrator)

### 요청 내용
```
요청 사항: Cloud SQL 에디션 정책 변경
- 현재: ENTERPRISE_PLUS 에디션 강제
- 변경: Standard, Enterprise, Enterprise Plus 모두 허용
- 이유: 개발 환경에서 저렴한 db-f1-micro 티어 사용 필요
```

### 변경 위치 (GCP 콘솔)
```
조직 정책 > 정책 검색 > "SQL Edition" 검색 > 수정
```

---

## 💡 현재 권장 방안

**비용을 최소화하려면:**

1. ✅ **지금**: 로컬 SQLite 계속 사용 (무료)
2. ✅ **테스트**: Enterprise 에디션 db-perf-optimized-N-2 ($200-300/월)
3. 🔄 **나중에**: 조직 정책 변경 요청 후 Standard 에디션 (저렴)

---

**자세한 정보**: [Cloud SQL 에디션 문서](https://cloud.google.com/sql/docs/mysql/editions)
