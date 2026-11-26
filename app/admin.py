"""
SQLAdmin configuration for babba-api

sqladmin ModelView 기반 관리자 패널 구성 (SQLAlchemy 2.x 호환)

Notes
- 현재 버전: sqladmin==0.21.0, SQLAlchemy==2.0.35
- 0.16+ 이후 ModelView 메타 초기화가 안정화되어 SA 2.x에서 동작합니다.
- 새로운 클래스 문법 권장: `class FooAdmin(ModelView, model=Foo)`
"""

from __future__ import annotations

import os
from fastapi import FastAPI
from sqladmin import Admin, ModelView, BaseView, expose  # type: ignore
from sqladmin.authentication import AuthenticationBackend  # type: ignore
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.middleware.sessions import SessionMiddleware
from app.database import engine
from app.models import (
    User,
    Company,
    Role,
    Product,
    Order,
    OrderItem,
    Member,
    Grade,
    CommissionType,
    CommissionRateWindow,
    Settlement,
    Statement,
    SettlementCompanyMonthlyAggregate,
    SettlementStatementConfirmation,
    LoginHistory,
    ContractEnd,
    SettlementSkipRecord,
    Notice,
)
from app.database import SessionLocal
from app.services.organization_service import UserService
from app.services.login_history_service import get_client_ip, record_login_history
from app.services.notice_service import (
    fetch_live_notices,
    format_notice_exposure_status,
    format_notice_period,
    notice_is_live,
    notice_reference_date,
)
import logging
from typing import Any, Iterable, List, Tuple, Callable
from starlette.requests import Request as StarletteRequest, Request
from sqlalchemy import select, func, or_
from sqlalchemy.sql import Select
from sqlalchemy.orm import selectinload
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
import wtforms
from wtforms import fields, validators
from sqladmin.fields import DateField as SQLAdminDateField

logger = logging.getLogger(__name__)

from app.services.monthly_settlement_summary_service import (
    MONTHLY_SETTLEMENT_SUMMARY_EXCLUDED_REGIONS,
    build_monthly_summary_row,
    fetch_confirmation_maps,
    fetch_monthly_payment_status_map,
    normalize_payment_date_for_input,
)
# Helper formatters
# =========================================================================

def _format_korean_date(val):
    """Format datetime to 'YYYY월MM월DD일' as requested (literal pattern).
    If value is None or not a datetime, returns empty string.
    """
    try:
        if not val:
            return ""
        if not isinstance(val, datetime):
            return ""
        return f"{val.strftime('%Y')}월{val.strftime('%m')}월{val.strftime('%d')}일"
    except Exception:
        return ""

def _format_currency(value):
    """Format number with 3-digit comma separator (e.g., 1,234,567)"""
    try:
        if value is None:
            return ""
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def _fmt_doc_submitted(model: Any, field_name: str):
    """서류 제출 여부 — 목록용 ✓ / ✗"""
    from markupsafe import Markup

    if bool(getattr(model, field_name, False)):
        return Markup(
            '<span class="user-doc-status user-doc-status--yes" title="제출">✓</span>'
        )
    return Markup(
        '<span class="user-doc-status user-doc-status--no" title="미제출">✗</span>'
    )


def _get_branch_manager_name(model, attribute):
    """Get the branch manager (지사장) name for a company"""
    try:
        from app.models import Company, User
        from app.database import engine
        from sqlalchemy.orm import Session
        
        company_id = getattr(model, 'company_id', None)
        if not company_id:
            return ""
        
        # Get session and query
        db = Session(bind=engine)
        try:
            # Find users with role_id=2 (지사장) for this company
            user = db.query(User).filter(
                User.company_id == company_id,
                User.role_id == 2
            ).first()
            
            if user:
                return user.name or ""
            return ""
        finally:
            db.close()
    except Exception:
        return ""


def _fmt_company_type(model, attr):
    """회사 유형(HQ/BRANCH)을 사용자 친화적 텍스트로 변환"""
    code = getattr(model, 'company_type', None)
    if code == 'HQ':
        return '본사직영'
    if code == 'BRANCH':
        return '지사'
    return code or ''


# 캐시: 등급 id -> 등급명 (프로세스 단위 간단 캐시)
_grade_name_cache: dict[int, str] = {}
_company_name_cache: dict[int, str] = {}
_role_name_cache: dict[int, str] = {}


def _fmt_grade_value(model, attr):
    """
    포매터: grade_value 텍스트 표시
    
    우선순위:
    1. 캐시에서 조회 (가장 빠름)
    2. eager-loaded grade 관계 사용 (회피 가능하지만 시도)
    3. DB 직접 조회 (캐시에 저장)
    """
    try:
        gid = getattr(model, 'grade_id', None)
        if not gid:
            return ''
        
        # 1) 캐시에 먼저 확인
        if gid in _grade_name_cache:
            return _grade_name_cache[gid]
        
        # 2) eager-loaded 관계 시도 (세션 바깥이면 실패 가능)
        try:
            grade = getattr(model, 'grade', None)
            if grade:
                grade_name = str(getattr(grade, 'grade_name', '') or '')
                _grade_name_cache[gid] = grade_name
                return grade_name
        except Exception:
            # lazy load 실패는 무시하고 다음 단계로
            pass
        
        # 3) DB에서 조회 (캐시에 저장)
        from app.database import SessionLocal
        from app.models import Grade
        db = SessionLocal()
        try:
            grade = db.query(Grade).filter(Grade.grade_id == gid).first()
            grade_name = str(getattr(grade, 'grade_name', '') or '') if grade else ''
            _grade_name_cache[gid] = grade_name
            return grade_name
        finally:
            db.close()
    except Exception:
        return ''


def _resolve_company_name(company_id: int) -> str | None:
    if company_id in _company_name_cache:
        return _company_name_cache[company_id]
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.company_id == company_id).first()
        if company and getattr(company, 'name', None):
            name_value = str(getattr(company, 'name') or '')
            if name_value:
                _company_name_cache[company_id] = name_value
                return name_value
    finally:
        db.close()
    return None

def _resolve_role_name(role_id: int | None) -> str | None:
    if not role_id:
        return None
    if role_id in _role_name_cache:
        return _role_name_cache[role_id]
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.role_id == role_id).first()
        if role and getattr(role, 'role_name', None):
            name_value = str(getattr(role, 'role_name') or '')
            _role_name_cache[role_id] = name_value
            return name_value
    finally:
        db.close()
    return None


def _fmt_commission_window_type(model, attr):  # type: ignore[no-redef]
    """CommissionRateWindow의 commission_type 포매터"""
    try:
        ct = getattr(model, 'commission_type', None)
        code = getattr(ct, 'code', None)
        name = getattr(ct, 'name', None)
        return str(code or name or getattr(model, 'commission_type_id', ''))
    except Exception:
        return str(getattr(model, 'commission_type_id', ''))


