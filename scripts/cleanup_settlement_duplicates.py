"""
Settlement 중복(mtd 스냅샷) 정리 + total_commission 백필.

1) monthly가 있는 user/company/year/month 의 mtd 행 삭제
2) 월내 mtd 일별 이력은 유지 (소속 원장별 일별 매출용)
3) monthly 행의 total_commission / net_settlement_amount 를 commission_details 기준으로 재계산

프로젝트 루트에서 실행:
    .venv/bin/python scripts/cleanup_settlement_duplicates.py
    .venv/bin/python scripts/cleanup_settlement_duplicates.py --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv
from sqlalchemy import text


def _commission_from_details(raw: str | None) -> int:
    if not raw:
        return 0
    try:
        details = json.loads(raw)
    except Exception:
        return 0
    total = 0
    for detail in details:
        commission = int(detail.get("commission") or 0)
        if commission:
            total += commission
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup duplicate settlement snapshots")
    parser.add_argument("--apply", action="store_true", help="실제로 DB에 반영 (기본은 dry-run)")
    args = parser.parse_args()

    load_dotenv(os.path.join(ROOT_DIR, ".env"))
    from app.database import SessionLocal
    from app.models import Settlement

    dry_run = not args.apply
    print(f"[info] mode={'APPLY' if args.apply else 'DRY-RUN'}")

    db = SessionLocal()
    try:
        # 1) monthly가 있는 기간의 mtd 삭제
        mtd_with_monthly = db.execute(text("""
            SELECT mtd.settlement_id
            FROM settlements mtd
            WHERE mtd.settlement_type = 'mtd'
              AND EXISTS (
                SELECT 1
                FROM settlements mon
                WHERE mon.user_id = mtd.user_id
                  AND mon.company_id = mtd.company_id
                  AND mon.settlement_type = 'monthly'
                  AND YEAR(mon.settlement_date) = YEAR(mtd.settlement_date)
                  AND MONTH(mon.settlement_date) = MONTH(mtd.settlement_date)
              )
        """)).fetchall()
        mtd_ids = [int(row[0]) for row in mtd_with_monthly]
        print(f"[info] mtd rows superseded by monthly: {len(mtd_ids)}")

        # 2) 월내 mtd 일별 이력은 유지한다.
        #    (소속 원장별 일별 매출 화면이 날짜별 스냅샷을 사용하므로
        #     최신 1건만 남기면 캘린더가 끊긴다.)
        print("[info] skip deleting intra-month mtd history (daily sales needs each day)")

        delete_ids = sorted(set(mtd_ids))
        print(f"[info] total mtd rows to delete (superseded by monthly only): {len(delete_ids)}")

        # 3) monthly total_commission 백필
        monthly_rows = db.query(Settlement).filter(Settlement.settlement_type == "monthly").all()
        backfill_count = 0
        mismatch_samples = []
        for row in monthly_rows:
            commission = _commission_from_details(row.commission_details)
            tax = int(commission * 0.03)
            local = int(tax * 0.10)
            net = commission - tax - local
            changed = (
                int(row.total_commission or 0) != commission
                or int(row.net_settlement_amount or 0) != net
                or int(row.deducted_tax or 0) != tax
                or int(row.deducted_local_tax or 0) != local
            )
            if not changed:
                continue
            backfill_count += 1
            if len(mismatch_samples) < 5:
                mismatch_samples.append({
                    "settlement_id": row.settlement_id,
                    "user_id": row.user_id,
                    "old_total": row.total_commission,
                    "new_total": commission,
                    "old_net": row.net_settlement_amount,
                    "new_net": net,
                })
            if not dry_run:
                row.total_commission = commission
                row.deducted_tax = tax
                row.deducted_local_tax = local
                row.net_settlement_amount = net
                db.add(row)

        print(f"[info] monthly rows needing total_commission/net backfill: {backfill_count}")
        for sample in mismatch_samples:
            print(f"[sample] {sample}")

        if dry_run:
            print("[info] dry-run complete. Re-run with --apply to persist.")
            return 0

        if delete_ids:
            deleted = (
                db.query(Settlement)
                .filter(Settlement.settlement_id.in_(delete_ids))
                .delete(synchronize_session=False)
            )
            print(f"[info] deleted mtd rows: {deleted}")

        db.commit()
        print("[ok] cleanup applied")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[fail] {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
