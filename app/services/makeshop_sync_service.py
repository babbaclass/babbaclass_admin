"""Makeshop 통합 동기화 — 주문 조회 구간·페이지네이션 헬퍼."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator, Optional

# MakeShop 주문 조회 최대 약 30일. 경계(9018) 여유를 위해 초 단위로 맞춤.
RECENT_ORDER_REFRESH_DAYS = 30


def _fmt_kst(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def resolve_order_sync_window(
    now_kst: datetime,
    inquiry_time_from: Optional[str],
    inquiry_time_to: Optional[str],
) -> tuple[str, str, dict[str, str]]:
    """
    주문 동기화 구간.

    - 기본(스케줄러): 최근 30일 (Makeshop 30일 제한 내)
    - 수동: 요청한 InquiryTimeFrom/To 그대로 사용
    """
    if inquiry_time_from is not None and inquiry_time_from != "2025-01-01 00:00:00":
        return (
            inquiry_time_from,
            inquiry_time_to or _fmt_kst(now_kst),
            {"mode": "explicit"},
        )

    to_dt = now_kst - timedelta(minutes=1)
    from_dt = to_dt - timedelta(days=RECENT_ORDER_REFRESH_DAYS)
    return (
        _fmt_kst(from_dt),
        _fmt_kst(to_dt),
        {"mode": "recent_30d", "days_back": str(RECENT_ORDER_REFRESH_DAYS)},
    )


def iter_inquiry_day_windows(
    inquiry_time_from: str,
    inquiry_time_to: str,
) -> Iterator[tuple[str, str]]:
    """
    조회 구간을 캘린더 일 단위로 분할한다.

    MakeShop 주문 2.0 권장(데이터 많을 때 1일) + totalCount 과소 보고 시 누락 완화.
    """
    start = datetime.strptime(inquiry_time_from, "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(inquiry_time_to, "%Y-%m-%d %H:%M:%S")
    if end < start:
        return

    # 같은 날이면 원본 구간 한 번만
    if start.date() == end.date():
        yield inquiry_time_from, inquiry_time_to
        return

    cursor = start
    while cursor <= end:
        day_start = cursor.replace(hour=0, minute=0, second=0, microsecond=0)
        if cursor.date() == start.date():
            day_start = cursor
        day_end = cursor.replace(hour=23, minute=59, second=59, microsecond=0)
        if day_end > end:
            day_end = end
        if day_start <= day_end:
            yield _fmt_kst(day_start), _fmt_kst(day_end)
        cursor = (cursor + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        if cursor.date() > end.date():
            break


def should_fetch_next_order_page(
    *,
    page_count: int,
    limit: int,
    fetched_in_window: int,
    total_count_api: int,
) -> bool:
    """
    다음 주문 페이지 조회 여부.

    구 로직 `page * limit >= totalCount` 는 page1에 count<<limit 이면
    totalCount가 더 커도 조기 종료하는 버그가 있어, 누적 건수 기준으로 판단한다.
    """
    if page_count <= 0:
        return False
    if total_count_api > 0 and fetched_in_window >= total_count_api:
        return False
    if page_count < limit:
        # 부분 페이지라도 API totalCount가 더 있으면 다음 페이지 시도
        return total_count_api > 0 and fetched_in_window < total_count_api
    return True