def _fmt_commission_window_company(model, attr):  # type: ignore[no-redef]
    """CommissionRateWindow의 회사명 포매터"""
    try:
        company_id = getattr(model, 'company_id', None)
        logger.debug(f"[Formatter] company_id={company_id}")
        
        if company_id is None:
            logger.debug(f"[Formatter] company_id is None, returning '전체'")
            return "전체"
        
        # 1) 캐시에서 먼저 확인
        if company_id in _company_name_cache:
            cached = _company_name_cache[company_id]
            logger.debug(f"[Formatter] Found in cache: {cached}")
            return cached
        
        # 2) eager-loaded company 관계 시도
        try:
            company = getattr(model, 'company', None)
            logger.debug(f"[Formatter] company object from getattr: {company}")
            if company is not None:
                company_name = getattr(company, 'name', None)
                logger.debug(f"[Formatter] company_name from relation: {company_name}")
                if company_name:
                    name_str = str(company_name)
                    _company_name_cache[company_id] = name_str
                    logger.debug(f"[Formatter] Cached and returning: {name_str}")
                    return name_str
        except Exception as e:
            logger.debug(f"[Formatter] Failed to get company from relation: {type(e).__name__}: {e}")
        
        # 3) DB에서 직접 조회 및 캐시
        logger.debug(f"[Formatter] Attempting DB lookup for company_id={company_id}")
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                company = db.query(Company).filter(Company.company_id == company_id).first()
                logger.debug(f"[Formatter] DB query result: {company}")
                if company:
                    name_value = getattr(company, 'name', None)
                    logger.debug(f"[Formatter] company.name from DB: {name_value}")
                    if name_value:
                        name_str = str(name_value)
                        _company_name_cache[company_id] = name_str
                        logger.debug(f"[Formatter] Cached from DB and returning: {name_str}")
                        return name_str
                    else:
                        logger.debug(f"[Formatter] company.name is None/empty")
                else:
                    logger.debug(f"[Formatter] Company not found in DB for id {company_id}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"[Formatter] DB error: {type(e).__name__}: {e}", exc_info=True)
        
        # 4) 모두 실패하면 ID만 반환
        logger.debug(f"[Formatter] All attempts failed, returning company_id as string: {company_id}")
        return str(company_id)
    except Exception as e:
        logger.error(f"[CommissionRateWindowAdmin] Unexpected error: {type(e).__name__}: {e}", exc_info=True)
        return ""


def _fmt_order_payment_status(model: Any, attribute: Any) -> str:
    """
    주문의 결제 상태를 사용자 친화적인 한글 텍스트로 반환합니다.
    
    매핑:
    - 'Y' 또는 유사 결제 완료 코드 → '결제 완료'
    - 'N' 또는 유사 결제 미처리 코드 → '결제 전'
    - 'C' 또는 유사 결제 취소 코드 → '결제 실패'
    """
    try:
        # 1) pay_status 우선 시도, 없으면 payment_status 시도
        status_value = getattr(model, 'pay_status', None) or getattr(model, 'payment_status', None)
        
        if status_value is None:
            return ""
        
        s = str(status_value).strip().upper()
        
        # 매핑: Y → 결제 완료
        if s in {"Y", "PAID", "PAID_SUCCESS", "COMPLETED", "OK", "TRUE", "1"}:
            return "결제 완료"
        
        # 매핑: N → 결제 전
        if s in {"N", "PENDING", "UNPAID", "NONE", "FALSE", "0", ""}:
            return "결제 전"
        
        # 매핑: C → 결제 실패
        if s in {"C", "CANCELLED", "FAILED", "FAIL", "CANCEL"}:
            return "결제 실패"
        
        # 그 외 알 수 없는 값은 빈 문자열 반환
        return ""
    except Exception:
        return ""

def _fmt_order_order_status(model: Any, attribute: Any) -> str:
    """
    주문의 주문 상태를 사용자 친화적인 한글 텍스트로 반환합니다.
    
    Makeshop API order_status 매핑:
    - 'N' → '배송 전' (배송전)
    - 'S' → '발송 준비' (발송준비)
    - 'Y' → '발송 완료' (발송완료)
    - 'D' → '취소 요청' (취소요청)
    - 'C' → '주문 취소' (주문취소)
    - 'R' → '반품' (반품)
    - 'X' → '배송 요청' (배송요청)
    - 'P' → '부분 배송' (부분배송)
    - 'E' → '환불 대기' (환불대기)
    - 'Q' → '부분 배송 준비' (부분배송준비)
    """
    try:
        status_value = getattr(model, 'order_status', None)
        
        if status_value is None:
            return ""
        
        s = str(status_value).strip().upper()
        
        # 순서대로 매핑
        status_map = {
            "N": "배송 전",
            "S": "발송 준비",
            "Y": "발송 완료",
            "D": "취소 요청",
            "C": "주문 취소",
            "R": "반품",
            "X": "배송 요청",
            "P": "부분 배송",
            "E": "환불 대기",
            "Q": "부분 배송 준비",
        }
        
        return status_map.get(s, "")
    except Exception:
        return ""

# =========================================================================
# Simple ColumnFilter implementations (structural match with SQLAdmin protocol)
# =========================================================================

class SelectEqualFilter:
    """
    Minimal ColumnFilter for equality with a fixed set of choices.
    Satisfies ColumnFilter protocol: parameter_name, lookups, get_filtered_query, title().
    """

    def __init__(self, column: Any, options: Iterable[tuple[str, str]], title: str | None = None, parameter_name: str | None = None) -> None:
        self.column = column
        self.title: str = title or getattr(column, "key", str(column))
        self.parameter_name: str = parameter_name or getattr(column, "key", "value")
        # cache options
        self._options: List[Tuple[str, str]] = list(options)

    async def lookups(self, request: StarletteRequest, model: Any, run_query: Callable[[Select], Any]) -> List[Tuple[str, str]]:
        return self._options

    async def get_filtered_query(self, query: Select, value: Any, model: Any) -> Select:  # SQLAlchemy Select is expected
        if value in (None, ""):
            return query
        try:
            return query.where(self.column == value)
        except Exception:
            # Fallback for ORM Query API if used
            return query.filter(self.column == value)

class BooleanEqualFilter(SelectEqualFilter):
    def __init__(self, column: Any, title: str | None = None, parameter_name: str | None = None) -> None:
        options = [("true", "활성"), ("false", "비활성")]
        super().__init__(column, options=options, title=title, parameter_name=parameter_name)

    async def get_filtered_query(self, query: Select, value: Any, model: Any) -> Select:
        if value in (None, ""):
            return query
        v = str(value).strip().lower() in {"1", "true", "y", "yes"}
        try:
            return query.where(self.column == v)
        except Exception:
            return query.filter(self.column == v)


class DistinctSelectFilter:
    def __init__(
        self,
        column: Any,
        title: str | None = None,
        parameter_name: str | None = None,
        limit: int | None = None,
        label_formatter: Callable[[Any], str] | None = None,
    ) -> None:
        self.column = column
        self.title: str = title or getattr(column, "key", str(column))
        self.parameter_name: str = parameter_name or getattr(column, "key", "value")
        self._limit = limit
        self._label_formatter = label_formatter or (lambda x: str(x))

    async def lookups(self, request: StarletteRequest, model: Any, run_query: Callable[[Select], Any]) -> List[Tuple[str, str]]:
        stmt = select(self.column).distinct().order_by(self.column)
        if self._limit:
            stmt = stmt.limit(self._limit)
        raw_result = await run_query(stmt)
        rows = raw_result.all() if hasattr(raw_result, "all") else list(raw_result)
        options: List[Tuple[str, str]] = []
        seen: set[str] = set()
        for row in rows:
            try:
                value = row[0]
            except Exception:
                value = row
            if value in (None, ""):
                continue
            option_value = str(value)
            if option_value in seen:
                continue
            seen.add(option_value)
            label = self._label_formatter(value)
            options.append((option_value, label))
        return options

    async def get_filtered_query(self, query: Select, value: Any, model: Any) -> Select:
        if value in (None, ""):
            return query
        filter_value = value
        if isinstance(value, str):
            column_type = getattr(self.column, "type", None)
            python_type = getattr(column_type, "python_type", None)
            try:
                if python_type:
                    filter_value = python_type(value)
            except Exception:
                filter_value = value
        try:
            return query.where(self.column == filter_value)
        except Exception:
            return query.filter(self.column == filter_value)

class AdminAuthenticationBackend(AuthenticationBackend):
    """Admin 패널 인증 백엔드"""
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)

    def __init__(self):
        super().__init__(secret_key="babba-api-secret-key")

    async def login(self, request: StarletteRequest) -> bool:  # type: ignore[override]
        def _set_error(message: str) -> None:
            request.session["auth_error"] = message

        request.session.pop("auth_error", None)
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
            if not username or not password:
                _set_error("로그인 아이디와 비밀번호를 모두 입력해주세요.")
                return False
            password_str = str(password)
            now = datetime.now(timezone.utc)
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.login_id == username).first()
                if user is None:
                    _set_error("로그인 아이디 또는 비밀번호가 올바르지 않습니다.")
                    return False

                locked_until = getattr(user, "locked_until", None)
                if locked_until:
                    if locked_until.tzinfo is None:
                        locked_until = locked_until.replace(tzinfo=timezone.utc)
                    if locked_until > now:
                        remaining = max(1, int((locked_until - now).total_seconds() + 59) // 60)
                        _set_error(f"로그인 실패 5회로 계정이 {remaining}분 동안 잠겼습니다.")
                        return False
                    user.locked_until = None
                    user.failed_login_attempts = 0

                try:
                    rid_int = int(getattr(user, "role_id", 0) or 0)
                except Exception:
                    rid_int = 0
                if rid_int not in {1, 2}:
                    _set_error("로그인 아이디 또는 비밀번호가 올바르지 않습니다.")
                    return False
                password_hash_val = str(user.password_hash or "")
                if not password_hash_val:
                    _set_error("로그인 아이디 또는 비밀번호가 올바르지 않습니다.")
                    return False
                if not UserService.verify_password(password_str, password_hash_val):
                    attempts = (getattr(user, "failed_login_attempts", 0) or 0) + 1
                    user.failed_login_attempts = attempts
                    message = "로그인 아이디 또는 비밀번호가 올바르지 않습니다."
                    if attempts >= self.MAX_FAILED_ATTEMPTS:
                        user.locked_until = now + self.LOCKOUT_DURATION
                        message = (
                            f"로그인 실패 5회로 계정이 {int(self.LOCKOUT_DURATION.total_seconds() // 60)}분 동안 잠겼습니다."
                        )
                    else:
                        left = self.MAX_FAILED_ATTEMPTS - attempts
                        message = f"로그인 아이디 또는 비밀번호가 올바르지 않습니다. {left}회 남음."
                    db.commit()
                    _set_error(message)
                    return False
                if user.is_active is not True:
                    _set_error("계정이 활성화되어 있지 않습니다.")
                    return False

                user.failed_login_attempts = 0
                user.locked_until = None
                db.commit()
                request.session.pop("auth_error", None)
                request.session["user_id"] = str(user.user_id)
                request.session["name"] = user.name
                request.session["is_admin"] = True
                request.session["role_id"] = int(rid_int)
                request.session["password_change_required"] = bool(getattr(user, "password_change_required", False))

                try:
                    role = db.query(Role).filter(Role.role_id == rid_int).first()
                    request.session["role_name"] = role.role_name if role else "사용자"
                except Exception:
                    request.session["role_name"] = "사용자"

                try:
                    company = db.query(Company).filter(Company.company_id == user.company_id).first()
                    request.session["company_name"] = company.name if company else ""
                except Exception:
                    request.session["company_name"] = ""

                ip_address = get_client_ip(request)
                user_agent = request.headers.get("User-Agent")
                record_login_history(
                    db=db,
                    user=user,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    source="admin-login",
                )

                return True
            finally:
                db.close()
        except Exception as exc:
            logger.exception("Admin login failed unexpectedly")
            _set_error("로그인에 실패했습니다.")
            return False

    async def authenticate(self, request: StarletteRequest) -> bool:  # type: ignore[override]
        if request.session.get("is_admin") is not True:
            return False
        db = SessionLocal()
        try:
            uid = request.session.get("user_id")
            if not uid:
                request.session.clear()
                return False
            user = db.query(User).filter(User.user_id == int(uid)).first()
            if user is None or getattr(user, "is_active", True) is not True:
                request.session.clear()
                return False
            try:
                rid_int = int(getattr(user, "role_id", 0) or 0)
            except Exception:
                rid_int = 0
            request.session["role_id"] = int(rid_int)
            request.session["password_change_required"] = bool(
                getattr(user, "password_change_required", False)
            )
            try:
                role = db.query(Role).filter(Role.role_id == rid_int).first()
                request.session["role_name"] = role.role_name if role else "사용자"
            except Exception:
                request.session["role_name"] = "사용자"
            try:
                company = db.query(Company).filter(Company.company_id == user.company_id).first()
                request.session["company_name"] = company.name if company else ""
            except Exception:
                request.session["company_name"] = ""
            if rid_int in {1, 2}:
                return True
            request.session.clear()
            return False
        finally:
            db.close()

    async def logout(self, request: StarletteRequest) -> bool:  # type: ignore[override]
        request.session.clear()
        return True


class AdminDeleteError(Exception):
    """Admin 삭제 차단 시 plain text 에러 메시지를 반환하기 위한 예외"""
    pass


class BabbaAdmin(Admin):
    async def delete(self, request: Request) -> Response:
        """Delete route - AdminDeleteError를 catch하여 plain text 응답 반환"""
        from starlette.responses import PlainTextResponse
        try:
            return await super().delete(request)
        except AdminDeleteError as e:
            return PlainTextResponse(str(e), status_code=400)

    async def login(self, request: Request) -> Response:
        assert self.authentication_backend is not None

        context: dict[str, str] = {}
        if request.method == "GET":
            error_message = request.session.pop("auth_error", None)
            if error_message:
                context["error"] = error_message
            return await self.templates.TemplateResponse(request, "sqladmin/login.html", context)

        ok = await self.authentication_backend.login(request)
        if not ok:
            error_message = request.session.pop("auth_error", None)
            context["error"] = error_message or "로그인에 실패했습니다."
            return await self.templates.TemplateResponse(
                request, "sqladmin/login.html", context, status_code=400
            )

        return RedirectResponse(request.url_for("admin:index"), status_code=302)

    async def logout(self, request: StarletteRequest) -> Response:
        if self.authentication_backend is not None:
            await self.authentication_backend.logout(request)
        request.session.clear()
        return RedirectResponse(request.url_for("admin:login"), status_code=302)

    async def authenticate(self, request: StarletteRequest) -> bool:  # type: ignore[override]
        if request.session.get("is_admin") is True:
            db = SessionLocal()
            try:
                uid = request.session.get("user_id")
                if not uid:
                    return False
                user = db.query(User).filter(User.user_id == int(uid)).first()
                # Avoid relying on implicit truthiness of SQLAlchemy columns
                if user is None or getattr(user, 'is_active', True) is not True:
                    request.session.clear()
                    return False
                # 세션에 역할 저장 및 허용 역할(1,2)만 인증 유지
                try:
                    rid_int = int(getattr(user, "role_id", 0) or 0)
                except Exception:
                    rid_int = 0
                request.session["role_id"] = int(rid_int)
                request.session["password_change_required"] = bool(getattr(user, "password_change_required", False))
                
                # role_name과 company_name을 세션에 갱신
                try:
                    role = db.query(Role).filter(Role.role_id == rid_int).first()
                    request.session["role_name"] = role.role_name if role else "사용자"
                except Exception:
                    request.session["role_name"] = "사용자"
                
                try:
                    company = db.query(Company).filter(Company.company_id == user.company_id).first()
                    request.session["company_name"] = company.name if company else ""
                except Exception:
                    request.session["company_name"] = ""
                
                if rid_int in {1, 2}:
                    return True
                request.session.clear()
                return False
            finally:
                db.close()
        return False


# =========================================================================
# Role-based visibility helpers
# =========================================================================

class RoleRestrictedModelView(ModelView):
    """ModelView with role-based sidebar visibility control via session.role_id.
    
    role_id=2 (지사장)인 경우 ModelView는 숨김 처리 (SSR BaseView만 표시)
    """
    allowed_role_ids: set[int] | None = None
    # 폼에서 자동 생성/수정 시간 필드 제외
    form_excluded_columns = ["created_at", "updated_at"]

    def is_visible(self, request: StarletteRequest) -> bool:  # type: ignore[override]
        try:
            rid = int(request.session.get("role_id") or 0)
        except Exception:
            rid = 0
        
        # role_id=2(지사장)인 경우 ModelView 숨김 (SSR BaseView만 표시)
        if rid == 2:
            return False
        
        if self.allowed_role_ids is None:
            return True
        return rid in self.allowed_role_ids
    
    async def scaffold_list_columns(self) -> List[str]:
        """Get columns to display in list view and export"""
        return self.column_list or []
    
    def _get_export_filename(self) -> str:
        """Generate export filename in format: YYYY-MM-DD-menuname.csv"""
        today = datetime.now().strftime("%Y-%m-%d")
        menu_name = self.name or "export"
        # 한글 메뉴명을 그대로 사용 (브라우저가 RFC 5987로 처리)
        return f"{today}-{menu_name}.csv"
    
    async def export_data(self, rows: Iterable, export_type: str = "csv"):  # type: ignore
        """Override export_data to use custom filename"""
        from urllib.parse import quote
        
        # 기본 export_data 호출
        response = await super().export_data(rows, export_type=export_type)
        
        # 파일명 생성
        menu_name = self.name or "export"
        today = datetime.now().strftime("%Y-%m-%d")
        utf8_filename = f"{today}-{menu_name}.csv"
        
        # ASCII 폴백 버전 (한글을 제거한 간단한 이름)
        ascii_filename = f"{today}-export.csv"
        
        # RFC 5987 형식으로 Content-Disposition 설정
        # filename: ASCII 폴백 (모든 브라우저 호환)
        # filename*: UTF-8 버전 (현대 브라우저가 이를 우선함)
        disposition = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{quote(utf8_filename, safe="")}'
        response.headers["Content-Disposition"] = disposition
        
        return response


# =========================================================================
# ModelView Definitions
# =========================================================================

class UserAdmin(RoleRestrictedModelView, model=User):
    name = "회원 관리"
    name_plural = "회원 관리"
    icon = "fa-solid fa-user"
    can_create = True
    allowed_role_ids = {1}
    create_modal_title = "회원 추가"
    list_template = "user_list_filters.html"
    create_template = "user_create.html"
    edit_template = "user_edit.html"
    # Company와 Role 관계를 미리 로드하여 N+1 쿼리 방지
    async_session_options = {
        "selectinload": ["company", "role", "contract_endings"]
    }
    # 리스트에 더 많은 필드 노출
    column_list = [
        "user_id",
        "code",
        "login_id",
        "name",
        "business_name",
        "email",
        "company_name",
        "role_name",
        "main_contact",
        "doc_contract",
        "doc_personal_info",
        "doc_bankbook",
        "doc_business_registration",
        "address",
        "contracted_at",
        "is_register",
    ]
    
    column_details_list = [
        "user_id",
        "code",
        "login_id",
        "name",
        "email",
        "company_name",
        "role_name",
        "main_contact",
        "bank_name",
        "bank_account",
        "address",
        "business_name",
        "contracted_at",
        "contract_end_date",
        "contract_end_memo",
        "settlement_personal",
        "settlement_business",
        "doc_contract",
        "doc_bankbook",
        "doc_personal_info",
        "doc_business_registration",
        "is_active",
        "is_register",
        "created_at",
        "updated_at",
    ]
    # Export 컬럼
    export_columns = [
        "user_id",
        "code",
        "login_id",
        "name",
        "email",
        "company_name",
        "role_name",
        "main_contact",
        "doc_contract",
        "doc_personal_info",
        "doc_bankbook",
        "doc_business_registration",
        "address",
        "business_name",
        "contracted_at",
        "contract_end_date",
        "contract_end_memo",
        "settlement_personal",
        "settlement_business",
        "bank_name",
        "bank_account",
        "is_register",
    ]
    # 검색 컬럼 지정 (컬럼명 문자열 사용)
    search_columns = [
        "name",
        "main_contact",
        "business_name",
        "address",
        "login_id",
        "email",
    ]
    # 라벨 한글화
    column_labels = {
        "user_id": "ID",
        "login_id": "로그인ID",
        "code": "코드",
        "name": "이름",
        "email": "이메일",
        "password_hash": "비밀번호",
        "company_name": "회사명",
        "role_name": "역할명",
        "main_contact": "대표 연락처",
        "bank_name": "은행명",
        "bank_account": "계좌번호",
        "address": "주소",
        "business_name": "사업자명",
        "contracted_at": "계약일",
        "settlement_personal": "개인 정산",
        "settlement_business": "사업자 정산",
        "doc_contract": "계약서",
        "doc_bankbook": "통장",
        "doc_personal_info": "신분증",
        "doc_business_registration": "사업자",
        "contract_end_date": "계약 종료일",
        "contract_end_memo": "메모",
        "is_active": "활성",
        "is_register": "가입 상태",
        "created_at": "생성일",
    }
    page_size = 25  # 페이지당 25개 행으로 줄임 (로딩 속도 향상)
    column_filters = [
        DistinctSelectFilter(User.company_id, title="회사", label_formatter=lambda value: (_resolve_company_name(value) or "")),
        DistinctSelectFilter(User.role_id, title="역할", label_formatter=lambda value: (_resolve_role_name(value) or "")),
        BooleanEqualFilter(User.is_register, title="가입 상태"),
        BooleanEqualFilter(User.is_active, title="활성"),
    ]

    def list_query(self, request: Request):
        stmt = super().list_query(request)

        # 기본값: 비활성 사용자는 목록에서 숨김 (필터를 명시하면 그대로 노출)
        if "is_active" not in request.query_params:
            stmt = stmt.where(User.is_active.is_(True))

        search_value = (request.query_params.get("search_value") or "").strip()
        if not search_value:
            return stmt
        search_type = request.query_params.get("search_type", "name")
        searchable_columns = {
            "name": User.name,
            "main_contact": User.main_contact,
            "business_name": User.business_name,
            "address": User.address,
            "login_id": User.login_id,
            "email": User.email,
        }
        column = searchable_columns.get(search_type, User.name)
        if search_type == "main_contact":
            normalized_column = func.replace(func.replace(column, "-", ""), " ", "")
            normalized_value = search_value.replace("-", "").replace(" ", "")
            if not normalized_value:
                return stmt
            return stmt.where(normalized_column.ilike(f"%{normalized_value}%"))
        return stmt.where(column.ilike(f"%{search_value}%"))
    
    # 캐시: 회사 id -> 회사명, 역할 id -> 역할명
    _company_name_cache: dict[int, str] = {}
    _role_name_cache: dict[int, str] = {}
    
    @staticmethod
    def _fmt_company_name(model: Any, attribute: Any) -> str:
        """
        포매터: company_name 텍스트 표시
        
        우선순위:
        1. 캐시에서 조회 (가장 빠름)
        2. eager-loaded company 관계 사용 (회피 가능하지만 시도)
        3. DB 직접 조회 (캐시에 저장)
        """
        try:
            cid = getattr(model, 'company_id', None)
            if not cid:
                return ''
            
            # 1) 캐시에 먼저 확인
            if cid in UserAdmin._company_name_cache:
                return UserAdmin._company_name_cache[cid]
            
            # 2) eager-loaded 관계 시도 (세션 바깥이면 실패 가능)
            try:
                company = getattr(model, 'company', None)
                if company:
                    comp_name = str(getattr(company, 'name', '') or '')
                    UserAdmin._company_name_cache[cid] = comp_name
                    return comp_name
            except Exception:
                # lazy load 실패는 무시하고 다음 단계로
                pass
            
            # 3) DB에서 조회 (캐시에 저장)
            db = SessionLocal()
            try:
                comp = db.query(Company).filter(Company.company_id == cid).first()
                comp_name = str(getattr(comp, 'name', '') or '') if comp else ''
                UserAdmin._company_name_cache[cid] = comp_name
                return comp_name
            finally:
                db.close()
        except Exception:
            return ''
    
    @staticmethod
    def _fmt_role_name(model: Any, attribute: Any) -> str:
        """
        포매터: role_name 텍스트 표시
        
        우선순위:
        1. 캐시에서 조회 (가장 빠름)
        2. eager-loaded role 관계 사용 (회피 가능하지만 시도)
        3. DB 직접 조회 (캐시에 저장)
        """
        try:
            rid = getattr(model, 'role_id', None)
            if not rid:
                return ''
            
            # 1) 캐시에 먼저 확인
            if rid in UserAdmin._role_name_cache:
                return UserAdmin._role_name_cache[rid]
            
            # 2) eager-loaded 관계 시도 (세션 바깥이면 실패 가능)
            try:
                role = getattr(model, 'role', None)
                if role:
                    role_name = str(getattr(role, 'role_name', '') or '')
                    UserAdmin._role_name_cache[rid] = role_name
                    return role_name
            except Exception:
                # lazy load 실패는 무시하고 다음 단계로
                pass
            
            # 3) DB에서 조회 (캐시에 저장)
            db = SessionLocal()
            try:
                role = db.query(Role).filter(Role.role_id == rid).first()
                role_name = str(getattr(role, 'role_name', '') or '') if role else ''
                UserAdmin._role_name_cache[rid] = role_name
                return role_name
            finally:
                db.close()
        except Exception:
            return ''
    
    column_formatters = {
        "company_name": _fmt_company_name,
        "role_name": _fmt_role_name,
        "doc_contract": lambda m, a: _fmt_doc_submitted(m, "doc_contract"),
        "doc_personal_info": lambda m, a: _fmt_doc_submitted(m, "doc_personal_info"),
        "doc_bankbook": lambda m, a: _fmt_doc_submitted(m, "doc_bankbook"),
        "doc_business_registration": lambda m, a: _fmt_doc_submitted(m, "doc_business_registration"),
        "settlement_personal": lambda m, a: "예" if getattr(m, "settlement_personal", False) else "아니오",
        "settlement_business": lambda m, a: "예" if getattr(m, "settlement_business", False) else "아니오",
        "created_at": lambda m, a: _format_korean_date(getattr(m, 'created_at', None)),
    }

    async def export_data(self, rows: Iterable, export_type: str = "csv"):  # type: ignore
        """Custom CSV export for User model that ensures company_name and role_name are populated.

        We build the CSV manually so we can use the formatter helpers which will:
        - use eager-loaded relationships when present
        - fall back to DB lookups and caches when needed

        This avoids None values for `company_name`/`role_name` during export.
        """
        # Only customize CSV exports; delegate others to parent
        if export_type != "csv":
            return await super().export_data(rows, export_type=export_type)

        import csv
        from io import StringIO
        from urllib.parse import quote

        cols = list(self.export_columns or self.column_list or [])

        sio = StringIO()
        writer = csv.writer(sio)

        # 헤더 (라벨 사용)
        header = [self.column_labels.get(c, c) for c in cols]
        writer.writerow(header)

        for item in rows:
            # item may be a model instance or a dict-like row
            values = []
            for c in cols:
                try:
                    if c == 'company_name':
                        v = self._fmt_company_name(item, None)
                    elif c == 'role_name':
                        v = self._fmt_role_name(item, None)
                    elif c in (
                        'doc_contract',
                        'doc_personal_info',
                        'doc_bankbook',
                        'doc_business_registration',
                    ):
                        v = 'O' if getattr(item, c, False) else 'X'
                    else:
                        if isinstance(item, dict):
                            v = item.get(c, '')
                        else:
                            v = getattr(item, c, '')
                except Exception:
                    v = ''
                if v is None:
                    v = ''
                values.append(v)
            writer.writerow(values)

        content = '\ufeff' + sio.getvalue()  # BOM for Excel compatibility
        body = content.encode('utf-8')

        response = Response(content=body, media_type='text/csv; charset=utf-8')

        # 파일명 설정 (RFC5987 지원)
        filename = self._get_export_filename()
        ascii_filename = filename.encode('utf-8', 'ignore').decode('ascii', 'ignore') or 'export.csv'
        response.headers['Content-Disposition'] = f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{quote(filename)}'

        return response

    # Use relationships for nicer selection in forms
    # NOTE: contract_end_date / contract_end_memo는 User 테이블 컬럼이 아니라
    # ContractEnd 테이블의 필드이므로 form_columns에 넣으면 sqladmin이
    # mapper.attrs에서 찾지 못해 폼에 렌더링되지 않습니다.
    # 대신 scaffold_form 오버라이드에서 WTForms 필드를 직접 주입합니다.
    form_columns = [
        "login_id",
        "name",
        "email",
        "code",
        "company",
        "role",
        "main_contact",
        "bank_name",
        "bank_account",
        "address",
        "business_name",
        "contracted_at",
        "is_active",
        "settlement_personal",
        "settlement_business",
        "doc_contract",
        "doc_bankbook",
        "doc_personal_info",
        "doc_business_registration",
        "is_register",
    ]
    
    # Override password_hash field to use PasswordField widget
    form_overrides = {
    }
    
    # 드롭다운으로 표시 (검색 대신)
    form_widget_args = {
        "role": {
            "render_kw": {
                "class": "form-select"
            }
        },
        "company": {
            "render_kw": {
                "class": "form-select company-search-select",
                "data-role": "company-search-select",
            }
        },
        "bank_account": {
            "render_kw": {
                "placeholder": "계좌번호 (예: 1234567890)"
            }
        },
        "address": {
            "render_kw": {
                "placeholder": "주소를 입력하세요",
                "rows": "2"
            }
        },
        "business_name": {
            "render_kw": {
                "placeholder": "사업자명을 입력하세요",
                "class": "form-control",
            }
        },
        "settlement_personal": {
            "render_kw": {"class": "form-check-input"},
        },
        "settlement_business": {
            "render_kw": {"class": "form-check-input"},
        },
        "doc_contract": {
            "render_kw": {"class": "form-check-input"},
        },
        "doc_bankbook": {
            "render_kw": {"class": "form-check-input"},
        },
        "doc_personal_info": {
            "render_kw": {"class": "form-check-input"},
        },
        "doc_business_registration": {
            "render_kw": {"class": "form-check-input"},
        },
        "contracted_at": {
            "render_kw": {
                "placeholder": "YYYY-MM-DD (예: 2025-01-15)",
                "pattern": "[0-9]{4}-[0-9]{2}-[0-9]{2}",
                "type": "date"
            }
        },
    }

    # scaffold_form 오버라이드: sqladmin 0.21.0에는 form_extra_fields가 없으므로
    # 폼 클래스 생성 후 contract_end_date / contract_end_memo 필드를 직접 주입
    @staticmethod
    def _company_select_label(company: Any) -> str:
        if company is None:
            return ""
        code = getattr(company, "code", "") or ""
        name = getattr(company, "name", "") or ""
        if code and name:
            return f"{code} · {name}"
        return name or code or str(company)

    @property
    def company_search_items(self) -> list[dict[str, Any]]:
        """회사 드롭다운 검색용 (코드·회사명)"""
        return [
            {
                "id": c.company_id,
                "code": (c.code or "").strip(),
                "name": (c.name or "").strip(),
            }
            for c in self.company_options
        ]

    async def scaffold_form(self, rules=None):
        form_class = await super().scaffold_form(rules=rules)
        if hasattr(form_class, "company"):
            form_class.company.kwargs["get_label"] = self._company_select_label
        # contracted_at 다음 위치에 계약 종료 필드 추가
        # sqladmin.fields.DateField → flatpickr 달력 위젯 사용 (다른 날짜 필드와 동일)
        form_class.contract_end_date = SQLAdminDateField(
            "계약 종료일",
            validators=[validators.Optional()],
            render_kw={
                "class": "form-control",
                "placeholder": "YYYY-MM-DD",
            },
        )
        form_class.contract_end_memo = fields.TextAreaField(
            "메모",
            validators=[validators.Optional()],
            render_kw={
                "placeholder": "메모를 입력하세요",
                "rows": "2",
                "class": "form-control",
            },
        )
        return form_class

    @property
    def company_options(self) -> List[Company]:
        db = SessionLocal()
        try:
            return (
                db.query(Company)
                .filter(Company.is_active.is_(True))
                .order_by(Company.name)
                .all()
            )
        finally:
            db.close()

    @property
    def role_options(self) -> List[Role]:
        db = SessionLocal()
        try:
            return db.query(Role).order_by(Role.role_name).all()
        finally:
            db.close()

    @staticmethod
    def _parse_contract_end_date(value: Any) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                return date.fromisoformat(s[:10])
            except ValueError:
                return None
        return None

    def _persist_contract_end(self, model: Any, request: StarletteRequest, is_created: bool) -> None:
        """ContractEnd 저장 (User 커밋 이후 호출 필요 — 신규 생성 시 user_id는 커밋 후에만 존재).

        company_id는 항상 User.company_id와 동기화한다 (소속 변경 후 화면 불일치 방지).
        """
        user_id = getattr(model, "user_id", None)
        company_id = getattr(model, "company_id", None)
        if not user_id or not company_id:
            return

        raw_date = getattr(request.state, "contract_end_date", None)
        raw_memo = getattr(request.state, "contract_end_memo", None)
        contract_end_date = self._parse_contract_end_date(raw_date)
        contract_end_memo = "" if raw_memo is None else str(raw_memo).strip()
        has_contract_fields = raw_date is not None or raw_memo is not None

        db = SessionLocal()
        try:
            if is_created:
                db.add(
                    ContractEnd(
                        user_id=user_id,
                        company_id=company_id,
                        contract_end_date=contract_end_date,
                        memo=contract_end_memo,
                    )
                )
                db.commit()
                return

            records = (
                db.query(ContractEnd)
                .filter(ContractEnd.user_id == user_id)
                .order_by(ContractEnd.contract_end_id.desc())
                .all()
            )
            if records:
                for record in records:
                    if record.company_id != company_id:
                        record.company_id = company_id
                latest = records[0]
                if raw_date is not None:
                    latest.contract_end_date = contract_end_date
                if raw_memo is not None:
                    latest.memo = contract_end_memo
                db.commit()
            elif has_contract_fields:
                db.add(
                    ContractEnd(
                        user_id=user_id,
                        company_id=company_id,
                        contract_end_date=contract_end_date,
                        memo=contract_end_memo,
                    )
                )
                db.commit()
        except Exception as e:
            logger.error(f"Failed to handle ContractEnd for user {user_id}: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
            for key in ("contract_end_date", "contract_end_memo"):
                if hasattr(request.state, key):
                    delattr(request.state, key)

    async def on_model_change(self, data: dict[str, Any], model: Any, is_created: bool, request: StarletteRequest) -> None:
        """Hook to hash password before saving
        - 새로운 사용자 생성 시: 기본 비밀번호 'admin123'으로 자동 설정
        - 기존 사용자 편집 시: password_hash가 비어있으면 건너뜀 (기존 비밀번호 유지)
        """
        # User 모델에 없는 필드 — 커밋 후 after_model_change에서 ContractEnd로 저장
        request.state.contract_end_date = data.pop("contract_end_date", None)
        request.state.contract_end_memo = data.pop("contract_end_memo", None)

        if is_created:
            data["password_hash"] = UserService.hash_password("admin123")
        else:
            password = data.get("password_hash", "").strip()
            if password:
                data["password_hash"] = UserService.hash_password(password)
            elif "password_hash" in data:
                del data["password_hash"]

        await super().on_model_change(data, model, is_created, request)

    async def after_model_change(
        self, data: dict[str, Any], model: Any, is_created: bool, request: StarletteRequest
    ) -> None:
        """User 저장·커밋 후 계약 종료일/메모·소속(company_id)을 ContractEnd에 반영"""
        self._persist_contract_end(model, request, is_created)
        await super().after_model_change(data, model, is_created, request)

class CompanyAdmin(RoleRestrictedModelView, model=Company):
    name = "지사 분류&등급 관리"
    name_plural = "지사 분류&등급 관리"
    icon = "fa-solid fa-building"
    can_create = True
    allowed_role_ids = {1}
    # Grade 관계를 미리 로드하여 N+1 쿼리 방지
    column_default_sort = ("created_at", True)  # True: desc
    
    # Eager load Grade relationship
    async_session_options = {
        "selectinload": ["grade"]
    }
    # 커스텀 리스트 템플릿 사용 (필터를 상단 드롭다운으로 이동)
    list_template = "company_list.html"
    column_list = [
        "company_id",
        "name",
        "manager_name",
        "company_type",
        # Hide hq_company_id (본사 ID) per request
        # Replace numeric grade_id with textual grade_value
        "grade_value",
        "is_active",
        "created_at",
    ]
    export_columns = [
        "company_id",
        "name",
        "company_type",
        "grade_value",
        "is_active",
        "created_at",
    ]
    column_searchable_list = [Company.name]
    # 기본 정렬: 최근 생성 역순
    column_default_sort = ("created_at", True)  # True: desc
    # 필터: 활성 여부, 회사 유형(HQ/BRANCH)
    column_filters = [
        BooleanEqualFilter(Company.is_active, title="활성"),
        # (value, label)
        SelectEqualFilter(Company.company_type, options=[("HQ", "본사"), ("BRANCH", "지사")], title="회사유형"),
    ]
    column_labels = {
        "company_id": "ID",
        "code": "코드",
        "name": "회사명",
        "manager_name": "지사장",
        "company_type": "유형",
        "grade_value": "등급",
        "is_active": "활성",
        "created_at": "생성일",
    }

    # Display company name together with branch manager name
    # 통합 포매터: 회사명 옆에 지사장명을 표시하고, 기타 포매터도 함께 정의
    column_formatters = {
        "manager_name": _get_branch_manager_name,
        "company_type": _fmt_company_type,
        "grade_value": _fmt_grade_value,
        "created_at": lambda m, a: _format_korean_date(getattr(m, 'created_at', None)),
    }
    # Grade 등급명 표시: 키는 모델 속성(InstrumentedAttribute)로 지정
    # 등급명은 Company.grade_name 속성 사용 (column_list에 포함)
    page_size = 25  # 페이지당 25개 행으로 줄임 (로딩 속도 향상)
    # No contacts column in company view anymore

    # 생성/수정 폼에서 created_at/updated_at 숨기기 (명시적 필드만 노출)
    # hq_company_id는 on_model_change에서 자동 설정 (BRANCH→1, HQ→None)
    form_columns = [
        "code",           # 회사 코드 (필수, 고유)
        "name",
        "company_type",
        "grade",          # 등급은 관계로 선택 (grade_name 기준)
        "is_active",
    ]

    # 드롭다운으로 표시 (검색 대신)
    form_widget_args = {
        "grade": {
            "render_kw": {
                "class": "form-select"
            }
        },
        "code": {
            "render_kw": {
                "placeholder": "예: BR001, HQ001",
            }
        },
    }

    async def on_model_change(self, data: dict[str, Any], model: Any, is_created: bool, request: StarletteRequest) -> None:
        """유형(company_type)에 따라 hq_company_id 자동 설정
        - BRANCH: hq_company_id = 1 (본사)
        - HQ: hq_company_id = None
        """
        company_type = data.get("company_type", getattr(model, "company_type", None))
        if company_type == "BRANCH":
            data["hq_company_id"] = 1
        else:
            data["hq_company_id"] = None
        await super().on_model_change(data, model, is_created, request)

    def search_placeholder(self) -> str:
        return "회사명 · 지사장"

    def search_query(self, stmt: Select, term: str) -> Select:
        """회사명·지사장(역할=지사장) 부분 일치 검색"""
        q = (term or "").strip()
        if not q:
            return stmt
        pattern = f"%{q}%"
        manager_company_ids = (
            select(User.company_id)
            .where(
                User.role_id == 2,
                User.company_id.isnot(None),
                User.name.ilike(pattern),
            )
            .distinct()
        )
        return stmt.where(
            or_(
                Company.name.ilike(pattern),
                Company.company_id.in_(manager_company_ids),
            )
        )

    def list_query(self, request: Request) -> Select:
        """기본 필터: is_active=True (활성화된 지사만 표시)
        
        사용자가 쿼리 파라미터로 필터를 명시적으로 설정하면 무시됨.
        """
        query = super().list_query(request)
        
        # is_active 필터가 URL에 명시되지 않았으면 기본값으로 True 적용
        if not request.query_params.get("is_active"):
            query = query.where(Company.is_active.is_(True))
        
        return query

    async def delete_model(self, request: StarletteRequest, pk: Any) -> None:
        """삭제 전 관련 레코드가 있는지 확인하여 안전하게 차단"""
        from starlette.responses import PlainTextResponse
        db = SessionLocal()
        try:
            cid = int(pk)
            checks = [
                (User, "소속 사용자"),
                (ContractEnd, "계약 종료 내역"),
                (Settlement, "정산 내역"),
                (SettlementCompanyMonthlyAggregate, "월별 정산 집계"),
                (CommissionRateWindow, "수수료율 설정"),
            ]
            issues = []
            for model_cls, label in checks:
                cnt = db.query(func.count()).select_from(model_cls).filter(
                    model_cls.company_id == cid
                ).scalar()
                if cnt:
                    issues.append(f"{label} {cnt}건")
        finally:
            db.close()

        if issues:
            detail = ", ".join(issues)
            msg = (
                f"지사(ID={cid})를 삭제할 수 없습니다.\n"
                f"연결된 데이터: {detail}\n"
                f"관련 데이터를 먼저 삭제하거나 이동해주세요."
            )
            raise AdminDeleteError(msg)

        await super().delete_model(request, pk)

class GradeAdmin(RoleRestrictedModelView, model=Grade):
    name = "등급 관리"
    name_plural = "등급 관리"
    icon = "fa-solid fa-layer-group"
    can_create = True
    allowed_role_ids = {1}
    column_list = [
        "grade_id",
        "grade_name",
        "display_order",
        "is_active",
        "created_at",
    ]
    export_columns = [
        "grade_id",
        "grade_name",
        "display_order",
        "is_active",
        "created_at",
    ]
    search_columns = ["grade_name"]
    column_default_sort = ("display_order", False)
    column_labels = {
        "grade_id": "ID",
        "grade_name": "등급명",
        "display_order": "표시순서",
        "is_active": "활성",
        "created_at": "생성일",
    }
    page_size = 50
    column_formatters = {
        "created_at": lambda m, a: _format_korean_date(getattr(m, 'created_at', None)),
    }


class RoleAdmin(RoleRestrictedModelView, model=Role):
    name = "역할 관리"
    name_plural = "역할 관리"
    icon = "fa-solid fa-shield"
    can_create = True
    allowed_role_ids = {1}
    column_list = [
        "role_id",
        "role_name",
        "is_active",
        "created_at",
    ]
    export_columns = [
        "role_id",
        "role_name",
        "is_active",
        "created_at",
    ]
    search_columns = ["role_name"]
    column_labels = {
        "role_id": "ID",
        "role_name": "역할명",
        "is_active": "활성",
        "created_at": "생성일",
    }
    page_size = 50
    column_formatters = {
        "created_at": lambda m, a: _format_korean_date(getattr(m, 'created_at', None)),
    }


class NoticeAdmin(RoleRestrictedModelView, model=Notice):
    name = "공지사항"
    name_plural = "공지사항"
    icon = "fa-solid fa-bullhorn"
    can_create = True
    can_edit = True
    can_delete = True
    allowed_role_ids = {1}
    list_template = "notice_list.html"
    column_list = [
        "notice_id",
        "title",
        "author_user_id",
        "visible_from",
        "visible_to",
        "is_exposed",
    ]
    column_details_list = [
        "notice_id",
        "title",
        "content",
        "author_user_id",
        "visible_from",
        "visible_to",
        "is_exposed",
        "created_at",
        "updated_at",
    ]
    form_columns = [
        "title",
        "content",
        "visible_from",
        "visible_to",
        "is_exposed",
    ]
    column_labels = {
        "notice_id": "ID",
        "title": "제목",
        "content": "내용",
        "author_user_id": "작성자",
        "visible_from": "노출 시작일",
        "visible_to": "노출 종료일",
        "is_exposed": "노출 설정",
        "created_at": "생성일",
        "updated_at": "수정일",
    }
    page_size = 25
    column_default_sort = ("notice_id", True)
    form_widget_args = {
        "content": {"rows": 12},
        "title": {"maxlength": 255},
    }
    form_overrides = {
        "content": fields.TextAreaField,
    }
    async_session_options = {
        "selectinload": ["author"],
    }

    def list_query(self, request: Request) -> Select:
        stmt = super().list_query(request)
        stmt = stmt.options(selectinload(Notice.author))

        search_value = (request.query_params.get("search") or "").strip()
        if search_value:
            pattern = f"%{search_value}%"
            stmt = (
                stmt.outerjoin(User, Notice.author_user_id == User.user_id)
                .where(
                    or_(
                        Notice.title.ilike(pattern),
                        Notice.content.ilike(pattern),
                        User.name.ilike(pattern),
                    )
                )
                .distinct()
            )

        exposure_filter = request.query_params.get("exposure_filter", "visible_only")
        if exposure_filter == "visible_only":
            ref = notice_reference_date()
            stmt = stmt.where(
                Notice.is_exposed.is_(True),
                Notice.visible_from <= ref,
                Notice.visible_to >= ref,
            )
        return stmt

    async def insert_model(self, request: StarletteRequest, data: dict) -> Any:
        user_id = request.session.get("user_id")
        if user_id:
            data["author_user_id"] = int(user_id)
        return await super().insert_model(request, data)

    @staticmethod
    def author_display(notice: Notice) -> str:
        author = getattr(notice, "author", None)
        if author:
            return (
                (getattr(author, "name", "") or "").strip()
                or (getattr(author, "login_id", "") or "").strip()
                or "-"
            )
        return "-"

    @staticmethod
    def exposure_period_display(notice: Notice) -> str:
        return format_notice_period(notice)

    @staticmethod
    def exposure_status_display(notice: Notice) -> str:
        return format_notice_exposure_status(notice)

    @staticmethod
    def exposure_status_is_live(notice: Notice) -> bool:
        return notice_is_live(notice)


class ProductAdmin(RoleRestrictedModelView, model=Product):
    name = "상품"
    name_plural = "상품"
    can_create = False
    can_edit = False
    can_delete = False
    allowed_role_ids = {1}
    column_list = [
        "id",
        "uid",
        "product_name",
        "sellprice",
        "quantity",
        "status",
        "created_at",
    ]
    search_columns = ["product_name", "uid"]
    column_default_sort = ("created_at", True)
    column_labels = {
        "id": "ID",
        "uid": "Makeshop 상품ID",
        "product_name": "상품명",
        "sellprice": "판매가",
        "quantity": "재고",
        "status": "상태",
        "created_at": "생성일",
    }
    page_size = 50
    column_formatters = {
        "created_at": lambda m, a: _format_korean_date(getattr(m, 'created_at', None)),
    }

class OrderAdmin(RoleRestrictedModelView, model=Order):
    name = "주문 관리"
    name_plural = "주문 관리"
    icon = "fa-solid fa-box"
    can_create = True
    can_edit = True
    can_delete = False
    allowed_role_ids = {1}
    
    column_list = [
        "id",
        "member_id",
        "order_date",
        "sender",
        "email",
        "phone",
        "start_price",
        "total_product_price",
        "basket_count",
        "group_name",
        "pay_status",
        "order_status",
        "used_reserve",
        "deli_price",
    ]
    search_columns = ["member_id", "sender", "email", "phone"]
    column_default_sort = ("created_at", True)
    column_labels = {
        "id": "ID",
        "member_id": "Member ID",
        "order_date": "Order Date",
        "sender": "Sender",
        "email": "Email",
        "phone": "Phone",
        "start_price": "Start Price",
        "total_product_price": "Total Price",
        "basket_count": "Basket Count",
        "group_name": "Group Name",
        "pay_status": "Payment Status",
        "order_status": "Order Status",
        "used_reserve": "Used Reserve",
        "deli_price": "Delivery Price",
    }
    page_size = 50
    column_formatters = {
        "pay_status": _fmt_order_payment_status,
        "order_status": _fmt_order_order_status,
    }

class OrderItemAdmin(RoleRestrictedModelView, model=OrderItem):
    name = "주문항목"
    name_plural = "주문항목"
    can_create = False
    can_edit = False
    can_delete = False
    allowed_role_ids = {1}
    column_list = [
        "id",
        "order_id",
        "product_name",
        "quantity",
        "unit_price",
        "total_price",
        "created_at",
    ]
    search_columns = ["order_id", "product_name"]
    column_labels = {
        "id": "ID",
        "order_id": "주문ID",
        "product_name": "상품명",
        "quantity": "수량",
        "unit_price": "단가",
        "total_price": "합계",
        "created_at": "생성일",
    }
    page_size = 50
    column_formatters = {
        "created_at": lambda m, a: _format_korean_date(getattr(m, 'created_at', None)),
    }

class MemberAdmin(RoleRestrictedModelView, model=Member):
    name = "메이크샵 회원"
    name_plural = "메이크샵 회원"
    icon = "fa-solid fa-user-tie"
    can_create = True
    allowed_role_ids = {1}
    
    def is_visible(self, request: StarletteRequest) -> bool:
        return False  # 임시 숨김
    column_list = [
        "id",
        "makeshop_member_id",
        "name",
        "email",
        "phone",
        "mem_type",
        "grade",
        "group_name",
        "email_receive",
        "sms_receive",
        "login_date",
        "total_purchase_amount",
        "total_orders",
        "company_name",
        "last_purchase_date",
        "created_at",
    ]
    search_columns = ["name", "email", "makeshop_member_id"]
    column_default_sort = ("created_at", True)
    column_labels = {
        "id": "ID",
        "makeshop_member_id": "Makeshop 회원ID",
        "name": "이름",
        "email": "이메일",
        "phone": "전화",
        "mem_type": "회원유형",
        "grade": "등급(숫자)",
        "group_name": "그룹명",
        "email_receive": "이메일수신",
        "sms_receive": "SMS수신",
        "login_date": "최근로그인",
        "total_purchase_amount": "총구매액",
        "total_orders": "총주문수",
        "company_name": "회사명",
        "last_purchase_date": "마지막구매",
        "created_at": "생성일",
    }
    page_size = 50
    column_formatters = {
        "created_at": lambda m, a: _format_korean_date(getattr(m, 'created_at', None)),
        "last_purchase_date": lambda m, a: _format_korean_date(getattr(m, 'last_purchase_date', None)),
        "login_date": lambda m, a: _format_korean_date(getattr(m, 'login_date', None)),
    }
    form_columns = [
        "makeshop_member_id",
        "name",
        "email",
        "phone",
        "mem_type",
        "simple_type",
        "grade",
        "reserve",
        "email_receive",
        "sms_receive",
        "login_date",
        "mod_date",
        "reg_date",
        "birth_day",
        "birth_day_year",
        "birth_format",
        "sex",
        "group_id",
        "group_name",
        "post",
        "address_detail",
        "push_receive",
        "point",
        "emoney",
        "is_app_use",
        "extension_period",
        "order_count",
        "company_name",
        "company_owner",
        "company_num",
        "company_corp",
        "company_biz",
        "company_item",
        "company_post",
        "company_addr",
        "total_purchase_amount",
        "total_orders",
        "last_purchase_date",
    ]

class CommissionTypeAdmin(RoleRestrictedModelView, model=CommissionType):
    name = "수수료 유형"
    name_plural = "수수료 유형"
    icon = "fa-solid fa-percent"
    can_create = True
    allowed_role_ids = {1}
    column_list = [
        "commission_type_id",
        "code",
        "name",
        "cate1_code_list",
        "cate1_name_list",
        "display_order",
        "is_active",
        "created_at",
    ]
    column_labels = {
        "commission_type_id": "ID",
        "code": "코드",
        "name": "이름",
        "cate1_code_list": "카테고리 코드 목록",
        "cate1_name_list": "카테고리 이름 목록",
        "display_order": "표시순서",
        "is_active": "활성",
        "created_at": "생성일",
    }
    search_columns = ["code", "name"]
    column_default_sort = ("display_order", False)
    page_size = 50
    column_formatters = {
        "created_at": lambda m, a: _format_korean_date(getattr(m, 'created_at', None)),
    }
    form_columns = ["code", "name", "cate1_code_list", "cate1_name_list", "display_order", "is_active"]
    
    # JSON 필드 처리를 위한 form_args
    form_args = {
        "cate1_code_list": {
            "render_kw": {
                "placeholder": '["001", "002", "003"]',
                "style": "width: 100%; min-height: 60px; box-sizing: border-box;"
            }
        },
        "cate1_name_list": {
            "render_kw": {
                "placeholder": '["[가입] 혼합형", "[가입] 수학형"]',
                "style": "width: 100%; min-height: 60px; box-sizing: border-box;"
            }
        }
    }
    
    async def on_model_change(self, data: dict[str, Any], model: Any, is_created: bool, request: StarletteRequest) -> None:
        """
        JSON 필드 처리: 문자열 형태의 JSON을 Python 객체로 변환
        """
        import json
        
        # cate1_code_list 처리
        if 'cate1_code_list' in data and isinstance(data['cate1_code_list'], str):
            try:
                if data['cate1_code_list'].strip():
                    data['cate1_code_list'] = json.loads(data['cate1_code_list'])
                else:
                    data['cate1_code_list'] = None
            except json.JSONDecodeError as e:
                logger.error(f"[CommissionTypeAdmin] Invalid JSON for cate1_code_list: {e}")
                raise ValueError(f"cate1_code_list: Invalid JSON format - {str(e)}")
        
        # cate1_name_list 처리
        if 'cate1_name_list' in data and isinstance(data['cate1_name_list'], str):
            try:
                if data['cate1_name_list'].strip():
                    data['cate1_name_list'] = json.loads(data['cate1_name_list'])
                else:
                    data['cate1_name_list'] = None
            except json.JSONDecodeError as e:
                logger.error(f"[CommissionTypeAdmin] Invalid JSON for cate1_name_list: {e}")
                raise ValueError(f"cate1_name_list: Invalid JSON format - {str(e)}")
        
        await super().on_model_change(data, model, is_created, request)

class CommissionRateWindowAdmin(RoleRestrictedModelView, model=CommissionRateWindow):
    name = "수수료율"
    name_plural = "수수료율"
    icon = "fa-solid fa-chart-bar"
    can_create = True
    allowed_role_ids = {1}
    column_list = [
        "id",
        "commission_type_id",
        "company_id",
        "start_year",
        "start_month",
        "end_year",
        "end_month",
        "min_amount",
        "max_amount",
        "rate_percent",
        "min_teachers",
        "priority",
        "description",
        "is_active",
        "created_at",
    ]
    column_labels = {
        "id": "ID",
        "commission_type_id": "타입",
        "company_id": "회사명",
        "start_year": "시작연",
        "start_month": "시작월",
        "end_year": "종료연",
        "end_month": "종료월",
        "rate_percent": "수수료(%)",
        "min_amount": "최소금액",
        "max_amount": "최대금액",
        "min_teachers": "최소원장수",
        "priority": "우선순위",
        "description": "설명",
        "is_active": "활성",
        "created_at": "생성일",
    }
    page_size = 50
    search_columns = ["start_year", "start_month", "rate_percent", "description"]
    column_default_sort = ("priority", True)

    column_formatters = {
        "commission_type_id": _fmt_commission_window_type,
        "company_id": _fmt_commission_window_company,
        "created_at": lambda m, a: _format_korean_date(getattr(m, 'created_at', None)),
    }

    form_columns = [
        "commission_type",
        "company",
        "start_year",
        "start_month",
        "end_year",
        "end_month",
        "min_amount",
        "max_amount",
        "rate_percent",
        "min_teachers",
        "priority",
        "description",
        "is_active",
    ]
    form_widget_args = {
        "commission_type": {
            "render_kw": {
                "class": "form-select"
            }
        },
        "company": {
            "render_kw": {
                "class": "form-select"
            }
        },
    }


class SettlementAdmin(RoleRestrictedModelView, model=Settlement):
    name = "정산"
    name_plural = "정산"
    can_create = True
    allowed_role_ids = {1}
    column_list = [
        "settlement_id",
        "user_id",
        "company_id",
        "settlement_type",
        "settlement_date",
        "total_commission",
        "deducted_tax",
        "deducted_local_tax",
        "net_settlement_amount",
        "is_paid",
        "paid_date",
        "created_at",
    ]
    column_labels = {
        "settlement_id": "정산ID",
        "user_id": "사용자ID",
        "company_id": "회사ID",
        "settlement_type": "정산타입",
        "settlement_date": "정산일",
        "total_commission": "총수수료",
        "deducted_tax": "소득세",
        "deducted_local_tax": "지방세",
        "net_settlement_amount": "지급액",
        "is_paid": "지급완료",
        "paid_date": "지급일",
        "created_at": "생성일",
    }
    page_size = 50
    search_columns = ["user_id", "company_id", "settlement_type"]
    column_default_sort = ("settlement_date", True)  # 최근 정산 역순
    
    # 필터
    column_filters = [
        SelectEqualFilter(Settlement.settlement_type, options=[("daily", "일별"), ("mtd", "월중(MTD)"), ("monthly", "월별"), ("yearly", "연간")], title="정산타입"),
        BooleanEqualFilter(Settlement.is_paid, title="지급완료"),
    ]
    
    column_formatters = {
        "settlement_date": lambda m, a: _format_korean_date(getattr(m, 'settlement_date', None)),
        "paid_date": lambda m, a: _format_korean_date(getattr(m, 'paid_date', None)),
        "created_at": lambda m, a: _format_korean_date(getattr(m, 'created_at', None)),
    }
    
    form_columns = [
        "user",
        "company",
        "settlement_type",
        "settlement_date",
        "total_commission",
        "deducted_tax",
        "deducted_local_tax",
        "net_settlement_amount",
        "commission_details",
        "is_paid",
        "paid_date",
    ]
    
    form_widget_args = {
        "user": {
            "render_kw": {
                "class": "form-select"
            }
        },
        "company": {
            "render_kw": {
                "class": "form-select"
            }
        },
    }


class SettlementCompanyMonthlyAggregateAdmin(RoleRestrictedModelView, model=SettlementCompanyMonthlyAggregate):
    """회사별 월별 정산 집계 현황"""
    name = "회사별 월별 정산"
    name_plural = "회사별 월별 정산"
    icon = "fa-solid fa-building-columns"
    can_create = False
    can_delete = False
    can_edit = False
    allowed_role_ids = {1, 2}
    
    column_list = [
        "company_id",
        "year",
        "month",
        "total_orders",
        "total_items",
        "total_amount",
    ]
    
    column_labels = {
        "company_id": "지사장",
        "year": "연도",
        "month": "월",
        "total_orders": "주문수",
        "total_items": "상품수",
        "total_amount": "주문금액",
    }
    
    page_size = 50
    search_columns = ["company_id"]
    column_default_sort = ("year", True)  # 최근 연도순
    
    column_filters = []
    
    column_formatters = {
        "company_id": _get_branch_manager_name,
        "total_amount": lambda m, a: _format_currency(getattr(m, 'total_amount', None)),
    }
    
    form_columns = []  # 읽기 전용이므로 비움


# =========================================================================
# BaseView with role-based access control
# =========================================================================

class RoleRestrictedBaseView(BaseView):
    """BaseView with role-based sidebar visibility control via session.role_id."""
    allowed_role_ids: set[int] | None = None

    def is_visible(self, request: StarletteRequest) -> bool:  # type: ignore[override]
        if self.allowed_role_ids is None:
            return True
        try:
            rid = int(request.session.get("role_id") or 0)
        except Exception:
            rid = 0
        is_allowed = rid in self.allowed_role_ids
        logger.debug(f"[is_visible] {self.name} (identity={self.identity}) - role_id={rid}, allowed_roles={self.allowed_role_ids}, result={is_allowed}")
        return is_allowed

    def _ensure_identity_path_param(self, request: StarletteRequest) -> None:
        identity = getattr(self, "identity", None)
        if not identity:
            return
        path_params = request.scope.setdefault("path_params", {})
        path_params["identity"] = identity


class BranchPasswordResetView(RoleRestrictedBaseView):
    """지사장 비밀번호 초기화 - SQLAdmin 템플릿 기반 렌더링"""
    name = "지사장 비밀번호 초기화"
    name_plural = "지사장 비밀번호 초기화"
    icon = "fa-solid fa-user-lock"
    allowed_role_ids = {1}
    identity = "branch-password-reset"

    _template_name = "branch_password_reset.html"

    def _fetch_branch_users(self) -> list[User]:
        db = SessionLocal()
        try:
            return (
                db.query(User)
                .filter(User.role_id == 2)
                .order_by(User.company_id, User.name)
                .options(selectinload(User.company))
                .all()
            )
        finally:
            db.close()

    async def _render_page(self, request: StarletteRequest, **context: Any) -> HTMLResponse:
        branch_users = self._fetch_branch_users()
        return await self.templates.TemplateResponse(request, self._template_name, {
            "branch_users": branch_users,
            **context,
        })

    @expose("/branch-password-reset", methods=["GET"], identity="branch-password-reset")  # type: ignore[misc]
    async def index(self, request: StarletteRequest) -> HTMLResponse:
        """지사장 비밀번호 초기화 페이지 - SQLAdmin 템플릿 사용"""
        user_id = request.session.get("user_id")
        role_id = int(request.session.get("role_id") or 0)

        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]
        allowed_roles: set[int] = self.allowed_role_ids or set()
        if role_id not in allowed_roles:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")

        logger.info(f"[BranchPasswordReset] Rendering list for role_id={role_id}")
        return await self._render_page(request)

    @expose("/branch-password-reset/reset", methods=["POST"], identity="branch-password-reset-reset")  # type: ignore[misc]
    async def reset_password(self, request: StarletteRequest) -> HTMLResponse:
        """지사장 비밀번호 초기화 - POST 처리"""
        user_id = request.session.get("user_id")
        role_id = int(request.session.get("role_id") or 0)

        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]
        allowed_roles: set[int] = self.allowed_role_ids or set()
        if role_id not in allowed_roles:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")

        form = await request.form()
        target_user_id = str(form.get("user_id", ""))
        new_password = "admin123"

        if not target_user_id:
            return await self._render_page(request, message="사용자를 선택할 수 없습니다.", status="error")

        success_message = ""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == int(target_user_id), User.role_id == 2).first()
            if user is None:
                return await self._render_page(request, message="지사장 계정을 찾을 수 없습니다.", status="error")

            hashed_password = UserService.hash_password(new_password)
            db.query(User).filter(User.user_id == user.user_id, User.role_id == 2).update(
                {
                    User.password_hash: hashed_password,
                    User.password_change_required: True,
                },
                synchronize_session=False,
            )
            db.commit()
            name_label = (user.name or "지사장")
            login_label = user.login_id or "로그인ID 없음"
            success_message = f"{name_label}({login_label}) 비밀번호를 \"{new_password}\"로 초기화했습니다."
        finally:
            db.close()

        return await self._render_page(request, message=success_message, status="success")


