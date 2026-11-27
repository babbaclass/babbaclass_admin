"""
임시: 신규 REST와 구 Open API 조회 결과를 병행 비교 후 Google Chat 리포트.

사용 후 제거 예정:
  - MAKESHOP_DUAL_COMPARE=false 로 즉시 비활성
  - 이상 없으면 본 모듈 + gateway 훅 삭제

모든 페이지·페이지 내 전 건 ID/핵심 필드를 비교한다.
쓰기 API(송장/배송)는 부작용이 있어 비교하지 않는다.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Set, Tuple

# import requests  # 레거시 Open API 비활성

from app.services.google_chat import send_google_chat_message
# from app.services.makeshop_service import MakeshopAPIClient

logger = logging.getLogger(__name__)

# 페이지 내 필드 비교: 해당 페이지의 공통 ID 전부 (부분 샘플이 아님)
_CHAT_DIFF_LINES = 20


def dual_compare_enabled() -> bool:
    """레거시 Open API 비활성으로 병행 비교도 끔."""
    # raw = (os.getenv("MAKESHOP_DUAL_COMPARE") or "false").strip().lower()
    # return raw in {"1", "true", "yes", "on"}
    return False


def _compare_every_page() -> bool:
    """기본 true — 전체 페이지 비교. false면 page=1만 (디버그용)."""
    raw = (os.getenv("MAKESHOP_DUAL_COMPARE_EVERY_PAGE") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _chat_on_match() -> bool:
    """일치 시에도 Chat 전송 (기본 true). false면 차이/오류만 전송."""
    raw = (os.getenv("MAKESHOP_DUAL_COMPARE_CHAT_ON_MATCH") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _should_report_page(page: int) -> bool:
    if _compare_every_page():
        return True
    return int(page) == 1


def _legacy_get(params: Dict[str, Any]) -> Dict[str, Any]:
    # 레거시 Open API 비활성 (MAKESHOP_SHOPKEY / LICENSEKEY / API_URL)
    # client = MakeshopAPIClient()
    # headers = {
    #     "Shopkey": client.shop_key,
    #     "Licensekey": client.license_key,
    #     "Content-Type": "application/json",
    # }
    # response = requests.get(
    #     f"{client.shop_domain}/list/open_api.html",
    #     headers=headers,
    #     params=params,
    #     timeout=client.timeout,
    # )
    # data = response.json()
    # if not isinstance(data, dict):
    #     return {"return_code": "9999", "message": "non-dict response", "list": []}
    # return data
    del params
    raise RuntimeError("Makeshop legacy Open API is disabled")


def fetch_legacy_products_page(*, page: int, limit: int) -> Dict[str, Any]:
    return _legacy_get(
        {"limit": limit, "page": page, "mode": "search", "type": "product"}
    )


def fetch_legacy_members_page(*, page: int, limit: int) -> Dict[str, Any]:
    return _legacy_get(
        {"limit": limit, "page": page, "mode": "search", "type": "user"}
    )


def fetch_legacy_orders_page(
    *,
    page: int,
    limit: int,
    inquiry_time_from: str,
    inquiry_time_to: str,
) -> Dict[str, Any]:
    return _legacy_get(
        {
            "limit": limit,
            "page": page,
            "mode": "search",
            "type": "order",
            "InquiryTimeFrom": inquiry_time_from,
            "InquiryTimeTo": inquiry_time_to,
        }
    )


def _as_list(payload: Optional[Dict[str, Any]]) -> List[Any]:
    if not payload:
        return []
    raw = payload.get("list")
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return list(raw.values())
    return []


def _product_ids(payload: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for item in _as_list(payload):
        if isinstance(item, dict) and item.get("uid") not in (None, ""):
            ids.add(str(item["uid"]))
    return ids


def _member_ids(payload: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for item in _as_list(payload):
        if isinstance(item, dict) and item.get("id") not in (None, ""):
            ids.add(str(item["id"]))
    return ids


def _order_map(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    raw = payload.get("list") if payload else None
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if isinstance(v, dict)}
    if isinstance(raw, list):
        out: Dict[str, Dict[str, Any]] = {}
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            order = entry.get("order") if isinstance(entry.get("order"), dict) else entry
            ordernum = order.get("ordernum")
            if ordernum:
                out[str(ordernum)] = entry
        return out
    return {}


def _norm(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            if float(value) == int(float(value)):
                return str(int(float(value)))
        except (TypeError, ValueError):
            pass
        return str(value)
    return str(value).strip()


def _compare_id_sets(
    rest_ids: Set[str],
    legacy_ids: Set[str],
) -> Tuple[int, int, List[str]]:
    only_rest = sorted(rest_ids - legacy_ids)
    only_legacy = sorted(legacy_ids - rest_ids)
    lines: List[str] = []
    if only_rest:
        lines.append(f"REST만: {', '.join(only_rest[:8])}" + ("…" if len(only_rest) > 8 else ""))
    if only_legacy:
        lines.append(
            f"구API만: {', '.join(only_legacy[:8])}" + ("…" if len(only_legacy) > 8 else "")
        )
    return len(only_rest), len(only_legacy), lines


def _compare_product_fields(
    rest: Dict[str, Any],
    legacy: Dict[str, Any],
) -> List[str]:
    rest_by_uid = {
        str(i["uid"]): i
        for i in _as_list(rest)
        if isinstance(i, dict) and i.get("uid") not in (None, "")
    }
    leg_by_uid = {
        str(i["uid"]): i
        for i in _as_list(legacy)
        if isinstance(i, dict) and i.get("uid") not in (None, "")
    }
    fields = ("product_name", "sellprice", "display", "sell_accept", "cate1")
    diffs: List[str] = []
    for uid in sorted(set(rest_by_uid) & set(leg_by_uid)):
        r, l = rest_by_uid[uid], leg_by_uid[uid]
        for field in fields:
            rv, lv = _norm(r.get(field)), _norm(l.get(field))
            # REST에 status 없음 — 빈 REST vs 구값 차이는 무시
            if field == "status" and rv == "":
                continue
            if rv != lv:
                diffs.append(f"uid={uid} {field}: REST={rv!r} 구={lv!r}")
    return diffs


def _compare_member_fields(
    rest: Dict[str, Any],
    legacy: Dict[str, Any],
) -> List[str]:
    rest_by_id = {
        str(i["id"]): i
        for i in _as_list(rest)
        if isinstance(i, dict) and i.get("id") not in (None, "")
    }
    leg_by_id = {
        str(i["id"]): i
        for i in _as_list(legacy)
        if isinstance(i, dict) and i.get("id") not in (None, "")
    }
    fields = ("hname", "email", "mobile", "group_name")
    diffs: List[str] = []
    for mid in sorted(set(rest_by_id) & set(leg_by_id)):
        r, l = rest_by_id[mid], leg_by_id[mid]
        for field in fields:
            rv, lv = _norm(r.get(field)), _norm(l.get(field))
            if rv != lv:
                diffs.append(f"id={mid} {field}: REST={rv!r} 구={lv!r}")
    return diffs


def _compare_order_fields(
    rest: Dict[str, Any],
    legacy: Dict[str, Any],
) -> List[str]:
    rest_map = _order_map(rest)
    leg_map = _order_map(legacy)
    diffs: List[str] = []
    for ordernum in sorted(set(rest_map) & set(leg_map)):
        r_entry, l_entry = rest_map[ordernum], leg_map[ordernum]
        r_order = r_entry.get("order") if isinstance(r_entry.get("order"), dict) else {}
        l_order = l_entry.get("order") if isinstance(l_entry.get("order"), dict) else {}
        r_pay = r_entry.get("payment") if isinstance(r_entry.get("payment"), dict) else {}
        l_pay = l_entry.get("payment") if isinstance(l_entry.get("payment"), dict) else {}
        for field in ("pay_price", "order_status", "sender", "order_date"):
            rv, lv = _norm(r_order.get(field)), _norm(l_order.get(field))
            if rv != lv:
                diffs.append(f"{ordernum} order.{field}: REST={rv!r} 구={lv!r}")
        rv, lv = _norm(r_pay.get("pay_status")), _norm(l_pay.get("pay_status"))
        if rv != lv:
            diffs.append(f"{ordernum} pay_status: REST={rv!r} 구={lv!r}")
        r_prod = r_entry.get("product")
        l_prod = l_entry.get("product")
        r_n = len(r_prod) if isinstance(r_prod, dict) else (len(r_prod) if isinstance(r_prod, list) else 0)
        l_n = len(l_prod) if isinstance(l_prod, dict) else (len(l_prod) if isinstance(l_prod, list) else 0)
        if r_n != l_n:
            diffs.append(f"{ordernum} product_count: REST={r_n} 구={l_n}")
    return diffs


def _legacy_ok(payload: Dict[str, Any]) -> bool:
    code = str(payload.get("return_code", "9999"))
    return code in {"0000", "0", "OK", "success", "9011"}


def build_compare_report(
    *,
    resource: str,
    page: int,
    rest_payload: Dict[str, Any],
    legacy_payload: Optional[Dict[str, Any]],
    legacy_error: Optional[str] = None,
    meta: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Returns (match, chat_message).
    match=True 이면 핵심 ID 집합·샘플 필드가 일치.
    """
    lines = [
        f"[MakeShop 비교] {resource} page={page}",
    ]
    if meta:
        lines.append(f"• {meta}")

    if legacy_error:
        lines.append(f"• 결과: 비교 불가 (구 API 오류)")
        lines.append(f"• 구 API: {legacy_error[:200]}")
        lines.append(f"• REST return_code: {rest_payload.get('return_code')}")
        lines.append(f"• REST count/total: {rest_payload.get('count')}/{rest_payload.get('totalCount')}")
        return False, "\n".join(lines)

    assert legacy_payload is not None
    if not _legacy_ok(legacy_payload):
        code = legacy_payload.get("return_code")
        msg = legacy_payload.get("message") or ""
        lines.append(f"• 결과: 비교 불가 (구 API return_code={code})")
        if msg:
            lines.append(f"• 구 API: {msg}")
        return False, "\n".join(lines)

    rest_code = str(rest_payload.get("return_code", ""))
    leg_code = str(legacy_payload.get("return_code", ""))
    lines.append(f"• return_code: REST={rest_code} 구={leg_code}")
    lines.append(
        f"• totalCount: REST={rest_payload.get('totalCount')} 구={legacy_payload.get('totalCount')}"
    )
    lines.append(
        f"• count: REST={rest_payload.get('count')} 구={legacy_payload.get('count')}"
    )

    field_diffs: List[str] = []
    only_rest = only_legacy = 0
    id_lines: List[str] = []

    if resource == "products":
        only_rest, only_legacy, id_lines = _compare_id_sets(
            _product_ids(rest_payload), _product_ids(legacy_payload)
        )
        field_diffs = _compare_product_fields(rest_payload, legacy_payload)
        lines.append(
            f"• uid 수: REST={len(_product_ids(rest_payload))} 구={len(_product_ids(legacy_payload))}"
        )
    elif resource == "members":
        only_rest, only_legacy, id_lines = _compare_id_sets(
            _member_ids(rest_payload), _member_ids(legacy_payload)
        )
        field_diffs = _compare_member_fields(rest_payload, legacy_payload)
        lines.append(
            f"• id 수: REST={len(_member_ids(rest_payload))} 구={len(_member_ids(legacy_payload))}"
        )
    elif resource == "orders":
        rest_map = _order_map(rest_payload)
        leg_map = _order_map(legacy_payload)
        only_rest, only_legacy, id_lines = _compare_id_sets(
            set(rest_map), set(leg_map)
        )
        field_diffs = _compare_order_fields(rest_payload, legacy_payload)
        lines.append(f"• ordernum 수: REST={len(rest_map)} 구={len(leg_map)}")
    else:
        lines.append("• 결과: 알 수 없는 resource")
        return False, "\n".join(lines)

    match = only_rest == 0 and only_legacy == 0 and not field_diffs
    # totalCount 불일치는 경고만 (페이지 샘플과 별개일 수 있음)
    total_mismatch = _norm(rest_payload.get("totalCount")) != _norm(
        legacy_payload.get("totalCount")
    )
    if total_mismatch:
        lines.append("• 참고: totalCount 불일치")

    if match and not total_mismatch:
        lines.append("• 결과: 일치")
    elif match and total_mismatch:
        lines.append("• 결과: 페이지 ID/필드 일치 (totalCount만 다름)")
        match = True
    else:
        lines.append("• 결과: 차이 있음")
        for line in id_lines[:4]:
            lines.append(f"  - {line}")
        for line in field_diffs[:_CHAT_DIFF_LINES]:
            lines.append(f"  - {line}")
        omitted = max(0, len(field_diffs) - _CHAT_DIFF_LINES)
        if omitted:
            lines.append(f"  - …외 {omitted}건")

    return match, "\n".join(lines)


