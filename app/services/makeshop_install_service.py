"""
MakeShop APP 설치 온보딩.

Docs: https://developer.makeshop.co.kr/docs/guide/app/install
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import MakeshopInstalledApp
from app.services.makeshop_hmac import verify_makeshop_hmac
from app.services.makeshop_rest_client import MakeshopRestAPIError, MakeshopRestClient

logger = logging.getLogger(__name__)


def _parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def upsert_installed_app(
    db: Session,
    *,
    shop_uid: str,
    action_type: str,
    app_info: dict[str, Any],
) -> MakeshopInstalledApp:
    row = (
        db.query(MakeshopInstalledApp)
        .filter(MakeshopInstalledApp.shop_uid == shop_uid)
        .first()
    )
    if not row:
        row = MakeshopInstalledApp(shop_uid=shop_uid)
        db.add(row)

    row.client_id = app_info.get("client_id") or row.client_id
    row.app_name = app_info.get("app_name") or row.app_name
    row.app_url = app_info.get("app_url") or row.app_url
    row.action_type = action_type
    row.installed_at = _parse_date(app_info.get("installed_at")) or row.installed_at
    row.expired_at = _parse_date(app_info.get("expired_at")) or row.expired_at
    row.raw_payload = json.dumps(app_info, ensure_ascii=False)
    db.commit()
    db.refresh(row)
    return row


def process_makeshop_install(
    db: Session,
    *,
    shop_uid: str,
    timestamp: str,
    action_type: str,
    received_hmac: str,
) -> dict[str, Any]:
    """
    HMAC 검증 → 설치 앱 정보 조회 → DB 저장.

    검증 실패 시 ValueError("invalid") 를 올려 라우터에서 사유를 숨긴다.
    """
    if not verify_makeshop_hmac(shop_uid, timestamp, action_type, received_hmac):
        raise ValueError("invalid")

    client = MakeshopRestClient(shop_uid=shop_uid, require_shop_uid=True)
    try:
        app_info = client.get_installed_app(shop_uid)
    except MakeshopRestAPIError as exc:
        logger.error("[MakeShop Install] installed-app lookup failed: %s", exc)
        raise

    row = upsert_installed_app(
        db,
        shop_uid=shop_uid,
        action_type=action_type,
        app_info=app_info,
    )

    logger.info(
        "[MakeShop Install] onboarded shop_uid=%s action=%s expired_at=%s",
        shop_uid,
        action_type,
        row.expired_at,
    )
    return {
        "success": True,
        "shop_uid": row.shop_uid,
        "action_type": action_type,
        "app_name": row.app_name,
        "installed_at": row.installed_at.isoformat() if row.installed_at else None,
        "expired_at": row.expired_at.isoformat() if row.expired_at else None,
        "message": f"Welcome, {shop_uid}! App installation and verification complete.",
    }