def _get_available_settlement_periods(db, company_id: int):
    """정산 데이터가 있는 년도/월 목록 조회 (월별 정산만)."""
    # 해당 회사의 원장(role_id=3) 월별(monthly) Settlement만 — MTD 일별 스냅샷은 제외
    query = db.query(Settlement).join(User, Settlement.user_id == User.user_id)
    query = query.filter(
        User.company_id == int(company_id),
        User.role_id == 3,
        Settlement.settlement_date.isnot(None),
        Settlement.settlement_type == "monthly",
    )
    
    settlements = query.all()
    
    # 년도별/월별 정리
    years = set()
    months = set()
    
    for s in settlements:
        if s.settlement_date:
            year_val = s.settlement_date.year
            month_val = s.settlement_date.month
            years.add(year_val)
            months.add(f"{year_val}-{month_val:02d}")
    
    # 정렬된 리스트로 변환
    year_list = sorted(years, reverse=True)
    month_list = sorted(months, reverse=True)
    
    return year_list, month_list


def _get_settlement_overview_data(db, company_id: int, year: str = None):
    """정산 개요 데이터 조회 - 서버 사이드 렌더링용"""
    from sqlalchemy import extract
    from collections import defaultdict
    import json
    from app.services.settlement_dedupe import select_canonical_settlements
    
    # 해당 회사의 원장(role_id=3) Settlement 조회
    query = db.query(Settlement).join(User, Settlement.user_id == User.user_id)
    query = query.filter(User.company_id == int(company_id), User.role_id == 3)
    
    # 연도 필터링
    if year and year != "전체":
        query = query.filter(extract('year', Settlement.settlement_date) == int(year))
    
    # mtd 스냅샷 + monthly 중복 합산 방지
    settlements = select_canonical_settlements(query.all())
    
    if not settlements:
        return [], {"sell_price_total": 0, "used_reserve_total": 0, "actual_payment_total": 0, "commission_total": 0, "net_settlement_total": 0}
    
    # 관련된 모든 주문번호 추출
    all_order_nums = set()
    for settlement in settlements:
        if settlement.commission_details:
            try:
                details = json.loads(settlement.commission_details)
                for detail in details:
                    ordernum = detail.get('ordernum')
                    if ordernum:
                        all_order_nums.add(ordernum)
            except Exception:
                pass
    
    # 모든 Order를 한 번에 조회 (배치 조회)
    orders_map = {}
    if all_order_nums:
        orders = db.query(Order).filter(Order.ordernum.in_(list(all_order_nums))).all()
        for order in orders:
            orders_map[order.ordernum] = order
    
    # 모든 OrderItem을 한 번에 조회 (주문별 상품 판매가 합계 계산용)
    order_items_map = defaultdict(list)  # ordernum -> [OrderItem, ...]
    if all_order_nums:
        order_items = db.query(OrderItem).filter(OrderItem.ordernum.in_(list(all_order_nums))).all()
        for item in order_items:
            order_items_map[item.ordernum].append(item)
    
    # 월별 그룹화 (YYYY-MM 형식)
    month_aggregates = defaultdict(lambda: {
        'sell_price_total': 0, 'used_reserve_total': 0, 'actual_payment_total': 0,
        'commission_total': 0, 'net_settlement_total': 0, 'processed_orders': set()
    })
    
    for settlement in settlements:
        if not settlement.settlement_date:
            continue
        month_key = settlement.settlement_date.strftime("%Y-%m")
        agg = month_aggregates[month_key]
        
        if settlement.commission_details:
            try:
                details = json.loads(settlement.commission_details)
                for detail in details:
                    commission = detail.get('commission', 0)
                    if commission == 0:
                        continue
                    ordernum = detail.get('ordernum')
                    if ordernum and ordernum in orders_map and ordernum not in agg['processed_orders']:
                        order = orders_map[ordernum]
                        # OrderItem의 sell_price 합계로 판매가 계산 (sell_price는 이미 총액)
                        order_sell_price = 0
                        if ordernum in order_items_map:
                            for item in order_items_map[ordernum]:
                                order_sell_price += int(getattr(item, 'sell_price', 0) or 0)
                        agg['sell_price_total'] += order_sell_price
                        agg['used_reserve_total'] += int(getattr(order, 'used_reserve', 0) or 0)
                        agg['actual_payment_total'] += int(getattr(order, 'pay_price', 0) or 0)
                        agg['processed_orders'].add(ordernum)
                    # 정산예정금액은 actual_payment 합계 (rate 적용 전)
                    agg['commission_total'] += int(detail.get('actual_payment', 0) or 0)
                    # 지급총액(공제전) = commission 합계 (rate 적용 후)
                    agg['net_settlement_total'] += commission
            except Exception:
                pass
    
    # 결과 배열 생성
    result_data = []
    total_sell_price = total_used_reserve = total_actual_payment = total_commission = total_net_settlement = 0
    
    for month_key in sorted(month_aggregates.keys(), reverse=True):
        agg = month_aggregates[month_key]
        # 결제 총액 = 판매가 - 적립금
        actual_payment = agg['sell_price_total'] - agg['used_reserve_total']
        result_data.append({
            "settlement_date": month_key,
            "sell_price_total": agg['sell_price_total'],
            "used_reserve_total": agg['used_reserve_total'],
            "actual_payment_total": actual_payment,
            "commission_total": agg['commission_total'],
            "net_settlement_total": agg['net_settlement_total']
        })
        total_sell_price += agg['sell_price_total']
        total_used_reserve += agg['used_reserve_total']
        total_actual_payment += actual_payment
        total_commission += agg['commission_total']
        total_net_settlement += agg['net_settlement_total']
    
    summary = {
        "sell_price_total": total_sell_price, "used_reserve_total": total_used_reserve,
        "actual_payment_total": total_actual_payment, "commission_total": total_commission,
        "net_settlement_total": total_net_settlement
    }
    return result_data, summary


