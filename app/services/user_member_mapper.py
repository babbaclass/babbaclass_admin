"""
User-Member 자동 매핑 서비스

생년월일, role, company가 같으면 User와 Member를 자동으로 연결합니다.
"""

from app.database import SessionLocal
from app.models import User, Member, Role, Company
import logging

logger = logging.getLogger(__name__)


def normalize_birth_date(birth_date_str: str) -> str | None:
    """
    생년월일을 정규화합니다.
    지원하는 형식: 'YYYYMMDD', 'YYYY-MM-DD', 'YYMMDD'
    """
    if not birth_date_str:
        return None
    
    # 공백 제거
    birth_date_str = birth_date_str.strip()
    
    # '-' 제거하여 숫자만 추출
    birth_date_str = birth_date_str.replace('-', '')
    
    if not birth_date_str.isdigit():
        return None
    
    # 6자리: 'YYMMDD' -> 'YYYYMMDD'로 변환
    if len(birth_date_str) == 6:
        yy = int(birth_date_str[:2])
        # 00-30은 2000년대, 31-99는 1900년대
        yyyy = 2000 + yy if yy <= 30 else 1900 + yy
        birth_date_str = f"{yyyy}{birth_date_str[2:]}"
    
    # 8자리: 'YYYYMMDD'
    if len(birth_date_str) == 8:
        return birth_date_str
    
    return None


def auto_match_user_with_member():
    """
    User와 Member를 자동으로 매칭합니다.
    
    조건:
    - User의 birth_date == Member의 birth_day (정규화 후)
    - User의 role_id 해당 role.role_name == Member의 group_name (선택)
    - User의 company_id 해당 company.name == Member의 company_name (선택)
    - User.member_id가 NULL인 경우만 업데이트
    
    Returns:
        dict: {matched_count, skipped_count, error_messages}
    """
    db = SessionLocal()
    try:
        result = {
            "matched_count": 0,
            "skipped_count": 0,
            "error_messages": [],
        }
        
        # member_id가 없는 User만 조회
        users_without_member = db.query(User).filter(User.member_id.is_(None)).all()
        
        logger.info(f"[USER-MEMBER] 매핑 시작: {len(users_without_member)}명의 User 처리 중...")
        
        for user in users_without_member:
            try:
                user_birth = normalize_birth_date(user.birth_date or "")
                if not user_birth:
                    result["skipped_count"] += 1
                    continue
                
                # 매칭 조건: 생년월일이 같은 Member 찾기
                query = db.query(Member).filter(
                    Member.birth_day == user_birth
                )
                
                # 회사명 필터 (선택)
                if user.company_id:
                    company = db.query(Company).filter(Company.company_id == user.company_id).first()
                    if company and company.name:
                        query = query.filter(Member.company_name == company.name)
                
                # 역할명 필터 (선택)
                if user.role_id:
                    role = db.query(Role).filter(Role.role_id == user.role_id).first()
                    if role and role.role_name:
                        query = query.filter(Member.group_name == role.role_name)
                
                # 첫 번째 매칭 결과 선택 (여러 개일 수 있음)
                member = query.first()
                
                if member:
                    user.member_id = member.id
                    result["matched_count"] += 1
                    logger.info(f"[USER-MEMBER] 매칭 완료: User {user.user_id} ({user.name}) -> Member {member.id}")
                else:
                    result["skipped_count"] += 1
                    
            except Exception as e:
                error_msg = f"User {user.user_id} 처리 실패: {str(e)}"
                result["error_messages"].append(error_msg)
                logger.error(f"[USER-MEMBER] {error_msg}")
        
        # 모든 변경사항 커밋
        db.commit()
        
        logger.info(f"[USER-MEMBER] 매핑 완료: {result['matched_count']}명 매칭, {result['skipped_count']}명 스킵")
        
        return result
        
    except Exception as e:
        db.rollback()
        error_msg = f"[USER-MEMBER] 매핑 프로세스 실패: {str(e)}"
        logger.error(error_msg)
        return {
            "matched_count": 0,
            "skipped_count": 0,
            "error_messages": [error_msg],
        }
    finally:
        db.close()


def get_user_member_status():
    """
    User-Member 매핑 상태를 조회합니다.
    
    Returns:
        dict: {total_users, matched_users, unmatched_users}
    """
    db = SessionLocal()
    try:
        total_users = db.query(User).count()
        matched_users = db.query(User).filter(User.member_id.isnot(None)).count()
        unmatched_users = total_users - matched_users
        
        return {
            "total_users": total_users,
            "matched_users": matched_users,
            "unmatched_users": unmatched_users,
            "match_percentage": round((matched_users / total_users * 100) if total_users > 0 else 0, 2),
        }
    finally:
        db.close()
