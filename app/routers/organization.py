"""
API endpoints for Company, Role, and User management

조직 구조 관리 CRUD 엔드포인트
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List, cast

from app.database import get_db
from app.schemas import (
    CompanyCreate, CompanyUpdate, CompanyResponse, CompanyDetailResponse,
    RoleCreate, RoleUpdate, RoleResponse,
    UserCreate, UserUpdate, UserResponse, UserDetailResponse
)
from app.services.organization_service import (
    CompanyService, RoleService, UserService
)
from app.models import Company

router = APIRouter(prefix="/api/v1", tags=["organization"])


# ========== Company Endpoints ==========

@router.post(
    "/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회사/지사 생성",
    description="새로운 본사 또는 지사를 생성합니다."
)
def create_company(
    company: CompanyCreate,
    db: Session = Depends(get_db)
):
    """Create a new company (HQ or BRANCH)"""
    db_company = CompanyService.create(db, company)
    return db_company


@router.get(
    "/companies/{company_id}",
    response_model=CompanyDetailResponse,
    summary="회사/지사 조회",
    description="특정 회사/지사의 상세 정보를 조회합니다."
)
def get_company(
    company_id: int,
    db: Session = Depends(get_db)
):
    """Get company by ID with branches (when HQ) and users"""
    db_company = CompanyService.get(db, company_id)
    if not db_company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회사를 찾을 수 없습니다."
        )
    
    users = UserService.get_by_company(db, company_id)
    branches: list[Company] = []
    if getattr(db_company, "company_type", None) == "HQ":
        branches = db.query(Company).filter(Company.hq_company_id == company_id, Company.company_type == "BRANCH").all()
    
    base = CompanyResponse.from_orm(db_company).model_dump()
    # enrich with group/grade labels if available
    # Map company_type back to company_group in response for compatibility
    base["company_group"] = getattr(db_company, "company_type", None)
    return {**base, "users": users, "branches": branches}


@router.get(
    "/companies",
    response_model=List[CompanyResponse],
    summary="모든 회사/지사 조회",
    description="모든 회사와 지사를 조회합니다."
)
def list_companies(
    skip: int = 0,
    limit: int = 100,
    company_group: str | None = None,
    db: Session = Depends(get_db)
):
    """Get all companies"""
    if company_group:
        companies = CompanyService.get_by_group(db, company_group, skip, limit)
    else:
        companies = CompanyService.get_all(db, skip, limit)
    
    # attach company_group from company_type for backward compatibility
    for c in companies:
        try:
            setattr(c, "company_group", getattr(c, "company_type", None))
        except Exception:
            pass
    return companies

@router.get(
    "/companies/{company_id}/branches",
    response_model=List[CompanyResponse],
    summary="지사 목록 조회",
    description="특정 본사의 지사 목록을 조회합니다."
)
def get_branches(
    company_id: int,
    db: Session = Depends(get_db)
):
    company = CompanyService.get(db, company_id)
    if not company or getattr(company, "company_type", None) != "HQ":
        raise HTTPException(status_code=404, detail="본사를 찾을 수 없거나 HQ가 아닙니다.")
    branches = db.query(Company).filter(Company.hq_company_id == company_id, Company.company_type == "BRANCH").all()
    for b in branches:
        setattr(b, "company_group", getattr(b, "company_type", None))
    return branches




@router.put(
    "/companies/{company_id}",
    response_model=CompanyResponse,
    summary="회사/지사 수정",
    description="회사/지사 정보를 수정합니다."
)
def update_company(
    company_id: int,
    company: CompanyUpdate,
    db: Session = Depends(get_db)
):
    """Update a company"""
    db_company = CompanyService.update(db, company_id, company)
    if not db_company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회사를 찾을 수 없습니다."
        )
    
    return db_company


@router.delete(
    "/companies/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="회사/지사 삭제",
    description="회사/지사를 삭제합니다."
)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db)
):
    """Delete a company"""
    success = CompanyService.delete(db, company_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회사를 찾을 수 없습니다."
        )


# ========== Role Endpoints ==========

@router.post(
    "/roles",
    response_model=RoleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="역할 생성",
    description="새로운 역할(직책)을 생성합니다."
)
def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db)
):
    """Create a new role"""
    # Check if role already exists
    existing_role = RoleService.get_by_name(db, role.role_name)
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 존재하는 역할명입니다."
        )
    
    db_role = RoleService.create(db, role)
    return db_role


@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="역할 조회",
    description="특정 역할의 정보를 조회합니다."
)
def get_role(
    role_id: int,
    db: Session = Depends(get_db)
):
    """Get role by ID"""
    db_role = RoleService.get(db, role_id)
    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="역할을 찾을 수 없습니다."
        )
    
    return db_role


@router.get(
    "/roles",
    response_model=List[RoleResponse],
    summary="모든 역할 조회",
    description="모든 역할을 조회합니다."
)
def list_roles(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all roles"""
    roles = RoleService.get_all(db, skip, limit)
    return roles