def _get_settlement_status_data(db, company_id: int, month: str = None, year: str = None, sort_by: str = "amount_desc"):
    """소속 원장별 월매출 데이터 조회 - 서버 사이드 렌더링용"""
    from app.services.settlement_status_service import get_settlement_status_data

    return get_settlement_status_data(db, company_id, month, year, sort_by)


class HomeDashboardView(RoleRestrictedBaseView):
    """홈 대시보드 - role_id=1(본사관리자)용 메뉴"""
    name = "홈"
    identity = "home"
    icon = "fa-solid fa-home"
    allowed_role_ids = {1}

    @expose("/home", methods=["GET"], identity="home")  # type: ignore[misc]
    async def index(self, request):  # type: ignore[override]
        """홈 대시보드 - 지사 목록 및 정산 현황"""
        import traceback

        try:
            user_id = request.session.get("user_id")
            role_id = request.session.get("role_id")

            if not user_id:
                return RedirectResponse(url="/admin/login", status_code=302)
            if role_id != 1:
                return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")

            # DB에서 대시보드 데이터 조회
            db = SessionLocal()
            try:
                # 정산 사전 검증 결과 조회 (캐시 우선 → DB 폴백)
                # 캐시가 있으면 캐시에서 빠르게 조회, 없으면 DB에서 로드
                from app.services.settlement_service import SettlementService
                pre_validation = None
                try:
                    pre_validation = SettlementService.get_pre_validation_from_db(db)
                except Exception as pv_err:
                    logger.warning(f"[HomeDashboardView] Pre-validation read failed: {pv_err}")

                # 활성 회사만 조회 (HQ와 BRANCH 모두)
                branches = db.query(Company).filter(
                    Company.company_type.in_(['HQ', 'BRANCH']),
                    Company.is_active.is_(True),
                ).order_by(Company.company_type.desc(), Company.name).all()

                # 지사별 연도 누적 실결제총액 (소속 원장별 월매출 '누적 총액'과 동일 로직)
                from app.services.settlement_status_service import get_all_branches_yearly_sales

                branch_sales, sales_year = get_all_branches_yearly_sales(db)

                branches_data = []

                for c in branches:
                    # 지사장(지사 담당자) 조회: role_id == 2
                    manager = db.query(User).filter(
                        User.company_id == c.company_id,
                        User.role_id == 2
                    ).first()
                    manager_name = manager.name if manager else "-"

                    yearly_sales = branch_sales.get(c.company_id, 0)

                    # 각 지사별로 링크 생성
                    branches_data.append({
                        "company_id": c.company_id,
                        "code": c.code,
                        "name": c.name or "-",
                        "manager_name": manager_name,
                        "yearly_sales": yearly_sales,
                        "links": {
                            "overview": f"/admin/settlement-overview?company_id={c.company_id}",
                            "status": f"/admin/settlement-status?company_id={c.company_id}",
                            "daily_status": f"/admin/settlement-daily-status?company_id={c.company_id}",
                            "statement": f"/admin/settlement-statement?company_id={c.company_id}",
                            "teachers": f"/admin/teachers-list?company_id={c.company_id}",
                        }
                    })

                # 요약 정보
                branch_count = len(branches_data)
                branch_head_count = db.query(User).filter(User.role_id == 2).count()

                dashboard = {
                    "branch_count": branch_count,
                    "branch_head_count": branch_head_count,
                    "settlement_current_month": {
                        "completed": 0,
                        "in_progress": 0,
                        "pending": 0,
                        "total": 0,
                    }
                }
            finally:
                db.close()

            logger.info(f"[HomeDashboardView] Rendering with {len(branches_data)} branches")
            return await self.templates.TemplateResponse(request, "home_dashboard.html", {
                "dashboard": dashboard,
                "branches": branches_data,
                "pre_validation": pre_validation,
                "sales_year": sales_year,
            })
        except Exception as e:
            logger.error(f"[HomeDashboardView] Error: {e}")
            logger.error(traceback.format_exc())
            raise


