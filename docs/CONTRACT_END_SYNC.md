# ContractEnd Table Synchronization

## 목적
`ContractEnd` 테이블은 `User` 테이블과 1:1로 대응하도록 설계되었습니다. 이 문서는
계약 종료 관리 메뉴에서 기대하는 데이터를 확보하기 위해 기존 사용자 데이터를
동기화하는 방법을 설명합니다.

## 주요 가정
1. `contract_end_date` (계약 종료일)은 별도로 입력하는 필드이므로 기본값은 NULL(빈값)입니다.
   기존 사용자도 `contracted_at`에 관계없이 빈값(Null)으로 생성되며, 이후 수동/별도 로직에서 채워야 합니다.
2. `memo` (메모)도 기본값은 빈값('')으로 시작하며, 필요에 따라 수동으로 입력합니다.
3. `total_payment_last_year`는 현재 데이터를 기반으로 산출하지 않고 0으로 초기화
   하며, 향후 집계로 업데이트합니다.
4. 이미 `contract_end` 테이블에 항목이 존재하면 새로운 행을 만들지 않고 입력을
   건너뜁니다.

## 사용 방법
```bash
python sync_contract_endings.py [--dry-run]
```
- `--dry-run`: 실제 DB에 쓰지 않고 생성될 레코드 수만 로그에 출력합니다.
- 스크립트는 `SessionLocal`을 사용하므로 로컬 가상환경이나 클라우드 환경에서 동일한
  `SQLALCHEMY_DATABASE_URL`을 참조하여 실행해야 합니다.

### Docker에서 실행
```bash
docker-compose exec app python sync_contract_endings.py [--dry-run]
```

## 스키마 정보
- **테이블명**: `contract_end` (v083 마이그레이션에서 `contract_endings`에서 변경)
- **주요 열**:
  - `contract_end_id` (PK)
  - `user_id` (FK → users, ON DELETE CASCADE)
  - `company_id` (FK → companies)
  - `contract_end_date` (DATE, nullable) - 수동 입력 필드
  - `total_payment_last_year` (INT, default=0)
  - `memo` (TEXT, nullable, default='') - 기본값은 빈값

## 출력 예시
```
INFO: Users processed: 52, records created: 12, skipped existing: 40
INFO: Dry-run mode: no changes were committed.
```

현재는 테스트 DB나 CI에 자동 실행되지는 않으며, 운영 환경에 배포할 때만 직접 실행하여
기존 사용자와 `ContractEnd` 간의 1:1 매핑을 보장합니다. Dockerfile에 스크립트가 포함되어
있으므로 필요 시 컨테이너 내에서 언제든 실행 가능합니다.

## 마이그레이션 히스토리
- **v081**: `contract_endings` 테이블 생성
- **v082**: `contract_end_date` 열 nullable 처리
- **v083**: 테이블명 `contract_endings` → `contract_end`, `note` → `memo` 열명 변경, `status` 열 삭제
