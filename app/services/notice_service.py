"""공지사항 노출·표시 헬퍼"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def notice_reference_date(now: datetime | None = None) -> date:
    if now is None:
        return datetime.now(KST).date()
    if now.tzinfo is None:
        return now.replace(tzinfo=ZoneInfo("UTC")).astimezone(KST).date()
    return now.astimezone(KST).date()


def notice_is_live(notice: Any, on_date: date | None = None) -> bool:
    """노출 ON이고 기간 내이면 True (노출 상태 O)."""
    if not bool(getattr(notice, "is_exposed", False)):
        return False
    visible_from = getattr(notice, "visible_from", None)
    visible_to = getattr(notice, "visible_to", None)
    if not visible_from or not visible_to:
        return False
    ref = on_date or notice_reference_date()
    return visible_from <= ref <= visible_to


def format_notice_period(notice: Any) -> str:
    visible_from = getattr(notice, "visible_from", None)
    visible_to = getattr(notice, "visible_to", None)
    if not visible_from or not visible_to:
        return "-"
    return (
        f"{visible_from.strftime('%Y.%m.%d')}~{visible_to.strftime('%Y.%m.%d')}"
    )


def format_notice_exposure_status(notice: Any, on_date: date | None = None) -> str:
    return "O" if notice_is_live(notice, on_date) else "X"


def fetch_live_notices(db: Any, on_date: date | None = None, limit: int | None = None) -> list[Any]:
    """노출 ON이고 기간 내인 공지를 최신순으로 조회."""
    from app.models import Notice

    ref = on_date or notice_reference_date()
    query = (
        db.query(Notice)
        .filter(
            Notice.is_exposed.is_(True),
            Notice.visible_from <= ref,
            Notice.visible_to >= ref,
        )
        .order_by(Notice.notice_id.desc())
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def render_notice_banner_html(notices: list[Any]) -> str:
    """정산 개요 등에 삽입할 공지 배너 HTML."""
    if not notices:
        return ""
    template = _jinja_env.get_template("partials/notice_banner.html")
    return template.render(live_notices=notices)
