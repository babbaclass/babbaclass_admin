"""
REST 상품/회원 adapter 단위 검증 (네트워크 불필요).

    python scripts/test_makeshop_rest_catalog_adapters.py
"""

from __future__ import annotations

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from app.services.makeshop_rest_member_adapter import adapt_members_to_legacy
from app.services.makeshop_rest_product_adapter import adapt_products_to_legacy


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_products() -> None:
    raw = {
        "return_code": "0000",
        "totalCount": "1",
        "page": "1",
        "count": "1",
        "list": [
            {
                "uid": "100",
                "product_name": "테스트",
                "sellprice": "12000",
                "buyprice": "8000",
                "cate1": "006",
                "quantity": "Unlimited",
                "keywords": "수학,바빠",
                "virtual_cate": [{"cate1": "001"}, {"cate1": "002"}],
            }
        ],
    }
    adapted = adapt_products_to_legacy(raw)
    _assert(adapted["return_code"] == "0000", "return_code")
    item = adapted["list"][0]
    _assert(item["sellprice"] == 12000, f"sellprice={item['sellprice']}")
    _assert(item["keyword"] == "수학,바빠", f"keyword={item.get('keyword')}")
    _assert(item["virtual_cate"] == "001,002", f"virtual_cate={item.get('virtual_cate')}")
    _assert(item["quantity"] == "Unlimited", "quantity preserved for parse_quantity")


def test_members() -> None:
    raw = {
        "data": {
            "return_code": "0000",
            "list": [
                {
                    "id": "teacher01",
                    "hname": "홍길동",
                    "grade": "3",
                    "order_count": "12",
                    "company_info": {
                        "company_name": "테스트학원",
                        "company_num": "123-45-67890",
                    },
                }
            ],
            "totalCount": 1,
            "page": 1,
            "count": 1,
        }
    }
    adapted = adapt_members_to_legacy(raw)
    item = adapted["list"][0]
    _assert(item["id"] == "teacher01", "id")
    _assert(item["grade"] == 3, f"grade={item['grade']}")
    _assert(item["order_count"] == 12, f"order_count={item['order_count']}")
    _assert(item["company_name"] == "테스트학원", "company_name flattened")


def main() -> int:
    test_products()
    test_members()
    print("[ok] product/member adapter tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
