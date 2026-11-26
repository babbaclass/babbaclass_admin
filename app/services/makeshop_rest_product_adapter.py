"""
MakeShop REST 상품 조회 → 구 Open API 상품 sync payload 정규화.

구 동기화(`/sync/makeshop/products`) 기대 형태:
{
  "return_code": "0000",
  "list": [ {uid, product_name, sellprice, cate1, quantity, ...}, ... ],
  "totalCount": N, "page": 1, "count": M
}
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.services.makeshop_rest_utils import (
    coerce_int,
    extract_list_and_meta,
    legacy_list_envelope,
)

PRODUCT_INT_FIELDS = (
    "sellprice",
    "buyprice",
    "consumerprice",
    "sellcount",
    "provide_delivery_price",
    "view_count",
    "cart_count",
    "wish_count",
    "review_count",
)


def _stringify_virtual_cate(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if isinstance(item, dict):
                code = item.get("cate1") or item.get("code") or item.get("uid")
                if code is not None:
                    parts.append(str(code))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return ",".join(parts) if parts else None
    return str(value)


def normalize_product_item(item: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(item)

    # REST: keywords / 구: keyword
    if (normalized.get("keyword") in (None, "")) and normalized.get("keywords") not in (None, ""):
        normalized["keyword"] = normalized.get("keywords")

    if "virtual_cate" in normalized:
        normalized["virtual_cate"] = _stringify_virtual_cate(normalized.get("virtual_cate"))

    # quantity는 Unlimited 문자열을 sync의 parse_quantity가 처리
    for field in PRODUCT_INT_FIELDS:
        if field in normalized and normalized[field] not in (None, ""):
            coerced = coerce_int(normalized[field])
            if coerced is not None:
                normalized[field] = coerced

    return normalized


def adapt_products_to_legacy(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw_list, meta = extract_list_and_meta(payload)
    items: List[Dict[str, Any]] = []

    if isinstance(raw_list, list):
        for entry in raw_list:
            if isinstance(entry, dict):
                items.append(normalize_product_item(entry))
    elif isinstance(raw_list, dict):
        for entry in raw_list.values():
            if isinstance(entry, dict):
                items.append(normalize_product_item(entry))

    return legacy_list_envelope(items, meta=meta)
