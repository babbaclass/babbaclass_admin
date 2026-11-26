"""
REST 주문 2.0 → 구 Open API adapter 단위 검증 (네트워크 불필요).

    python scripts/test_makeshop_rest_order_adapter.py
"""

from __future__ import annotations

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from app.services.makeshop_rest_order_adapter import adapt_orders_v2_to_legacy


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_order_centric_payload() -> None:
    raw = {
        "data": {
            "list": {
                "20260101000000-1": {
                    "order": {
                        "ordernum": "20260101000000-1",
                        "is_member": "MEMBER",
                        "pay_price": "12345",
                        "order_status": "S",
                        "memo": [{"content": "배송 전 연락"}, {"content": "부재 시 문앞"}],
                        "basket_count": "2",
                    },
                    "payment": {"pay_status": "Y", "in_card_price": "12345"},
                    "product": {
                        "1": {
                            "num": "1",
                            "product_uid": "100",
                            "product_name": "테스트상품",
                            "product_cate1": "006",
                            "basket_stock": "3",
                            "sell_price": "4000",
                            "basket_status": "S11",
                            "deliveryInfo": {
                                "post": "06236",
                                "address": "서울시",
                                "address2": "101",
                                "deli_price": "3000",
                            },
                        }
                    },
                }
            },
            "totalCount": "1",
            "page": "1",
            "count": "1",
        }
    }

    adapted = adapt_orders_v2_to_legacy(raw)
    _assert(adapted["return_code"] == "0000", "return_code")
    _assert("20260101000000-1" in adapted["list"], "list key")

    entry = adapted["list"]["20260101000000-1"]
    order = entry["order"]
    product = entry["product"]["1"]

    _assert(order["is_member"] == 1, f"is_member={order['is_member']}")
    _assert(order["pay_price"] == 12345, f"pay_price={order['pay_price']}")
    _assert(order["memo"] == "배송 전 연락\n부재 시 문앞", f"memo={order['memo']}")
    _assert(product["cate1"] == "006", f"cate1={product.get('cate1')}")
    _assert(product["basket_stock"] == 3, f"basket_stock={product['basket_stock']}")
    _assert(product["sell_price"] == 4000, f"sell_price={product['sell_price']}")
    _assert(entry["payment"]["pay_status"] == "Y", "pay_status")
    _assert(adapted["totalCount"] == 1, "totalCount")


def test_null_data() -> None:
    adapted = adapt_orders_v2_to_legacy({"data": None, "totalCount": 0})
    _assert(adapted["list"] == {}, "empty list")
    _assert(adapted["totalCount"] == 0, "totalCount 0")


def test_guest_and_product_centric_fallback() -> None:
    raw = {
        "list": {
            "row-1": {
                "ordernum": "20260102000000-2",
                "product_uid": "200",
                "product_name": "상품B",
                "product_cate1": "004",
                "basket_stock": "1",
                "sell_price": "9900",
                "basket_status": "D11",
                "is_member": "GUEST",
                "pay_status": "Y",
            }
        }
    }
    adapted = adapt_orders_v2_to_legacy(raw)
    _assert("20260102000000-2" in adapted["list"], "ordernum regroup")
    entry = adapted["list"]["20260102000000-2"]
    _assert(entry["order"]["is_member"] == 0, "GUEST -> 0")
    _assert(entry["payment"]["pay_status"] == "Y", "flat pay_status")
    product = entry["product"]["1"]
    _assert(product["cate1"] == "004", "product_cate1 mapped")
    _assert("is_member" not in product, "order fields removed from product")


def main() -> int:
    test_order_centric_payload()
    test_null_data()
    test_guest_and_product_centric_fallback()
    print("[ok] makeshop_rest_order_adapter tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