class SettlementOverviewView(RoleRestrictedBaseView):
    """정산 개요 - SQLAdmin 템플릿 기반 렌더링"""
    name = "정산 개요"
    identity = "settlement-overview"
    icon = "fa-solid fa-chart-pie"
    allowed_role_ids = {2}

    @expose("/settlement-overview", methods=["GET"], identity="settlement-overview")  # type: ignore[misc]
    async def index(self, request):  # type: ignore[override]
        """정산 개요 페이지 - SQLAdmin 템플릿 사용"""
        import traceback
        
        try:
            user_id = request.session.get("user_id")
            role_id = request.session.get("role_id")
            
            if not user_id:
                return RedirectResponse(url="/admin/login", status_code=302)
            if role_id not in {1, 2}:
                return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")
            
            # URL에서 year, company_id 파라미터 가져오기
            year = request.query_params.get("year", "전체")
            company_id_param = request.query_params.get("company_id")
            
            # DB에서 데이터 조회
            db = SessionLocal()
            try:
                current_user = db.query(User).filter(User.user_id == user_id).first()
                if not current_user:
                    return HTMLResponse(content="<h3>사용자 정보를 찾을 수 없습니다.</h3>")
                
                company_id = current_user.company_id
                # 홈에서 전달된 company_id가 있으면 사용 (본사 관리자가 지사 정산 조회 시)
                if company_id_param and role_id == 1:
                    company_id = int(company_id_param)
                
                data, summary = _get_settlement_overview_data(db, company_id, year)
                
                # 실제 정산 데이터가 있는 년도만 필터 옵션에 포함
                available_years, _ = _get_available_settlement_periods(db, company_id)
                live_notices = fetch_live_notices(db)
            finally:
                db.close()
            
            # 연도 옵션 생성 - 실제 데이터가 있는 년도만
            year_options = [{"value": "전체", "label": "전체"}] + [
                {"value": str(y), "label": f"{y}년"} 
                for y in available_years
            ]
            
            logger.info(f"[SettlementOverviewView] Rendering template with data count: {len(data)}, company_id={company_id}, company_id_param={company_id_param}")
            return await self.templates.TemplateResponse(request, "settlement_overview.html", {
                "data": data,
                "summary": summary,
                "year_options": year_options,
                "selected_year": year,
                "company_id": company_id,
                "live_notices": live_notices,
            })
        except Exception as e:
            logger.error(f"[SettlementOverviewView] Error: {e}")
            logger.error(traceback.format_exc())
            raise


