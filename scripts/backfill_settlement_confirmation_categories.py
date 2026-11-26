"""
정산서 확인 기록 confirmation_category(지급/이월) 일괄 보정.

6/10 등 지급 기간 내 확인했으나 이월로 분류된 기록을 수정합니다.

사용 예:
  # 전체 미분류·오분류 보정 (dry-run)
  python scripts/backfill_settlement_confirmation_categories.py

  # 실제 반영
  python scripts/backfill_settlement_confirmation_categories.py --apply

  # 2026-06-10 KST 확인분만 보정
  python scripts/backfill_settlement_confirmation_categories.py --apply --date 2026-06-10
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.monthly_settlement_summary_service import (
    backfill_confirmation_categories,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> int:
    parser = argparse.ArgumentParser(description="정산서 확인 지급/이월 일괄 보정")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="DB에 실제 반영 (없으면 dry-run)",
    )
    parser.add_argument(
        "--date",
        type=parse_date,
        default=None,
        help="KST 기준 확인일만 처리 (예: 2026-06-10)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="변경 대상 상세 로그 출력",
    )
    args = parser.parse_args()

    dry_run = not args.apply
    db = SessionLocal()
    try:
        stats = backfill_confirmation_categories(
            db,
            dry_run=dry_run,
            only_kst_date=args.date,
        )
    finally:
        db.close()

    mode = "DRY-RUN" if dry_run else "APPLIED"
    date_label = args.date.isoformat() if args.date else "전체"
    logger.info("[%s] 대상=%s, total=%s, 지급으로=%s, 이월로=%s, 변경없음=%s",
                mode, date_label, stats["total"],
                stats["updated_to_payment"], stats["updated_to_carryover"],
                stats["unchanged"])
    if args.verbose and stats.get("details"):
        for row in stats["details"]:
            logger.info(
                "  user_id=%s period=%s confirmed_kst=%s %s -> %s",
                row["user_id"], row["period"], row["confirmed_kst"],
                row["old"], row["new"],
            )

    if dry_run and stats["updated_to_payment"] + stats["updated_to_carryover"] > 0:
        logger.info("실제 반영: python scripts/backfill_settlement_confirmation_categories.py --apply%s",
                    f" --date {args.date.isoformat()}" if args.date else "")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
