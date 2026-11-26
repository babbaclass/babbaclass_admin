"""
Seed script: insert BASCLE dynamic commission rate windows

Rules to insert/upsert:
- Default 25%: no conditions (applies when no higher-priority window matches)
- 27%: min_teachers >= 10 AND min_monthly_sales >= 1,000,000
- 30%: min_teachers >= 20 AND min_monthly_sales >= 3,000,000

Priority: higher min thresholds get higher priority (30% > 27% > default)

Run this script from project root (inside virtualenv or container):
    python scripts/seed_bascle_rates.py

Note: If your environment uses a remote DB (Cloud SQL), run inside environment that has DB connectivity
(e.g., inside the running `babba-local` container) or set appropriate env vars before running.
"""

from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import CommissionType, CommissionRateWindow
from sqlalchemy import and_
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upsert_window(db, commission_type_id, start_year, start_month, rate_percent,
                  min_teachers=None, max_teachers=None, min_amount=None, max_amount=None, priority=0, role_id=2, description=None):
    """Find an existing window with same keys and update, else insert new."""
    # match on commission_type_id + start_year + start_month + min_teachers + max_teachers + min_amount + max_amount + role_id
    q = db.query(CommissionRateWindow).filter(
        CommissionRateWindow.commission_type_id == commission_type_id,
        CommissionRateWindow.start_year == start_year,
        CommissionRateWindow.start_month == start_month,
        CommissionRateWindow.role_id == role_id,
    )

    # allow NULLs: match when both are NULL or both equal
    if min_teachers is None:
        q = q.filter(CommissionRateWindow.min_teachers.is_(None))
    else:
        q = q.filter(CommissionRateWindow.min_teachers == min_teachers)

    if max_teachers is None:
        q = q.filter(CommissionRateWindow.max_teachers.is_(None))
    else:
        q = q.filter(CommissionRateWindow.max_teachers == max_teachers)

    if min_amount is None:
        q = q.filter(CommissionRateWindow.min_amount.is_(None))
    else:
        q = q.filter(CommissionRateWindow.min_amount == min_amount)

    if max_amount is None:
        q = q.filter(CommissionRateWindow.max_amount.is_(None))
    else:
        q = q.filter(CommissionRateWindow.max_amount == max_amount)

    existing = q.first()
    if existing:
        existing.rate_percent = rate_percent
        existing.priority = priority
        existing.is_active = True
        existing.description = description
        existing.updated_at = datetime.now()
        db.add(existing)
        logger.info(f"Updated existing CommissionRateWindow id={existing.id} rate={rate_percent}%")
        return existing
    else:
        new = CommissionRateWindow(
            commission_type_id=commission_type_id,
            start_year=start_year,
            start_month=start_month,
            end_year=None,
            end_month=None,
            rate_percent=rate_percent,
            min_amount=min_amount or 0,
            max_amount=max_amount,
            company_id=None,
            priority=priority,
            is_active=True,
            min_teachers=min_teachers,
            max_teachers=max_teachers,
            min_monthly_sales=None,
            role_id=role_id,
            description=description
        )
        db.add(new)
        db.flush()
        logger.info(f"Inserted CommissionRateWindow id={new.id} rate={rate_percent}%")
        return new


def main():
    db = SessionLocal()
    try:
        bascle = db.query(CommissionType).filter(CommissionType.code == 'BASCLE').first()
        if not bascle:
            logger.error("CommissionType 'BASCLE' not found. Create BASCLE commission type first.")
            return 1

        commission_type_id = bascle.commission_type_id
        now = datetime.now()
        # use wide start to be effective
        start_year = now.year
        start_month = 1

        # 30%: 20 < teachers_count < unlimited AND 3,000,000 < monthly_sales < unlimited
        upsert_window(
            db,
            commission_type_id=commission_type_id,
            start_year=start_year,
            start_month=start_month,
            rate_percent=30.00,
            min_teachers=20,
            max_teachers=None,
            min_amount=3000000,
            max_amount=None,
            priority=20,
            role_id=2,
            description='30%: 20 < 원장수 AND 3,000,000 < 월매출'
        )

        # 27%: 10 < teachers_count < 20 AND 1,000,000 < monthly_sales < 3,000,000
        upsert_window(
            db,
            commission_type_id=commission_type_id,
            start_year=start_year,
            start_month=start_month,
            rate_percent=27.00,
            min_teachers=10,
            max_teachers=20,
            min_amount=1000000,
            max_amount=3000000,
            priority=10,
            role_id=2,
            description='27%: 10 < 원장수 < 20 AND 1,000,000 < 월매출 < 3,000,000'
        )

        # default 25%: no conditions, lowest priority
        upsert_window(
            db,
            commission_type_id=commission_type_id,
            start_year=start_year,
            start_month=start_month,
            rate_percent=25.00,
            min_teachers=None,
            max_teachers=None,
            min_amount=None,
            max_amount=None,
            priority=0,
            role_id=2,
            description='Default 25% (기본값)'
        )

        db.commit()
        logger.info("BASCLE commission rate windows seeded/updated successfully.")
        return 0
    except Exception as e:
        logger.exception("Failed to seed BASCLE rates: %s", e)
        db.rollback()
        return 2
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main())
