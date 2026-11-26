"""소속 원장별 월매출/일별 매출 화면·엑셀 공통 데이터 조합."""
from __future__ import annotations

import calendar
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, extract, func, or_
from sqlalchemy.orm import Session

from app.models import Order, OrderItem, Product, Settlement, User

BRANCH_MANAGER_ROLE_ID = 2
TEACHER_ROLE_ID = 3
MTD_SETTLEMENT_TYPE = "mtd"
MONTHLY_SETTLEMENT_TYPE = "monthly"
KST = ZoneInfo("Asia/Seoul")


def _empty_aggregate(user_id: int, name: str, phone: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "name": name,
        "phone": phone,
        "consumer_price_total": 0,
        "sell_price_total": 0,
        "delivery_total": 0,
        "used_reserve_total": 0,
        "actual_payment_total": 0,
        "processed_orders": set(),
        "is_branch_manager": False,
    }


def _year_cumulative_order_end_exclusive(year: int) -> str:
    """연도 누적 조회 시 주문 종료일(미포함). 당해 연도는 당월 1일 전까지(홈 총매출과 동일)."""
    now = datetime.now(KST)
    if year < now.year:
        return f"{year + 1}-01-01"
    if year > now.year:
        return f"{year}-01-01"
    if now.month <= 1:
        return f"{year}-01-01"
    return f"{year}-{now.month:02d}-01"


def _year_cumulative_order_end_compact(year: int) -> str:
    return _year_cumulative_order_end_exclusive(year).replace("-", "")[:8]


def _apply_order_period_filter(query, month: str | None, year: str | None):
    """주문일 기준 기간 필터 (YYYY-MM-DD / YYYYMMDD 혼용)."""
    if month and month != "전체":
        year_val, mon_val = month.split("-")
        y, m = int(year_val), int(mon_val)
        start_dash = f"{y}-{m:02d}-01"
        end_dash = f"{y + 1}-01-01" if m == 12 else f"{y}-{m + 1:02d}-01"
        start_compact = f"{y}{m:02d}01"
        end_compact = end_dash.replace("-", "")[:8]
        return query.filter(
            or_(
                and_(Order.order_date >= start_dash, Order.order_date < end_dash),
                and_(Order.order_date >= start_compact, Order.order_date < end_compact),
            )
        )
    if year:
        y = int(year)
        start_dash = f"{y}-01-01"
        start_compact = f"{y}0101"
        if month == "전체" or not month:
            end_dash = _year_cumulative_order_end_exclusive(y)
            end_compact = _year_cumulative_order_end_compact(y)
        else:
            end_dash = f"{y + 1}-01-01"
            end_compact = f"{y + 1}0101"
        return query.filter(
            or_(
                and_(Order.order_date >= start_dash, Order.order_date < end_dash),
                and_(Order.order_date >= start_compact, Order.order_date < end_compact),
            )
        )
    return query


def _apply_order_mtd_filter(query, end_date: date):
    """이번 달 1일~기준일(포함) 주문 필터."""
    start_dash = end_date.replace(day=1).strftime("%Y-%m-%d")
    end_dash = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
    start_compact = end_date.replace(day=1).strftime("%Y%m%d")
    end_compact = (end_date + timedelta(days=1)).strftime("%Y%m%d")
    return query.filter(
        or_(
            and_(Order.order_date >= start_dash, Order.order_date < end_dash),
            and_(Order.order_date >= start_compact, Order.order_date < end_compact),
        )
    )


