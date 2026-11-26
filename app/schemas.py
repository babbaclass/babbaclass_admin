"""
Pydantic schemas for API request/response validation

조직 구조 관리: Company, Role, User
"""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List


# ========== Company Schemas ==========

class CompanyBase(BaseModel):
    """Base schema for Company (simplified, contacts removed)"""
    company_group: str = Field(..., description="'HQ'(본사) 또는 'BRANCH'(지사)")  # maps to company_type
    name: str = Field(..., min_length=1, max_length=255, description="본사명 또는 지사명")
    address: Optional[str] = Field(None, max_length=500, description="주소")


class CompanyCreate(CompanyBase):
    """Schema for creating a Company"""
    pass


class CompanyUpdate(BaseModel):
    """Schema for updating a Company (simplified)"""
    company_group: Optional[str] = None
    name: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class CompanyResponse(CompanyBase):
    """Schema for Company response"""
    company_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CompanyDetailResponse(CompanyResponse):
    """Schema for Company detailed response with users"""
    users: Optional[List['UserResponse']] = None
    branches: Optional[List['CompanyResponse']] = None  # for HQ companies


# ========== Role Schemas ==========

class RoleBase(BaseModel):
    """Base schema for Role"""
    role_name: str = Field(..., min_length=1, max_length=100, description="역할명")
    description: Optional[str] = Field(None, description="역할 설명")


class RoleCreate(RoleBase):
    """Schema for creating a Role"""
    pass


class RoleUpdate(BaseModel):
    """Schema for updating a Role"""
    role_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RoleResponse(RoleBase):
    """Schema for Role response"""
    role_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== User Schemas ==========

class UserBase(BaseModel):
    """Base schema for User (simplified contacts)"""
    name: str = Field(..., min_length=1, max_length=255, description="사용자명")
    email: EmailStr = Field(..., description="이메일 (로그인 ID)")
    company_id: int = Field(..., description="소속 위치 ID")
    role_id: int = Field(..., description="직책/역할 ID")
    main_contact: Optional[str] = Field(None, max_length=255, description="대표 연락처")
    sub_contact: Optional[str] = Field(None, max_length=255, description="보조 연락처")


class UserCreate(UserBase):
    """Schema for creating a User"""
    password: str = Field(..., min_length=8, description="비밀번호 (최소 8자)")


class UserUpdate(BaseModel):
    """Schema for updating a User (simplified contacts)"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    company_id: Optional[int] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8, description="새 비밀번호")
    main_contact: Optional[str] = None
    sub_contact: Optional[str] = None


class UserResponse(UserBase):
    """Schema for User response"""
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """Schema for User detailed response"""
    company_name: Optional[str] = None
    role_name: Optional[str] = None

# Contact schemas removed – simplified contact representation inline on User.


# Update forward references for nested models
CompanyDetailResponse.update_forward_refs()
UserDetailResponse.update_forward_refs()
