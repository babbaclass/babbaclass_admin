"""소속 원장 리스트 데이터 조회"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import ContractEnd, Order, OrderItem, User
from app.services.order_query import COMPLETED_ORDER_STATUSES, order_date_in_period_filters

SIX_MONTH_LOOKBACK_DAYS = 180
ONE_YEAR_LOOKBACK_DAYS = 365


def _format_join_date(contracted_at: str | None) -> str:
    if not contracted_at:
        return "-"
    s = str(contracted_at).strip()
    if len(s) >= 10 and s[4] == "-":
        return s[:10].replace("-", ".")
    if len(s) >= 8 and s[4:6].isdigit():
        return f"{s[:4]}.{s[4:6]}.{s[6:8]}"
    return s


def _calc_d_day(contract_end_date: date | None, today: date | None = None) -> tuple[str, str]:
    today = today or date.today()
    if not isinstance(contract_end_date, date):
        return "-", ""
    diff_days = (contract_end_date - today).days
    if diff_days > 0:
        color = ""
        if diff_days <= 30:
            color = "#0000ff"
        elif diff_days <= 90:
            color = "#078b00"
        return str(diff_days), color
    return "계약종료", "#ff0004"


def _d_day_sort_value(d_day: str) -> int:
    """D-day순 정렬용: 임박한 계약종료일 우선, 미등록은 맨 뒤"""
    if d_day == "-":
        return 999999
    if d_day == "계약종료":
        return 0
    try:
        return int(d_day)
    except ValueError:
        return 999999


def _signup_order_subquery(db: Session):
    return (
        db.query(OrderItem.ordernum)
        .filter(OrderItem.product_name.like("[가입]%"))
        .distinct()
    )


def _completed_order_filters(db: Session, *, start: date, end_exclusive: date):
    return (
        Order.pay_status == "Y",
        Order.order_status.in_(COMPLETED_ORDER_STATUSES),
        order_date_in_period_filters(start, end_exclusive),
        ~Order.ordernum.in_(_signup_order_subquery(db)),
    )


def _fetch_purchase_count_map(
    db: Session,
    teacher_ids: list[int],
    *,
    start: date,
    end_exclusive: date,
) -> dict[int, int]:
    if not teacher_ids:
        return {}

    rows = (
        db.query(User.user_id, func.count(Order.id))
        .join(Order, Order.member_id == User.login_id)
        .filter(
            User.user_id.in_(teacher_ids),
            *_completed_order_filters(db, start=start, end_exclusive=end_exclusive),
        )
        .group_by(User.user_id)
        .all()
    )
    return {int(uid): int(count) for uid, count in rows}


def _fetch_yearly_payment_map(
    db: Session,
    teacher_ids: list[int],
    *,
    start: date,
    end_exclusive: date,
) -> dict[int, int]:
    if not teacher_ids:
        return {}

    rows = (
        db.query(
            User.user_id,
            func.coalesce(func.sum(Order.pay_price), 0).label("total_pay"),
        )
        .join(Order, Order.member_id == User.login_id)
        .filter(
            User.user_id.in_(teacher_ids),
            *_completed_order_filters(db, start=start, end_exclusive=end_exclusive),
        )
        .group_by(User.user_id)
        .all()
    )
    return {int(uid): int(total) for uid, total in rows}


def fetch_teachers_list_data(db: Session, company_id: int) -> list[dict[str, Any]]:
    """지사 소속 원장(role_id=3) 리스트 데이터"""
    teachers = (
        db.query(User)
        .filter(User.company_id == company_id, User.role_id == 3)
        .all()
    )
    if not teachers:
        return []

    today = date.today()
    six_month_start = today - timedelta(days=SIX_MONTH_LOOKBACK_DAYS)
    one_year_start = today - timedelta(days=ONE_YEAR_LOOKBACK_DAYS)
    tomorrow = today + timedelta(days=1)

    teacher_ids = [t.user_id for t in teachers]
    contract_end_map: dict[int, date | None] = {}
    contract_rows = (
        db.query(ContractEnd.user_id, ContractEnd.contract_end_date)
        .filter(ContractEnd.user_id.in_(teacher_ids))
        .order_by(ContractEnd.contract_end_id.desc())
        .all()
    )
    for uid, end_date in contract_rows:
        if uid not in contract_end_map:
            contract_end_map[uid] = end_date

    purchase_map = _fetch_purchase_count_map(
        db,
        teacher_ids,
        start=six_month_start,
        end_exclusive=tomorrow,
    )
    payment_map = _fetch_yearly_payment_map(
        db,
        teacher_ids,
        start=one_year_start,
        end_exclusive=tomorrow,
    )

    rows: list[dict[str, Any]] = []
    for t in teachers:
        purchase_count = purchase_map.get(t.user_id, 0)
        yearly_payment = payment_map.get(t.user_id, 0)
        contract_end_date = contract_end_map.get(t.user_id)
        if contract_end_date is None and getattr(t, "contract_end_date", None):
            contract_end_date = t.contract_end_date

        d_day, d_day_color = _calc_d_day(contract_end_date, today)
        d_day_sort = _d_day_sort_value(d_day)

        rows.append(
            {
                "name": t.name or "-",
                "purchase_count": int(purchase_count),
                "yearly_payment": yearly_payment,
                "yearly_payment_display": f"{yearly_payment:,}원" if yearly_payment else "",
                "d_day": d_day,
                "d_day_color": d_day_color,
                "d_day_sort": d_day_sort,
                "join_date": _format_join_date(t.contracted_at),
                "join_date_sort": (t.contracted_at or "0000-00-00").replace(".", "-")[:10],
                "contact": t.main_contact or "-",
            }
        )

    return rows