def _aggregate_user_order_sales(
    db: Session,
    user: User,
    *,
    month: str | None = None,
    year: str | None = None,
    mtd_end_date: date | None = None,
    is_branch_manager: bool = False,
) -> dict[str, Any]:
    """회원 본인 주문(member_id=login_id) 매출 집계."""
    agg = _empty_aggregate(
        int(user.user_id),
        user.name or "",
        user.main_contact or "",
    )
    agg["is_branch_manager"] = is_branch_manager

    login_id = (user.login_id or "").strip()
    if not login_id:
        return agg

    query = db.query(Order).filter(
        Order.member_id == login_id,
        Order.order_status.in_(["Y", "P"]),
        Order.pay_status == "Y",
    )
    if mtd_end_date is not None:
        query = _apply_order_mtd_filter(query, mtd_end_date)
    else:
        query = _apply_order_period_filter(query, month, year)
    orders = query.all()
    if not orders:
        return agg

    order_nums = [o.ordernum for o in orders if o.ordernum]
    order_items_map: dict[str, list[OrderItem]] = defaultdict(list)
    if order_nums:
        for item in db.query(OrderItem).filter(OrderItem.ordernum.in_(order_nums)).all():
            order_items_map[item.ordernum].append(item)

    product_cache: dict[str, Product | None] = {}

    for order in orders:
        ordernum = order.ordernum
        if not ordernum or ordernum in agg["processed_orders"]:
            continue
        sell_price = 0
        for item in order_items_map.get(ordernum, []):
            sell_price += int(getattr(item, "sell_price", 0) or 0)
            product_uid = getattr(item, "product_uid", None)
            quantity = int(getattr(item, "basket_stock", 1) or 1)
            if product_uid:
                if product_uid not in product_cache:
                    product_cache[product_uid] = (
                        db.query(Product).filter(Product.uid == product_uid).first()
                    )
                product = product_cache[product_uid]
                if product:
                    consumer_price = int(product.consumerprice or 0)
                    if consumer_price == 0:
                        consumer_price = int(product.sellprice or 0)
                    agg["consumer_price_total"] += consumer_price * quantity

        agg["sell_price_total"] += sell_price
        agg["used_reserve_total"] += int(getattr(order, "used_reserve", 0) or 0)
        agg["delivery_total"] += int(getattr(order, "deli_price", 0) or 0)
        agg["processed_orders"].add(ordernum)

    agg["actual_payment_total"] = agg["sell_price_total"] - agg["used_reserve_total"]
    return agg


def _aggregate_branch_manager_sales(
    db: Session,
    manager: User,
    *,
    month: str | None = None,
    year: str | None = None,
    mtd_end_date: date | None = None,
) -> dict[str, Any]:
    """지사장 본인 주문(member_id=login_id) 매출 집계."""
    return _aggregate_user_order_sales(
        db,
        manager,
        month=month,
        year=year,
        mtd_end_date=mtd_end_date,
        is_branch_manager=True,
    )


def _aggregate_teachers_from_settlements(
    db: Session,
    teacher_map: dict[int, User],
    settlements: list[Settlement],
) -> list[dict[str, Any]]:
    """Settlement commission_details 기반 원장 매출 집계."""
    all_order_nums: set[str] = set()
    for settlement in settlements:
        if not settlement.commission_details:
            continue
        try:
            for detail in json.loads(settlement.commission_details):
                ordernum = detail.get("ordernum")
                if ordernum:
                    all_order_nums.add(ordernum)
        except Exception:
            pass

    orders_map: dict[str, Order] = {}
    if all_order_nums:
        for order in db.query(Order).filter(Order.ordernum.in_(list(all_order_nums))).all():
            orders_map[order.ordernum] = order

    user_aggregates: dict[int, dict[str, Any]] = {}
    for uid, user_obj in teacher_map.items():
        user_aggregates[uid] = _empty_aggregate(
            uid,
            user_obj.name or "",
            user_obj.main_contact or "",
        )

    for settlement in settlements:
        uid = settlement.user_id
        if uid not in user_aggregates:
            continue
        agg = user_aggregates[uid]
        if not settlement.commission_details:
            continue
        try:
            for detail in json.loads(settlement.commission_details):
                if detail.get("commission", 0) == 0:
                    continue
                # 표 판매가/적립금 = 정산 상세 판매금액·(판매-결제)와 동일 기준
                payment_amount = int(detail.get("payment_amount", 0) or 0)
                actual_payment = int(detail.get("actual_payment", 0) or 0)
                if detail.get("points_used") is not None:
                    points_used = int(detail.get("points_used") or 0)
                else:
                    points_used = payment_amount - actual_payment
                agg["sell_price_total"] += payment_amount
                agg["used_reserve_total"] += points_used
                ordernum = detail.get("ordernum")
                if ordernum and ordernum in orders_map and ordernum not in agg["processed_orders"]:
                    order = orders_map[ordernum]
                    agg["delivery_total"] += int(getattr(order, "deli_price", 0) or 0)
                    agg["processed_orders"].add(ordernum)
                product_uid = detail.get("product_uid")
                quantity = detail.get("quantity", 0)
                if product_uid:
                    product = db.query(Product).filter(Product.uid == product_uid).first()
                    if product:
                        consumer_price = product.consumerprice or 0
                        if consumer_price == 0:
                            consumer_price = product.sellprice or 0
                        agg["consumer_price_total"] += int(consumer_price * quantity)
        except Exception:
            pass

    return list(user_aggregates.values())


