"""
MakeShop 조회/쓰기 경로 선택.

신규 Open API(REST)만 사용한다.
구 Open API(MAKESHOP_SHOPKEY / LICENSEKEY / API_URL)는 비활성.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy.orm import Session

from app.services.makeshop_service import MAKESHOP_ERROR_CODES, MakeshopAPIError

logger = logging.getLogger(__name__)


def use_makeshop_rest() -> bool:
    """항상 REST. 레거시 Open API 롤백 경로 비활성."""
    # raw = (os.getenv("MAKESHOP_USE_REST") or "true").strip().lower()
    # if raw in {"0", "false", "no", "off"}:
    #     return False
    return True


def resolve_makeshop_shop_uid(db: Optional[Session] = None) -> str:
    uid = (os.getenv("MAKESHOP_SHOP_UID") or "").strip()
    if uid:
        return uid
    if db is not None:
        from app.models import MakeshopInstalledApp

        row = (
            db.query(MakeshopInstalledApp)
            .order_by(MakeshopInstalledApp.id.desc())
            .first()
        )
        if row and row.shop_uid:
            return str(row.shop_uid)
    raise ValueError(
        "MAKESHOP_SHOP_UID가 없고 makeshop_installed_apps에도 shop_uid가 없습니다."
    )


def _raise_if_legacy_error(response_data: Dict[str, Any]) -> None:
    return_code = str(response_data.get("return_code", "9999"))
    if return_code not in {"0000", "0", "OK", "success", "9011"}:
        error_message = MAKESHOP_ERROR_CODES.get(return_code, "알 수 없는 오류")
        raise MakeshopAPIError(return_code, error_message)


def _fetch_products_legacy_open_api(*, page: int, limit: int) -> Dict[str, Any]:
    # 레거시 Open API 비활성
    # client = MakeshopAPIClient()
    # params = {"limit": limit, "page": page, "mode": "search", "type": "product"}
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
    # return response.json()
    del page, limit
    raise RuntimeError("Makeshop legacy Open API is disabled")


def _fetch_members_legacy_open_api(*, page: int, limit: int) -> Dict[str, Any]:
    # 레거시 Open API 비활성
    # client = MakeshopAPIClient()
    # ...
    del page, limit
    raise RuntimeError("Makeshop legacy Open API is disabled")


def _fetch_orders_legacy_open_api(
    *,
    page: int,
    limit: int,
    inquiry_time_from: str,
    inquiry_time_to: str,
) -> Dict[str, Any]:
    # 레거시 Open API 비활성
    # client = MakeshopAPIClient()
    # ...
    del page, limit, inquiry_time_from, inquiry_time_to
    raise RuntimeError("Makeshop legacy Open API is disabled")


def fetch_products_page(
    *,
    page: int,
    limit: int,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """상품 1페이지 — legacy envelope `{return_code, list, totalCount, ...}`."""
    if use_makeshop_rest():
        # from app.services.makeshop_dual_compare import run_dual_compare_and_notify
        from app.services.makeshop_rest_client import MakeshopRestClient

        client = MakeshopRestClient(shop_uid=resolve_makeshop_shop_uid(db))
        payload = client.get_products_legacy(page=page, limit=limit)
        _raise_if_legacy_error(payload)
        logger.info("[MakeShop] products page=%s via REST", page)
        # 레거시 dual compare 비활성
        # run_dual_compare_and_notify(
        #     resource="products",
        #     page=page,
        #     rest_payload=payload,
        #     legacy_fetcher=lambda: _fetch_products_legacy_open_api(
        #         page=page, limit=limit
        #     ),
        # )
        return payload

    # response_data = _fetch_products_legacy_open_api(page=page, limit=limit)
    # _raise_if_legacy_error(response_data)
    # logger.info("[MakeShop] products page=%s via legacy Open API", page)
    # return response_data
    raise RuntimeError("Makeshop legacy Open API is disabled")


def fetch_members_page(
    *,
    page: int,
    limit: int,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """회원 1페이지 — legacy envelope."""
    if use_makeshop_rest():
        # from app.services.makeshop_dual_compare import run_dual_compare_and_notify
        from app.services.makeshop_rest_client import MakeshopRestClient

        # REST 쪽 limit이 과도하면 거절될 수 있어 상한 적용
        rest_limit = min(int(limit), 1000)
        client = MakeshopRestClient(shop_uid=resolve_makeshop_shop_uid(db))
        payload = client.get_members_legacy(page=page, limit=rest_limit)
        _raise_if_legacy_error(payload)
        logger.info("[MakeShop] members page=%s via REST (limit=%s)", page, rest_limit)
        # run_dual_compare_and_notify(
        #     resource="members",
        #     page=page,
        #     rest_payload=payload,
        #     legacy_fetcher=lambda: _fetch_members_legacy_open_api(
        #         page=page, limit=rest_limit
        #     ),
        # )
        return payload

    # response_data = _fetch_members_legacy_open_api(page=page, limit=limit)
    # _raise_if_legacy_error(response_data)
    # logger.info("[MakeShop] members page=%s via legacy Open API", page)
    # return response_data
    raise RuntimeError("Makeshop legacy Open API is disabled")


def fetch_orders_page(
    *,
    page: int,
    limit: int,
    inquiry_time_from: str,
    inquiry_time_to: str,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """주문 1페이지 — legacy envelope (`list`는 ordernum 키 dict)."""
    if use_makeshop_rest():
        # from app.services.makeshop_dual_compare import run_dual_compare_and_notify
        from app.services.makeshop_rest_client import MakeshopRestClient

        client = MakeshopRestClient(shop_uid=resolve_makeshop_shop_uid(db))
        payload = client.get_orders_v2_legacy(
            inquiry_time_from=inquiry_time_from,
            inquiry_time_to=inquiry_time_to,
            page=page,
            limit=limit,
        )
        _raise_if_legacy_error(payload)
        logger.info("[MakeShop] orders page=%s via REST", page)
        # run_dual_compare_and_notify(
        #     resource="orders",
        #     page=page,
        #     rest_payload=payload,
        #     legacy_fetcher=lambda: _fetch_orders_legacy_open_api(
        #         page=page,
        #         limit=limit,
        #         inquiry_time_from=inquiry_time_from,
        #         inquiry_time_to=inquiry_time_to,
        #     ),
        #     meta=f"{inquiry_time_from} ~ {inquiry_time_to}",
        # )
        return payload

    # response_data = _fetch_orders_legacy_open_api(...)
    # _raise_if_legacy_error(response_data)
    # return response_data
    raise RuntimeError("Makeshop legacy Open API is disabled")


def get_delivery_companies(db: Optional[Session] = None) -> List[Dict[str, Any]]:
    if use_makeshop_rest():
        from app.services.makeshop_rest_client import MakeshopRestClient

        client = MakeshopRestClient(shop_uid=resolve_makeshop_shop_uid(db))
        payload = client.get_delivery_companies()
        data = payload.get("list")
        if data is None and isinstance(payload.get("data"), dict):
            data = payload["data"].get("list")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return list(data.values())
        return []

    # return MakeshopAPIClient().get_delivery_companies()
    raise RuntimeError("Makeshop legacy Open API is disabled")


def health_check(db: Optional[Session] = None) -> bool:
    """연결 확인 — REST만 사용."""
    if use_makeshop_rest():
        from app.services.makeshop_rest_client import MakeshopRestAPIError, MakeshopRestClient

        try:
            client = MakeshopRestClient(shop_uid=resolve_makeshop_shop_uid(db))
            client.issue_access_token()
            client.get_products(page=1, limit=1)
            return True
        except (MakeshopRestAPIError, ValueError, Exception) as exc:
            logger.warning("[MakeShop] REST health_check failed: %s", exc)
            return False
    # return MakeshopAPIClient().health_check()
    raise RuntimeError("Makeshop legacy Open API is disabled")


def register_tracking_by_order(
    order_id: int,
    delicom: int,
    delinum: str,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """송장 등록 — REST만 사용."""
    # if not use_makeshop_rest():
    #     return MakeshopAPIClient().register_tracking_by_order(
    #         order_id=order_id,
    #         delicom=delicom,
    #         delinum=delinum,
    #     )

    from app.database import SessionLocal
    from app.models import Order, OrderItem
    from app.services.makeshop_rest_client import MakeshopRestAPIError, MakeshopRestClient

    session = SessionLocal()
    try:
        order = session.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {
                "success": False,
                "error": f"Order not found: id={order_id}",
                "results": [],
            }
        order_num = str(order.ordernum)
        order_items = (
            session.query(OrderItem)
            .filter(OrderItem.ordernum == order.ordernum)
            .filter(OrderItem.basket_status.isnot(None))
            .filter(OrderItem.basket_status.like("D%"))
            .all()
        )
        item_nums: List[int] = []
        for item in order_items:
            item_num_val = getattr(item, "num", None)
            if item_num_val is not None and str(item_num_val).strip():
                try:
                    item_nums.append(int(str(item_num_val)))
                except (ValueError, TypeError):
                    continue
    finally:
        session.close()

    if not item_nums:
        return {
            "success": False,
            "error": "No items found for this order",
            "results": [],
        }

    try:
        client = MakeshopRestClient(shop_uid=resolve_makeshop_shop_uid(db))
        return client.register_tracking(
            ordernum=order_num,
            item_nums=item_nums,
            delicom=delicom,
            delinum=delinum,
            auto_process_delivery=True,
        )
    except MakeshopRestAPIError as exc:
        logger.error("[MakeShop REST] register_tracking failed: %s", exc)
        return {"success": False, "error": str(exc), "results": []}


def process_shipping(
    items: Sequence[Dict[str, Any]],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """배송 처리 — items: [{order_num, item_num}, ...]. REST만 사용."""
    # if not use_makeshop_rest():
    #     return MakeshopAPIClient().process_shipping(list(items))

    from app.services.makeshop_rest_client import MakeshopRestAPIError, MakeshopRestClient

    datas = [
        {"ordernum": str(it.get("order_num")), "num": str(it.get("item_num"))}
        for it in items
        if it.get("order_num") is not None and it.get("item_num") is not None
    ]
    if not datas:
        return {"success": False, "error": "유효한 항목 없음", "results": []}

    try:
        client = MakeshopRestClient(shop_uid=resolve_makeshop_shop_uid(db))
        payload = client.process_delivery(datas)
        return {
            "success": True,
            "results": datas,
            "raw": payload,
            "error": None,
        }
    except MakeshopRestAPIError as exc:
        return {"success": False, "error": str(exc), "results": []}
