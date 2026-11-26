"""
MakeShop APP 설치 콜백 HMAC 검증.

Docs: https://developer.makeshop.co.kr/docs/guide/app/install
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

logger = logging.getLogger(__name__)

# 가이드 권장: 현재 시각과 timestamp 차이가 5분(300,000ms) 초과 시 만료
DEFAULT_HMAC_MAX_AGE_MS = 300_000


def verify_makeshop_hmac(
    shop_uid: str,
    timestamp: str,
    action_type: str,
    received_hmac: str,
    *,
    client_secret: str | None = None,
    max_age_ms: int = DEFAULT_HMAC_MAX_AGE_MS,
) -> bool:
    """
    MakeShop APP URL 쿼리 파라미터 HMAC-SHA256 무결성 검증.

    서명 메시지: ``{shop_uid}:{timestamp}:{action_type}``
    """
    secret = client_secret if client_secret is not None else os.getenv("MAKESHOP_CLIENT_SECRET")
    if not secret:
        logger.error("[MakeShop HMAC] MAKESHOP_CLIENT_SECRET is not configured")
        return False

    if not shop_uid or not timestamp or not action_type or not received_hmac:
        return False

    try:
        current_ms = int(time.time() * 1000)
        request_ms = int(timestamp)
        if abs(current_ms - request_ms) > max_age_ms:
            logger.warning(
                "[MakeShop HMAC] timestamp expired (delta_ms=%s)",
                abs(current_ms - request_ms),
            )
            return False
    except (TypeError, ValueError):
        return False

    message = f"{shop_uid}:{timestamp}:{action_type}".encode("utf-8")
    computed = hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, received_hmac.strip().lower())