def _format_status_rows(
    items: list[dict[str, Any]],
    sort_by: str,
    branch_manager_user_id: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if branch_manager_user_id is not None:
        by_user: dict[int, dict[str, Any]] = {}
        for item in items:
            uid = int(item["user_id"])
            if uid == branch_manager_user_id:
                item["is_branch_manager"] = True
            by_user[uid] = item
        items = list(by_user.values())

    if sort_by == "amount_asc":
        items.sort(key=lambda x: x["sell_price_total"] - x["used_reserve_total"])
    elif sort_by == "name_asc":
        items.sort(key=lambda x: x["name"])
    else:
        items.sort(key=lambda x: x["sell_price_total"] - x["used_reserve_total"], reverse=True)

    result_data: list[dict[str, Any]] = []
    total_consumer = total_sell = total_delivery = total_reserve = total_actual = 0

    for idx, agg in enumerate(items, 1):
        actual_payment = agg["sell_price_total"] - agg["used_reserve_total"]
        result_data.append({
            "no": idx,
            "user_id": agg["user_id"],
            "name": agg["name"],
            "phone": agg["phone"],
            "consumer_price_total": agg["consumer_price_total"],
            "sell_price_total": agg["sell_price_total"],
            "delivery_total": agg["delivery_total"],
            "used_reserve_total": agg["used_reserve_total"],
            "actual_payment_total": actual_payment,
            "is_branch_manager": bool(agg.get("is_branch_manager")),
        })
        total_consumer += agg["consumer_price_total"]
        total_sell += agg["sell_price_total"]
        total_delivery += agg["delivery_total"]
        total_reserve += agg["used_reserve_total"]
        total_actual += actual_payment

    summary = {
        "consumer_price_total": total_consumer,
        "sell_price_total": total_sell,
        "delivery_total": total_delivery,
        "used_reserve_total": total_reserve,
        "actual_payment_total": total_actual,
    }
    return result_data, summary


def _get_company_users(db: Session, company_id: int) -> tuple[User | None, list[User]]:
    branch_manager = (
        db.query(User)
        .filter(User.company_id == int(company_id), User.role_id == BRANCH_MANAGER_ROLE_ID)
        .order_by(User.user_id.asc())
        .first()
    )
    teachers = (
        db.query(User)
        .filter(User.company_id == int(company_id), User.role_id == TEACHER_ROLE_ID)
        .all()
    )
    if branch_manager:
        teachers = [t for t in teachers if t.user_id != branch_manager.user_id]
    return branch_manager, teachers


def get_settlement_status_data(
    db: Session,
    company_id: int,
    month: str | None = None,
    year: str | None = None,
    sort_by: str = "amount_desc",
) -> tuple[list[dict[str, Any]], dict[str, int] | None, int | None]:
    """소속 원장별 월매출 + 지사장 본인 매출 데이터 조회."""
    branch_manager, all_teachers = _get_company_users(db, company_id)
    branch_manager_user_id = int(branch_manager.user_id) if branch_manager else None

    if not all_teachers and not branch_manager:
        return [], None, None

    teacher_map = {t.user_id: t for t in all_teachers}
    teacher_ids = list(teacher_map.keys())

    settlements: list[Settlement] = []
    if teacher_ids:
        query = db.query(Settlement).filter(
            Settlement.user_id.in_(teacher_ids),
            Settlement.settlement_type == MONTHLY_SETTLEMENT_TYPE,
        )
        if month and month != "전체":
            year_val, mon_val = month.split("-")
            query = query.filter(
                extract("year", Settlement.settlement_date) == int(year_val),
                extract("month", Settlement.settlement_date) == int(mon_val),
            )
        elif year:
            query = query.filter(extract("year", Settlement.settlement_date) == int(year))
        settlements = query.all()

    items = _aggregate_teachers_from_settlements(db, teacher_map, settlements)
    if branch_manager:
        items.append(_aggregate_branch_manager_sales(db, branch_manager, month=month, year=year))

    result_data, summary = _format_status_rows(items, sort_by, branch_manager_user_id)
    return result_data, summary, branch_manager_user_id


def get_branch_yearly_actual_payment_total(
    db: Session,
    company_id: int,
    year: int,
) -> int:
    """지사 연도 누적 실결제총액 (소속 원장별 월매출 '누적 총액' 합계와 동일)."""
    sales_map, _ = get_all_branches_yearly_sales(db, year=year, company_ids=[int(company_id)])
    return int(sales_map.get(int(company_id), 0) or 0)


def _sum_actual_payment_from_settlements(settlements: list[Settlement]) -> int:
    """commission≠0 라인의 payment_amount - points_used 합 (주문/상품 조회 없이)."""
    sell_total = 0
    reserve_total = 0
    for settlement in settlements:
        if not settlement.commission_details:
            continue
        try:
            for detail in json.loads(settlement.commission_details):
                if detail.get("commission", 0) == 0:
                    continue
                payment_amount = int(detail.get("payment_amount", 0) or 0)
                actual_payment = int(detail.get("actual_payment", 0) or 0)
                if detail.get("points_used") is not None:
                    points_used = int(detail.get("points_used") or 0)
                else:
                    points_used = payment_amount - actual_payment
                sell_total += payment_amount
                reserve_total += points_used
        except Exception:
            continue
    return sell_total - reserve_total


def _batch_branch_manager_yearly_actuals(
    db: Session,
    managers: list[User],
    year: int,
) -> dict[int, int]:
    """지사장 본인 주문 연도 누적 실결제 (company_id → amount)."""
    if not managers:
        return {}

    login_to_company: dict[str, int] = {}
    for manager in managers:
        login_id = (manager.login_id or "").strip()
        if login_id and manager.company_id:
            login_to_company[login_id] = int(manager.company_id)
    if not login_to_company:
        return {}

    query = db.query(Order).filter(
        Order.member_id.in_(list(login_to_company.keys())),
        Order.order_status.in_(["Y", "P"]),
        Order.pay_status == "Y",
    )
    query = _apply_order_period_filter(query, month="전체", year=str(year))
    orders = query.all()
    if not orders:
        return {}

    order_nums = [o.ordernum for o in orders if o.ordernum]
    items_sell: dict[str, int] = defaultdict(int)
    if order_nums:
        for item in db.query(OrderItem).filter(OrderItem.ordernum.in_(order_nums)).all():
            items_sell[item.ordernum] += int(getattr(item, "sell_price", 0) or 0)

    by_company: dict[int, int] = defaultdict(int)
    for order in orders:
        login_id = (order.member_id or "").strip()
        company_id = login_to_company.get(login_id)
        if not company_id or not order.ordernum:
            continue
        sell = items_sell.get(order.ordernum, 0)
        reserve = int(getattr(order, "used_reserve", 0) or 0)
        by_company[company_id] += sell - reserve
    return dict(by_company)


def get_all_branches_yearly_sales(
    db: Session,
    year: int | None = None,
    company_ids: list[int] | None = None,
) -> tuple[dict[int, int], int]:
    """홈/계약종료용 지사별 연도 누적 실결제총액 (일괄 집계)."""
    from app.models import Company

    sales_year = year if year is not None else datetime.now(KST).year
    if company_ids is None:
        resolved_ids = [
            int(cid)
            for (cid,) in db.query(Company.company_id)
            .filter(
                Company.company_type.in_(["HQ", "BRANCH"]),
                Company.is_active.is_(True),
            )
            .all()
        ]
    else:
        resolved_ids = [int(cid) for cid in company_ids]

    branch_sales: dict[int, int] = {cid: 0 for cid in resolved_ids}
    if not resolved_ids:
        return branch_sales, sales_year

    users = (
        db.query(User)
        .filter(
            User.company_id.in_(resolved_ids),
            User.role_id.in_([TEACHER_ROLE_ID, BRANCH_MANAGER_ROLE_ID]),
        )
        .all()
    )
    teachers_by_company: dict[int, list[int]] = defaultdict(list)
    # 구 get_settlement_status_data와 동일: 지사당 지사장 1명(user_id 오름차순 최초)
    managers_by_company: dict[int, User] = {}
    teacher_ids: list[int] = []
    for user in users:
        cid = int(user.company_id) if user.company_id else None
        if cid is None:
            continue
        if user.role_id == TEACHER_ROLE_ID:
            teachers_by_company[cid].append(int(user.user_id))
            teacher_ids.append(int(user.user_id))
        elif user.role_id == BRANCH_MANAGER_ROLE_ID:
            prev = managers_by_company.get(cid)
            if prev is None or int(user.user_id) < int(prev.user_id):
                managers_by_company[cid] = user
    managers = list(managers_by_company.values())

    settlements_by_user: dict[int, list[Settlement]] = defaultdict(list)
    if teacher_ids:
        settlements = (
            db.query(Settlement)
            .filter(
                Settlement.user_id.in_(teacher_ids),
                Settlement.settlement_type == MONTHLY_SETTLEMENT_TYPE,
                extract("year", Settlement.settlement_date) == int(sales_year),
            )
            .all()
        )
        for settlement in settlements:
            settlements_by_user[int(settlement.user_id)].append(settlement)

    for cid, uids in teachers_by_company.items():
        company_settlements: list[Settlement] = []
        for uid in uids:
            company_settlements.extend(settlements_by_user.get(uid, []))
        branch_sales[cid] = _sum_actual_payment_from_settlements(company_settlements)

    bm_actuals = _batch_branch_manager_yearly_actuals(db, managers, sales_year)
    for cid, amount in bm_actuals.items():
        branch_sales[cid] = branch_sales.get(cid, 0) + int(amount)

    return branch_sales, sales_year


def _mtd_snapshot_base_filter(
    db: Session,
    company_id: int,
    teacher_ids: list[int],
    year: int,
    month: int,
):
    query = db.query(Settlement).filter(
        Settlement.company_id == int(company_id),
        Settlement.settlement_type == MTD_SETTLEMENT_TYPE,
        extract("year", Settlement.settlement_date) == year,
        extract("month", Settlement.settlement_date) == month,
    )
    if teacher_ids:
        query = query.filter(Settlement.user_id.in_(teacher_ids))
    return query


def _resolve_mtd_snapshot_date(
    db: Session,
    company_id: int,
    teacher_ids: list[int],
    requested_date: date | None,
    reference_date: date,
) -> date | None:
    """회사 MTD 스냅샷 기준일 결정 (요청일 또는 당월 최신)."""
    target_year = requested_date.year if requested_date else reference_date.year
    target_month = requested_date.month if requested_date else reference_date.month

    if requested_date:
        exists = (
            _mtd_snapshot_base_filter(db, company_id, teacher_ids, target_year, target_month)
            .filter(
                extract("day", Settlement.settlement_date) == requested_date.day,
            )
            .first()
        )
        return requested_date if exists else None

    latest = (
        _mtd_snapshot_base_filter(db, company_id, teacher_ids, target_year, target_month)
        .with_entities(func.max(Settlement.settlement_date))
        .scalar()
    )
    if not latest:
        return None
    return latest.date() if hasattr(latest, "date") else latest


def get_daily_sales_status_data(
    db: Session,
    company_id: int,
    snapshot_date: date | None = None,
    sort_by: str = "amount_desc",
    reference_date: date | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int] | None, dict[str, Any]]:
    """소속 원장별 이번 달 누적 매출 (MTD 스냅샷 + 지사장 본인 주문)."""
    branch_manager, teachers = _get_company_users(db, company_id)

    meta: dict[str, Any] = {
        "period_start": None,
        "snapshot_date": None,
        "has_snapshot": False,
        "branch_manager_user_id": None,
    }

    branch_manager_user_id = int(branch_manager.user_id) if branch_manager else None

    if not teachers and not branch_manager:
        return [], None, meta

    teacher_map = {t.user_id: t for t in teachers}
    teacher_ids = list(teacher_map.keys())

    ref = reference_date or date.today()
    resolved_snapshot = _resolve_mtd_snapshot_date(
        db, company_id, teacher_ids, snapshot_date, ref
    )
    if resolved_snapshot:
        meta["snapshot_date"] = resolved_snapshot.isoformat()
        meta["period_start"] = resolved_snapshot.replace(day=1).isoformat()
        meta["has_snapshot"] = True

        settlements = (
            db.query(Settlement)
            .filter(
                Settlement.company_id == int(company_id),
                Settlement.user_id.in_(teacher_ids),
                Settlement.settlement_type == MTD_SETTLEMENT_TYPE,
                extract("year", Settlement.settlement_date) == resolved_snapshot.year,
                extract("month", Settlement.settlement_date) == resolved_snapshot.month,
                extract("day", Settlement.settlement_date) == resolved_snapshot.day,
            )
            .all()
        )
        items = _aggregate_teachers_from_settlements(db, teacher_map, settlements)
    else:
        items = [
            _empty_aggregate(t.user_id, t.name or "", t.main_contact or "")
            for t in teachers
        ]

    if branch_manager and resolved_snapshot:
        items.append(
            _aggregate_branch_manager_sales(
                db,
                branch_manager,
                mtd_end_date=resolved_snapshot,
            )
        )
    elif branch_manager:
        items.append(_empty_aggregate(
            int(branch_manager.user_id),
            branch_manager.name or "",
            branch_manager.main_contact or "",
        ))
        items[-1]["is_branch_manager"] = True

    meta["branch_manager_user_id"] = branch_manager_user_id
    result_data, summary = _format_status_rows(items, sort_by, branch_manager_user_id)
    return result_data, summary, meta


