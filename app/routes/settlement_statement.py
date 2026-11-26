"""
정산서 페이지 라우트

정산서 조회 페이지를 FastAPI 라우트로 제공합니다.
"""

from fastapi import APIRouter, Request
from starlette.templating import Jinja2Templates
from starlette.responses import HTMLResponse
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settlement"])

# 템플릿 디렉토리 설정
template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=template_dir)


@router.get("/settlement-statement/")
async def settlement_statement(
    request: Request,
    year: int | None = None,
    month: int | None = None,
    company_id: int | None = None,
):
    """정산서 페이지"""
    
    # 기본값: 현재 연월
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month
    
    # 로그인 정보
    user_id = request.session.get("user_id")
    role_id = request.session.get("role_id")
    
    if not user_id:
        return templates.TemplateResponse("settlement_statement.html", {
            "request": request,
            "error": "로그인이 필요합니다",
            "year": year,
            "month": month
        })
    
    # 역할 확인 (1, 2, 3 모두 접근 가능)
    if role_id not in {1, 2, 3}:
        return templates.TemplateResponse("settlement_statement.html", {
            "request": request,
            "error": "접근 권한이 없습니다",
            "year": year,
            "month": month
        })
    
    # Jinja2 템플릿으로 렌더링
    return templates.TemplateResponse("settlement_statement.html", {
        "request": request,
        "year": year,
        "month": month,
        "user_id": user_id,
        "role_id": role_id
    })


# 아래 라우트들은 BaseView로 대체되었으므로 제거
# - /settlement-status/ -> SettlementStatusView (admin.py)
# - /settlement-overview/ -> SettlementOverviewView (admin.py)

