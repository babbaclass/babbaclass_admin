"""
관리자 계정 생성 유틸리티

DB에 관리자 계정을 생성하고 비밀번호를 bcrypt로 암호화하여 저장합니다.
사용법: python -m app.create_admin
"""

from app.database import SessionLocal, engine, Base
from app.models import User, Company, Role
from app.services.organization_service import UserService
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 비밀번호 해시/검증은 UserService를 통해 일원화 (bcrypt_sha256 우선)


def create_admin_user(name: str, email: str, password: str,
                      company_group: str = "HQ", company_name: str = "본사",
                      role_name: str = "본사 관리자") -> None:
    """
    관리자 계정 생성
    
    Args:
        name: 사용자명
        email: 이메일(로그인 ID)
        password: 평문 비밀번호
        company_group: 회사 그룹(HQ/BRANCH)
        company_name: 회사명
        role_name: 역할명(예: 본사 관리자)
    """
    # DB 테이블 생성
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # 기존 사용자 확인
        existing_user = db.query(User).filter(User.email == email).first()
        
        if existing_user:
            logger.warning(f"⚠️ 이미 존재하는 사용자: {email}")
            return
        
        # 비밀번호 해싱 (UserService)
        password_hash = UserService.hash_password(password)
        
        # 회사와 역할 확보(없으면 생성)
        company = db.query(Company).filter(Company.company_group == company_group, Company.name == company_name).first()
        if company is None:
            company = Company(company_group=company_group, name=company_name)
            db.add(company)
            db.flush()  # company_id 확보

        role = db.query(Role).filter(Role.role_name == role_name).first()
        if role is None:
            role = Role(role_name=role_name, description="관리자")
            db.add(role)
            db.flush()  # role_id 확보

        # 새 사용자 생성
        admin_user = User(
            name=name,
            email=email,
            password_hash=password_hash,
            company_id=company.company_id,
            role_id=role.role_id,
            is_active=True
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        logger.info("✅ 관리자 계정 생성 완료")
        logger.info(f"   - ID: {admin_user.user_id}")
        logger.info(f"   - 이름: {admin_user.name}")
        logger.info(f"   - 이메일: {admin_user.email}")
        logger.info(f"   - 회사: {company.company_group} / {company.name}")
        logger.info(f"   - 역할: {role.role_name}")
        logger.info(f"   - 활성화: {admin_user.is_active}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 관리자 계정 생성 실패: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    # 기본 관리자 계정 생성
    create_admin_user(
        name="관리자",
        email="admin@babba-api.local",
        password="admin123"  # ⚠️ 프로덕션에서는 반드시 변경하세요!
    )
