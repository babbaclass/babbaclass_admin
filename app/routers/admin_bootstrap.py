from fastapi import APIRouter, Depends, HTTPException, Header, Body
from sqlalchemy.orm import Session
from typing import Optional
import os

from app.database import get_db
from app.models import Company, Role, User
from app.services.organization_service import UserService
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


class BootstrapRequest(BaseModel):
    """Request body for creating/updating an admin user.

    name/email/password는 필수이며, 나머지는 기본값이 있습니다.
    """
    name: str
    email: EmailStr
    password: str
    company_group: str = "HQ"
    company_name: str = "본사"
    role_name: str = "본사 관리자"


def _require_bootstrap_token(x_admin_bootstrap_token: Optional[str]) -> None:
    expected = os.getenv("ADMIN_BOOTSTRAP_TOKEN")
    if not expected:
        raise HTTPException(status_code=500, detail="ADMIN_BOOTSTRAP_TOKEN is not configured")
    if not x_admin_bootstrap_token or x_admin_bootstrap_token != expected:
        raise HTTPException(status_code=401, detail="Invalid bootstrap token")


@router.post("/bootstrap", summary="Create or update an admin user")
def create_or_update_admin(
    payload: BootstrapRequest = Body(...),
    db: Session = Depends(get_db),
    x_admin_bootstrap_token: Optional[str] = Header(default=None, convert_underscores=False),
):
    """
    Create or update an admin user via API.

    Security: Requires header `X-Admin-Bootstrap-Token` to match ADMIN_BOOTSTRAP_TOKEN env var.
    """
    _require_bootstrap_token(x_admin_bootstrap_token)

    # Extract
    name = payload.name
    email = str(payload.email)
    password = payload.password
    company_group = payload.company_group
    company_name = payload.company_name
    role_name = payload.role_name

    print("[/users/bootstrap] start", {
        "email": email,
        "company_group": company_group,
        "company_name": company_name,
        "role_name": role_name,
    })

    # Ensure company by company_type
    company = db.query(Company).filter(Company.company_type == company_group, Company.name == company_name).first()
    if company is None:
        try:
            company = Company(company_type=company_group, name=company_name)
            db.add(company)
            db.flush()
        except Exception as e:
            db.rollback()
            print("[/users/bootstrap] company insert failed:", str(e))
            raise HTTPException(status_code=500, detail=f"company insert failed: {e}")

    # Ensure role
    role = db.query(Role).filter(Role.role_name == role_name).first()
    if role is None:
        try:
            role = Role(role_name=role_name, description="관리자")
            db.add(role)
            db.flush()
        except Exception as e:
            db.rollback()
            print("[/users/bootstrap] role insert failed:", str(e))
            raise HTTPException(status_code=500, detail=f"role insert failed: {e}")

    # Upsert user
    user = db.query(User).filter(User.email == email).first()
    password_hash = UserService.hash_password(password)
    try:
        if user is None:
            user = User(
                name=name,
                email=email,
                password_hash=password_hash,
                company_id=company.company_id,
                role_id=role.role_id,
                is_active=True,
            )
            db.add(user)
        else:
            # Use setattr to avoid static type confusion between Column[...] and runtime values
            setattr(user, "name", name or user.name)
            setattr(user, "password_hash", password_hash)
            setattr(user, "company_id", company.company_id)
            setattr(user, "role_id", role.role_id)
            setattr(user, "is_active", True)

        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        print("[/users/bootstrap] user upsert failed:", str(e))
        raise HTTPException(status_code=500, detail=f"user upsert failed: {e}")

    return {
        "status": "ok",
        "user_id": user.user_id,
        "email": user.email,
        "company": {"group": getattr(company, "company_type", None), "name": company.name},
        "role": role.role_name,
    }
