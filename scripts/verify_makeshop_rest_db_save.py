"""
신규 Open API(REST) → legacy 어댑터 → DB upsert 소량 검증.

Docs: https://developer.makeshop.co.kr/docs/api/order/주문

프로젝트 루트:
  .venv/bin/python scripts/verify_makeshop_rest_db_save.py
  .venv/bin/python scripts/verify_makeshop_rest_db_save.py --limit 3 --days 3
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(ROOT_DIR, ".env"))
os.environ["MAKESHOP_USE_REST"] = "true"


def _safe_string(value: Any):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _safe_int(value: Any):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return None


def _parse_quantity(value: Any) -> int:
    if isinstance(value, str):
        if value.lower() == "unlimited":
            return -1
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    if isinstance(value, int):
        return value
    return 0


def _check(label: str, expected: Any, actual: Any, *, allow_empty_api: bool = False) -> Tuple[bool, str]:
    """allow_empty_api: sync가 `or existing` 로 유지하는 빈 API 필드는 통과."""
    exp = "" if expected is None else str(expected)
    act = "" if actual is None else str(actual)
    if allow_empty_api and exp == "":
        return True, f"SKIP {label}: api empty (sync keeps existing db={act!r})"
    ok = exp == act
    return ok, f"{'OK' if ok else 'DIFF'} {label}: api={exp!r} db={act!r}"


def verify_products(db, limit: int) -> List[str]:
    from app.models import Product
    from app.services.makeshop_api_gateway import fetch_products_page

    lines: List[str] = []
    payload = fetch_products_page(page=1, limit=limit, db=db)
    products = payload.get("list") or []
    lines.append(f"[products] return_code={payload.get('return_code')} fetched={len(products)}")

    ok_all = True
    for product_data in products[:limit]:
        product_id = product_data.get("uid")
        if not product_id:
            continue
        db_product = db.query(Product).filter(Product.uid == product_id).first()
        if db_product:
            db_product.product_name = _safe_string(product_data.get("product_name")) or db_product.product_name
            db_product.sellprice = _safe_int(product_data.get("sellprice")) or db_product.sellprice
            db_product.status = _safe_string(product_data.get("status")) or db_product.status
            db_product.quantity = _parse_quantity(product_data.get("quantity", 0))
            db_product.cate1 = _safe_string(product_data.get("cate1")) or db_product.cate1
            db_product.display = _safe_string(product_data.get("display")) or db_product.display
            action = "updated"
        else:
            db_product = Product(
                uid=product_id,
                product_name=_safe_string(product_data.get("product_name", "")) or "",
                sellprice=_safe_int(product_data.get("sellprice")) or 0,
                quantity=_parse_quantity(product_data.get("quantity", 0)),
                status=_safe_string(product_data.get("status", "active")),
                cate1=_safe_string(product_data.get("cate1")),
                display=_safe_string(product_data.get("display")),
            )
            db.add(db_product)
            action = "created"
        db.commit()
        db.refresh(db_product)

        checks = [
            _check("product_name", product_data.get("product_name"), db_product.product_name),
            _check("sellprice", _safe_int(product_data.get("sellprice")), db_product.sellprice),
            # REST 상품에 status 없음(display/sell_accept 사용). sync는 빈 값이면 기존 유지.
            _check("status", product_data.get("status"), db_product.status, allow_empty_api=True),
            _check("display", product_data.get("display"), getattr(db_product, "display", None), allow_empty_api=True),
        ]
        for ok, msg in checks:
            ok_all = ok_all and ok
            lines.append(f"  [{action}] uid={product_id} {msg}")
    lines.append(f"[products] RESULT={'PASS' if ok_all and products else 'FAIL'}")
    return lines


def verify_members(db, limit: int) -> List[str]:
    from app.models import Member
    from app.services.makeshop_api_gateway import fetch_members_page

    lines: List[str] = []
    payload = fetch_members_page(page=1, limit=limit, db=db)
    members = payload.get("list") or []
    lines.append(f"[members] return_code={payload.get('return_code')} fetched={len(members)}")

    ok_all = True
    for member_data in members[:limit]:
        member_id = member_data.get("id")
        if not member_id:
            continue
        db_member = (
            db.query(Member)
            .filter(Member.makeshop_member_id == member_id)
            .first()
        )
        if db_member:
            db_member.hname = member_data.get("hname", db_member.hname)
            db_member.email = member_data.get("email", db_member.email)
            db_member.mobile = member_data.get("mobile", db_member.mobile)
            db_member.group_name = member_data.get("group_name", db_member.group_name)
            action = "updated"
        else:
            db_member = Member(
                makeshop_member_id=member_id,
                hname=member_data.get("hname", ""),
                email=member_data.get("email"),
                mobile=member_data.get("mobile"),
                group_name=member_data.get("group_name"),
            )
            db.add(db_member)
            action = "created"
        db.commit()
        db.refresh(db_member)

        checks = [
            _check("hname", member_data.get("hname"), db_member.hname),
            _check("email", member_data.get("email"), db_member.email),
            _check("mobile", member_data.get("mobile"), db_member.mobile),
        ]
        for ok, msg in checks:
            ok_all = ok_all and ok
            lines.append(f"  [{action}] id={member_id} {msg}")
    lines.append(f"[members] RESULT={'PASS' if ok_all and members else 'FAIL'}")
    return lines


def verify_orders(db, limit: int, days: int) -> List[str]:
    from app.models import Order, OrderItem
    from app.services.makeshop_api_gateway import fetch_orders_page

    lines: List[str] = []
    end = datetime.now()
    start = end - timedelta(days=days)
    inquiry_from = start.strftime("%Y-%m-%d %H:%M:%S")
    inquiry_to = end.strftime("%Y-%m-%d %H:%M:%S")
    payload = fetch_orders_page(
        page=1,
        limit=limit,
        inquiry_time_from=inquiry_from,
        inquiry_time_to=inquiry_to,
        db=db,
    )
    orders: Dict[str, Any] = payload.get("list") or {}
    if isinstance(orders, list):
        lines.append("[orders] FAIL unexpected list shape (expected dict)")
        return lines

    lines.append(
        f"[orders] return_code={payload.get('return_code')} "
        f"period={inquiry_from}~{inquiry_to} fetched={len(orders)}"
    )

    ok_all = True
    for ordernum, wrapper in list(orders.items())[:limit]:
        order_data = wrapper.get("order", {})
        payment_data = wrapper.get("payment", {})
        product_data = wrapper.get("product", {})
        ordernum = order_data.get("ordernum") or ordernum
        if not ordernum:
            continue

        db_order = db.query(Order).filter(Order.ordernum == ordernum).first()
        if db_order:
            db_order.sender = _safe_string(order_data.get("sender")) or db_order.sender
            db_order.pay_price = _safe_int(order_data.get("pay_price")) or db_order.pay_price
            db_order.pay_status = _safe_string(payment_data.get("pay_status")) or db_order.pay_status
            db_order.order_status = _safe_string(order_data.get("order_status")) or db_order.order_status
            db_order.order_date = _safe_string(order_data.get("order_date")) or db_order.order_date
            action = "updated"
        else:
            db_order = Order(
                ordernum=ordernum,
                member_id=_safe_string(order_data.get("id")),
                order_date=_safe_string(order_data.get("order_date")),
                sender=_safe_string(order_data.get("sender")),
                pay_price=_safe_int(order_data.get("pay_price")) or 0,
                order_status=_safe_string(order_data.get("order_status")) or "pending",
                pay_status=_safe_string(payment_data.get("pay_status")) or "pending",
            )
            db.add(db_order)
            action = "created"

        item_count = 0
        if isinstance(product_data, dict):
            existing = {
                i.product_uid: i
                for i in db.query(OrderItem).filter(OrderItem.ordernum == ordernum).all()
            }
            for idx, (_key, product_item) in enumerate(product_data.items()):
                if not isinstance(product_item, dict):
                    continue
                product_uid = _safe_string(product_item.get("product_uid")) or f"UNKNOWN_{idx}"
                item_count += 1
                if product_uid in existing:
                    item = existing[product_uid]
                    item.product_name = _safe_string(product_item.get("product_name")) or item.product_name
                    item.sell_price = _safe_int(product_item.get("sell_price")) or item.sell_price
                    item.num = _safe_string(product_item.get("num")) or item.num
                    item.basket_status = _safe_string(product_item.get("basket_status")) or item.basket_status
                else:
                    db.add(
                        OrderItem(
                            ordernum=ordernum,
                            product_uid=product_uid,
                            product_name=_safe_string(product_item.get("product_name")) or "상품명 없음",
                            basket_stock=_safe_int(product_item.get("basket_stock")) or 1,
                            sell_price=_safe_int(product_item.get("sell_price")) or 0,
                            num=_safe_string(product_item.get("num")),
                            basket_status=_safe_string(product_item.get("basket_status")),
                        )
                    )

        db.commit()
        db.refresh(db_order)
        db_items = db.query(OrderItem).filter(OrderItem.ordernum == ordernum).count()

        checks = [
            _check("sender", order_data.get("sender"), db_order.sender),
            _check("pay_price", _safe_int(order_data.get("pay_price")), db_order.pay_price),
            _check("order_status", order_data.get("order_status"), db_order.order_status),
            _check("order_date", order_data.get("order_date"), db_order.order_date),
        ]
        items_ok = db_items >= item_count if item_count else True
        ok_all = ok_all and items_ok
        for ok, msg in checks:
            ok_all = ok_all and ok
            lines.append(f"  [{action}] ordernum={ordernum} {msg}")
        lines.append(
            f"  [{action}] ordernum={ordernum} "
            f"{'OK' if items_ok else 'DIFF'} order_items: api={item_count} db={db_items}"
        )

    lines.append(f"[orders] RESULT={'PASS' if ok_all and orders else 'FAIL'}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="REST → DB 소량 저장 검증")
    parser.add_argument("--limit", type=int, default=3, help="엔티티별 샘플 수")
    parser.add_argument("--days", type=int, default=3, help="주문 조회 일수")
    args = parser.parse_args()

    from app.database import SessionLocal
    from app.services.makeshop_api_gateway import use_makeshop_rest

    print(f"[info] MAKESHOP_USE_REST={use_makeshop_rest()}")
    print(f"[info] shop_uid={os.getenv('MAKESHOP_SHOP_UID')}")
    print(f"[info] limit={args.limit} order_days={args.days}")
    print("[info] APIs: product / user / order 2.0 (Developer Center)")

    db = SessionLocal()
    try:
        sections = [
            verify_products(db, args.limit),
            verify_members(db, args.limit),
            verify_orders(db, args.limit, args.days),
        ]
    finally:
        db.close()

    failed = False
    for lines in sections:
        print()
        for line in lines:
            print(line)
            if "RESULT=FAIL" in line:
                failed = True

    print()
    print("[summary]", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