class SettlementStatusView(RoleRestrictedBaseView):
    """소속 원장별 월매출 - SQLAdmin 템플릿 기반 렌더링"""
    name = "소속 원장별 월매출"
    identity = "settlement-status"
    icon = "fa-solid fa-chart-line"
    allowed_role_ids = {2}

    @expose("/settlement-status", methods=["GET"], identity="settlement-status")  # type: ignore[misc]
    async def index(self, request):  # type: ignore[override]
        """정산 현황 페이지 - SQLAdmin 템플릿 사용"""
        from starlette.responses import RedirectResponse
        import traceback
        
        try:
            user_id = request.session.get("user_id")
            role_id = request.session.get("role_id")
            
            if not user_id:
                return RedirectResponse(url="/admin/login", status_code=302)
            if role_id not in {1, 2}:
                return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")
            
            # URL에서 month, company_id 파라미터 가져오기
            month_param = request.query_params.get("month")
            company_id_param = request.query_params.get("company_id")
            year_param = request.query_params.get("year")
            
            # DB에서 데이터 조회
            db = SessionLocal()
            try:
                current_user = db.query(User).filter(User.user_id == user_id).first()
                if not current_user:
                    return HTMLResponse(content="<h3>사용자 정보를 찾을 수 없습니다.</h3>")
                
                company_id = current_user.company_id
                # 홈에서 전달된 company_id가 있으면 사용 (본사 관리자가 지사 정산 조회 시)
                if company_id_param and role_id == 1:
                    company_id = int(company_id_param)
                available_years, available_months = _get_available_settlement_periods(db, company_id)

                months_by_year = {}
                for month_value in available_months:
                    year = month_value.split("-")[0]
                    months_by_year.setdefault(year, []).append(month_value)

                default_month = available_months[0] if available_months else "전체"
                if month_param and month_param != "전체" and month_param in available_months:
                    selected_month = month_param
                elif month_param == "전체":
                    selected_month = "전체"
                else:
                    selected_month = default_month

                if selected_month and selected_month != "전체":
                    selected_year = selected_month.split("-")[0]
                elif year_param:
                    selected_year = year_param
                else:
                    selected_year = available_years[0] if available_years else None

                sort_by = request.query_params.get("sort_by", "amount_desc")
                data, summary, branch_manager_user_id = _get_settlement_status_data(
                    db, company_id, selected_month, selected_year, sort_by
                )
            finally:
                db.close()
            
            return await self.templates.TemplateResponse(request, "settlement_status.html", {
                "data": data,
                "summary": summary,
                "year_tabs": available_years,
                "months_by_year": months_by_year,
                "selected_month": selected_month,
                "selected_year": selected_year,
                "company_id": company_id,
                "branch_manager_user_id": branch_manager_user_id,
                "sort_by": sort_by,
            })
        except Exception as e:
            logger.error(f"[SettlementStatusView] Error: {e}")
            logger.error(traceback.format_exc())
            raise


class SettlementDailyStatusView(RoleRestrictedBaseView):
    """소속 원장별 일별 매출 - SQLAdmin 템플릿 기반 렌더링"""
    name = "소속 원장별 일별 매출"
    identity = "settlement-daily-status"
    icon = "fa-solid fa-calendar-day"
    allowed_role_ids = {2}

    @expose("/settlement-daily-status", methods=["GET"], identity="settlement-daily-status")  # type: ignore[misc]
    async def index(self, request):  # type: ignore[override]
        """일별 매출 실적 페이지 (월 단위 누적)"""
        from starlette.responses import RedirectResponse
        from datetime import datetime as dt
        import calendar
        import traceback

        from app.services.settlement_status_service import (
            get_mtd_filter_years,
            get_daily_sales_month_overview,
            get_daily_sales_status_data,
        )

        try:
            user_id = request.session.get("user_id")
            role_id = request.session.get("role_id")

            if not user_id:
                return RedirectResponse(url="/admin/login", status_code=302)
            if role_id not in {1, 2}:
                return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")

            month_param = request.query_params.get("month")
            year_param = request.query_params.get("year")
            month_num_param = request.query_params.get("month_num")
            date_param = request.query_params.get("target_date")
            company_id_param = request.query_params.get("company_id")
            sort_by = request.query_params.get("sort_by", "amount_desc")

            now_kst = dt.now(ZoneInfo("Asia/Seoul"))
            today_kst = now_kst.date()

            db = SessionLocal()
            try:
                current_user = db.query(User).filter(User.user_id == user_id).first()
                if not current_user:
                    return HTMLResponse(content="<h3>사용자 정보를 찾을 수 없습니다.</h3>")

                company_id = current_user.company_id
                if company_id_param and role_id == 1:
                    company_id = int(company_id_param)

                filter_years = get_mtd_filter_years(
                    db, company_id, reference_date=today_kst
                )

                selected_year = str(today_kst.year)
                selected_month_num = today_kst.month
                if year_param:
                    try:
                        selected_year = str(int(year_param))
                    except ValueError:
                        pass
                if month_num_param:
                    try:
                        month_candidate = int(month_num_param)
                        if 1 <= month_candidate <= 12:
                            selected_month_num = month_candidate
                    except ValueError:
                        pass
                elif month_param and "-" in month_param:
                    try:
                        year_part, month_part = month_param.split("-", 1)
                        selected_year = str(int(year_part))
                        selected_month_num = int(month_part)
                    except ValueError:
                        pass

                if filter_years and int(selected_year) not in filter_years:
                    selected_year = str(filter_years[0])

                year_int = int(selected_year)
                month_int = selected_month_num
                selected_month = f"{year_int}-{month_int:02d}"

                daily_rows, month_meta = get_daily_sales_month_overview(
                    db,
                    company_id,
                    year_int,
                    month_int,
                    reference_date=today_kst,
                    sort_by=sort_by,
                )

                requested_date = None
                if date_param:
                    try:
                        requested_date = dt.strptime(date_param, "%Y-%m-%d").date()
                    except ValueError:
                        requested_date = None

                if requested_date and (
                    requested_date.year != year_int or requested_date.month != month_int
                ):
                    requested_date = None

                if requested_date is None and daily_rows:
                    requested_date = dt.strptime(daily_rows[-1]["date"], "%Y-%m-%d").date()

                data, summary, detail_meta = get_daily_sales_status_data(
                    db,
                    company_id,
                    requested_date,
                    sort_by,
                    reference_date=today_kst,
                )
            finally:
                db.close()

            snapshot_date = detail_meta.get("snapshot_date")
            period_start = detail_meta.get("period_start") or month_meta.get("period_start")

            return await self.templates.TemplateResponse(request, "settlement_daily_status.html", {
                "data": data,
                "summary": summary,
                "daily_rows": daily_rows,
                "selected_month": selected_month,
                "selected_year": selected_year,
                "selected_month_num": selected_month_num,
                "filter_years": filter_years,
                "month_label": month_meta.get("month_label"),
                "selected_date": snapshot_date,
                "selected_day_label": (
                    f"{month_int}/{requested_date.day}" if requested_date else None
                ),
                "period_start": period_start,
                "has_snapshot": detail_meta.get("has_snapshot", False),
                "has_any_snapshot": month_meta.get("has_any_snapshot", False),
                "branch_manager_user_id": detail_meta.get("branch_manager_user_id"),
                "company_id": company_id,
                "sort_by": sort_by,
            })
        except Exception as e:
            logger.error(f"[SettlementDailyStatusView] Error: {e}")
            logger.error(traceback.format_exc())
            raise


class SettlementStatementView(RoleRestrictedBaseView):
    """정산서 목록 - 년도/월 선택 페이지"""
    name = "정산서"
    identity = "settlement-statement"
    icon = "fa-solid fa-file-invoice-dollar"
    allowed_role_ids = {2}

    @expose("/settlement-statement", methods=["GET"], identity="settlement-statement")  # type: ignore[misc]
    async def index(self, request):  # type: ignore[override]
        """정산서 목록 페이지 - 년도/월 버튼만 표시"""
        user_id = request.session.get("user_id")
        role_id = request.session.get("role_id")
        
        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)
        if role_id not in {1, 2}:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")
        
        # URL 파라미터에서 company_id 받기 (홈에서 전달)
        company_id = request.query_params.get("company_id")
        
        return await self.templates.TemplateResponse(request, "settlement_statement_list.html", {
            "company_id": company_id,
        })


