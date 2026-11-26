"""Order 테이블 공통 조회 조건."""
from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_

from app.models import Order

COMPLETED_ORDER_STATUSES = ("Y", "P")


def order_date_in_period_filters(start: date, end_exclusive: date):
    """order_date가 YYYY-MM-DD 또는 YYYYMMDD... 형식 모두 지원."""
    start_dash = start.strftime("%Y-%m-%d")
    end_dash = end_exclusive.strftime("%Y-%m-%d")
    start_compact = start.strftime("%Y%m%d")
    end_compact = end_exclusive.strftime("%Y%m%d")
    return or_(
        and_(Order.order_date >= start_dash, Order.order_date < end_dash),
        and_(Order.order_date >= start_compact, Order.order_date < end_compact),
    )
