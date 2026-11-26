"""계약 종료 관리 화면/엑셀 공통 데이터 조합."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models import ContractEnd, Order, OrderItem, User
from app.services.order_query import COMPLETED_ORDER_STATUSES, order_date_in_period_filters

BRANCH_MANAGER_ROLE_ID = 2
TEACHER_ROLE_ID = 3


def parse_contract_start(user: User | None, contract_end_date: date | None) -> date | None:
    """계약 시작일: contracted_at 우선, 없으면 계약 종료일에서 1년 역산."""
    if user and user.contracted_at:
        raw = str(user.contracted_at).strip().replace(".", "-")[:10]
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            pass
    if isinstance(contract_end_date, date):
        return contract_end_date - timedelta(days=365)
    return None


def get_yearly_branch_sales(
    db: Session,
    company_ids: list[int] | None = None,
) -> tuple[dict[int, int], int]:
    """홈 · 소속 원장별 월매출 누적과 동일한 지사별 실결제 합계."""
    from app.services.settlement_status_service import get_all_branches_yearly_sales

    return get_all_branches_yearly_sales(db, company_ids=company_ids)


def count_teachers_by_company(db: Session) -> dict[int, int]:
    """지사별 소속 원장(role_id=3) 수 (지사 본인 제외)."""
    rows = (
        db.query(User.company_id, func.count(User.user_id))
        .filter(User.role_id == TEACHER_ROLE_ID)
        .group_by(User.company_id)
        .all()
    )
    return {cid: int(cnt) for cid, cnt in rows}


def get_personal_payment_map(db: Session, user_ids: list[int]) -> dict[int, int]:
    """1년간 본인 결제 총액 (가입비 주문 제외)."""
    if not user_ids:
        return {}
    one_year_ago_str = (date.today() - timedelta(days=365)).strftime("%Y%m%d") + "000000"
    payment_rows = (
        db.query(
            User.user_id,
            func.coalesce(func.sum(Order.pay_price), 0).label("total_pay"),
        )
        .join(Order, Order.member_id == User.login_id)
        .filter(
            User.user_id.in_(user_ids),
            Order.order_date >= one_year_ago_str,
            ~Order.ordernum.in_(
                db.query(OrderItem.ordernum)
                .filter(OrderItem.product_name.like("[가입]%"))
                .distinct()
            ),
        )
        .group_by(User.user_id)
        .all()
    )
    return {uid: int(total_pay) for uid, total_pay in payment_rows}


def _order_date_in_period_filters(start: date, end_exclusive: date):
    return order_date_in_period_filters(start, end_exclusive)


def get_company_sales_in_period(
    db: Session,
    company_id: int,
    start: date,
    end_exclusive: date,
) -> int:
    """지사 소속 전체(가입비+원장+지사장) 실결제 합계."""
    total = (
        db.query(func.coalesce(func.sum(Order.pay_price), 0))
        .join(User, Order.member_id == User.login_id)
        .filter(
            User.company_id == company_id,
            Order.order_status.in_(COMPLETED_ORDER_STATUSES),
            Order.pay_status == "Y",
            _order_date_in_period_filters(start, end_exclusive),
        )
        .scalar()
    )
    return int(total or 0)


def resolve_contract_end_company_id(record: ContractEnd) -> int | None:
    """소속 company_id: User.company_id 우선 (ContractEnd 스냅샷보다 현재 소속 기준)."""
    user = record.user
    if user and user.company_id:
        return int(user.company_id)
    if record.company_id:
        return int(record.company_id)
    return None


def build_contract_period_sales_cache(
    db: Session,
    records: list[ContractEnd],
) -> dict[tuple[int, date, date], int]:
    """지사장별 계약 12개월 누적매출을 주문 1회 조회로 일괄 집계."""
    keys: set[tuple[int, date, date]] = set()
    for record in records:
        user = record.user
        if not user or user.role_id != BRANCH_MANAGER_ROLE_ID:
            continue
        company_id = resolve_contract_end_company_id(record)
        if not company_id:
            continue
        start = parse_contract_start(user, record.contract_end_date)
        if not start:
            continue
        end = start + timedelta(days=365)
        keys.add((company_id, start, end))

    cache = {key: 0 for key in keys}
    if not keys:
        return cache

    min_start = min(start for _, start, _ in keys)
    max_end = max(end for _, _, end in keys)
    company_ids = sorted({company_id for company_id, _, _ in keys})
    rows = (
        db.query(User.company_id, Order.order_date, Order.pay_price)
        .join(Order, Order.member_id == User.login_id)
        .filter(
            User.company_id.in_(company_ids),
            Order.order_status.in_(COMPLETED_ORDER_STATUSES),
            Order.pay_status == "Y",
            _order_date_in_period_filters(min_start, max_end),
        )
        .all()
    )

    windows_by_company: dict[int, list[tuple[int, date, date]]] = {}
    for key in keys:
        windows_by_company.setdefault(key[0], []).append(key)

    for company_id, raw_order_date, pay_price in rows:
        if not raw_order_date or company_id is None:
            continue
        for key in windows_by_company.get(int(company_id), []):
            if _order_date_matches_period(raw_order_date, key[1], key[2]):
                cache[key] += int(pay_price or 0)
    return cache


def _order_date_matches_period(value: Any, start: date, end_exclusive: date) -> bool:
    """기존 SQL의 YYYY-MM-DD / YYYYMMDD 문자열 OR 비교와 동일하게 판정."""
    raw = str(value or "").strip()
    start_dash = start.strftime("%Y-%m-%d")
    end_dash = end_exclusive.strftime("%Y-%m-%d")
    start_compact = start.strftime("%Y%m%d")
    end_compact = end_exclusive.strftime("%Y%m%d")
    return (
        start_dash <= raw < end_dash
        or start_compact <= raw < end_compact
    )


def _format_amount(value: int | None) -> str:
    if not value:
        return ""
    return f"{value:,}"


def build_contract_end_rows(
    db: Session,
    records: list[ContractEnd],
    today: date | None = None,
) -> list[dict[str, Any]]:
    """ContractEnd 레코드 목록을 화면/엑셀용 row dict로 변환."""
    today = today or date.today()
    personal_payment_user_ids = [
        r.user_id for r in records
        if r.user_id
        and r.user
        and r.user.role_id in (BRANCH_MANAGER_ROLE_ID, TEACHER_ROLE_ID)
    ]
    payment_map = get_personal_payment_map(db, personal_payment_user_ids)
    teacher_counts = count_teachers_by_company(db)
    yearly_company_ids = sorted({
        cid
        for record in records
        if record.user and record.user.role_id == BRANCH_MANAGER_ROLE_ID
        for cid in [resolve_contract_end_company_id(record)]
        if cid
    })
    yearly_sales_map, sales_year = get_yearly_branch_sales(
        db,
        company_ids=yearly_company_ids,
    )
    period_sales_cache = build_contract_period_sales_cache(db, records)

    rows: list[dict[str, Any]] = []
    for record in records:
        contract_date = record.contract_end_date
        d_day_display = "-"
        d_day_color = ""
        if isinstance(contract_date, date):
            diff_days = (contract_date - today).days
            if diff_days > 0:
                d_day_display = str(diff_days)
                if diff_days <= 30:
                    d_day_color = "#0000ff"
                elif diff_days <= 90:
                    d_day_color = "#078b00"
            else:
                d_day_display = "계약종료"
                d_day_color = "#ff0004"

        user_obj = record.user
        # 소속은 현재 User.company 기준 (ContractEnd.company_id 스냅샷과 어긋나지 않게)
        company_id = resolve_contract_end_company_id(record)
        company_obj = None
        if user_obj and user_obj.company:
            company_obj = user_obj.company
        elif record.company:
            company_obj = record.company
        company_name = (company_obj.name if company_obj else None) or (
            company_obj.code if company_obj else None
        ) or "-"
        user_name = user_obj.name if user_obj else "-"
        role_id = user_obj.role_id if user_obj else None
        is_branch_manager = role_id == BRANCH_MANAGER_ROLE_ID

        member_count = teacher_counts.get(company_id, 0) if company_id else 0
        cumulative_sales_1: int | None = None
        cumulative_sales_2: int | None = None
        total_pay: int | None = None

        if role_id in (BRANCH_MANAGER_ROLE_ID, TEACHER_ROLE_ID):
            total_pay = payment_map.get(record.user_id, 0)

        if is_branch_manager and company_id:
            cumulative_sales_2 = yearly_sales_map.get(company_id, 0)
            start = parse_contract_start(user_obj, contract_date)
            if start:
                end = start + timedelta(days=365)
                cumulative_sales_1 = period_sales_cache.get(
                    (company_id, start, end), 0
                )

        memo_text = record.memo or ""

        rows.append({
            "company": company_name,
            "company_id": company_id,
            "settlement_status_url": (
                f"/admin/settlement-status?company_id={company_id}" if company_id else ""
            ),
            "user_name": user_name,
            "user_id": record.user_id,
            "role_id": role_id,
            "contract_end_id": record.contract_end_id,
            "contract_end_date": contract_date.strftime("%Y-%m-%d") if isinstance(contract_date, date) else "-",
            "d_day": d_day_display,
            "d_day_color": d_day_color,
            "member_count": member_count if member_count else "",
            "cumulative_sales_1": _format_amount(cumulative_sales_1),
            "cumulative_sales_1_value": cumulative_sales_1 or 0,
            "cumulative_sales_2": _format_amount(cumulative_sales_2),
            "cumulative_sales_2_value": cumulative_sales_2 or 0,
            "sales_year": sales_year,
            "total_payment": _format_amount(total_pay),
            "total_payment_value": total_pay or 0,
            "has_memo": bool(memo_text.strip()),
            "renewal_count": record.renewal_count or 0,
            "memo": memo_text,
        })
    return rows


def _d_day_sort_key(d_day: str) -> tuple[int, int]:
    """D-day 정렬용: (우선순위, 일수). 미입력 맨 뒤, 계약종료 그 앞."""
    if d_day == "-":
        return (2, 0)
    if d_day == "계약종료":
        return (1, 0)
    try:
        return (0, int(d_day))
    except ValueError:
        return (2, 0)


def _numeric_sort_key(value: int, *, descending: bool = False) -> tuple[int, int]:
    """값 없음(0)은 맨 뒤."""
    has_value = value > 0
    ordered = -value if descending else value
    return (0 if has_value else 1, ordered)


def sort_contract_end_rows(rows: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    """계약 종료 관리 row 정렬."""

    def _sort_key_dday_asc(r: dict[str, Any]) -> tuple[int, str]:
        has_date = r["contract_end_date"] != "-"
        return (0 if has_date else 1, r["contract_end_date"])

    if sort == "company_asc":
        rows.sort(key=lambda r: r["company"])
    elif sort == "company_desc":
        rows.sort(key=lambda r: r["company"], reverse=True)
    elif sort == "user_asc":
        rows.sort(key=lambda r: r["user_name"])
    elif sort == "user_desc":
        rows.sort(key=lambda r: r["user_name"], reverse=True)
    elif sort == "dday_asc":
        rows.sort(key=lambda r: _d_day_sort_key(r["d_day"]))
    elif sort == "dday_desc":
        rows.sort(key=lambda r: _d_day_sort_key(r["d_day"]), reverse=True)
    elif sort == "member_count_asc":
        rows.sort(key=lambda r: _numeric_sort_key(int(r["member_count"] or 0)))
    elif sort == "member_count_desc":
        rows.sort(
            key=lambda r: _numeric_sort_key(int(r["member_count"] or 0), descending=True)
        )
    elif sort == "sales1_asc":
        rows.sort(key=lambda r: _numeric_sort_key(r["cumulative_sales_1_value"]))
    elif sort == "sales1_desc":
        rows.sort(
            key=lambda r: _numeric_sort_key(r["cumulative_sales_1_value"], descending=True)
        )
    elif sort == "sales2_asc":
        rows.sort(key=lambda r: _numeric_sort_key(r["cumulative_sales_2_value"]))
    elif sort == "sales2_desc":
        rows.sort(
            key=lambda r: _numeric_sort_key(r["cumulative_sales_2_value"], descending=True)
        )
    elif sort in ("total_payment_asc",):
        rows.sort(key=lambda r: _numeric_sort_key(r["total_payment_value"]))
    elif sort in ("total_payment_desc", "payment_desc"):
        rows.sort(
            key=lambda r: _numeric_sort_key(r["total_payment_value"], descending=True)
        )
    elif sort == "renewal_count_asc":
        rows.sort(key=lambda r: r["renewal_count"])
    elif sort == "renewal_count_desc":
        rows.sort(key=lambda r: r["renewal_count"], reverse=True)
    else:
        rows.sort(key=_sort_key_dday_asc)
    return rows
