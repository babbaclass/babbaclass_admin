from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.sheet_import_service import import_google_sheet, google_sheet_to_csv_url, fetch_csv, parse_csv
from app.models import User, Company, Role, Settlement, Statement, SettlementStatementConfirmation
import logging
import requests

router = APIRouter(prefix="/admin-api/sheets", tags=["Admin Tools"])

logger = logging.getLogger(__name__)


class SheetImportRequest(BaseModel):
    sheet_url: HttpUrl
    sheet_name: str | None = None
    table_name: str | None = None
    truncate_before: bool = False


class UserImportRequest(BaseModel):
    sheet_url: HttpUrl
    sheet_name: str | None = None
    skip_duplicates: bool = True  # 이메일 중복 시 건너뛰기


@router.post("/import")
def import_sheet(req: SheetImportRequest, db: Session = Depends(get_db)):
    try:
        logger.info(
            f"[SheetImportAPI] Request: url={req.sheet_url}, sheet={req.sheet_name}, table={req.table_name}, truncate={req.truncate_before}"
        )
        result = import_google_sheet(
            db,
            sheet_url=str(req.sheet_url),
            sheet_name=req.sheet_name,
            table_name=req.table_name,
            truncate_before=req.truncate_before,
        )
        logger.info(
            f"[SheetImportAPI] Success: table={result.get('table_name')}, rows={result.get('rows_inserted')}, created={result.get('created_table')}"
        )
        return result
    except Exception as e:
        logger.exception(f"[SheetImportAPI] Failed to import: url={req.sheet_url}, err={e}")
        raise HTTPException(status_code=400, detail=f"시트 가져오기 실패: {e}")