@router.put(
    "/roles/{role_id}",
    response_model=RoleResponse,
    summary="역할 수정",
    description="역할 정보를 수정합니다."
)
def update_role(
    role_id: int,
    role: RoleUpdate,
    db: Session = Depends(get_db)
):
    """Update a role"""
    db_role = RoleService.update(db, role_id, role)
    if not db_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="역할을 찾을 수 없습니다."
        )
    
    return db_role


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="역할 삭제",
    description="역할을 삭제합니다."
)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db)
):
    """Delete a role"""
    success = RoleService.delete(db, role_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="역할을 찾을 수 없습니다."
        )


# ========== User Endpoints ==========

@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="사용자 생성",
    description="새로운 사용자(직원)를 생성합니다."
)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    """Create a new user"""
    # Validate company_id
    company = CompanyService.get(db, user.company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="회사를 찾을 수 없습니다."
        )
    
    # Validate role_id
    role = RoleService.get(db, user.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="역할을 찾을 수 없습니다."
        )
    
    # Check if email already exists
    existing_user = UserService.get_by_email(db, user.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 존재하는 이메일입니다."
        )
    
    db_user = UserService.create(db, user)
    return db_user


@router.get(
    "/users/{user_id}",
    response_model=UserDetailResponse,
    summary="사용자 조회",
    description="특정 사용자의 상세 정보를 조회합니다."
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get user by ID with company and role names"""
    db_user = UserService.get(db, user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    # Get additional details
    company = CompanyService.get(db, cast(int, db_user.company_id))
    role = RoleService.get(db, cast(int, db_user.role_id))
    return {
        **UserResponse.from_orm(db_user).model_dump(),
        "company_name": company.name if company else None,
        "role_name": role.role_name if role else None
    }


@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="모든 사용자 조회",
    description="모든 사용자를 조회합니다."
)
def list_users(
    skip: int = 0,
    limit: int = 100,
    company_id: int | None = None,
    role_id: int | None = None,
    db: Session = Depends(get_db)
):
    """Get all users with optional filtering"""
    if company_id:
        users = UserService.get_by_company(db, company_id)
    elif role_id:
        users = UserService.get_by_role(db, role_id)
    else:
        users = UserService.get_all(db, skip, limit)
    
    return users[skip:skip+limit]


# 조직 상하관계 관련 엔드포인트는 제거되었습니다.


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    summary="사용자 수정",
    description="사용자 정보를 수정합니다."
)
def update_user(
    user_id: int,
    user: UserUpdate,
    db: Session = Depends(get_db)
):
    """Update a user"""
    db_user = UserService.update(db, user_id, user)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )
    
    return db_user


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="사용자 삭제",
    description="사용자를 삭제합니다."
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Delete a user"""
    success = UserService.delete(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다."
        )


# ========== Authentication Endpoint ==========

@router.post(
    "/auth/login",
    summary="사용자 로그인",
    description="이름과 비밀번호로 로그인합니다."
)
def login(
    request: Request,
    name: str,
    password: str,
    db: Session = Depends(get_db)
):
    """Authenticate user by name"""
    user = UserService.authenticate(db, name, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이름 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    from app.services.login_history_service import get_client_ip, record_login_history

    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    record_login_history(
        db=db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        source="user-api",
    )

    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "company_id": user.company_id,
        "role_id": user.role_id,
        "message": "로그인 성공"
    }
