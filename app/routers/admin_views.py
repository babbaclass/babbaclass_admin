"""
Admin 뷰 라우터
"""
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import logging
from datetime import date, timedelta
from typing import Optional
import io

from app.database import SessionLocal
from app.models import ContractEnd, User, Company, MonthlySettlementPaymentStatus
from app.services.contract_end_management_service import (
    build_contract_end_rows,
    sort_contract_end_rows,
)
from sqlalchemy.orm import selectinload
from app.services.monthly_settlement_summary_service import (
    MONTHLY_SETTLEMENT_SUMMARY_EXCLUDED_REGIONS,
    build_monthly_summary_row,
    fetch_confirmation_maps,
    fetch_monthly_payment_status_map,
    format_payment_date_display,
    normalize_payment_date_for_input,
)
from sqlalchemy import func, and_, or_
from sqlalchemy.exc import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Views"])


class RenewalCountUpdate(BaseModel):
    """계약 연장 횟수 업데이트 요청"""
    renewal_count: int = Field(..., ge=0, le=20, description="계약 연장 횟수 (0~20)")


@router.put("/api/contract-end/{contract_end_id}/renewal-count")
async def update_renewal_count(
    contract_end_id: int,
    body: RenewalCountUpdate,
    request: Request,
):
    """계약 연장 횟수 업데이트 API (드롭다운에서 변경 시 호출)"""
    # 세션 인증 확인
    user_id = request.session.get("user_id")
    role_id = int(request.session.get("role_id") or 0)
    if not user_id or role_id != 1:
        return JSONResponse({"error": "접근 권한이 없습니다."}, status_code=403)

    db = SessionLocal()
    try:
        record = db.query(ContractEnd).filter(
            ContractEnd.contract_end_id == contract_end_id
        ).first()

        if not record:
            return JSONResponse({"error": "계약 기록을 찾을 수 없습니다."}, status_code=404)

        record.renewal_count = body.renewal_count
        db.commit()

        logger.info(
            f"[ContractEnd] renewal_count 업데이트: contract_end_id={contract_end_id}, "
            f"renewal_count={body.renewal_count}, by user_id={user_id}"
        )
        return JSONResponse({
            "status": "success",
            "contract_end_id": contract_end_id,
            "renewal_count": body.renewal_count,
        })
    except Exception as e:
        db.rollback()
        logger.error(f"[ContractEnd] renewal_count 업데이트 실패: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.get("/api/contract-end/export-excel")
async def export_contract_end_excel(
    request: Request,
    company_id: Optional[str] = None,
    dday_filter: Optional[str] = None,
    memo_filter: Optional[str] = None,
    role_filter: Optional[str] = None,
    search: Optional[str] = None,
    sort: Optional[str] = "dday_asc"
):
    """계약 종료 관리 데이터 엑셀 다운로드"""
    # 세션 인증 확인
    user_id = request.session.get("user_id")
    role_id = int(request.session.get("role_id") or 0)
    if not user_id or role_id != 1:
        return JSONResponse({"error": "접근 권한이 없습니다."}, status_code=403)

    db = SessionLocal()
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        
        # 필터 파라미터 변환
        try:
            company_filter = int(company_id) if company_id else None
        except (ValueError, TypeError):
            company_filter = None

        # 데이터 조회 (ContractEndManagementView와 동일 로직)
        query = (
            db.query(ContractEnd)
            .options(
                selectinload(ContractEnd.user).selectinload(User.company),
                selectinload(ContractEnd.company),
            )
        )

        # D-day 필터
        today = date.today()
        if dday_filter == "120":
            query = query.filter(
                ContractEnd.contract_end_date > today,
                ContractEnd.contract_end_date <= today + timedelta(days=120),
            )
        elif dday_filter == "90":
            query = query.filter(
                ContractEnd.contract_end_date > today,
                ContractEnd.contract_end_date <= today + timedelta(days=90),
            )
        elif dday_filter == "30":
            query = query.filter(
                ContractEnd.contract_end_date > today,
                ContractEnd.contract_end_date <= today + timedelta(days=30),
            )
        elif dday_filter == "expired":
            query = query.filter(ContractEnd.contract_end_date <= today)

        # 메모 유무 필터
        if memo_filter == "yes":
            query = query.filter(
                ContractEnd.memo.isnot(None),
                ContractEnd.memo != "",
            )
        elif memo_filter == "no":
            query = query.filter(
                (ContractEnd.memo.is_(None)) | (ContractEnd.memo == "")
            )

        search_param = (search or "").strip()

        # 소속·역할·검색: 현재 User.company 기준
        needs_user_join = (
            company_filter is not None
            or role_filter in ("2", "3")
            or bool(search_param)
        )
        if needs_user_join:
            query = query.join(ContractEnd.user)
        if company_filter is not None:
            query = query.filter(User.company_id == company_filter)
        if search_param:
            pattern = f"%{search_param}%"
            query = (
                query.outerjoin(Company, Company.company_id == User.company_id)
                .filter(
                    or_(
                        Company.name.ilike(pattern),
                        Company.code.ilike(pattern),
                        User.name.ilike(pattern),
                    )
                )
            )
        if role_filter in ("2", "3"):
            query = query.filter(User.role_id == int(role_filter))

        records = query.all()
        rows = build_contract_end_rows(db, records, today=today)
        rows = sort_contract_end_rows(rows, sort or "dday_asc")
        sales_year = rows[0]["sales_year"] if rows else date.today().year

        # Excel 생성
        wb = Workbook()
        ws = wb.active
        ws.title = "계약 종료 관리"

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="2196F3", end_color="2196F3", fill_type="solid")
        center_align = Alignment(horizontal="center", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")

        headers = [
            "소속",
            "이름",
            "D-day",
            "소속원 개수",
            f"누적매출1 (계약일로부터)",
            f"누적매출2 ({sales_year}년)",
            "1년간 본인 결제 총액",
            "계약 연장 횟수",
            "비고",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align

        for row_idx, row_data in enumerate(rows, 2):
            ws.cell(row=row_idx, column=1, value=row_data["company"])
            ws.cell(row=row_idx, column=2, value=row_data["user_name"])
            ws.cell(row=row_idx, column=3, value=row_data["d_day"]).alignment = center_align
            ws.cell(row=row_idx, column=4, value=row_data["member_count"] or "").alignment = center_align
            ws.cell(row=row_idx, column=5, value=row_data["cumulative_sales_1_value"] or "").alignment = right_align
            ws.cell(row=row_idx, column=6, value=row_data["cumulative_sales_2_value"] or "").alignment = right_align
            ws.cell(row=row_idx, column=7, value=row_data["total_payment_value"] or "").alignment = right_align
            ws.cell(row=row_idx, column=8, value=row_data["renewal_count"]).alignment = center_align
            ws.cell(row=row_idx, column=9, value=row_data["memo"])

        # 열 너비 조정
        ws.column_dimensions['A'].width = 15
        ws.column_dimensions['B'].width = 12
        ws.column_dimensions['C'].width = 10
        ws.column_dimensions['D'].width = 12
        ws.column_dimensions['E'].width = 20
        ws.column_dimensions['F'].width = 20
        ws.column_dimensions['G'].width = 18
        ws.column_dimensions['H'].width = 14
        ws.column_dimensions['I'].width = 30

        # 숫자 포맷
        for row in ws.iter_rows(min_row=2, max_row=len(rows) + 1, min_col=5, max_col=7):
            for cell in row:
                if cell.value not in (None, ""):
                    cell.number_format = '#,##0'

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        excel_data = output.getvalue()
        output.close()

        filename = f"계약종료관리_{date.today().strftime('%Y%m%d')}.xlsx"
        from urllib.parse import quote
        encoded_filename = quote(filename.encode('utf-8'), safe='')
        fallback_filename = "contract_end_management.xlsx"

        return StreamingResponse(
            iter([excel_data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            status_code=200,
            headers={
                "Content-Disposition": f'attachment; filename="{fallback_filename}"; filename*=UTF-8\'\'{encoded_filename}',
                "Content-Length": str(len(excel_data)),
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )

    except Exception as e:
        logger.error(f"[export_contract_end_excel] Error: {str(e)}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


class MonthlyPaymentNoteUpdate(BaseModel):
    """월 정산 요약표 지급일·비고 업데이트"""
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)
    company_id: int = Field(..., ge=1)
    payment_note: Optional[str] = Field(default=None, max_length=255)
    remark: Optional[str] = Field(default=None, max_length=255)


@router.put("/api/monthly-settlement/payment-note")
async def update_monthly_payment_note(
    body: MonthlyPaymentNoteUpdate,
    request: Request,
):
    """월 정산 요약표 지급일·비고 저장"""
    user_id = request.session.get("user_id")
    role_id = int(request.session.get("role_id") or 0)
    if not user_id or role_id != 1:
        return JSONResponse({"error": "접근 권한이 없습니다."}, status_code=403)

    if body.payment_note is None and body.remark is None:
        return JSONResponse({"error": "저장할 항목이 없습니다."}, status_code=400)

    db = SessionLocal()
    try:
        record = (
            db.query(MonthlySettlementPaymentStatus)
            .filter(
                MonthlySettlementPaymentStatus.company_id == body.company_id,
                MonthlySettlementPaymentStatus.year == body.year,
                MonthlySettlementPaymentStatus.month == body.month,
            )
            .first()
        )

        note = None
        if body.payment_note is not None:
            note = normalize_payment_date_for_input((body.payment_note or "").strip())

        remark = None
        if body.remark is not None:
            remark = (body.remark or "").strip()

        if record:
            if note is not None:
                record.payment_note = note
            if remark is not None:
                record.remark = remark
            record.updated_by = user_id
        else:
            record = MonthlySettlementPaymentStatus(
                company_id=body.company_id,
                year=body.year,
                month=body.month,
                payment_note=note or "",
                remark=remark or "",
                updated_by=user_id,
            )
            db.add(record)

        db.commit()
        return {
            "status": "success",
            "payment_note": record.payment_note or "",
            "remark": record.remark or "",
        }
    except (OperationalError, ProgrammingError) as e:
        db.rollback()
        logger.error(f"[update_monthly_payment_note] DB error: {e}", exc_info=True)
        return JSONResponse(
            {"error": "지급 여부 저장 테이블이 없습니다. alembic upgrade head 실행 후 다시 시도해주세요."},
            status_code=503,
        )
    except Exception as e:
        db.rollback()
        logger.error(f"[update_monthly_payment_note] Error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()


@router.get("/api/monthly-settlement/export-excel")
async def export_monthly_settlement_excel(
    request: Request,
    year: int,
    month: int
):
    """월별 정산 요약 엑셀 다운로드"""
    # 세션 인증 확인
    user_id = request.session.get("user_id")
    role_id = int(request.session.get("role_id") or 0)
    if not user_id or role_id != 1:
        return JSONResponse({"error": "접근 권한이 없습니다."}, status_code=403)

    db = SessionLocal()
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from app.models import Statement, Company, User
        from sqlalchemy import func as sa_func
        
        # 모든 BRANCH/HQ 회사 + 지사장(role_id=2) 조회
        all_branches = (
            db.query(Company, User)
            .outerjoin(User, (User.company_id == Company.company_id) & (User.role_id == 2))
            .filter(Company.company_type.in_(['HQ', 'BRANCH']))
            .order_by(Company.name)
            .all()
        )

        # User.company_id 기준 total_commission 합산 (공제 전 금액)
        from app.models import Settlement
        from sqlalchemy import extract as sa_extract
        settlement_gross_totals = (
            db.query(
                User.company_id,
                sa_func.coalesce(sa_func.sum(Settlement.total_commission), 0).label('total_gross')
            )
            .join(Settlement, Settlement.user_id == User.user_id)
            .filter(
                User.role_id == 3,
                Settlement.settlement_type == 'monthly',
                sa_extract('year', Settlement.settlement_date) == year,
                sa_extract('month', Settlement.settlement_date) == month,
            )
            .group_by(User.company_id)
            .all()
        )
        amount_map = {int(row[0]): int(row[1]) for row in settlement_gross_totals}
        payment_status_map = fetch_monthly_payment_status_map(db, year, month)

        manager_ids = [
            int(manager.user_id)
            for _, manager in all_branches
            if manager and getattr(manager, "user_id", None)
        ]
        confirmation_map, issued_at_map = fetch_confirmation_maps(
            db,
            year=year,
            month=month,
            manager_user_ids=manager_ids,
        )

        # 데이터 구성 (모든 지사 포함, 제외 지역은 목록에서 생략)
        rows = []
        for company, manager in all_branches:
            region_name = company.name or company.code
            if region_name in MONTHLY_SETTLEMENT_SUMMARY_EXCLUDED_REGIONS:
                continue
            amount = amount_map.get(company.company_id, 0)
            manager_id = int(manager.user_id) if manager else 0
            row = build_monthly_summary_row(
                company=company,
                manager=manager,
                amount=amount,
                year=year,
                month=month,
                payment_status=payment_status_map.get(company.company_id),
                confirmation=confirmation_map.get(manager_id),
                issued_at=issued_at_map.get(manager_id),
            )
            rows.append({
                "region": row["region"],
                "name": row["name"],
                "confirmation_status": row["confirmation_status"],
                "settlement_result": row["settlement_result"],
                "settlement_type": row["settlement_type"],
                "bank_name": row["bank_name"],
                "bank_account": row["bank_account"],
                "amount": row["amount"],
                "payment_note": format_payment_date_display(row["payment_date"]),
                "remark": row["remark"],
            })

        # 금액 기준 내림차순 정렬
        rows.sort(key=lambda x: x['amount'], reverse=True)

        # Excel 생성
        wb = Workbook()
        ws = wb.active
        ws.title = f"{year}년 {month}월 정산"

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="2196F3", end_color="2196F3", fill_type="solid")
        center_align = Alignment(horizontal="center", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")

        headers = ["순번", "지역", "이름", "정산확인", "정산결과", "정산유형", "은행", "계좌번호", "금액", "지급일", "비고"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align

        grand_total = 0
        for row_idx, row_data in enumerate(rows, 2):
            ws.cell(row=row_idx, column=1, value=row_idx - 1).alignment = center_align
            ws.cell(row=row_idx, column=2, value=row_data["region"])
            ws.cell(row=row_idx, column=3, value=row_data["name"])
            ws.cell(row=row_idx, column=4, value=row_data.get("confirmation_status", "")).alignment = center_align
            ws.cell(row=row_idx, column=5, value=row_data.get("settlement_result", "")).alignment = center_align
            ws.cell(row=row_idx, column=6, value=row_data.get("settlement_type", "")).alignment = center_align
            ws.cell(row=row_idx, column=7, value=row_data.get("bank_name", ""))
            ws.cell(row=row_idx, column=8, value=row_data.get("bank_account", ""))
            ws.cell(row=row_idx, column=9, value=row_data["amount"]).alignment = right_align
            ws.cell(row=row_idx, column=10, value=row_data.get("payment_note", ""))
            ws.cell(row=row_idx, column=11, value=row_data.get("remark", ""))
            grand_total += row_data["amount"]

        # 합계행
        sum_row = len(rows) + 2
        sum_fill = PatternFill(start_color="FFFACD", end_color="FFFACD", fill_type="solid")
        sum_font = Font(bold=True)
        for col in range(1, 12):
            ws.cell(row=sum_row, column=col).fill = sum_fill
            ws.cell(row=sum_row, column=col).font = sum_font
        
        ws.cell(row=sum_row, column=1, value="").alignment = center_align
        ws.cell(row=sum_row, column=2, value="정산 금액 합")
        ws.cell(row=sum_row, column=9, value=grand_total).alignment = right_align

        # 열 너비 조정
        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 18
        ws.column_dimensions['C'].width = 14
        ws.column_dimensions['D'].width = 10
        ws.column_dimensions['E'].width = 10
        ws.column_dimensions['F'].width = 10
        ws.column_dimensions['G'].width = 12
        ws.column_dimensions['H'].width = 18
        ws.column_dimensions['I'].width = 14
        ws.column_dimensions['J'].width = 14
        ws.column_dimensions['K'].width = 24

        # 금액 숫자 포맷
        for row in ws.iter_rows(min_row=2, max_row=sum_row, min_col=9, max_col=9):
            for cell in row:
                cell.number_format = '#,##0'

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        excel_data = output.getvalue()
        output.close()

        filename = f"정산요약표_{year}년_{str(month).zfill(2)}월.xlsx"
        from urllib.parse import quote
        encoded_filename = quote(filename.encode('utf-8'), safe='')
        fallback_filename = "monthly_settlement_summary.xlsx"

        return StreamingResponse(
            iter([excel_data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            status_code=200,
            headers={
                "Content-Disposition": f'attachment; filename="{fallback_filename}"; filename*=UTF-8\'\'{encoded_filename}',
                "Content-Length": str(len(excel_data)),
                "Cache-Control": "no-cache, no-store, must-revalidate"
            }
        )

    except Exception as e:
        logger.error(f"[export_monthly_settlement_excel] Error: {str(e)}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()
