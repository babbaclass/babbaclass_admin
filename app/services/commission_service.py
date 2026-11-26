from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import CommissionType, CommissionRateWindow

# Contract:
# - Input: type_code (str), target_date (date/datetime)
# - Output: Decimal percentage (0..100) as Decimal('5.00')
# - If multiple windows match, choose by: priority desc, start_year desc, start_month desc
# - If none, return Decimal('0.00') by default (can switch to raising ValueError)

def get_commission_rate(db: Session, type_code: str, target_date: date | datetime, amount: int = 0) -> Decimal:
    if isinstance(target_date, datetime):
        y = target_date.year
        m = target_date.month
    else:
        y = target_date.year
        m = target_date.month

    # Resolve type id
    ctype = db.query(CommissionType).filter(CommissionType.code == type_code).first()
    if not ctype:
        return Decimal('0.00')

    # Build base filter for window include check
    # (start_year, start_month) <= (y,m) and (end_year,end_month) is NULL or >= (y,m)
    # Using numeric comparison for pairs
    pair_cur = y * 100 + m
    pair_start = (CommissionRateWindow.start_year * 100 + CommissionRateWindow.start_month)
    pair_end = (CommissionRateWindow.end_year * 100 + CommissionRateWindow.end_month)

    q = db.query(CommissionRateWindow).filter(
        CommissionRateWindow.commission_type_id == ctype.commission_type_id,
    CommissionRateWindow.is_active.is_(True),
        pair_start <= pair_cur,
        or_(CommissionRateWindow.end_year.is_(None), pair_end >= pair_cur),
    )

    # Amount tier filter: amount within [min_amount, max_amount or infinity]
    if amount < 0:
        amount = 0
    q = q.filter(
        CommissionRateWindow.min_amount <= amount,
        or_(CommissionRateWindow.max_amount.is_(None), CommissionRateWindow.max_amount >= amount)
    )

    q = q.order_by(
        CommissionRateWindow.priority.desc(),
        CommissionRateWindow.start_year.desc(),
        CommissionRateWindow.start_month.desc(),
        CommissionRateWindow.min_amount.desc(),  # higher min_amount (more specific) last? choose desc to prioritize closest floor
        CommissionRateWindow.id.desc(),
    )

    row = q.first()
    if not row:
        return Decimal('0.00')
    rate_value = getattr(row, 'rate_percent', None)
    if rate_value is None:
        return Decimal('0.00')
    # Ensure Decimal type
    return Decimal(str(rate_value))
