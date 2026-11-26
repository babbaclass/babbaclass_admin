"""
MakeShop REST 주문 2.0 응답 → 구 Open API 주문 payload 정규화.

구 동기화(`/sync/makeshop/orders`)가 기대하는 형태:
{
  "return_code": "0000",
  "list": {
    "<ordernum>": {
      "order": {...},
      "payment": {...},
      "product": {"1": {...}, ...},
      "extension": [...]
    }
  },
  "totalCount": N,
  "page": 1,
  "count": M
}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


ORDER_INT_FIELDS = (
    "start_price",
    "pay_price",
    "deli_price",
    "repay_price",
    "used_emoney",
    "used_reserve",
    "reserve",
    "total_product_price",
    "basket_count",
)

PRODUCT_INT_FIELDS = (
    "basket_stock",
    "sell_price",
    "product_price",
    "product_buyprice",
    "product_reserve",
    "option_price",
    "plus_price",
    "plus_reserve",
    "vat",
)


def _coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def _normalize_is_member(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) else 0

    text = str(value).strip().upper()
    if text in {"1", "Y", "YES", "TRUE", "MEMBER"}:
        return 1
    if text in {"0", "N", "NO", "FALSE", "GUEST"}:
        return 0
    return _coerce_int(value, 0) or 0


def _normalize_memo(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                text = item.strip()
                if text:
                    parts.append(text)
                continue
            if isinstance(item, dict):
                for key in ("content", "memo", "message", "text"):
                    if item.get(key):
                        parts.append(str(item[key]).strip())
                        break
                else:
                    parts.append(str(item))
        return "\n".join(p for p in parts if p) or None
    return str(value)


def _normalize_order(order: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(order)
    if "is_member" in normalized:
        normalized["is_member"] = _normalize_is_member(normalized.get("is_member"))
    if "memo" in normalized:
        normalized["memo"] = _normalize_memo(normalized.get("memo"))
    for field in ORDER_INT_FIELDS:
        if field in normalized and normalized[field] is not None and normalized[field] != "":
            coerced = _coerce_int(normalized[field])
            if coerced is not None:
                normalized[field] = coerced
    return normalized


def _normalize_product_item(item: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(item)

    cate1 = normalized.get("cate1")
    product_cate1 = normalized.get("product_cate1")
    if (cate1 is None or cate1 == "") and product_cate1 not in (None, ""):
        normalized["cate1"] = product_cate1

    for field in PRODUCT_INT_FIELDS:
        if field in normalized and normalized[field] is not None and normalized[field] != "":
            coerced = _coerce_int(normalized[field])
            if coerced is not None:
                normalized[field] = coerced

    delivery = normalized.get("deliveryInfo")
    if isinstance(delivery, dict):
        delivery_copy = dict(delivery)
        for field in ("deli_price", "add_deli_price"):
            if field in delivery_copy and delivery_copy[field] not in (None, ""):
                coerced = _coerce_int(delivery_copy[field])
                if coerced is not None:
                    delivery_copy[field] = coerced
        normalized["deliveryInfo"] = delivery_copy

    return normalized


def _normalize_products(products: Any) -> Dict[str, Any]:
    if not products:
        return {}

    if isinstance(products, list):
        mapped: Dict[str, Any] = {}
        for index, item in enumerate(products, start=1):
            if not isinstance(item, dict):
                continue
            key = str(item.get("num") or index)
            mapped[key] = _normalize_product_item(item)
        return mapped

    if isinstance(products, dict):
        return {
            str(key): _normalize_product_item(value)
            for key, value in products.items()
            if isinstance(value, dict)
        }

    return {}


_FLAT_ORDER_FIELDS = {
    "ordernum",
    "order_date",
    "is_member",
    "start_price",
    "pay_price",
    "deli_price",
    "order_status",
    "sender",
    "phone",
    "mobile",
    "email",
    "pay_path",
    "id",
    "used_emoney",
    "used_reserve",
    "group_name",
    "memo",
    "cash_receipt",
    "cash_receipt_status",
    "total_product_price",
    "basket_count",
}
_FLAT_PAYMENT_FIELDS = {
    "paymethod",
    "simple_pay",
    "pay_date",
    "pay_status",
    "in_card_price",
    "banker",
    "bank_name",
    "bank_account",
}
_FLAT_META_FIELDS = {"order", "payment", "product", "extension"}


def _normalize_order_entry(entry: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any]]]:
    order = entry.get("order") if isinstance(entry.get("order"), dict) else {}
    payment = entry.get("payment") if isinstance(entry.get("payment"), dict) else {}
    products = entry.get("product")

    # 상품 기준(format 기본값) flat entry 방어: order 없이 product 필드만 있는 경우
    if not order and any(k in entry for k in ("product_uid", "basket_status", "sell_price")):
        ordernum = str(entry.get("ordernum") or "").strip()
        if not ordernum:
            return None
        order = {
            key: entry[key]
            for key in _FLAT_ORDER_FIELDS
            if key in entry and entry[key] is not None
        }
        order.setdefault("ordernum", ordernum)
        if not payment:
            payment = {
                key: entry[key]
                for key in _FLAT_PAYMENT_FIELDS
                if key in entry and entry[key] is not None
            }
        product_item = {
            k: v
            for k, v in entry.items()
            if k not in _FLAT_META_FIELDS
            and k not in _FLAT_ORDER_FIELDS
            and k not in _FLAT_PAYMENT_FIELDS
        }
        products = {"1": product_item}

    order = _normalize_order(order)
    products = _normalize_products(products)

    ordernum = str(order.get("ordernum") or "").strip()
    if not ordernum:
        return None

    payment = dict(payment)
    if "in_card_price" in payment and payment["in_card_price"] not in (None, ""):
        coerced = _coerce_int(payment["in_card_price"])
        if coerced is not None:
            payment["in_card_price"] = coerced

    normalized_entry: Dict[str, Any] = {
        "order": order,
        "payment": payment,
        "product": products,
    }
    if "extension" in entry:
        normalized_entry["extension"] = entry.get("extension")
    return ordernum, normalized_entry


def _extract_list_and_meta(payload: Dict[str, Any]) -> Tuple[Any, Dict[str, Any]]:
    """REST envelope에서 list와 pagination 메타를 꺼낸다."""
    if not payload:
        return None, {}

    candidates: List[Dict[str, Any]] = [payload]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.insert(0, data)
    elif data is None and "data" in payload:
        # data: null → 주문 0건
        meta = {
            "totalCount": payload.get("totalCount") or payload.get("total_count") or 0,
            "totalPage": payload.get("totalPage") or payload.get("total_page"),
            "page": payload.get("page") or 1,
            "count": payload.get("count") or 0,
        }
        return None, meta

    for candidate in candidates:
        if "list" in candidate:
            meta = {
                "totalCount": candidate.get("totalCount", candidate.get("total_count")),
                "totalPage": candidate.get("totalPage", candidate.get("total_page")),
                "page": candidate.get("page"),
                "count": candidate.get("count"),
            }
            return candidate.get("list"), meta

    return None, {}


def adapt_orders_v2_to_legacy(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    REST 주문 2.0 응답을 구 Open API 주문 동기화용 payload로 변환한다.

    Args:
        payload: `MakeshopRestClient.get_orders_v2()` 원본 응답.

    Returns:
        구 Open API 호환 dict (`return_code`, `list`, pagination 필드 포함).
    """
    if not payload:
        return {
            "return_code": "0000",
            "list": {},
            "totalCount": 0,
            "page": 1,
            "count": 0,
        }

    raw_list, meta = _extract_list_and_meta(payload)
    adapted_list: Dict[str, Any] = {}

    if isinstance(raw_list, dict):
        entries = raw_list.items()
        for key, entry in entries:
            if not isinstance(entry, dict):
                continue
            normalized = _normalize_order_entry(entry)
            if not normalized:
                # key 자체가 ordernum 인 경우 보완
                if "order" not in entry and any(
                    k in entry for k in ("product_uid", "basket_status", "sell_price")
                ):
                    patched = dict(entry)
                    patched.setdefault("ordernum", key)
                    normalized = _normalize_order_entry(patched)
                if not normalized:
                    continue
            ordernum, order_entry = normalized
            # 동일 주문에 상품 기준 row가 여러 개면 product를 merge
            if ordernum in adapted_list and order_entry.get("product"):
                existing_products = adapted_list[ordernum].setdefault("product", {})
                for pkey, pval in order_entry["product"].items():
                    merge_key = pkey
                    if merge_key in existing_products:
                        merge_key = str(len(existing_products) + 1)
                    existing_products[merge_key] = pval
                if order_entry.get("payment") and not adapted_list[ordernum].get("payment"):
                    adapted_list[ordernum]["payment"] = order_entry["payment"]
                continue
            adapted_list[ordernum] = order_entry
    elif isinstance(raw_list, list):
        for entry in raw_list:
            if not isinstance(entry, dict):
                continue
            normalized = _normalize_order_entry(entry)
            if not normalized:
                continue
            ordernum, order_entry = normalized
            adapted_list[ordernum] = order_entry

    count = len(adapted_list)
    total_count = meta.get("totalCount")
    if total_count in (None, ""):
        total_count = count
    else:
        total_count = _coerce_int(total_count, count)

    page = _coerce_int(meta.get("page"), 1) or 1
    result: Dict[str, Any] = {
        "return_code": "0000",
        "list": adapted_list,
        "totalCount": total_count,
        "page": page,
        "count": _coerce_int(meta.get("count"), count) or count,
    }
    if meta.get("totalPage") not in (None, ""):
        result["totalPage"] = _coerce_int(meta.get("totalPage"), 0)

    return result
