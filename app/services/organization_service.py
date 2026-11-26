"""Service layer for CRUD operations on Company, Role, and User models (simplified: contacts removed)"""

from __future__ import annotations

from sqlalchemy.orm import Session
from app.models import Company, Role, User
from app.schemas import (
    CompanyCreate, CompanyUpdate, RoleCreate, RoleUpdate,
    UserCreate, UserUpdate
)
from passlib.context import CryptContext

# Password hashing context: bcrypt only
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ========== Company Services ==========

class CompanyService:
    """Service for Company CRUD operations"""

    @staticmethod
    def create(db: Session, company: CompanyCreate) -> Company:
        """Create a new company (no contacts JSON)"""
        data = company.model_dump()
        # Map company_group (schema field) -> company_type (column)
        company_type = data.pop("company_group", None) or "HQ"
        db_company = Company(company_type=company_type, **data)
        db.add(db_company)
        db.commit()
        db.refresh(db_company)
        return db_company

    @staticmethod
    def get(db: Session, company_id: int) -> Company | None:
        """Get company by ID"""
        return db.query(Company).filter(Company.company_id == company_id).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> list[Company]:
        """Get all companies"""
        return db.query(Company).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_group(db: Session, company_group: str, skip: int = 0, limit: int = 100) -> list[Company]:
        """Get companies by group (HQ or BRANCH)"""
        return (
            db.query(Company)
            .filter(Company.company_type == company_group)
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update(db: Session, company_id: int, company: CompanyUpdate) -> Company | None:
        """Update a company"""
        db_company = CompanyService.get(db, company_id)
        if not db_company:
            return None
        
        update_data = company.model_dump(exclude_unset=True)
        # Handle company_group(schema) -> company_type(column)
        if "company_group" in update_data and update_data["company_group"] is not None:
            group_code = update_data.pop("company_group")
            update_data["company_type"] = group_code
        for key, value in update_data.items():
            setattr(db_company, key, value)
        
        db.commit()
        db.refresh(db_company)
        return db_company

    @staticmethod
    def delete(db: Session, company_id: int) -> bool:
        """Delete a company"""
        db_company = CompanyService.get(db, company_id)
        if not db_company:
            return False
        
        db.delete(db_company)
        db.commit()
        return True


# ========== Role Services ==========

class RoleService:
    """Service for Role CRUD operations"""

    @staticmethod
    def create(db: Session, role: RoleCreate) -> Role:
        """Create a new role"""
        db_role = Role(**role.model_dump())
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        return db_role

    @staticmethod
    def get(db: Session, role_id: int) -> Role | None:
        """Get role by ID"""
        return db.query(Role).filter(Role.role_id == role_id).first()

    @staticmethod
    def get_by_name(db: Session, role_name: str) -> Role | None:
        """Get role by name"""
        return db.query(Role).filter(Role.role_name == role_name).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> list[Role]:
        """Get all roles"""
        return db.query(Role).offset(skip).limit(limit).all()

    @staticmethod
    def update(db: Session, role_id: int, role: RoleUpdate) -> Role | None:
        """Update a role"""
        db_role = RoleService.get(db, role_id)
        if not db_role:
            return None
        
        update_data = role.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_role, key, value)
        
        db.commit()
        db.refresh(db_role)
        return db_role

    @staticmethod
    def delete(db: Session, role_id: int) -> bool:
        """Delete a role"""
        db_role = RoleService.get(db, role_id)
        if not db_role:
            return False
        
        db.delete(db_role)
        db.commit()
        return True


# ========== User Services ==========

class UserService:
    """Service for User CRUD operations"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password using bcrypt."""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False

    @staticmethod
    def create(db: Session, user: UserCreate) -> User:
        """Create a new user (contacts removed)
        
        이메일 중복 시 기존 사용자를 업데이트합니다.
        """
        hashed_password = UserService.hash_password(user.password)
        user_data = user.model_dump(exclude={'password'})
        
        # 같은 이메일의 기존 사용자 확인
        existing_user = db.query(User).filter(User.email == user_data['email']).first()
        
        if existing_user:
            # 기존 사용자 업데이트
            for key, value in user_data.items():
                setattr(existing_user, key, value)
            setattr(existing_user, "password_hash", hashed_password)
            db.commit()
            db.refresh(existing_user)
            return existing_user
        else:
            # 신규 사용자 생성
            db_user = User(**user_data, password_hash=hashed_password)
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user

    @staticmethod
    def get(db: Session, user_id: int) -> User | None:
        """Get user by ID"""
        return db.query(User).filter(User.user_id == user_id).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_by_name(db: Session, name: str) -> User | None:
        """Get user by name (login identifier)"""
        return db.query(User).filter(User.name == name).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
        """Get all users"""
        return db.query(User).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_company(db: Session, company_id: int) -> list[User]:
        """Get all users in a company"""
        return db.query(User).filter(User.company_id == company_id).all()

    @staticmethod
    def get_by_role(db: Session, role_id: int) -> list[User]:
        """Get all users with a specific role"""
        return db.query(User).filter(User.role_id == role_id).all()

    @staticmethod
    def get_subordinates(db: Session, user_id: int) -> list[User]:
        """Deprecated: hierarchy not supported"""
        return []

    @staticmethod
    def update(db: Session, user_id: int, user: UserUpdate) -> User | None:
        """Update a user"""
        db_user = UserService.get(db, user_id)
        if not db_user:
            return None
        
        update_data = user.model_dump(exclude_unset=True, exclude={'password'})
        
        # Handle password separately if provided
        if user.password:
            update_data['password_hash'] = UserService.hash_password(user.password)
        
        for key, value in update_data.items():
            setattr(db_user, key, value)
        
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def delete(db: Session, user_id: int) -> bool:
        """Delete a user"""
        db_user = UserService.get(db, user_id)
        if not db_user:
            return False
        
        db.delete(db_user)
        db.commit()
        return True

    @staticmethod
    def authenticate(db: Session, name: str, password: str) -> User | None:
        """Authenticate user by name and password"""
        user = UserService.get_by_name(db, name)
        if not user or not UserService.verify_password(password, str(user.password_hash)):
            return None
        # is_register=True이고 role_id가 1 또는 2인 경우만 로그인 가능
        if user.is_register is not True or user.role_id not in (1, 2):
            return None
        return user
