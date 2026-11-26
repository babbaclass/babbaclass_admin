"""
MakeShop REST API 주문 2.0 조회 로컬 검증 스크립트.

프로젝트 루트에서 실행:
    python scripts/test_makeshop_rest_orders.py
    python scripts/test_makeshop_rest_orders.py --days 7 --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv

REQUIRED_ENV_VARS = (
    "MAKESHOP_CLIENT_ID",
    "MAKESHOP_CLIENT_SECRET",
    "MAKESHOP_SHOP_UID",
)


def _count_orders(data: Any) -> int | None:
    if data is None:
        return 0
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("list", "orders", "items", "data"):
            if key in data:
                return _count_orders(data[key])
        return len(data)
    return None


def _preview_orders(data: Any, limit: int = 3) -> str:
    if isinstance(data, list):
        return json.dumps(data[:limit], ensure_ascii=False, indent=2)
    if isinstance(data, dict):
        for key in ("list", "orders", "items", "data"):
            if key in data:
                return _preview_orders(data[key], limit=limit)
        return json.dumps(dict(list(data.items())[:limit]), ensure_ascii=False, indent=2)
    return json.dumps(data, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description="MakeShop REST 주문 2.0 조회 테스트")
    parser.add_argument("--days", type=int, default=7, help="조회 기간(일), 최대 30")
    parser.add_argument("--limit", type=int, default=5, help="페이지당 건수")
    parser.add_argument("--page", type=int, default=1, help="페이지 번호")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="구 Open API 호환 payload로 변환해 출력",
    )
    args = parser.parse_args()

    load_dotenv(dotenv_path=os.path.join(ROOT_DIR, ".env"))

    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        print("[error] 필수 환경변수가 없습니다:", ", ".join(missing))
        return 1

    days = max(1, min(args.days, 30))
    now = datetime.now()
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    inquiry_from = start.strftime("%Y-%m-%d %H:%M:%S")
    inquiry_to = end.strftime("%Y-%m-%d %H:%M:%S")

    print("[info] MakeShop REST 주문 2.0 조회 테스트 시작")
    print(f"[info] shop_uid={os.getenv('MAKESHOP_SHOP_UID')}")
    print(f"[info] period={inquiry_from} ~ {inquiry_to}")
    print(f"[info] page={args.page}, limit={args.limit}")

    from app.services.makeshop_rest_client import MakeshopRestAPIError, MakeshopRestClient

    try:
        client = MakeshopRestClient()
        client.issue_access_token(force_refresh=True)
        if args.legacy:
            payload = client.get_orders_v2_legacy(
                inquiry_time_from=inquiry_from,
                inquiry_time_to=inquiry_to,
                page=args.page,
                limit=args.limit,
            )
        else:
            payload = client.get_orders_v2(
                inquiry_time_from=inquiry_from,
                inquiry_time_to=inquiry_to,
                page=args.page,
                limit=args.limit,
            )
    except MakeshopRestAPIError as exc:
        print(f"[fail] 주문 조회 실패: {exc}")
        if exc.payload:
            print("[fail] payload=", json.dumps(exc.payload, ensure_ascii=False, indent=2))
        return 1
    except Exception as exc:
        print(f"[fail] 예상치 못한 오류: {exc}")
        return 1

    print("[ok] 주문 2.0 조회 성공")
    if args.legacy:
        print(f"[ok] return_code={payload.get('return_code')}")
        print(f"[ok] totalCount={payload.get('totalCount')}")
        print(f"[ok] count={payload.get('count')}")
        data = payload.get("list")
    else:
        print(f"[ok] success={payload.get('success')}")
        print(f"[ok] code={payload.get('code')}")
        print(f"[ok] message={payload.get('message')}")
        data = payload.get("data") if "data" in payload else payload.get("list")

    count = _count_orders(data)
    if count is not None:
        print(f"[ok] order_count={count}")
    else:
        print("[ok] order_count=unknown")

    print("[ok] preview=")
    print(_preview_orders(data, limit=3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