@router.post("/import/users")
def import_users_from_sheet(
    sheet_url: str = Query(..., description="Google Sheet URL"),
    sheet_name: str | None = Query(None, description="시트 이름 (옵션)"),
    db: Session = Depends(get_db)
):
    """
    Google Sheets에서 User 데이터를 가져와서 users 테이블에 적재합니다.
    
    code 값이 있으면 기존 사용자를 업데이트하고, 없으면 신규 생성합니다.
    password가 없으면 기본값 'admin123'을 사용합니다.
    
    company_id 설정 방식:
    1. code 값이 있는 경우: code 앞 5자리와 company.code 앞 5자리를 비교하여 일치하는 company_id 자동 설정
    2. code로 매칭 실패 시: company_name으로 company_id 조회

    필요한 시트 컬럼:
    - name: 사용자 이름 (필수)
    - email: 이메일 주소 (선택)
    - password: 비밀번호 (선택, 기본값: "admin123")
    - login_id: 로그인용 ID (선택)
    - company_name: 회사명 (선택, code로 매칭 실패 시 필수)
    - role_id: 역할 ID (필수)
    - code: 사번/코드 (선택, 있으면 업데이트, 없으면 생성 / 앞 5자리로 company 자동 매칭)
    - main_contact: 주 연락처 (선택)
    - bank_name: 은행명 (선택)
    - bank_account: 계좌번호 (선택)
    - address: 주소 (선택)
    - contracted_at: 계약일 (선택, YYYY-MM-DD 형식)
    - is_active: 활성화 여부 (선택, 기본값: TRUE)
    """
    try:
        from app.services.sheet_import_service import google_sheet_to_csv_url, fetch_csv, parse_csv
        from passlib.context import CryptContext

        # 비밀번호 해싱 컨텍스트
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

        logger.info(f"[UserImportAPI] Starting user import from sheet: {sheet_url}")

        # 1. Google Sheet에서 CSV 데이터 가져오기
        csv_url = google_sheet_to_csv_url(str(sheet_url), sheet_name)
        csv_text = fetch_csv(csv_url)
        headers, data = parse_csv(csv_text)

        logger.info(f"[UserImportAPI] Parsed CSV: {len(headers)} columns, {len(data)} rows")

        # 2. 필수 컬럼 확인
        required_columns = ['name', 'role_id']
        header_lower = [h.lower() for h in headers]

        missing_columns = []
        for req_col in required_columns:
            if req_col not in header_lower:
                missing_columns.append(req_col)

        if missing_columns:
            raise ValueError(f"필수 컬럼이 누락되었습니다: {', '.join(missing_columns)}")

        # 컬럼 인덱스 매핑
        col_indices = {}
        for col in required_columns + ['email', 'password', 'login_id', 'code', 'main_contact', 'bank_name', 'bank_account', 'address', 'contracted_at', 'is_active']:
            if col in header_lower:
                col_indices[col] = header_lower.index(col)

        # 3. code로 company_id 매핑을 위해 Company 테이블 로드
        companies_by_code_prefix = {}  # code 앞 5자리로 company_id 매핑
        for c in db.query(Company).all():
            if c.code:
                code_str = str(c.code)
                if len(code_str) >= 5:
                    prefix = code_str[:5]
                    companies_by_code_prefix[prefix] = c.company_id

        # 4. 데이터 검증 및 변환
        created_count = 0
        updated_count = 0
        error_rows = []

        for row_idx, row in enumerate(data, 1):
            try:
                # 필수 필드 추출
                name = row[col_indices['name']].strip() if 'name' in col_indices and col_indices['name'] < len(row) else ''
                
                # role_id 추출
                role_id = None
                if 'role_id' in col_indices and col_indices['role_id'] < len(row):
                    role_id_str = row[col_indices['role_id']].strip()
                    role_id = int(role_id_str) if role_id_str and role_id_str.isdigit() else None

                # 선택 필드 추출
                email = row[col_indices['email']].strip().lower() if 'email' in col_indices and col_indices['email'] < len(row) and row[col_indices['email']].strip() else None
                
                # email이 없으면 임시 이메일 생성
                if not email:
                    email = f"user_{row_idx}@temp.babba.local"
                
                password = row[col_indices['password']].strip() if 'password' in col_indices and col_indices['password'] < len(row) and row[col_indices['password']].strip() else None
                login_id = row[col_indices['login_id']].strip() if 'login_id' in col_indices and col_indices['login_id'] < len(row) and row[col_indices['login_id']].strip() else None
                
                # code 추출 (먼저 추출해야 login_id 생성에 사용 가능) - string으로 유지 (leading zero 보존)
                code = None
                if 'code' in col_indices and col_indices['code'] < len(row):
                    code = row[col_indices['code']].strip() if row[col_indices['code']].strip() else None
                
                # login_id가 "가입 전"이거나 없으면 고유한 임시 값 생성
                if not login_id or login_id == "가입 전":
                    # code가 있으면 code 사용, 없으면 row_idx 사용
                    temp_suffix = code if code else f"temp_{row_idx}"
                    login_id = f"pending_{temp_suffix}"

                main_contact = row[col_indices['main_contact']].strip() if 'main_contact' in col_indices and col_indices['main_contact'] < len(row) and row[col_indices['main_contact']].strip() else None
                bank_name = row[col_indices['bank_name']].strip() if 'bank_name' in col_indices and col_indices['bank_name'] < len(row) and row[col_indices['bank_name']].strip() else None
                bank_account = row[col_indices['bank_account']].strip() if 'bank_account' in col_indices and col_indices['bank_account'] < len(row) and row[col_indices['bank_account']].strip() else None
                address = row[col_indices['address']].strip() if 'address' in col_indices and col_indices['address'] < len(row) and row[col_indices['address']].strip() else None
                contracted_at = row[col_indices['contracted_at']].strip() if 'contracted_at' in col_indices and col_indices['contracted_at'] < len(row) and row[col_indices['contracted_at']].strip() else None

                is_active = True
                if 'is_active' in col_indices and col_indices['is_active'] < len(row):
                    active_str = row[col_indices['is_active']].strip().lower()
                    is_active = active_str in ('true', '1', 'y', 'yes', '활성')

                # 필수 필드 검증
                if not name:
                    raise ValueError("name 필드가 비어있습니다")
                if not role_id:
                    raise ValueError("role_id 필드가 비어있습니다")

                # company_id 결정: code 앞 5자리로만 매칭
                company_id = None
                
                if code:
                    # code 앞 5자리로 company 찾기
                    code_str = str(code)
                    if len(code_str) >= 5:
                        code_prefix = code_str[:5]
                        if code_prefix in companies_by_code_prefix:
                            company_id = companies_by_code_prefix[code_prefix]
                            logger.info(f"[UserImport] Row {row_idx}: code {code}의 앞 5자리({code_prefix})로 company_id={company_id} 매칭")
                
                # code가 없거나 5자리 미만이거나 매칭 실패하면 에러
                if not company_id:
                    raise ValueError(f"code(앞 5자리로 매칭 가능)가 필요합니다. 현재 code: {code}")

                # 비밀번호 기본값 처리 및 해싱
                if not password:
                    password = "admin123"
                password_hash = pwd_context.hash(password)

                # is_register 값 결정: login_id가 없으면 False, 있으면 True
                is_register = True if login_id else False

                # code 값으로 기존 사용자 확인
                existing_user = None
                if code:
                    existing_user = db.query(User).filter(User.code == code).first()
                
                # code로 못 찾으면 email로 확인 (같은 email은 업데이트)
                if not existing_user and email:
                    existing_user = db.query(User).filter(User.email == email).first()

                if existing_user:
                    # 업데이트
                    existing_user.name = name
                    existing_user.email = email
                    existing_user.password_hash = password_hash
                    existing_user.login_id = login_id
                    existing_user.company_id = company_id
                    existing_user.role_id = role_id
                    existing_user.main_contact = main_contact
                    existing_user.bank_name = bank_name
                    existing_user.bank_account = bank_account
                    existing_user.address = address
                    existing_user.contracted_at = contracted_at
                    existing_user.is_active = is_active
                    existing_user.is_register = is_register
                    if code:
                        existing_user.code = code
                    updated_count += 1
                else:
                    # 신규 생성
                    user = User(
                        name=name,
                        email=email,
                        password_hash=password_hash,
                        login_id=login_id,
                        company_id=company_id,
                        role_id=role_id,
                        code=code,
                        main_contact=main_contact,
                        bank_name=bank_name,
                        bank_account=bank_account,
                        address=address,
                        contracted_at=contracted_at,
                        is_active=is_active,
                        is_register=is_register
                    )
                    db.add(user)
                    created_count += 1

            except Exception as e:
                error_rows.append({
                    'row': row_idx,
                    'data': row,
                    'error': str(e)
                })

        # 5. 변경사항 커밋
        db.commit()

        result = {
            "status": "success",
            "message": "사용자 데이터 가져오기 완료",
            "total_rows": len(data),
            "created_users": created_count,
            "updated_users": updated_count,
            "error_rows": len(error_rows),
            "errors": error_rows[:10]  # 처음 10개 오류만 반환
        }

        logger.info(f"[UserImportAPI] Completed: {result}")
        return result

    except Exception as e:
        db.rollback()
        logger.exception(f"[UserImportAPI] Failed: {e}")
        raise HTTPException(status_code=400, detail=f"사용자 데이터 가져오기 실패: {str(e)}")


