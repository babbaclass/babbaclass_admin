"""Google Chat incoming webhook 알림."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import requests

from app.services.makeshop_rest_stats import format_rest_stats_chat_lines

logger = logging.getLogger(__name__)


def _truthy(name: str, default: str = "false") -> bool:
    return (os.getenv(name) or default).strip().lower() in {"1", "true", "yes", "on"}


def send_google_chat_message(
    message: str,
    *,
    webhook_url: Optional[str] = None,
) -> bool:
    """
    Google Chat incoming webhook으로 텍스트 메시지만 보냅니다. (멘션 없음)

    Env:
      GOOGLE_CHAT_WEBHOOK_URL
    """
    url = (webhook_url or os.getenv("GOOGLE_CHAT_WEBHOOK_URL") or "").strip()
    if not url:
        logger.debug("[Google Chat] webhook URL 없음 — 알림 스킵")
        return False

    try:
        response = requests.post(
            url,
            json={"text": message},
            headers={"Content-Type": "application/json; charset=UTF-8"},
            timeout=10,
        )
        if 200 <= response.status_code < 300:
            logger.info("[Google Chat] message sent")
            return True
        logger.warning(
            "[Google Chat] send failed HTTP %s: %s",
            response.status_code,
            response.text[:200],
        )
    except requests.RequestException as exc:
        logger.warning("[Google Chat] send error: %s", exc)
    return False


def makeshop_rest_chat_enabled() -> bool:
    """MAKESHOP_REST_CHAT_NOTIFY 기본 true (webhook 있을 때만 실제 전송)."""
    return _truthy("MAKESHOP_REST_CHAT_NOTIFY", "true")


def should_notify_makeshop_rest_success(
    method: str,
    *,
    params: Optional[dict] = None,
) -> bool:
    """
    호출 단위 성공 Chat.

    - sync 집계(scope) 안: 기본 off (종료 요약에 건수 포함)
    - sync 밖 쓰기(POST 등): 기본 on (송장/배송 등 요약이 없음)
    - MAKESHOP_REST_CHAT_NOTIFY_SUCCESS 로 강제 on/off 가능
    """
    del params
    if not makeshop_rest_chat_enabled():
        return False

    raw = os.getenv("MAKESHOP_REST_CHAT_NOTIFY_SUCCESS")
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    from app.services.makeshop_rest_stats import get_rest_call_stats_collector

    # sync 중이면 성공은 요약으로만
    if get_rest_call_stats_collector() is not None:
        return False
    # sync 밖 GET도 스팸 방지
    if method.upper() == "GET":
        return False
    return True


def should_notify_makeshop_rest_failure() -> bool:
    """실패는 즉시 Chat (기본 on)."""
    return makeshop_rest_chat_enabled()


def notify_order_sync_result(
    *,
    success: bool,
    inquiry_from: Optional[str] = None,
    inquiry_to: Optional[str] = None,
    api_mode: Optional[str] = None,
    windows: Optional[int] = None,
    total_processed: Optional[int] = None,
    created: Optional[int] = None,
    updated: Optional[int] = None,
    total_pages: Optional[int] = None,
    error: Optional[str] = None,
    sync_window: Optional[dict] = None,
    rest_stats: Optional[Dict[str, Any]] = None,
) -> bool:
    """최근 주문 동기화(조회→DB upsert) 요약을 Google Chat으로 보냅니다."""
    try:
        status = "성공" if success else "실패"
        lines = [
            f"[MakeShop 주문동기화] {status}",
        ]
        if inquiry_from or inquiry_to:
            lines.append(f"• 기간: {inquiry_from or '?'} ~ {inquiry_to or '?'}")
        if sync_window:
            mode = sync_window.get("mode")
            days = sync_window.get("days_back")
            if mode or days:
                lines.append(f"• 모드: {mode or '-'} (days={days or '-'})")
        if api_mode:
            lines.append(f"• API: {api_mode}")
        if windows is not None:
            lines.append(f"• 일 구간 수: {windows}")
        if total_pages is not None:
            lines.append(f"• 조회 페이지: {total_pages}")
        lines.extend(format_rest_stats_chat_lines(rest_stats))
        if total_processed is not None:
            lines.append(f"• DB 처리: {total_processed}건")
        if created is not None:
            lines.append(f"• 신규: {created}")
        if updated is not None:
            lines.append(f"• 수정: {updated}")
        if error:
            lines.append(f"• 오류: {error[:400]}")
        return send_google_chat_message("\n".join(lines))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Google Chat] notify_order_sync_result error: %s", exc)
        return False


def notify_makeshop_sync_result(
    *,
    resource: str,
    success: bool,
    api_mode: Optional[str] = None,
    total_processed: Optional[int] = None,
    created: Optional[int] = None,
    updated: Optional[int] = None,
    total_pages: Optional[int] = None,
    error: Optional[str] = None,
    rest_stats: Optional[Dict[str, Any]] = None,
) -> bool:
    """상품/회원 등 동기화 종료 요약."""
    try:
        status = "성공" if success else "실패"
        title = {
            "products": "상품동기화",
            "members": "회원동기화",
            "orders": "주문동기화",
        }.get(resource, f"{resource}동기화")
        lines = [f"[MakeShop {title}] {status}"]
        if api_mode:
            lines.append(f"• API: {api_mode}")
        if total_pages is not None:
            lines.append(f"• 조회 페이지: {total_pages}")
        lines.extend(format_rest_stats_chat_lines(rest_stats))
        if total_processed is not None:
            lines.append(f"• DB 처리: {total_processed}건")
        if created is not None:
            lines.append(f"• 신규: {created}")
        if updated is not None:
            lines.append(f"• 수정: {updated}")
        if error:
            lines.append(f"• 오류: {error[:400]}")
        return send_google_chat_message("\n".join(lines))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Google Chat] notify_makeshop_sync_result error: %s", exc)
        return False


def format_makeshop_rest_chat_message(
    *,
    success: bool,
    method: str,
    path: str,
    shop_uid: Optional[str] = None,
    status_code: Optional[int] = None,
    code: Optional[str] = None,
    detail: Optional[str] = None,
    elapsed_ms: Optional[int] = None,
    extra: Optional[str] = None,
) -> str:
    status = "성공" if success else "실패"
    lines = [
        f"[MakeShop REST] {status}",
        f"• {method.upper()} {path}",
    ]
    if shop_uid:
        lines.append(f"• shop_uid: {shop_uid}")
    if status_code is not None:
        lines.append(f"• HTTP: {status_code}")
    if code:
        lines.append(f"• code: {code}")
    if elapsed_ms is not None:
        lines.append(f"• 소요: {elapsed_ms}ms")
    if detail:
        lines.append(f"• 상세: {detail[:300]}")
    if extra:
        lines.append(f"• {extra}")
    return "\n".join(lines)


def notify_makeshop_rest_call(
    *,
    success: bool,
    method: str,
    path: str,
    shop_uid: Optional[str] = None,
    status_code: Optional[int] = None,
    code: Optional[str] = None,
    detail: Optional[str] = None,
    elapsed_ms: Optional[int] = None,
    params: Optional[dict] = None,
    extra: Optional[str] = None,
) -> bool:
    """
    MakeShop REST 호출 단위 알림.
    - 집계(scope): 항상 record
    - Chat: 실패만 기본 전송 (성공은 sync 요약으로)
    """
    try:
        from app.services.makeshop_rest_stats import record_rest_call

        record_rest_call(
            success=success,
            method=method,
            path=path,
            status_code=status_code,
            code=code,
            detail=detail,
        )

        if success:
            if not should_notify_makeshop_rest_success(method, params=params):
                return False
        elif not should_notify_makeshop_rest_failure():
            return False

        message = format_makeshop_rest_chat_message(
            success=success,
            method=method,
            path=path,
            shop_uid=shop_uid,
            status_code=status_code,
            code=code,
            detail=detail,
            elapsed_ms=elapsed_ms,
            extra=extra,
        )
        return send_google_chat_message(message)
    except Exception as exc:  # noqa: BLE001 — 알림 실패가 API를 깨면 안 됨
        logger.warning("[Google Chat] notify_makeshop_rest_call error: %s", exc)
        return False
