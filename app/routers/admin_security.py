"""Minimal admin security endpoints (password change hooks)"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.database import SessionLocal
from app.models import User
from app.services.organization_service import UserService

router = APIRouter()
logger = logging.getLogger(__name__)


class PasswordChangePayload(BaseModel):
    current_password: str | None = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


@router.post("/password-change")
async def change_password(request: Request, payload: PasswordChangePayload):
    user_id = request.session.get("user_id")
    role_id = request.session.get("role_id")
    if not user_id or role_id not in {1, 2}:
        return JSONResponse({"status": "error", "message": "권한이 없습니다"}, status_code=401)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == int(user_id)).first()
        if user is None:
            return JSONResponse({"status": "error", "message": "사용자를 찾을 수 없습니다"}, status_code=404)

        if not UserService.verify_password(payload.current_password or "", user.password_hash):
            return JSONResponse({"status": "error", "message": "현재 비밀번호가 일치하지 않습니다"}, status_code=400)

        if payload.new_password != payload.confirm_password:
            return JSONResponse({"status": "error", "message": "새 비밀번호와 확인값이 일치하지 않습니다"}, status_code=400)

        if payload.new_password == payload.current_password:
            return JSONResponse({"status": "error", "message": "새 비밀번호는 현재 비밀번호와 달라야 합니다"}, status_code=400)

        setattr(user, "password_hash", UserService.hash_password(payload.new_password))
        user.password_change_required = False
        db.commit()

        request.session["password_change_required"] = False
        return JSONResponse({"status": "success", "message": "비밀번호를 저장했습니다"})
    except Exception:
        logger.exception("Failed to change password for admin user")
        return JSONResponse({"status": "error", "message": "비밀번호 저장 중 오류가 발생했습니다"}, status_code=500)
    finally:
        db.close()


@router.post("/session-keepalive")
async def session_keepalive(request: Request):
    if request.session.get("is_admin") is not True:
        return JSONResponse({"status": "error", "message": "권한이 없습니다"}, status_code=401)

    request.session["last_keepalive"] = datetime.now(timezone.utc).isoformat()
    return JSONResponse({"status": "success", "message": "세션을 연장했습니다"})