def run_dual_compare_and_notify(
    *,
    resource: str,
    page: int,
    rest_payload: Dict[str, Any],
    legacy_fetcher,
    meta: Optional[str] = None,
) -> None:
    """
    구 API를 추가로 호출해 비교하고 Google Chat으로 보낸다.
    예외를 밖으로 올리지 않는다 (본 동기화 경로 보호).
    """
    if not dual_compare_enabled():
        return
    if not _should_report_page(page):
        logger.debug("[MakeShop 비교] skip page=%s (page1 only)", page)
        return

    legacy_payload: Optional[Dict[str, Any]] = None
    legacy_error: Optional[str] = None
    try:
        legacy_payload = legacy_fetcher()
    except Exception as exc:  # noqa: BLE001
        legacy_error = str(exc)
        logger.warning("[MakeShop 비교] legacy fetch failed: %s", exc)

    try:
        _match, message = build_compare_report(
            resource=resource,
            page=page,
            rest_payload=rest_payload,
            legacy_payload=legacy_payload,
            legacy_error=legacy_error,
            meta=meta,
        )
        should_chat = (not _match) or _chat_on_match() or bool(legacy_error)
        sent = False
        if should_chat:
            sent = send_google_chat_message(message)
        logger.info(
            "[MakeShop 비교] resource=%s page=%s match=%s chat_sent=%s",
            resource,
            page,
            _match,
            sent,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[MakeShop 비교] notify failed: %s", exc)
