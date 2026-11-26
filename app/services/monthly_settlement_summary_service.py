"""월 정산 요약표 공통 로직"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.exc import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

MONTHLY_SETTLEMENT_SUMMARY_EXCLUDED_REGIONS = frozenset({
    "어드민_본사관리자",
    "본사직영",
    "본사직영 2",
})


def normalize_payment_date_for_input(value: str | None) -> str:
    """date input용 YYYY-MM-DD (기존 YYYY.MM.DD 등 호환)"""
    if not value:
        return ""
    s = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    m = re.fullmatch(r"(\d{4})[./](\d{1,2})[./](\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def format_payment_date_display(value: str | None) -> str:
    """표시용 YYYY.MM.DD"""
    iso = normalize_payment_date_for_input(value)
    if not iso:
        return ""
    y, m, d = iso.split("-")
    return f"{y}.{m}.{d}"


def fetch_monthly_payment_note_map(db, year: int, month: int) -> dict[int, str]:
    """월 정산 요약표 지급일 메모 조회 (하위 호환)"""
    status_map = fetch_monthly_payment_status_map(db, year, month)
    return {cid: data.get("payment_note", "") for cid, data in status_map.items()}


def fetch_monthly_payment_status_map(db, year: int, month: int) -> dict[int, dict[str, str]]:
    """월 정산 요약표 지급일·비고 조회"""
    from app.models import MonthlySettlementPaymentStatus

    try:
        rows = (
            db.query(
                MonthlySettlementPaymentStatus.company_id,
                MonthlySettlementPaymentStatus.payment_note,
                MonthlySettlementPaymentStatus.remark,
            )
            .filter(
                MonthlySettlementPaymentStatus.year == year,
                MonthlySettlementPaymentStatus.month == month,
            )
            .all()
        )
        return {
            int(cid): {
                "payment_note": note or "",
                "remark": remark or "",
            }
            for cid, note, remark in rows
        }
    except (OperationalError, ProgrammingError) as exc:
        logger.warning(
            "monthly_settlement_payment_status remark query failed, falling back: %s",
            exc,
        )
        try:
            rows = (
                db.query(
                    MonthlySettlementPaymentStatus.company_id,
                    MonthlySettlementPaymentStatus.payment_note,
                )
                .filter(
                    MonthlySettlementPaymentStatus.year == year,
                    MonthlySettlementPaymentStatus.month == month,
                )
                .all()
            )
            return {
                int(cid): {
                    "payment_note": note or "",
                    "remark": "",
                }
                for cid, note in rows
            }
        except (OperationalError, ProgrammingError) as fallback_exc:
            logger.warning(
                "monthly_settlement_payment_status table unavailable (run alembic upgrade head): %s",
                fallback_exc,
            )
            return {}


def format_settlement_type(user: Any | None) -> str:
    """정산유형 표시: 개인 / 사업자"""
    if not user:
        return "-"
    personal = bool(getattr(user, "settlement_personal", False))
    business = bool(getattr(user, "settlement_business", False))
    if personal and business:
        return "개인/사업자"
    if personal:
        return "개인"
    if business:
        return "사업자"
    return "-"


def format_settlement_type_statement_display(user: Any | None) -> str:
    """정산서 정산 유형 표시."""
    if not user:
        return "-"
    personal = bool(getattr(user, "settlement_personal", False))
    business = bool(getattr(user, "settlement_business", False))
    if business:
        return "[사업자](정산금 지급 전까지 세금계산서 발행 필수)"
    if personal:
        return "[개인]"
    return "-"


def format_settlement_result(payment_date: str | None) -> str:
    """정산결과: 지급일이 있으면 지급완료, 없으면 빈칸."""
    if normalize_payment_date_for_input(payment_date):
        return "지급완료"
    return ""


def format_display_name(user: Any | None) -> str:
    """이름 칸: 정산유형이 '사업자'이면 사업자명, 그 외에는 개인 이름."""
    if not user:
        return "-"
    personal_name = (getattr(user, "name", "") or "").strip() or "-"
    if format_settlement_type(user) != "사업자":
        return personal_name
    business_name = (getattr(user, "business_name", "") or "").strip()
    return business_name or personal_name


def format_bank_name(user: Any | None) -> str:
    """은행명."""
    if not user:
        return "-"
    bank = (getattr(user, "bank_name", "") or "").strip()
    return bank or "-"


def format_bank_account(user: Any | None) -> str:
    """계좌번호."""
    if not user:
        return "-"
    account = (getattr(user, "bank_account", "") or "").strip()
    return account or "-"


def format_account_info(user: Any | None) -> str:
    """계좌 정보: 은행명 + 계좌번호 (하위 호환)"""
    if not user:
        return "-"
    bank = format_bank_name(user)
    account = format_bank_account(user)
    if bank != "-" and account != "-":
        return f"{bank} {account}"
    if bank != "-":
        return bank
    if account != "-":
        return account
    return "-"


def _to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # DB/server_default(func.now())는 UTC naive인 경우가 많음
        return dt.replace(tzinfo=timezone.utc).astimezone(KST)
    return dt.astimezone(KST)


def max_confirmable_settlement_period(now: datetime | None = None) -> tuple[int, int]:
    """
    조회·확인 가능한 최대 정산 월 (당월 정산서는 익월부터 확인).
    예: 2026년 6월 10일 → (2026, 5)까지
    """
    now_kst = _to_kst(now) if now is not None else datetime.now(KST)
    year, month = now_kst.year, now_kst.month
    if month == 1:
        return year - 1, 12
    return year, month - 1


def is_settlement_period_confirmable(
    year: int,
    month: int,
    now: datetime | None = None,
) -> bool:
    """정산서 조회·확인 가능 여부 (전월까지만)."""
    max_y, max_m = max_confirmable_settlement_period(now)
    return (int(year), int(month)) <= (max_y, max_m)


ISSUED_STATEMENT_STATUSES = ("ISSUED", "CONFIRMED", "PAID")


def is_company_monthly_statement_issued(
    db,
    *,
    company_id: int,
    year: int,
    month: int,
) -> bool:
    """
    지사 정산서 발행 여부.

    목록 월 그리드와 동일: 소속 원장(role_id=3)의 monthly settlement가
    ISSUED/CONFIRMED/PAID 중 하나라도 있으면 발행된 것으로 본다.
    """
    from sqlalchemy import extract, func

    from app.models import Settlement, User

    if not company_id:
        return False

    issued_count = (
        db.query(func.count(Settlement.settlement_id))
        .join(User, User.user_id == Settlement.user_id)
        .filter(
            User.company_id == int(company_id),
            User.role_id == 3,
            Settlement.settlement_type == "monthly",
            extract("year", Settlement.settlement_date) == int(year),
            extract("month", Settlement.settlement_date) == int(month),
            Settlement.statement_status.in_(ISSUED_STATEMENT_STATUSES),
        )
        .scalar()
    )
    return int(issued_count or 0) > 0


def resolve_statement_company_id_for_user(
    user: Any,
    *,
    company_id_param: int | None = None,
) -> int | None:
    """정산서 조회 대상 company_id (본사는 쿼리 company_id 우선)."""
    role_id = int(getattr(user, "role_id", 0) or 0)
    if role_id == 1 and company_id_param:
        return int(company_id_param)
    company_id = getattr(user, "company_id", None)
    if company_id:
        return int(company_id)
    return None


def months_selectable_for_settlement_year(
    year: int,
    now: datetime | None = None,
) -> list[int]:
    """연도별 월 필터에 노출할 월 목록."""
    max_y, max_m = max_confirmable_settlement_period(now)
    if year < max_y:
        return list(range(1, 13))
    if year > max_y:
        return []
    return list(range(1, max_m + 1))


def filter_confirmable_month_entries(
    entries: list[dict[str, Any]],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """정산서 목록 API용 (year/month dict) 전월까지만 남김."""
    max_y, max_m = max_confirmable_settlement_period(now)
    return [
        entry
        for entry in entries
        if (int(entry["year"]), int(entry["month"])) <= (max_y, max_m)
    ]


def _default_issuance_month(settlement_year: int, settlement_month: int) -> tuple[int, int]:
    """정산 월 익월에 정산서 발행 (매월 10일 배치 기준)."""
    if settlement_month == 12:
        return settlement_year + 1, 1
    return settlement_year, settlement_month + 1


def _issuance_month(
    issued_at: datetime | None,
    settlement_year: int,
    settlement_month: int,
) -> tuple[int, int]:
    """
    정산서 확인 기간의 발행월.

    지급/이월 구간은 정산 익월 10~15일로 고정한다.
    (statement_issued_at은 배치·재집계 시점마다 달라질 수 있어 기간 계산에 쓰지 않음)
    """
    _ = issued_at
    return _default_issuance_month(settlement_year, settlement_month)


def resolve_confirmation_window(
    issued_at: datetime | None,
    year: int,
    month: int,
) -> tuple[datetime, datetime, datetime]:
    """
    [정산서확인] 지급/이월 반영 기간 (KST).

    - 지급: 발행월 10일 00:00 ~ 15일 23:59
    - 이월: 16일 00:00 이후 확인한 경우
    """
    issue_year, issue_month = _issuance_month(issued_at, year, month)
    window_start = datetime(issue_year, issue_month, 10, 0, 0, 0, tzinfo=KST)
    window_end = datetime(issue_year, issue_month, 15, 23, 59, 59, tzinfo=KST)
    carryover_start = datetime(issue_year, issue_month, 16, 0, 0, 0, tzinfo=KST)
    return window_start, window_end, carryover_start


def resolve_confirmation_deadline(
    issued_at: datetime | None,
    year: int,
    month: int,
) -> datetime:
    """지급 처리 마감: 발행월 15일 23:59:59 (KST)."""
    _, window_end, _ = resolve_confirmation_window(issued_at, year, month)
    return window_end


def is_confirmation_within_payment_window(
    confirmed_at: datetime,
    issued_at: datetime | None,
    year: int,
    month: int,
) -> bool:
    """확인일(KST)이 지급 기간(발행월 10~15일)이면 True."""
    confirmed_d = _to_kst(confirmed_at).date()
    if _is_kst_date_in_issuance_payment_period(confirmed_d, year, month):
        return True
    if (
        date(confirmed_d.year, confirmed_d.month, 10)
        <= confirmed_d
        <= date(confirmed_d.year, confirmed_d.month, 15)
        and (year, month) == (confirmed_d.year, confirmed_d.month)
    ):
        return True
    return False


def is_moment_within_payment_window(
    settlement_year: int,
    settlement_month: int,
    moment: datetime | None = None,
) -> bool:
    """현재(또는 지정) 시각이 지급 기간 내인지 — 확인 버튼 팝업용."""
    moment_kst = _to_kst(moment) if moment is not None else datetime.now(KST)
    return is_confirmation_within_payment_window(
        moment_kst, None, settlement_year, settlement_month
    )


def _is_kst_date_in_issuance_payment_period(
    confirmed_d: date,
    settlement_year: int,
    settlement_month: int,
) -> bool:
    """확인일이 해당 정산의 발행월 10~15일이면 True."""
    issue_year, issue_month = _issuance_month(None, settlement_year, settlement_month)
    return (
        date(issue_year, issue_month, 10)
        <= confirmed_d
        <= date(issue_year, issue_month, 15)
    )


def compute_confirmation_category(
    confirmed_at: datetime,
    settlement_year: int,
    settlement_month: int,
) -> str:
    """
    확인 시각 기준 지급/이월 분류.

    지급: 정산서 발행월 10~15일(KST)에 확인
    이월: 그 외 (16일 이후 등)
    """
    confirmed_d = _to_kst(confirmed_at).date()

    if _is_kst_date_in_issuance_payment_period(
        confirmed_d, settlement_year, settlement_month
    ):
        return "지급"

    # 확인일이 당월 10~15인데 정산월이 발행월로 잘못 저장된 경우
    # (예: 6/10에 5월 정산서 확인인데 month=6으로 저장)
    if (
        date(confirmed_d.year, confirmed_d.month, 10)
        <= confirmed_d
        <= date(confirmed_d.year, confirmed_d.month, 15)
        and (settlement_year, settlement_month) == (confirmed_d.year, confirmed_d.month)
    ):
        return "지급"

    return "이월"


def resolve_confirmation_status(
    *,
    confirmation: Any | None,
    issued_at: datetime | None,
    year: int,
    month: int,
    now: datetime | None = None,
) -> str:
    """
    정산확인 상태: 미지급 / 지급 / 이월
    - 지급: 발행월 10~15일 사이 확인
    - 이월: 16일 이후 확인한 경우만
    - 미지급: 미확인 (기한 경과 후에도 미확인이면 미지급 유지)
    """
    if confirmation is not None:
        confirmed_at = getattr(confirmation, "confirmed_at", None)
        if confirmed_at:
            return compute_confirmation_category(confirmed_at, year, month)
        return "미지급"

    return "미지급"


def backfill_confirmation_categories(
    db,
    *,
    dry_run: bool = True,
    only_kst_date: date | None = None,
) -> dict[str, int]:
    """
    기존 정산서 확인 기록의 confirmation_category 일괄 보정.

    only_kst_date: 지정 시 해당 KST 날짜에 확인한 기록만 처리 (예: 2026-06-10)
    """
    from app.models import SettlementStatementConfirmation, User

    query = (
        db.query(SettlementStatementConfirmation)
        .join(User, SettlementStatementConfirmation.user_id == User.user_id)
        .filter(User.role_id == 2)
    )
    confirmations = query.all()

    stats = {
        "total": 0,
        "updated_to_payment": 0,
        "updated_to_carryover": 0,
        "unchanged": 0,
        "details": [],
    }

    for confirmation in confirmations:
        confirmed_at = getattr(confirmation, "confirmed_at", None)
        if not confirmed_at:
            continue

        confirmed_kst = _to_kst(confirmed_at)
        if only_kst_date and confirmed_kst.date() != only_kst_date:
            continue

        stats["total"] += 1
        settle_year = int(confirmation.year)
        settle_month = int(confirmation.month)
        new_category = compute_confirmation_category(
            confirmed_at,
            settle_year,
            settle_month,
        )
        old_category = getattr(confirmation, "confirmation_category", None)

        if old_category != new_category:
            stats["details"].append({
                "user_id": confirmation.user_id,
                "period": f"{settle_year}-{settle_month:02d}",
                "confirmed_kst": confirmed_kst.isoformat(),
                "old": old_category,
                "new": new_category,
            })

        if old_category == new_category:
            stats["unchanged"] += 1
            continue

        if not dry_run:
            confirmation.confirmation_category = new_category

        if new_category == "지급":
            stats["updated_to_payment"] += 1
        else:
            stats["updated_to_carryover"] += 1

    if not dry_run:
        db.commit()

    return stats


def fetch_issued_at_for_periods(
    db,
    periods: list[tuple[int, int, int]],
) -> dict[tuple[int, int, int], datetime | None]:
    """(user_id, 정산연, 정산월) → statement_issued_at"""
    from sqlalchemy import extract

    from app.models import Settlement

    if not periods:
        return {}

    period_set = set(periods)
    user_ids = list({user_id for user_id, _, _ in period_set})
    rows = (
        db.query(
            Settlement.user_id,
            extract("year", Settlement.settlement_date).label("settle_year"),
            extract("month", Settlement.settlement_date).label("settle_month"),
            Settlement.statement_issued_at,
        )
        .filter(
            Settlement.user_id.in_(user_ids),
            Settlement.settlement_type == "monthly",
        )
        .all()
    )

    result: dict[tuple[int, int, int], datetime | None] = {}
    for user_id, settle_year, settle_month, issued_at in rows:
        key = (int(user_id), int(settle_year), int(settle_month))
        if key in period_set:
            result[key] = issued_at
    return result


def fetch_confirmation_maps(
    db,
    *,
    year: int,
    month: int,
    manager_user_ids: list[int],
) -> tuple[dict[int, Any], dict[int, datetime | None]]:
    """지사장별 정산서 확인 기록·발행일 조회"""
    from sqlalchemy import extract

    from app.models import Settlement, SettlementStatementConfirmation

    confirmation_map: dict[int, Any] = {}
    issued_at_map: dict[int, datetime | None] = {}

    if not manager_user_ids:
        return confirmation_map, issued_at_map

    confirmations = (
        db.query(SettlementStatementConfirmation)
        .filter(
            SettlementStatementConfirmation.year == year,
            SettlementStatementConfirmation.month == month,
            SettlementStatementConfirmation.user_id.in_(manager_user_ids),
        )
        .all()
    )
    confirmation_map = {int(c.user_id): c for c in confirmations}

    settlements = (
        db.query(Settlement.user_id, Settlement.statement_issued_at)
        .filter(
            Settlement.user_id.in_(manager_user_ids),
            Settlement.settlement_type == "monthly",
            extract("year", Settlement.settlement_date) == year,
            extract("month", Settlement.settlement_date) == month,
        )
        .all()
    )
    for user_id, issued_at in settlements:
        issued_at_map[int(user_id)] = issued_at

    return confirmation_map, issued_at_map


def build_monthly_summary_row(
    *,
    company: Any,
    manager: Any | None,
    amount: int,
    year: int,
    month: int,
    payment_status: dict[str, str] | None,
    confirmation: Any | None,
    issued_at: datetime | None,
) -> dict[str, Any]:
    """월 정산 요약표 행 데이터 구성"""
    payment_status = payment_status or {}
    # 해당 연·월에 저장된 비고만 표시 (다른 월 내용·자동 안내 문구는 노출하지 않음)
    remark = (payment_status.get("remark") or "").strip()

    manager_id = int(getattr(manager, "user_id", 0) or 0) if manager else 0
    confirmation_status = resolve_confirmation_status(
        confirmation=confirmation,
        issued_at=issued_at,
        year=year,
        month=month,
    )

    payment_date = normalize_payment_date_for_input(payment_status.get("payment_note", ""))

    return {
        "company_id": int(company.company_id),
        "region": company.name or company.code,
        "name": format_display_name(manager),
        "confirmation_status": confirmation_status,
        "settlement_result": format_settlement_result(payment_date),
        "settlement_type": format_settlement_type(manager),
        "bank_name": format_bank_name(manager),
        "bank_account": format_bank_account(manager),
        "account_info": format_account_info(manager),
        "amount": amount,
        "payment_date": payment_date,
        "remark": remark,
        "manager_user_id": manager_id,
    }
