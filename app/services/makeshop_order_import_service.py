from __future__ import annotations
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import select
import sqlalchemy as sa

from app.models import Order, OrderItem


def _safe_int(v: Any, default: int | None = None) -> int | None:
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _get_first(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _stringify_address(info: Dict[str, Any] | None) -> str | None:
    if not info:
        return None
    parts: List[str] = []
    post = str(info.get('post') or '').strip()
    addr = str(info.get('address') or '').strip()
    addr2 = str(info.get('address2') or '').strip()
    if post:
        parts.append(f"({post})")
    if addr:
        parts.append(addr)
    if addr2:
        parts.append(addr2)
    return ' '.join(parts) if parts else None


def upsert_order_from_payload(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert Makeshop order(s) into Order / OrderItem tables from stdClass-like JSON.

    Expected shape (simplified):
    {
      "list": {
        "<ordernum>": {
          "order": { ... },
          "payment": { ... },
          "product": { "1": { ... }, ... },
          "extension": [ ... ]
        },
        ...
      }
    }
    Returns summary: { processed: n, upserted: m, orders: [ { makeshop_order_id, items } ] }
    """
    orders_input = payload.get('list') or {}
    if isinstance(orders_input, list):
        # rare: if API returned a list instead of map, map by included ordernum
        mapped = {}
        for item in orders_input:
            try:
                on = str(((item or {}).get('order') or {}).get('ordernum') or '')
                if on:
                    mapped[on] = item
            except Exception:
                continue
        orders_input = mapped

    if not isinstance(orders_input, dict) or not orders_input:
        raise ValueError('payload.list must be a non-empty object mapping ordernum to order payloads')

    upserted = 0
    results: List[Dict[str, Any]] = []

    for ordernum, entry in orders_input.items():
        try:
            entry = entry or {}
            order_info = (entry.get('order') or {})
            payment = (entry.get('payment') or {})
            products = (entry.get('product') or {})

            makeshop_order_id = str(order_info.get('ordernum') or ordernum)
            if not makeshop_order_id:
                # skip invalid
                continue

            # Upsert Order by makeshop_order_id
            o: Order | None = db.execute(
                select(Order).where(Order.makeshop_order_id == makeshop_order_id)
            ).scalar_one_or_none()

            if not o:
                o = Order(makeshop_order_id=makeshop_order_id)
                db.add(o)
                db.flush()
                # set initial fields via setattr to satisfy type checker
                setattr(o, 'customer_name', str(order_info.get('sender') or ''))
                setattr(o, 'customer_email', str(order_info.get('email') or ''))
                setattr(o, 'customer_phone', str(_get_first(order_info, 'mobile', 'phone') or ''))
                setattr(o, 'total_price', _safe_int(_get_first(order_info, 'pay_price', 'start_price')) or 0)
                setattr(o, 'payment_status', str(payment.get('pay_status') or ''))
                setattr(o, 'order_status', str(order_info.get('order_status') or ''))
                setattr(o, 'items_count', int(_safe_int(order_info.get('basket_count')) or 0))
                setattr(o, 'notes', str(order_info.get('memo') or ''))
                setattr(o, 'shipping_address', None)
            else:
                # update basic fields
                setattr(o, 'customer_name', str(order_info.get('sender') or getattr(o, 'customer_name')))
                setattr(o, 'customer_email', str(order_info.get('email') or getattr(o, 'customer_email')))
                setattr(o, 'customer_phone', str(_get_first(order_info, 'mobile', 'phone') or getattr(o, 'customer_phone')))
                pay_total = _safe_int(_get_first(order_info, 'pay_price', 'start_price'))
                if pay_total is not None:
                    setattr(o, 'total_price', pay_total)
                setattr(o, 'payment_status', str(payment.get('pay_status') or getattr(o, 'payment_status')))
                setattr(o, 'order_status', str(order_info.get('order_status') or getattr(o, 'order_status')))
                bc = _safe_int(order_info.get('basket_count'))
                if bc is not None:
                    setattr(o, 'items_count', int(bc))
                memo = order_info.get('memo')
                if memo is not None:
                    setattr(o, 'notes', str(memo))

            # Derive shipping address from first product.deliveryInfo
            ship_addr = None
            if isinstance(products, dict):
                for _, p in products.items():
                    di = (p or {}).get('deliveryInfo') or {}
                    ship_addr = _stringify_address(di)
                    if ship_addr:
                        break
            if ship_addr:
                setattr(o, 'shipping_address', ship_addr)

            # Clear existing order items for this order
            db.execute(sa.text('DELETE FROM order_items WHERE makeshop_order_id = :oid'), { 'oid': makeshop_order_id })

            # Insert items
            item_count = 0
            if isinstance(products, dict):
                for _, p in products.items():
                    if p is None:
                        continue
                    qty = int(_safe_int(p.get('basket_stock')) or 0)
                    if qty <= 0:
                        continue
                    unit = _safe_int(_get_first(p, 'sell_price', 'product_price')) or 0
                    total = unit * qty
                    prod_id = str(p.get('product_uid') or '')
                    item = OrderItem(
                        order_id=makeshop_order_id,  # reuse external id for convenience
                        makeshop_order_id=makeshop_order_id,
                        product_id=prod_id,
                        product_name=str(p.get('product_name') or ''),
                        quantity=qty,
                        unit_price=unit,
                        total_price=total,
                    )
                    db.add(item)
                    item_count += 1

            # Update items_count if not present
            if (getattr(o, 'items_count') in (None, 0)) and item_count:
                setattr(o, 'items_count', item_count)

            db.flush()
            upserted += 1
            results.append({
                'makeshop_order_id': makeshop_order_id,
                'items': item_count,
                'total_price': o.total_price,
                'payment_status': o.payment_status,
                'order_status': o.order_status,
            })
        except Exception as e:
            # continue with others but record error
            results.append({ 'error': str(e), 'ordernum': str(ordernum) })

    db.commit()
    return {
        'processed': len(orders_input),
        'upserted': upserted,
        'orders': results,
    }
