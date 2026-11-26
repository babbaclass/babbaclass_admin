"""
MakeShop REST 상품/회원/택배사 조회 로컬 스모크 테스트.

    python scripts/test_makeshop_rest_catalog.py
    python scripts/test_makeshop_rest_catalog.py --legacy
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv

REQUIRED_ENV_VARS = (
    "MAKESHOP_CLIENT_ID",
    "MAKESHOP_CLIENT_SECRET",
    "MAKESHOP_SHOP_UID",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="MakeShop REST 상품/회원/택배사 테스트")
    parser.add_argument("--legacy", action="store_true", help="legacy adapter 출력")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    load_dotenv(dotenv_path=os.path.join(ROOT_DIR, ".env"))
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        print("[error] 필수 환경변수가 없습니다:", ", ".join(missing))
        return 1

    from app.services.makeshop_rest_client import MakeshopRestAPIError, MakeshopRestClient

    client = MakeshopRestClient()
    try:
        client.issue_access_token(force_refresh=True)

        products = (
            client.get_products_legacy(limit=args.limit)
            if args.legacy
            else client.get_products(limit=args.limit)
        )
        members = (
            client.get_members_legacy(limit=args.limit)
            if args.legacy
            else client.get_users(limit=args.limit)
        )
        companies = client.get_delivery_companies()
    except MakeshopRestAPIError as exc:
        print(f"[fail] {exc}")
        if exc.payload:
            print(json.dumps(exc.payload, ensure_ascii=False, indent=2)[:2000])
        return 1

    def _len(payload: dict) -> int:
        data = payload.get("list")
        if data is None and isinstance(payload.get("data"), dict):
            data = payload["data"].get("list")
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return len(data)
        return 0

    print("[ok] products=", _len(products), "keys=", list(products.keys())[:8])
    print("[ok] members=", _len(members), "keys=", list(members.keys())[:8])
    company_list = companies.get("list") or (companies.get("data") or {}).get("list") or []
    print("[ok] delivery_companies=", len(company_list) if isinstance(company_list, list) else company_list)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