@router.get("/resolve")
def resolve_sheet_url(sheet_url: HttpUrl = Query(...), sheet_name: str | None = Query(None)):
    """Return the resolved CSV URL (and quick reachability check) for debugging.

    Example:
      GET /admin-api/sheets/resolve?sheet_url=https://docs.google.com/spreadsheets/d/<ID>/edit?gid=<GID>
    """
    try:
        csv_url = google_sheet_to_csv_url(str(sheet_url), sheet_name)
        status = None
        length = None
        try:
            r = requests.get(csv_url, timeout=10)
            status = r.status_code
            length = int(r.headers.get("Content-Length", "0") or 0)
        except Exception:
            # Swallow network errors; still return csv_url so the user can inspect
            pass
        return {"csv_url": csv_url, "status": status, "content_length": length}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"URL 해석 실패: {e}")


@router.post("/auto-match-users")
def auto_match_users_with_members(db: Session = Depends(get_db)):
    """User와 Member를 자동으로 매칭합니다.
    
    조건:
    - 생년월일(birth_date)이 같은 경우
    - Role과 회사명도 일치하는 경우 우선 선택
    
    Returns:
        {matched_count, skipped_count, error_messages, status}
    """
    try:
        from app.services.user_member_mapper import auto_match_user_with_member
        
        logger.info("[UserMemberMatch] 사용자-회원 자동 매칭 시작")
        result = auto_match_user_with_member()
        logger.info(f"[UserMemberMatch] 완료: {result['matched_count']}명 매칭")
        
        return {
            "status": "success",
            "matched_count": result["matched_count"],
            "skipped_count": result["skipped_count"],
            "error_messages": result["error_messages"],
        }
    except Exception as e:
        logger.exception(f"[UserMemberMatch] 실패: {e}")
        raise HTTPException(status_code=400, detail=f"자동 매칭 실패: {e}")


@router.get("/user-member-status")
def get_user_member_match_status(db: Session = Depends(get_db)):
    """User-Member 매칭 상태를 조회합니다.
    
    Returns:
        {total_users, matched_users, unmatched_users, match_percentage}
    """
    try:
        from app.services.user_member_mapper import get_user_member_status
        
        status = get_user_member_status()
        return {
            "status": "success",
            **status
        }
    except Exception as e:
        logger.exception(f"[UserMemberMatch] 상태 조회 실패: {e}")
        raise HTTPException(status_code=400, detail=f"상태 조회 실패: {e}")


@router.post("/users/clear-all")
def clear_all_users(
    db: Session = Depends(get_db)
) -> dict:
    """
    Users 테이블의 모든 데이터를 삭제합니다.
    관련 테이블(settlements, statements, settlement_statement_confirmations)도 함께 삭제됩니다.
    
    주의: 이 작업은 되돌릴 수 없습니다.
    """
    try:
        logger.info("[UserClearAll] 모든 사용자 데이터 삭제 시작")
        
        # 현재 사용자 수 조회
        total_users = db.query(User).count()
        
        # 외래 키 제약을 위해 순서대로 삭제
        # 1. settlement_statement_confirmations 삭제
        deleted_confirmations = db.query(SettlementStatementConfirmation).delete()
        
        # 2. settlements 삭제
        deleted_settlements = db.query(Settlement).delete()
        
        # 3. statements 삭제
        deleted_statements = db.query(Statement).delete()
        
        # 4. users 삭제
        deleted_users = db.query(User).delete()
        
        db.commit()
        
        logger.info(f"[UserClearAll] 완료: users={deleted_users}, settlements={deleted_settlements}, statements={deleted_statements}, confirmations={deleted_confirmations}")
        
        return {
            "status": "success",
            "message": f"모든 사용자 데이터가 삭제되었습니다 ({total_users}명)",
            "deleted": {
                "users": deleted_users,
                "settlements": deleted_settlements,
                "statements": deleted_statements,
                "confirmations": deleted_confirmations
            }
        }
    except Exception as e:
        db.rollback()
        logger.exception(f"[UserClearAll] 실패: {e}")
        raise HTTPException(status_code=400, detail=f"사용자 데이터 삭제 실패: {str(e)}")