class ContractEndManagementView(RoleRestrictedBaseView):
    """계약 종료 관리 - 지사별 계약 종료 예정 정보"""
    name = "계약 종료 관리"
    identity = "contract-end-management"
    icon = "fa-solid fa-file-contract"
    allowed_role_ids = {1}

    @expose("/contract-end-management", methods=["GET"], identity="contract-end-management")  # type: ignore[misc]
    async def index(self, request: Request) -> HTMLResponse:
        self._ensure_identity_path_param(request)
        user_id = request.session.get("user_id")
        role_id = int(request.session.get("role_id") or 0)

        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]
        allowed_roles = self.allowed_role_ids or set()
        if role_id not in allowed_roles:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")

        company_id_param = request.query_params.get("company_id")
        dday_filter_param = request.query_params.get("dday_filter", "")
        memo_filter_param = request.query_params.get("memo_filter", "")
        role_filter_param = request.query_params.get("role_filter", "")
        search_param = (request.query_params.get("search") or "").strip()
        sort_param = request.query_params.get("sort", "dday_asc")

        # 페이징 파라미터
        try:
            page = max(1, int(request.query_params.get("page", "1")))
        except (ValueError, TypeError):
            page = 1
        try:
            per_page = int(request.query_params.get("per_page", "25"))
            if per_page not in (25, 50, 100):
                per_page = 25
        except (ValueError, TypeError):
            per_page = 25

        try:
            company_filter = int(company_id_param) if company_id_param else None
        except ValueError:
            company_filter = None

        db = SessionLocal()
        try:
            companies = (
                db.query(Company)
                .filter(Company.is_active.is_(True))
                .order_by(Company.name)
                .all()
            )

            query = (
                db.query(ContractEnd)
                .options(
                    selectinload(ContractEnd.user).selectinload(User.company),
                    selectinload(ContractEnd.company),
                )
            )
            # D-day 필터: 오늘 기준 계약 종료일까지 남은 일수로 필터링
            today = date.today()
            if dday_filter_param == "120":
                query = query.filter(
                    ContractEnd.contract_end_date > today,
                    ContractEnd.contract_end_date <= today + timedelta(days=120),
                )
            elif dday_filter_param == "90":
                query = query.filter(
                    ContractEnd.contract_end_date > today,
                    ContractEnd.contract_end_date <= today + timedelta(days=90),
                )
            elif dday_filter_param == "30":
                query = query.filter(
                    ContractEnd.contract_end_date > today,
                    ContractEnd.contract_end_date <= today + timedelta(days=30),
                )
            elif dday_filter_param == "expired":
                query = query.filter(ContractEnd.contract_end_date <= today)
            # 메모 유무 필터
            if memo_filter_param == "yes":
                query = query.filter(
                    ContractEnd.memo.isnot(None),
                    ContractEnd.memo != "",
                )
            elif memo_filter_param == "no":
                query = query.filter(
                    (ContractEnd.memo.is_(None)) | (ContractEnd.memo == "")
                )
            # 소속·역할·검색: 현재 User.company 기준
            needs_user_join = (
                company_filter is not None
                or role_filter_param in ("2", "3")
                or bool(search_param)
            )
            if needs_user_join:
                query = query.join(ContractEnd.user)
            if company_filter is not None:
                query = query.filter(User.company_id == company_filter)
            if search_param:
                pattern = f"%{search_param}%"
                query = (
                    query.outerjoin(Company, Company.company_id == User.company_id)
                    .filter(
                        or_(
                            Company.name.ilike(pattern),
                            Company.code.ilike(pattern),
                            User.name.ilike(pattern),
                        )
                    )
                )
            # 역할 필터: 지사(role_id=2), 원장(role_id=3)
            if role_filter_param in ("2", "3"):
                query = query.filter(User.role_id == int(role_filter_param))

            records = query.all()

            from app.services.contract_end_management_service import (
                build_contract_end_rows,
                sort_contract_end_rows,
            )

            rows = build_contract_end_rows(db, records, today=today)
            rows = sort_contract_end_rows(rows, sort_param)
            sales_year = rows[0]["sales_year"] if rows else date.today().year

            # 페이징 계산
            total_count = len(rows)
            total_pages = max(1, (total_count + per_page - 1) // per_page)
            if page > total_pages:
                page = total_pages
            offset = (page - 1) * per_page
            start_index = offset + 1 if total_count > 0 else 0
            end_index = min(offset + per_page, total_count)
            paged_rows = rows[offset:offset + per_page]
        finally:
            db.close()

        return await self.templates.TemplateResponse(request, "contract_end_management.html", {
            "rows": paged_rows,
            "total": total_count,
            "sales_year": sales_year,
            "companies": companies,
            "selected_company_id": company_id_param or "",
            "selected_dday_filter": dday_filter_param,
            "selected_memo_filter": memo_filter_param,
            "selected_role_filter": role_filter_param,
            "selected_search": search_param,
            "selected_sort": sort_param,
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "total_pages": total_pages,
            "start_index": start_index,
            "end_index": end_index,
        })


class MonthlySummaryView(RoleRestrictedBaseView):
    """월별 정산 요약표 - 본사 관리자 전용 (메뉴 미표시)"""
    name = "월 정산 요약 표"
    identity = "monthly-settlement-summary"
    icon = "fa-solid fa-calendar"
    allowed_role_ids = {1}

    def is_visible(self, request: StarletteRequest) -> bool:  # type: ignore[override]
        """사이드 메뉴에 표시하지 않음 (direct URL 또는 프로그래매틱 접근만 허용)"""
        return False

    @expose("/monthly-settlement-summary", methods=["GET"], identity="monthly-settlement-summary")  # type: ignore[misc]
    async def index(self, request: Request) -> HTMLResponse:
        self._ensure_identity_path_param(request)
        user_id = request.session.get("user_id")
        role_id = int(request.session.get("role_id") or 0)

        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]
        
        if role_id != 1:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")

        db = SessionLocal()
        try:
            from sqlalchemy import extract, func as sa_func

            # 정산 데이터가 있는 연도 조회
            years = (
                db.query(extract('year', Settlement.settlement_date).label('year'))
                .filter(Settlement.settlement_type == 'monthly')
                .distinct()
                .order_by('year')
                .all()
            )
            
            # 최근 2개 연도는 항상 보여주기
            available_years = set([r[0] for r in years if r[0]])
            current_year = datetime.now().year
            available_years.add(current_year)
            available_years.add(current_year - 1)
            available_years = sorted([int(y) for y in available_years], reverse=True)

            # 연도별/월별 정산금액합 조회 (monthly-settlement-detail과 동일: 공제 전 = total_commission)
            from sqlalchemy import extract as sa_extract
            monthly_totals_rows = (
                db.query(
                    sa_extract('year', Settlement.settlement_date).label('year'),
                    sa_extract('month', Settlement.settlement_date).label('month'),
                    User.company_id,
                    sa_func.coalesce(sa_func.sum(Settlement.total_commission), 0).label('total_gross')
                )
                .join(User, User.user_id == Settlement.user_id)
                .join(Company, Company.company_id == User.company_id)
                .filter(
                    Settlement.settlement_type == 'monthly',
                    User.role_id == 3,
                    sa_extract('year', Settlement.settlement_date).in_([int(y) for y in available_years]),
                    Company.name.notin_(MONTHLY_SETTLEMENT_SUMMARY_EXCLUDED_REGIONS),
                )
                .group_by(
                    sa_extract('year', Settlement.settlement_date),
                    sa_extract('month', Settlement.settlement_date),
                    User.company_id,
                )
                .all()
            )

            # { year: { month: total } } 맵 구성 — 회사별 공제 전 금액 합산 (detail과 동일)
            monthly_totals: dict[int, dict[int, int]] = {}
            for y in available_years:
                monthly_totals[int(y)] = {}
            for row in monthly_totals_rows:
                y = int(row[0])
                m = int(row[1])
                gross = int(row[3])
                monthly_totals.setdefault(y, {})
                monthly_totals[y][m] = monthly_totals[y].get(m, 0) + gross

            # 연도별 누적 합계
            yearly_totals: dict[int, int] = {}
            for y in available_years:
                y_int = int(y)
                yearly_totals[y_int] = sum(monthly_totals.get(y_int, {}).values())

            return await self.templates.TemplateResponse(request, "monthly_settlement_summary.html", {
                "available_years": available_years,
                "monthly_totals": monthly_totals,
                "yearly_totals": yearly_totals,
            })
        finally:
            db.close()


class MonthlySummaryDetailView(RoleRestrictedBaseView):
    """월별 정산 요약 상세 - 지역별 현황 (메뉴 미표시)"""
    name = "월 정산 요약 상세"
    identity = "monthly-settlement-detail"
    icon = "fa-solid fa-calendar-days"
    allowed_role_ids = {1}

    def is_visible(self, request: StarletteRequest) -> bool:  # type: ignore[override]
        """사이드 메뉴에 표시하지 않음 (direct URL 또는 프로그래매틱 접근만 허용)"""
        return False

    @expose("/monthly-settlement-detail", methods=["GET"], identity="monthly-settlement-detail")  # type: ignore[misc]
    async def index(self, request: Request) -> HTMLResponse:
        self._ensure_identity_path_param(request)
        user_id = request.session.get("user_id")
        role_id = int(request.session.get("role_id") or 0)

        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]
        
        if role_id != 1:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")

        year = request.query_params.get("year")
        month = request.query_params.get("month")

        if not year or not month:
            return HTMLResponse(content="<h3>연도와 월을 선택해주세요.</h3>")

        try:
            year_int = int(year)
            month_int = int(month)
        except (ValueError, TypeError):
            return HTMLResponse(content="<h3>잘못된 연도 또는 월입니다.</h3>")

        db = SessionLocal()
        try:
            from sqlalchemy import func as sa_func

            # 모든 BRANCH 회사 + 지사장(role_id=2) 조회
            all_branches = (
                db.query(Company, User)
                .outerjoin(User, (User.company_id == Company.company_id) & (User.role_id == 2))
                .filter(Company.company_type.in_(['HQ', 'BRANCH']))
                .order_by(Company.name)
                .all()
            )

            # User.company_id 기준 total_commission 합산 (공제 전 금액)
            from sqlalchemy import extract as sa_extract
            settlement_gross_totals = (
                db.query(
                    User.company_id,
                    sa_func.coalesce(sa_func.sum(Settlement.total_commission), 0).label('total_gross')
                )
                .join(Settlement, Settlement.user_id == User.user_id)
                .filter(
                    User.role_id == 3,
                    Settlement.settlement_type == 'monthly',
                    sa_extract('year', Settlement.settlement_date) == year_int,
                    sa_extract('month', Settlement.settlement_date) == month_int,
                )
                .group_by(User.company_id)
                .all()
            )
            amount_map = {int(row[0]): int(row[1]) for row in settlement_gross_totals}
            payment_status_map = fetch_monthly_payment_status_map(db, year_int, month_int)

            manager_ids = [
                int(manager.user_id)
                for _, manager in all_branches
                if manager and getattr(manager, "user_id", None)
            ]
            confirmation_map, issued_at_map = fetch_confirmation_maps(
                db,
                year=year_int,
                month=month_int,
                manager_user_ids=manager_ids,
            )

            # 모든 지사를 포함한 데이터 구성 (정산 0인 지사 포함)
            rows = []
            grand_total = 0
            for company, manager in all_branches:
                region_name = company.name or company.code
                if region_name in MONTHLY_SETTLEMENT_SUMMARY_EXCLUDED_REGIONS:
                    continue
                amount = amount_map.get(company.company_id, 0)
                grand_total += amount
                manager_id = int(manager.user_id) if manager else 0
                rows.append(
                    build_monthly_summary_row(
                        company=company,
                        manager=manager,
                        amount=amount,
                        year=year_int,
                        month=month_int,
                        payment_status=payment_status_map.get(company.company_id),
                        confirmation=confirmation_map.get(manager_id),
                        issued_at=issued_at_map.get(manager_id),
                    )
                )

            # 금액 기준 내림차순 정렬
            rows.sort(key=lambda x: x['amount'], reverse=True)

            return await self.templates.TemplateResponse(request, "monthly_settlement_detail.html", {
                "year": year_int,
                "month": month_int,
                "month_name": f"{month_int}월",
                "rows": rows,
                "grand_total": grand_total,
            })
        finally:
            db.close()


class SettlementConfirmationOverviewView(RoleRestrictedBaseView):
    """지사장 정산서 확인 이력 - 본사 관리자 전용"""
    name = "지사장 정산서 확인"
    identity = "settlement-confirmations"
    icon = "fa-solid fa-clipboard-check"
    allowed_role_ids = {1}

    @expose("/settlement-confirmations", methods=["GET"], identity="settlement-confirmations")  # type: ignore[misc]
    async def index(self, request: Request) -> HTMLResponse:
        self._ensure_identity_path_param(request)
        user_id = request.session.get("user_id")
        role_id = int(request.session.get("role_id") or 0)

        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]
        allowed_roles = self.allowed_role_ids or set()
        if role_id not in allowed_roles:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")

        company_id_param = request.query_params.get("company_id")
        year_param = request.query_params.get("year")
        month_param = request.query_params.get("month")

        try:
            company_filter = int(company_id_param) if company_id_param else None
        except ValueError:
            company_filter = None

        try:
            target_year = int(year_param) if year_param else None
        except ValueError:
            target_year = None

        try:
            target_month = int(month_param) if month_param else None
        except ValueError:
            target_month = None

        db = SessionLocal()
        try:
            companies = (
                db.query(Company)
                .filter(Company.is_active.is_(True))
                .order_by(Company.name)
                .all()
            )

            periods_query = (
                db.query(
                    SettlementStatementConfirmation.year,
                    SettlementStatementConfirmation.month,
                )
                .join(User, SettlementStatementConfirmation.user_id == User.user_id)
                .filter(User.role_id == 2)
                .distinct()
            )

            period_rows = periods_query.all()
            now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
            from app.services.monthly_settlement_summary_service import (
                fetch_issued_at_for_periods,
                is_settlement_period_confirmable,
                max_confirmable_settlement_period,
                months_selectable_for_settlement_year,
            )
            from sqlalchemy import and_, or_

            max_period_year, max_period_month = max_confirmable_settlement_period(now_kst)
            available_years = sorted(
                {row[0] for row in period_rows if row[0] and row[0] <= max_period_year},
                reverse=True,
            )
            months_by_year = {
                y: months_selectable_for_settlement_year(y, now_kst)
                for y in available_years
            }
            if target_year:
                available_months = months_by_year.get(target_year, [])
            else:
                available_months = months_by_year.get(
                    max_period_year,
                    list(range(1, max_period_month + 1)),
                )

            if target_year and target_month:
                if not is_settlement_period_confirmable(target_year, target_month, now_kst):
                    target_month = None

            base_query = (
                db.query(SettlementStatementConfirmation)
                .join(User, SettlementStatementConfirmation.user_id == User.user_id)
                .options(
                    selectinload(SettlementStatementConfirmation.user).selectinload(User.company)
                )
                .filter(User.role_id == 2)
                .filter(
                    or_(
                        SettlementStatementConfirmation.year < max_period_year,
                        and_(
                            SettlementStatementConfirmation.year == max_period_year,
                            SettlementStatementConfirmation.month <= max_period_month,
                        ),
                    )
                )
            )

            if company_filter:
                base_query = base_query.filter(User.company_id == company_filter)
            if target_year:
                base_query = base_query.filter(SettlementStatementConfirmation.year == target_year)
            if target_month:
                base_query = base_query.filter(SettlementStatementConfirmation.month == target_month)

            confirmations = base_query.order_by(SettlementStatementConfirmation.confirmed_at.desc()).all()

            issued_at_map = fetch_issued_at_for_periods(
                db,
                [
                    (int(c.user_id), int(c.year), int(c.month))
                    for c in confirmations
                ],
            )
        finally:
            db.close()

        seoul_tz = ZoneInfo("Asia/Seoul")
        rows = []
        from app.services.monthly_settlement_summary_service import (
            resolve_confirmation_status,
        )

        for confirmation in confirmations:
            manager = confirmation.user
            company = getattr(manager, "company", None)
            company_id_value = getattr(company, "company_id", None)
            statement_url = f"/admin/settlement-statement-detail?year={confirmation.year}&month={confirmation.month}"
            if company_id_value:
                statement_url += f"&company_id={company_id_value}"

            confirmed_at_value = getattr(confirmation, "confirmed_at", None)
            confirmed_at_display = "-"
            if isinstance(confirmed_at_value, datetime):
                if confirmed_at_value.tzinfo is None:
                    confirmed_at_value = confirmed_at_value.replace(tzinfo=timezone.utc)
                confirmed_at_display = confirmed_at_value.astimezone(seoul_tz).strftime("%Y-%m-%d %H:%M:%S")

            issued_at = issued_at_map.get(
                (int(confirmation.user_id), int(confirmation.year), int(confirmation.month))
            )
            status_label = resolve_confirmation_status(
                confirmation=confirmation,
                issued_at=issued_at,
                year=int(confirmation.year),
                month=int(confirmation.month),
                now=now_kst,
            )

            rows.append({
                "company_id": company_id_value,
                "company": getattr(company, "name", "-"),
                "manager": manager.name or manager.login_id or "-",
                # 로그인ID 대신 [미지급/지급/이월] 분류 표시
                "confirmation_status": status_label,
                "year_month": f"{confirmation.year}-{confirmation.month:02d}",
                "confirmed_at_kst": confirmed_at_display,
                "statement_url": statement_url,
            })

        return await self.templates.TemplateResponse(request, "settlement_confirmations.html", {
            "rows": rows,
            "companies": companies,
            "selected_company_id": company_filter,
            "selected_year": target_year,
            "selected_month": target_month,
            "available_years": available_years,
            "available_months": available_months,
            "months_by_year": months_by_year,
            "max_confirmable_period": f"{max_period_year}-{max_period_month:02d}",
            "total_confirmations": len(rows),
        })


