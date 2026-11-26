from __future__ import annotations
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import select
import sqlalchemy as sa
from hashlib import sha256
from app.models import (
    Product,
    Brand,
    ProductBrand,
    ProductOptionGroup,
    ProductOptionValue,
    ProductStock,
    # ProductStockOptionValue,  # not used in batch1
    ProductDiscount,
    ProductDelivery,
    ProductColor,
    ProductCouponException,
)


def _safe_int(v: Any, default: int | None = None) -> int | None:
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _split_csv(s: str | None) -> List[str]:
    if not s:
        return []
    return [x.strip() for x in str(s).split(',') if str(x).strip() != '']


def upsert_product_from_payload(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Upsert Makeshop product and related records (Batch1 scope).

    Contract:
    - payload corresponds to list[0] object in the provided sample structure.
    - Returns summary dict with ids and counts.
    """
    # 1) Core products upsert by uid (mapped from makeshop uid)
    source_uid = _safe_int(payload.get('uid'))
    if not source_uid:
        raise ValueError("uid is required in payload")
    makeshop_id = str(source_uid)
    prod = db.execute(select(Product).where(Product.uid == makeshop_id)).scalar_one_or_none()
    if not prod:
        prod = Product(uid=makeshop_id, product_name=str(payload.get('product_name') or ''), sellprice=_safe_int(payload.get('sellprice')) or 0)
        db.add(prod)
        db.flush()

    for attr, value in [
        ('brandcode', payload.get('brandcode')),
        ('cate1', payload.get('cate1')),
        ('cate2', payload.get('cate2')),
        ('virtual_cate', payload.get('virtual_cate')),
        ('category_name', payload.get('category_name')),
        ('consumerprice', _safe_int(payload.get('consumerprice'))),
        ('reserve', _safe_int(payload.get('reserve'))),
        ('keyword', payload.get('keyword')),
        ('sell_accept', payload.get('sell_accept')),
        ('display', payload.get('display')),
        ('product_type', payload.get('product_type')),
        ('best_product_display', payload.get('best_product_display')),
        ('best_review_display', payload.get('best_review_display')),
        ('sellcount', _safe_int(payload.get('sellcount'))),
        ('regdate', payload.get('regdate')),
        ('moddate', payload.get('moddate')),
        # 'quantity' not stored in DB
        ('provide_delivery_price', _safe_int(payload.get('provide_delivery_price'))),
        ('max_order_quantity_method', payload.get('max_order_quantity_method')),
        ('min_order_quantity_method', payload.get('min_order_quantity_method')),
        ('vat', payload.get('vat')),
        ('vat_type', payload.get('vat_type')),
        ('product_content', payload.get('product_content')),
        ('display_date', payload.get('display_date')),
        ('importune', payload.get('importune')),
        ('view_count', _safe_int(payload.get('view_count'))),
        ('cart_count', _safe_int(payload.get('cart_count'))),
        ('is_add_composition', payload.get('is_add_composition')),
        ('ems_type', payload.get('ems_type')),
    ]:
        setattr(prod, attr, value if value != '' else None)
    setattr(prod, 'product_name', str(payload.get('product_name') or getattr(prod, 'product_name')))
    setattr(prod, 'sellprice', _safe_int(payload.get('sellprice')) or getattr(prod, 'sellprice'))
    buyprice_val = _safe_int(payload.get('buyprice'))
    if buyprice_val is not None:
        setattr(prod, 'buyprice', buyprice_val)

    # 2) Link summarized Product (optional alignment)
    # Use 'uid' as makeshop product id for compatibility
    # Summary Product is prod itself

    # 3) Brands (N:M)
    brands = payload.get('brand') or []
    # clear existing links for mk
    db.execute(sa.text('DELETE FROM product_brands WHERE product_id = :pid'), { 'pid': prod.id or 0 })
    for b in brands:
        name = str((b or {}).get('name') or '').strip()
        if not name:
            continue
        # find or create brand by (name, brand_mid, brand_sid)
        brand = db.execute(select(Brand).where(Brand.name == name)).scalar_one_or_none()
        if not brand:
            brand = Brand(name=name, brand_mid=_safe_int((b or {}).get('brand_mid')), brand_sid=_safe_int((b or {}).get('brand_sid')))
            db.add(brand)
            db.flush()
        link = ProductBrand(product_id=prod.id, brand_id=brand.brand_id)
        db.add(link)

    # 4) Option groups/values
    options = (payload.get('options') or {}).get('option') or []
    # delete existing groups/values via cascade approach (manual):
    db.execute(sa.text('DELETE FROM product_stock_option_values WHERE stock_id IN (SELECT id FROM product_stocks WHERE product_id=:pid)'), { 'pid': prod.id or 0 })
    db.execute(sa.text('DELETE FROM product_stocks WHERE product_id=:pid'), { 'pid': prod.id or 0 })
    db.execute(sa.text('DELETE FROM product_option_values WHERE group_id IN (SELECT id FROM product_option_groups WHERE product_id=:pid)'), { 'pid': prod.id or 0 })
    db.execute(sa.text('DELETE FROM product_option_groups WHERE product_id=:pid'), { 'pid': prod.id or 0 })

    group_map: Dict[int, ProductOptionGroup] = {}
    for idx, og in enumerate(options):
        gid = _safe_int((og or {}).get('opt_id')) or (idx + 1)
        g = ProductOptionGroup(
            product_id=prod.id,
            source_opt_id=gid,
            opt_type=str((og or {}).get('opt_type') or None) or None,
            opt_name=str((og or {}).get('opt_name') or None) or None,
            opt_use=str((og or {}).get('opt_use') or None) or None,
            opt_mix=str((og or {}).get('opt_mix') or None) or None,
            opt_mandatory=str((og or {}).get('opt_mandatory') or None) or None,
            opt_oneclick=str((og or {}).get('opt_oneclick') or None) or None,
            position=idx,
        )
        db.add(g)
        db.flush()
        group_map[gid] = g
        # values and prices are CSV aligned
        values = _split_csv(str((og or {}).get('opt_value') or ''))
        prices = _split_csv(str((og or {}).get('opt_price') or ''))
        for vi, val in enumerate(values):
            extra = _safe_int(prices[vi]) if vi < len(prices) else None
            db.add(ProductOptionValue(group_id=g.id, value_index=vi, value_text=val, extra_price=extra))

    # 5) Stocks (basic)
    basics = (payload.get('options') or {}).get('basic') or []
    for s in basics:
        sto_id = _safe_int((s or {}).get('sto_id'))
        # opt_ids are not used in batch1 (value hash only); ignore opt_ids_csv
        # build composed_key as sorted indices from opt values text (we only have values string "44,타입1")
        values_str = str((s or {}).get('sto_opt_values') or '')
        value_tokens = [v.strip() for v in values_str.split(',') if v.strip()]
        hash_key = sha256(('|'.join(value_tokens)).encode('utf-8')).hexdigest()
        stock = ProductStock(
            product_id=prod.id,
            source_sto_id=sto_id or 0,
            sto_type=str((s or {}).get('sto_type') or None) or None,
            sto_price=_safe_int((s or {}).get('sto_price')),
            sto_provide_price=_safe_int((s or {}).get('sto_provide_price')),
            sto_real_stock=_safe_int((s or {}).get('sto_real_stock')),
            sto_unlimit=str((s or {}).get('sto_unlimit') or None) or None,
            sto_stop_use=str((s or {}).get('sto_stop_use') or None) or None,
            sto_stop_stock=_safe_int((s or {}).get('sto_stop_stock')),
            sto_order_stock=_safe_int((s or {}).get('sto_order_stock')),
            sto_state_code=str((s or {}).get('sto_state_code') or None) or None,
            sto_option_code=str((s or {}).get('sto_option_code') or None) or None,
            composed_key_hash=hash_key,
        )
        db.add(stock)
        db.flush()
        # We cannot map to option value IDs precisely without a full cross-table of values; store as hash only in batch1.

    # 6) Discount (single)
    discount = payload.get('discount') or None
    db.execute(sa.text('DELETE FROM product_discounts WHERE product_id=:pid'), {'pid': prod.id or 0})
    if discount:
        db.add(ProductDiscount(
            product_id=prod.id,
            source_discount_uid=_safe_int(discount.get('uid')),
            sale_type=str(discount.get('sale_type') or None) or None,
            title=str(discount.get('title') or None) or None,
            user_type=str(discount.get('user_type') or None) or None,
            view_type=str(discount.get('view_type') or None) or None,
            device=str(discount.get('device') or None) or None,
            discount_price=_safe_int(discount.get('discount_price')),
            unit=str(discount.get('unit') or None) or None,
            start_date=discount.get('start_date'),
            end_date=discount.get('end_date'),
            cut_option=str(discount.get('cut_option') or None) or None,
            cut_position=_safe_int(discount.get('cut_position')),
            option_discount=str(discount.get('option_discount') or None) or None,
            product_coupon_except=str(discount.get('product_coupon_except') or None) or None,
        ))

    # 7) Delivery
    each_deliverys = payload.get('each_deliverys') or None
    db.execute(sa.text('DELETE FROM product_delivery WHERE product_id=:pid'), {'pid': prod.id or 0})
    if each_deliverys:
        db.add(ProductDelivery(
            product_id=prod.id,
            deli_type=str(each_deliverys.get('type') or None) or None,
            deli_price=_safe_int(each_deliverys.get('deli_price')),
        ))

    # 8) Colors
    colors = payload.get('color') or []
    db.execute(sa.text('DELETE FROM product_colors WHERE product_id=:pid'), {'pid': prod.id or 0})
    for c in colors:
        db.add(ProductColor(
            product_id=prod.id,
            color_type=str((c or {}).get('type') or None) or None,
            color_code=str((c or {}).get('code') or None) or None,
            color_name=str((c or {}).get('name') or None) or None,
        ))

    # 9) Coupon exceptions
    coupon_ex = (payload.get('coupon_except') or {}).get('list') or []
    db.execute(sa.text('DELETE FROM product_coupon_exceptions WHERE product_id=:pid'), {'pid': prod.id or 0})
    for ex in coupon_ex:
        db.add(ProductCouponException(product_id=prod.id, except_code=str(ex)))

    db.commit()
    return {
        'product_id': prod.id,
        'uid': prod.uid,
        'product_name': prod.product_name,
    }
