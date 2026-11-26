"""
MakeShop REST 회원 조회 → 구 Open API 회원 sync payload 정규화.

구 동기화(`/sync/makeshop/members`) 기대 형태:
{
  "return_code": "0000",
  "list": [ {id, hname, email, mobile, ...}, ... ],
  "totalCount": N, "page": 1, "count": M
}
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.makeshop_rest_utils import (
    coerce_int,
    extract_list_and_meta,
    legacy_list_envelope,
)

MEMBER_INT_FIELDS = (
    "grade",
    "reserve",
    "point",
    "emoney",
    "order_count",
)


def normalize_member_item(item: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(item)

    for field in MEMBER_INT_FIELDS:
        if field in normalized and normalized[field] not in (None, ""):
            coerced = coerce_int(normalized[field])
            if coerced is not None:
                normalized[field] = coerced

    company = normalized.get("company_info")
    if isinstance(company, dict):
        # sync가 company_info.* 과 flat company_* 둘 다 읽을 수 있게 flat도 채움
        for key in (
            "company_name",
            "company_owner",
            "company_num",
            "company_corp",
            "company_biz",
            "company_item",
            "company_post",
            "company_addr",
        ):
            if normalized.get(key) in (None, "") and company.get(key) not in (None, ""):
                normalized[key] = company.get(key)

    return normalized


def adapt_members_to_legacy(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw_list, meta = extract_list_and_meta(payload)
    items: List[Dict[str, Any]] = []

    if isinstance(raw_list, list):
        for entry in raw_list:
            if isinstance(entry, dict):
                items.append(normalize_member_item(entry))
    elif isinstance(raw_list, dict):
        for entry in raw_list.values():
            if isinstance(entry, dict):
                items.append(normalize_member_item(entry))

    return legacy_list_envelope(items, meta=meta)