class SettlementSkipRecordsView(RoleRestrictedBaseView):
    """정산 스킵 기록 - 본사 관리자 전용"""

    name = "정산 안된 내역"
    identity = "settlement-skip-records"
    icon = "fa-solid fa-exclamation-triangle"
    allowed_role_ids = {1}

    @expose("/settlement-skip-records", methods=["GET"], identity="settlement-skip-records")  # type: ignore[misc]
    async def index(self, request: Request) -> HTMLResponse:
        self._ensure_identity_path_param(request)
        user_id = request.session.get("user_id")
        role_id = int(request.session.get("role_id") or 0)

        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]
        allowed_roles = self.allowed_role_ids or set()
        if role_id not in allowed_roles:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")

        year_param = request.query_params.get("year")
        month_param = request.query_params.get("month")
        reason_param = request.query_params.get("reason")

        # 기간 파라미터가 없으면 당월을 기본값으로 설정
        # URL에 ?year=&month= 처럼 빈 값이 오면 "전체" 의도 → None
        # URL에 파라미터 자체가 없으면 (첫 진입) → 당월 기본값
        now = datetime.now()
        has_query = "year" in request.query_params or "month" in request.query_params
        try:
            if year_param:
                year_filter = int(year_param)
            elif has_query:
                year_filter = None  # 명시적으로 "전체" 선택
            else:
                year_filter = now.year  # 첫 진입 시 당월
        except ValueError:
            year_filter = now.year
        try:
            if month_param:
                month_filter = int(month_param)
            elif has_query:
                month_filter = None
            else:
                month_filter = now.month
        except ValueError:
            month_filter = now.month

        db = SessionLocal()
        try:
            period_rows = (
                db.query(
                    SettlementSkipRecord.settlement_year,
                    SettlementSkipRecord.settlement_month,
                )
                .distinct()
                .order_by(
                    SettlementSkipRecord.settlement_year.desc(),
                    SettlementSkipRecord.settlement_month.desc(),
                )
                .all()
            )
            reason_rows = (
                db.query(SettlementSkipRecord.skip_reason)
                .distinct()
                .order_by(SettlementSkipRecord.skip_reason)
                .all()
            )

            query = (
                db.query(SettlementSkipRecord)
                .options(
                    selectinload(SettlementSkipRecord.user).selectinload(User.company)
                )
                .order_by(SettlementSkipRecord.recorded_at.desc())
            )

            if year_filter is not None:
                query = query.filter(SettlementSkipRecord.settlement_year == year_filter)
            if month_filter is not None:
                query = query.filter(SettlementSkipRecord.settlement_month == month_filter)
            if reason_param:
                query = query.filter(SettlementSkipRecord.skip_reason == reason_param)

            records = query.limit(300).all()
        finally:
            db.close()

        available_years = []
        month_values: set[int] = set()
        for year_value, month_value in period_rows:
            if year_value and year_value not in available_years:
                available_years.append(year_value)
            if month_value is not None:
                try:
                    month_values.add(int(month_value))
                except Exception:
                    pass

        available_years.sort(reverse=True)
        available_months = sorted(month_values, reverse=True)
        reason_options = [r[0] for r in reason_rows if r[0]]

        seoul_tz = ZoneInfo("Asia/Seoul")
        rows: list[dict[str, Any]] = []
        for record in records:
            recorded_at_value = getattr(record, "recorded_at", None)
            recorded_at_display = "-"
            if isinstance(recorded_at_value, datetime):
                if recorded_at_value.tzinfo is None:
                    recorded_at_value = recorded_at_value.replace(tzinfo=timezone.utc)
                recorded_at_display = recorded_at_value.astimezone(seoul_tz).strftime("%Y-%m-%d %H:%M:%S")

            user_obj = getattr(record, "user", None)
            company_obj = getattr(user_obj, "company", None)
            order_info = getattr(record, "order_info", None)
            order_snapshot = "-"
            parts: list[str] = []
            if isinstance(order_info, dict):
                if order_info.get("pay_price") is not None:
                    try:
                        pay_value = int(order_info.get("pay_price"))
                        parts.append(f"결제={pay_value:,}원")
                    except (TypeError, ValueError):
                        pass
                if order_info.get("deli_price") is not None:
                    try:
                        deli_value = int(order_info.get("deli_price"))
                        parts.append(f"배송비={deli_value:,}원")
                    except (TypeError, ValueError):
                        pass
            if parts:
                order_snapshot = " / ".join(parts)

            rows.append({
                "period": f"{record.settlement_year}-{record.settlement_month:02d}",
                "ordernum": record.ordernum,
                "member_id": record.member_id or "-",
                "item_id": record.item_id or "-",
                "reason": record.skip_reason,
                "detail": record.skip_detail or "-",
                "user_login": getattr(user_obj, "login_id", "-"),
                "user_name": getattr(user_obj, "name", "-"),
                "company": getattr(company_obj, "name", "-"),
                "recorded_at_kst": recorded_at_display,
                "order_snapshot": order_snapshot,
            })

        return await self.templates.TemplateResponse(request, "settlement_skip_records.html", {
            "rows": rows,
            "total": len(rows),
            "available_years": available_years,
            "available_months": available_months,
            "selected_year": year_filter,
            "selected_month": month_filter,
            "reason_options": reason_options,
            "selected_reason": reason_param,
        })


class LoginHistoryView(RoleRestrictedBaseView):
    """로그인 이력 - 본사 관리자 전용"""

    name = "로그인 이력"
    identity = "login-history"
    icon = "fa-solid fa-history"
    allowed_role_ids = {1}

    @expose("/login-history", methods=["GET"], identity="login-history")  # type: ignore[misc]
    async def index(self, request: Request) -> HTMLResponse:
        self._ensure_identity_path_param(request)
        user_id = request.session.get("user_id")
        role_id = int(request.session.get("role_id") or 0)

        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)  # type: ignore[return-value]
        allowed_roles = self.allowed_role_ids or set()
        if role_id not in allowed_roles:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")

        db = SessionLocal()
        try:
            query = (
                db.query(LoginHistory, Role)
                .outerjoin(Role, LoginHistory.role_id == Role.role_id)
                .order_by(LoginHistory.login_at.desc())
                .limit(200)
            )
            entries = query.all()
        finally:
            db.close()

        seoul_tz = ZoneInfo("Asia/Seoul")
        rows: list[dict[str, Any]] = []
        for history, role in entries:
            login_at_value = getattr(history, "login_at", None)
            login_at_kst = "-"
            if isinstance(login_at_value, datetime):
                if login_at_value.tzinfo is None:
                    login_at_value = login_at_value.replace(tzinfo=timezone.utc)
                login_at_kst = login_at_value.astimezone(seoul_tz).strftime("%Y-%m-%d %H:%M:%S")
            rows.append({
                "user_id": getattr(history, "user_id", "-"),
                "login_id": getattr(history, "login_id", "-"),
                "user_name": getattr(history, "user_name", "-"),
                "role_name": getattr(role, "role_name", "-"),
                "ip_address": getattr(history, "ip_address", "-"),
                "user_agent": getattr(history, "user_agent", "-"),
                "login_at": login_at_value,
                "login_at_kst": login_at_kst,
                "source": getattr(history, "source", "-"),
            })

        return await self.templates.TemplateResponse(request, "login_history.html", {
            "rows": rows,
            "total": len(rows),
        })


class SettlementStatementDetailView(RoleRestrictedBaseView):
    """정산서 상세 - 특정 년/월의 정산서 상세 페이지"""
    name = "정산서 상세"
    identity = "settlement-statement-detail"
    icon = "fa-solid fa-file-invoice-dollar"
    allowed_role_ids = {1, 2}  # 관리자, 지사장만

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/settlement-statement-detail", methods=["GET"], identity="settlement-statement-detail")  # type: ignore[misc]
    async def index(self, request):  # type: ignore[override]
        """정산서 상세 페이지 - 특정 년/월의 정산서 표시"""
        user_id = request.session.get("user_id")
        role_id = request.session.get("role_id")
        
        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)
        if role_id not in {1, 2}:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")
        
        # URL 파라미터에서 company_id 받기 (홈에서 전달)
        company_id = request.query_params.get("company_id")
        
        from app.services.monthly_settlement_summary_service import (
            is_company_monthly_statement_issued,
            is_settlement_period_confirmable,
            max_confirmable_settlement_period,
        )

        now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
        max_y, max_m = max_confirmable_settlement_period(now_kst)
        default_year, default_month = max_y, max_m

        year = int(request.query_params.get("year", default_year))
        month = int(request.query_params.get("month", default_month))

        if not is_settlement_period_confirmable(year, month, now_kst):
            return HTMLResponse(
                content=(
                    f"<h3>아직 조회할 수 없는 정산서입니다.</h3>"
                    f"<p>{year}년 {month:02d}월 정산서는 "
                    f"{max_y}년 {max_m:02d}월까지 확인 가능합니다.</p>"
                    f'<p><a href="/admin/settlement-statement">정산서 목록으로</a></p>'
                ),
                status_code=400,
            )

        # 지사장: 미발행이면 상세 URL 직접 접속도 차단
        role_id_value = int(role_id) if role_id is not None else None
        if role_id_value == 2:
            db = SessionLocal()
            try:
                current_user = db.query(User).filter(User.user_id == int(user_id)).first()
                company_id_value = int(getattr(current_user, "company_id", 0) or 0) if current_user else 0
                if not company_id_value or not is_company_monthly_statement_issued(
                    db, company_id=company_id_value, year=year, month=month
                ):
                    return HTMLResponse(
                        content=(
                            f"<h3>아직 발행되지 않은 정산서입니다.</h3>"
                            f"<p>{year}년 {month:02d}월 정산서는 발행 후 확인할 수 있습니다.</p>"
                            f'<p><a href="/admin/settlement-statement">정산서 목록으로</a></p>'
                        ),
                        status_code=400,
                    )
            finally:
                db.close()

        return await self.templates.TemplateResponse(request, "settlement_statement_detail.html", {
            "year": year,
            "month": month,
            "company_id": company_id,
            "role_id": role_id_value,
        })


class TeachersListView(RoleRestrictedBaseView):
    """소속 원장 리스트 - SQLAdmin 템플릿 기반 렌더링"""
    name = "소속 원장 리스트"
    identity = "teachers-list"
    icon = "fa-solid fa-chalkboard-teacher"
    allowed_role_ids = {2}

    @expose("/teachers-list", methods=["GET"], identity="teachers-list")  # type: ignore[misc]
    async def index(self, request):  # type: ignore[override]
        """소속 원장 리스트 페이지 - SQLAdmin 템플릿 사용"""
        from app.services.teachers_list_service import fetch_teachers_list_data

        user_id = request.session.get("user_id")
        role_id = request.session.get("role_id")
        
        if not user_id:
            return RedirectResponse(url="/admin/login", status_code=302)
        if role_id not in {1, 2}:
            return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")
        
        # URL에서 sort, company_id 파라미터 가져오기
        sort_by = request.query_params.get("sort", "all")
        company_id_param = request.query_params.get("company_id")
        
        # DB에서 소속 원장 목록 조회
        db = SessionLocal()
        try:
            current_user = db.query(User).filter(User.user_id == user_id).first()
            if not current_user:
                return HTMLResponse(content="<h3>사용자 정보를 찾을 수 없습니다.</h3>")
            
            # company_id 결정: URL 파라미터 우선, 없으면 current_user.company_id
            try:
                target_company_id = int(company_id_param) if company_id_param else current_user.company_id
            except (TypeError, ValueError):
                target_company_id = current_user.company_id
            
            # role_id=1(본사관리자)은 모든 지사 조회 가능, role_id=2(지사장)는 자신의 지사만 조회 가능
            if int(role_id) == 2 and target_company_id != current_user.company_id:
                return HTMLResponse(content="<h3>접근 권한이 없습니다.</h3>")
            
            teachers_data = fetch_teachers_list_data(db, target_company_id)

            if sort_by == "name":
                teachers_data.sort(key=lambda x: x["name"])
            elif sort_by == "join_date":
                teachers_data.sort(
                    key=lambda x: x["join_date_sort"] if x["join_date"] != "-" else "0000-00-00",
                    reverse=True,
                )
            elif sort_by == "purchase_count":
                teachers_data.sort(key=lambda x: x["purchase_count"], reverse=True)
            elif sort_by == "yearly_payment":
                teachers_data.sort(key=lambda x: x["yearly_payment"], reverse=True)
            elif sort_by == "d_day":
                teachers_data.sort(key=lambda x: x["d_day_sort"])
            
        finally:
            db.close()
        
        # 정렬 옵션
        sort_options = [
            {"value": "all", "label": "전체"},
            {"value": "name", "label": "이름순"},
            {"value": "join_date", "label": "가입일순"},
            {"value": "purchase_count", "label": "구매건순"},
            {"value": "yearly_payment", "label": "누적액순"},
            {"value": "d_day", "label": "D-day순"},
        ]
        
        return await self.templates.TemplateResponse(request, "teachers_list.html", {
            "data": teachers_data,
            "sort_options": sort_options,
            "selected_sort": sort_by,
            # Preserve company_id in the template so the sort form keeps it when submitted
            "company_id": company_id_param,
        })

def setup_admin(app: FastAPI) -> Admin:
    """SQLAdmin 설정 - ModelView 등록 기반, 실패 시 안전한 기본 모드로 폴백"""
    # SessionMiddleware 추가 (인증 세션 관리용)
    app.add_middleware(SessionMiddleware, secret_key="babba-api-secret-key", max_age=10 * 60)
    
    # 템플릿 디렉토리 경로 확인
    template_path = os.path.join(os.path.dirname(__file__), "templates")
    logger.info(f"[ADMIN] Template directory: {template_path}")
    logger.info(f"[ADMIN] Template directory exists: {os.path.exists(template_path)}")
    
    # 먼저 정적 파일 마운트 시도
    try:
        from fastapi.staticfiles import StaticFiles
        import sqladmin
        sqladmin_dir = os.path.dirname(sqladmin.__file__)
        statics_path = os.path.join(sqladmin_dir, "statics")
        if os.path.isdir(statics_path):
            app.mount("/admin/statics", StaticFiles(directory=statics_path), name="admin_statics")
            logger.info(f"[ADMIN] ✅ Mounted sqladmin statics from: {statics_path}")
        else:
            logger.warning(f"[ADMIN] ⚠️ sqladmin statics directory not found at: {statics_path}")
    except Exception as e:
        logger.warning(f"[ADMIN] ⚠️ Failed to mount sqladmin statics: {e}")
    
    # app/static 디렉토리 마운트 (로고 및 커스텀 자산)
    try:
        from fastapi.staticfiles import StaticFiles
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        if os.path.isdir(static_dir):
            app.mount("/static", StaticFiles(directory=static_dir), name="static")
            logger.info(f"[ADMIN] ✅ Mounted app static files from: {static_dir}")
        else:
            logger.warning(f"[ADMIN] ⚠️ App static directory not found at: {static_dir}")
    except Exception as e:
        logger.warning(f"[ADMIN] ⚠️ Failed to mount app static files: {e}")
    
    # 항상 Admin 인스턴스부터 생성
    admin = BabbaAdmin(
        app=app,
        engine=engine,
        title="바빠 스마트 클래스 정산 서비스",
        logo_url="/static/babba-logo.png",
        base_url="/admin",
        templates_dir=template_path,
        authentication_backend=AdminAuthenticationBackend(),  # 인증 백엔드 추가
    )

    # 등록을 안전하게 수행하는 헬퍼 (개별 실패가 전체를 중단하지 않도록)
    def _safe_add(view_cls):
        try:
            logger.info(f"[ADMIN] Registering view: {view_cls.__name__}")
            admin.add_view(view_cls)
            logger.info(f"[ADMIN] View registered: {getattr(view_cls, 'identity', view_cls.__name__)}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ADMIN] View register failed: {view_cls.__name__} -> {type(e).__name__}: {e}")

    # 본사 관리자(role_id=1) 사이드바 메뉴 순서 (구분선은 layout.html에서 삽입)
    # 그룹1: 홈 · 계약 종료 관리 · 지사장 정산서 확인
    # 그룹2: 회원 관리 · 지사 관리 · 등급 관리 · 역할 관리 · 공지사항
    # 그룹3: 정산 안된 내역 · 수수료 유형 · 수수료율
    # 그룹4: 로그인 이력 · 지사장 비밀번호 초기화
    for bv in [
        HomeDashboardView,
        ContractEndManagementView,
        SettlementConfirmationOverviewView,
    ]:
        _safe_add(bv)

    for mv in [
        UserAdmin,
        CompanyAdmin,
        GradeAdmin,
        RoleAdmin,
        NoticeAdmin,
    ]:
        _safe_add(mv)

    for item in [
        SettlementSkipRecordsView,
        CommissionTypeAdmin,
        CommissionRateWindowAdmin,
        # OrderAdmin,  # 숨김 처리
        # MemberAdmin,  # 필요 시 추가
    ]:
        _safe_add(item)

    for bv in [
        LoginHistoryView,
        BranchPasswordResetView,
    ]:
        _safe_add(bv)

    # 지사장(role_id=2) 전용 메뉴
    for bv in [
        SettlementOverviewView,
        SettlementStatusView,
        SettlementDailyStatusView,
        SettlementStatementView,
        TeachersListView,
    ]:
        _safe_add(bv)

    # 메뉴 미표시 페이지 (직접 URL 접근)
    for hidden in [
        MonthlySummaryView,
        MonthlySummaryDetailView,
        SettlementStatementDetailView,
    ]:
        _safe_add(hidden)

    logger.info("=" * 70)
    logger.info("✅ SQLAdmin 설정 완료")
    logger.info("📊 관리 페이지: /admin/")
    logger.info("=" * 70)
    
    return admin

