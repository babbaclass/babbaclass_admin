"""MakeShop REST 공통 유틸."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def extract_list_and_meta(payload: Optional[Dict[str, Any]]) -> Tuple[Any, Dict[str, Any]]:
    """REST 응답에서 list와 페이지 메타를 추출한다."""
    if not payload:
        return None, {}

    candidates: List[Dict[str, Any]] = [payload]
    data = payload.get("data")
    if isinstance(data, dict):
        candidates.insert(0, data)
    elif data is None and "data" in payload:
        return None, {
            "totalCount": payload.get("totalCount") or payload.get("total_count") or 0,
            "totalPage": payload.get("totalPage") or payload.get("total_page"),
            "page": payload.get("page") or 1,
            "count": payload.get("count") or 0,
            "return_code": payload.get("return_code"),
        }

    for candidate in candidates:
        if "list" in candidate:
            return candidate.get("list"), {
                "totalCount": candidate.get("totalCount", candidate.get("total_count")),
                "totalPage": candidate.get("totalPage", candidate.get("total_page")),
                "page": candidate.get("page"),
                "count": candidate.get("count"),
                "return_code": candidate.get("return_code", payload.get("return_code")),
            }

    return None, {"return_code": payload.get("return_code")}


def legacy_list_envelope(
    items: List[Any],
    *,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta = meta or {}
    count = len(items)
    total_count = meta.get("totalCount")
    if total_count in (None, ""):
        total_count = count
    else:
        total_count = coerce_int(total_count, count)

    result: Dict[str, Any] = {
        "return_code": str(meta.get("return_code") or "0000"),
        "list": items,
        "totalCount": total_count,
        "page": coerce_int(meta.get("page"), 1) or 1,
        "count": coerce_int(meta.get("count"), count) or count,
    }
    if meta.get("totalPage") not in (None, ""):
        result["totalPage"] = coerce_int(meta.get("totalPage"), 0)
    return result