def _list_mtd_snapshot_dates(
    db: Session,
    company_id: int,
    teacher_ids: list[int],
    year: int,
    month: int,
    *,
    max_date: date | None = None,
) -> list[date]:
    """해당 월 MTD 스냅샷이 존재하는 날짜 목록 (오름차순)."""
    if not teacher_ids:
        return []

    rows = (
        _mtd_snapshot_base_filter(db, company_id, teacher_ids, year, month)
        .with_entities(Settlement.settlement_date)
        .distinct()
        .order_by(Settlement.settlement_date.asc())
        .all()
    )
    dates: list[date] = []
    for row in rows:
        raw = row[0]
        snap = raw.date() if hasattr(raw, "date") else raw
        if max_date and snap > max_date:
            continue
        dates.append(snap)
    return dates


def get_available_mtd_periods(
    db: Session,
    company_id: int,
    *,
    reference_date: date | None = None,
) -> tuple[list[int], dict[str, list[str]]]:
    """MTD 스냅샷이 있는 년도·월 목록 (당월은 스냅샷 없어도 포함)."""
    ref = reference_date or date.today()
    branch_manager, teachers = _get_company_users(db, company_id)
    teacher_ids = [int(t.user_id) for t in teachers]

    months: set[str] = {f"{ref.year}-{ref.month:02d}"}
    if teacher_ids:
        rows = (
            db.query(Settlement.settlement_date)
            .filter(
                Settlement.company_id == int(company_id),
                Settlement.user_id.in_(teacher_ids),
                Settlement.settlement_type == MTD_SETTLEMENT_TYPE,
                Settlement.settlement_date.isnot(None),
            )
            .distinct()
            .all()
        )
        for row in rows:
            raw = row[0]
            snap = raw.date() if hasattr(raw, "date") else raw
            months.add(f"{snap.year}-{snap.month:02d}")

    months_by_year: dict[str, list[str]] = {}
    for month_value in sorted(months, reverse=True):
        year = month_value.split("-")[0]
        months_by_year.setdefault(year, []).append(month_value)

    year_list = sorted(months_by_year.keys(), reverse=True, key=int)
    return year_list, months_by_year


