"""
MakeShop REST API 토큰 발급 로컬 검증 스크립트.

프로젝트 루트에서 실행:
    python scripts/test_makeshop_rest_token.py

필수 환경변수 (.env):
    MAKESHOP_CLIENT_ID
    MAKESHOP_CLIENT_SECRET
    MAKESHOP_SHOP_UID
선택:
    MAKESHOP_REST_BASE_URL (기본: https://connect.makeshop.co.kr)
    MAKESHOP_API_TIMEOUT
"""

from __future__ import annotations

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


def _mask(value: str, visible: int = 4) -> str:
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}...{value[-visible:]}"


def _print_public_ip_hint() -> None:
    try:
        import requests

        response = requests.get("https://ifconfig.me", timeout=5)
        response.raise_for_status()
        print(f"[hint] 현재 공인 IP: {response.text.strip()}")
        print("[hint] Developer Center 접근 허용 IP에 위 주소가 등록되어 있는지 확인하세요.")
    except Exception as exc:
        print(f"[hint] 공인 IP 확인 실패: {exc}")


def main() -> int:
    load_dotenv(dotenv_path=os.path.join(ROOT_DIR, ".env"))

    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        print("[error] 필수 환경변수가 없습니다:", ", ".join(missing))
        print("[error] .env 파일에 REST API 인증 정보를 추가한 뒤 다시 실행하세요.")
        return 1

    print("[info] MakeShop REST 토큰 발급 테스트 시작")
    print(f"[info] shop_uid={os.getenv('MAKESHOP_SHOP_UID')}")
    print(f"[info] client_id={_mask(os.getenv('MAKESHOP_CLIENT_ID', ''))}")
    print(f"[info] base_url={os.getenv('MAKESHOP_REST_BASE_URL', 'https://connect.makeshop.co.kr')}")

    from app.services.makeshop_rest_client import MakeshopRestAPIError, MakeshopRestClient

    try:
        client = MakeshopRestClient()
        result = client.issue_access_token(force_refresh=True)
    except MakeshopRestAPIError as exc:
        print(f"[fail] 토큰 발급 실패: {exc}")
        if exc.payload:
            print(f"[fail] payload={exc.payload}")
        _print_public_ip_hint()
        return 1
    except Exception as exc:
        print(f"[fail] 예상치 못한 오류: {exc}")
        _print_public_ip_hint()
        return 1

    access_token = str(result.get("access_token") or "")
    print("[ok] 토큰 발급 성공")
    print(f"[ok] token_type={result.get('token_type')}")
    print(f"[ok] expires_in={result.get('expires_in')}s")
    print(f"[ok] cached={result.get('cached')}")
    print(f"[ok] access_token={_mask(access_token, visible=8)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
