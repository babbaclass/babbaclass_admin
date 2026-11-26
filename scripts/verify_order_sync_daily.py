"""
최근 N일 주문: MakeShop REST 조회 vs DB 일별 대조 리포트.

프로젝트 루트:
  .venv/bin/python scripts/verify_order_sync_daily.py
  .venv/bin/python scripts/verify_order_sync_daily.py --days 30
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))
os.environ.setdefault("MAKESHOP_USE_REST", "true")
os.environ["MAKESHOP_DUAL_COMPARE"] = "false"
os.environ["MAKESHOP_REST_CHAT_NOTIFY"] = "false"


def _day_range(d: datetime) -> Tuple[str, str]:
    start = d.replace(hour=0, minute=0, second=0, microsecond=0)
    end = d.replace(hour=23, minute=59, second=59, microsecond=0)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")


def _norm_price(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(int(float(str(value).replace(",", ""))))
    except (TypeError, ValueError):
        return str(value)


def fetch_api_orders(
    client,
    win_from: str,
    win_to: str,
    limit: int = 1000,
) -> Dict[str, Dict[str, Any]]:
    from app.services.makeshop_rest_client import MakeshopRestAPIError
    from app.services.makeshop_sync_service import should_fetch_next_order_page

    page = 1
    fetched = 0
    orders: Dict[str, Dict[str, Any]] = {}
    while True:
        payload = None
        for attempt in range(6):
            try:
                payload = client.get_orders_v2_legacy(
                    inquiry_time_from=win_from,
                    inquiry_time_to=win_to,
                    page=page,
                    limit=limit,
                )
                break
            except MakeshopRestAPIError as exc:
                msg = str(exc).lower()
                if "429" in msg or "too_many" in msg:
                    wait = min(60, 2 ** attempt * 2)
                    print(f"  [rate-limit] wait {wait}s (page={page} attempt={attempt+1})")
                    time.sleep(wait)
                    continue
                raise
        if payload is None:
            raise RuntimeError(f"order fetch failed after retries: {win_from} ~ {win_to}")

        batch = payload.get("list") or {}
        if not isinstance(batch, dict) or not batch:
            break
        orders.update(batch)
        page_count = len(batch)
        fetched += page_count
        try:
            total = int(payload.get("totalCount") or 0)
        except (TypeError, ValueError):
            total = 0
        if not should_fetch_next_order_page(
            page_count=page_count,
            limit=limit,
            fetched_in_window=fetched,
            total_count_api=total,
        ):
            break
        page += 1
        if page > 100:
            break
        time.sleep(0.35)
    return orders


def summarize_day(day: datetime, db, client) -> Dict[str, Any]:
    from app.models import Order, OrderItem

    win_from, win_to = _day_range(day)
    day_prefix = day.strftime("%Y-%m-%d")
    api_orders = fetch_api_orders(client, win_from, win_to)

    api_snap: Dict[str, Dict[str, Any]] = {}
    for onum, wrap in api_orders.items():
        if not isinstance(wrap, dict):
            continue
        od = wrap.get("order") or {}
        pay = wrap.get("payment") or {}
        num = str(od.get("ordernum") or onum)
        product = wrap.get("product")
        api_snap[num] = {
            "order_status": str(od.get("order_status") or ""),
            "pay_status": str(pay.get("pay_status") or ""),
            "pay_price": _norm_price(od.get("pay_price")),
            "order_date": str(od.get("order_date") or "")[:19],
            "item_count": len(product) if isinstance(product, dict) else 0,
        }

    api_nums: Set[str] = set(api_snap)
    db_rows = db.query(Order).filter(Order.order_date.like(f"{day_prefix}%")).all()
    db_by_num = {str(r.ordernum): r for r in db_rows if r.ordernum}

    missing = sorted(api_nums - set(db_by_num))
    extra = sorted(set(db_by_num) - api_nums)

    field_mismatch: List[Tuple[str, List[str]]] = []
    item_short: List[Tuple[str, int, int]] = []
    # pay_price api=0 keep-db is expected with `or` upsert — track separately
    pay0_kept: List[str] = []

    for num in sorted(api_nums & set(db_by_num)):
        row = db_by_num[num]
        snap = api_snap[num]
        diffs: List[str] = []
        if str(row.order_status or "") != snap["order_status"]:
            diffs.append(
                f"order_status api={snap['order_status']!r} db={row.order_status!r}"
            )
        if str(row.pay_status or "") != snap["pay_status"]:
            diffs.append(f"pay_status api={snap['pay_status']!r} db={row.pay_status!r}")

        db_price = _norm_price(row.pay_price)
        if snap["pay_price"] != db_price:
            if snap["pay_price"] in {"0", ""} and db_price not in {"0", ""}:
                pay0_kept.append(num)
            else:
                diffs.append(f"pay_price api={snap['pay_price']!r} db={db_price!r}")

        db_date = str(row.order_date or "")[:19]
        if snap["order_date"] and db_date != snap["order_date"]:
            diffs.append(f"order_date api={snap['order_date']!r} db={db_date!r}")

        if diffs:
            field_mismatch.append((num, diffs))

        if snap["item_count"]:
            db_items = db.query(OrderItem).filter(OrderItem.ordernum == num).count()
            if db_items < snap["item_count"]:
                item_short.append((num, snap["item_count"], db_items))

    # presence OK if no missing; field/item issues listed separately
    presence_ok = len(missing) == 0
    strict_ok = presence_ok and not field_mismatch and not item_short

    return {
        "day": day_prefix,
        "api": len(api_nums),
        "db": len(db_by_num),
        "matched": len(api_nums & set(db_by_num)),
        "missing": missing,
        "extra": extra,
        "field_mismatch": field_mismatch,
        "item_short": item_short,
        "pay0_kept": pay0_kept,
        "presence_ok": presence_ok,
        "strict_ok": strict_ok,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="주문 REST vs DB 일별 대조")
    parser.add_argument("--days", type=int, default=30, help="최근 N일 (오늘 포함)")
    args = parser.parse_args()

    from app.database import SessionLocal
    from app.services.makeshop_rest_client import MakeshopRestClient

    now = datetime.now(ZoneInfo("Asia/Seoul"))
    days = max(1, args.days)
    print(f"[info] order sync daily verify days={days} asof={now.isoformat()}")
    print("[info] compare: REST order/2 vs DB orders/order_items")
    print()

    client = MakeshopRestClient()
    client.issue_access_token(force_refresh=True)

    db = SessionLocal()
    rows: List[Dict[str, Any]] = []
    try:
        for i in range(days):
            day = (now - timedelta(days=i)).replace(tzinfo=None)
            day_local = datetime(day.year, day.month, day.day)
            print(f"[run] {day_local.date()} ...", flush=True)
            rows.append(summarize_day(day_local, db, client))
            time.sleep(0.6)
    finally:
        db.close()

    rows_sorted = sorted(rows, key=lambda r: r["day"])

    print()
    print("=" * 88)
    print(f"{'day':12} {'verdict':8} {'api':>5} {'db':>5} {'miss':>5} {'field':>5} {'items':>5} {'pay0':>5}")
    print("-" * 88)

    miss_days = 0
    field_days = 0
    item_days = 0
    total_api = total_miss = total_field = total_item = 0

    for r in rows_sorted:
        if not r["presence_ok"]:
            verdict = "MISS"
            miss_days += 1
        elif r["field_mismatch"] or r["item_short"]:
            verdict = "CHECK"
            if r["field_mismatch"]:
                field_days += 1
            if r["item_short"]:
                item_days += 1
        else:
            verdict = "PASS"

        total_api += r["api"]
        total_miss += len(r["missing"])
        total_field += len(r["field_mismatch"])
        total_item += len(r["item_short"])

        print(
            f"{r['day']:12} {verdict:8} {r['api']:5d} {r['db']:5d} "
            f"{len(r['missing']):5d} {len(r['field_mismatch']):5d} "
            f"{len(r['item_short']):5d} {len(r['pay0_kept']):5d}"
        )

    print("-" * 88)
    print(
        f"{'TOTAL':12} {'':8} {total_api:5d} {'':5} "
        f"{total_miss:5d} {total_field:5d} {total_item:5d}"
    )
    print()

    # details
    any_detail = False
    for r in rows_sorted:
        if r["missing"] or r["field_mismatch"] or r["item_short"]:
            if not any_detail:
                print("===== DETAILS =====")
                any_detail = True
            print(f"\n[{r['day']}]")
            if r["missing"]:
                print(f"  missing in DB ({len(r['missing'])}): {', '.join(r['missing'][:20])}")
                if len(r["missing"]) > 20:
                    print(f"  ... +{len(r['missing']) - 20} more")
            for num, diffs in r["field_mismatch"][:10]:
                print(f"  field {num}: {'; '.join(diffs)}")
            if len(r["field_mismatch"]) > 10:
                print(f"  ... +{len(r['field_mismatch']) - 10} field diffs")
            for num, a, b in r["item_short"][:10]:
                print(f"  items {num}: api={a} db={b}")

    print()
    print("===== SUMMARY =====")
    print(f"days: {days}")
    print(f"PASS days (presence+fields+items): {sum(1 for r in rows if r['strict_ok'])}")
    print(f"MISS days (API order absent in DB): {miss_days}")
    print(f"CHECK days (present but field/item diff): {sum(1 for r in rows if r['presence_ok'] and not r['strict_ok'])}")
    print(f"API orders total: {total_api}")
    print(f"Missing ordernums total: {total_miss}")
    print(f"Field mismatches total: {total_field}")
    print(f"OrderItem shortfalls total: {total_item}")
    print(
        "Note: pay0_kept = API pay_price 0 but DB kept previous (sync uses `or` upsert); not counted as MISS."
    )

    # exit non-zero only on missing orders
    return 1 if total_miss else 0


if __name__ == "__main__":
    raise SystemExit(main())