def get_mtd_filter_years(
    db: Session,
    company_id: int,
    *,
    reference_date: date | None = None,
) -> list[int]:
    """필터용 연도 목록 (데이터 최초 연도 ~ 현재 연도, 내림차순)."""
    ref = reference_date or date.today()
    _, months_by_year = get_available_mtd_periods(db, company_id, reference_date=ref)
    if months_by_year:
        min_year = min(int(year_key) for year_key in months_by_year)
    else:
        min_year = ref.year
    return list(range(ref.year, min_year - 1, -1))


def get_daily_sales_month_overview(
    db: Session,
    company_id: int,
    year: int,
    month: int,
    *,
    reference_date: date | None = None,
    sort_by: str = "amount_desc",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """한 달 페이지용 일별 누적 매출 행 목록."""
    ref = reference_date or date.today()
    branch_manager, teachers = _get_company_users(db, company_id)
    teacher_ids = [int(t.user_id) for t in teachers]

    last_day = calendar.monthrange(year, month)[1]
    month_label = f"{month}/1 ~ {month}/{last_day}"
    meta: dict[str, Any] = {
        "year": year,
        "month": month,
        "month_label": month_label,
        "period_start": date(year, month, 1).isoformat(),
        "period_end": date(year, month, last_day).isoformat(),
        "has_any_snapshot": False,
    }

    if not teachers and not branch_manager:
        return [], meta

    max_date = ref if (year, month) == (ref.year, ref.month) else date(year, month, last_day)
    snapshot_dates = _list_mtd_snapshot_dates(
        db, company_id, teacher_ids, year, month, max_date=max_date
    )
    if not snapshot_dates:
        return [], meta

    meta["has_any_snapshot"] = True
    daily_rows: list[dict[str, Any]] = []
    for snap_date in snapshot_dates:
        _, summary, day_meta = get_daily_sales_status_data(
            db,
            company_id,
            snap_date,
            sort_by,
            reference_date=ref,
        )
        if not day_meta.get("has_snapshot") or not summary:
            continue
        daily_rows.append({
            "day": snap_date.day,
            "date": snap_date.isoformat(),
            "day_label": f"{month}/{snap_date.day}",
            "period_label": f"{month}/1 ~ {month}/{snap_date.day}",
            "summary": summary,
        })

    return daily_rows, meta
