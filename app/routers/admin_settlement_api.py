"""
Admin settlement API endpoints - AJAX content loading for SQLAdmin
정산서 및 관련 페이지의 콘텐츠를 JSON 형식으로 반환
"""

from __future__ import annotations

from typing import Optional, Any, Dict, List
from fastapi import APIRouter, Request, Body
from starlette.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import logging
from sqlalchemy import func, extract
from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import User, Order, OrderItem, Settlement, SettlementCompanyMonthlyAggregate, SettlementStatementConfirmation, SettlementSkipRecord, Statement
from app.services.notice_service import fetch_live_notices, render_notice_banner_html
from app.settlement_tax import calc_settlement_taxes
from app.services.settlement_dedupe import select_canonical_settlements

router = APIRouter()
logger = logging.getLogger(__name__)


# Pydantic 모델 정의
class SettlementRunRequest(BaseModel):
    """정산 실행 요청 모델"""
    year: int = Field(..., description="정산 연도 (예: 2025)", ge=2020, le=2100)
    month: int = Field(..., description="정산 월 (1-12)", ge=1, le=12)
    settlement_type: str = Field(default="monthly", description="정산 유형 (daily, monthly, yearly)")


class SettlementClearRequest(BaseModel):
    """정산 데이터 삭제 요청"""
    year: Optional[int] = Field(None, description="삭제하려는 연도", ge=2020, le=2100)
    month: Optional[int] = Field(None, description="삭제하려는 월 (1-12)", ge=1, le=12)


def check_admin_access(request: Request) -> Dict[str, Any]:
    """간단한 관리자/지사장 접근 권한 확인"""
    try:
        user_id = request.session.get("user_id")
        role_id = request.session.get("role_id")
    except Exception:
        user_id = None
        role_id = None
    if not user_id or role_id not in {1, 2}:
        return {"allowed": False, "reason": "접근 권한이 없습니다"}
    return {"allowed": True}


def get_statement_summary_amounts(
    db,
    *,
    year: int,
    month: int,
    user_id: Optional[int] = None,
    company_id: Optional[int] = None,
    teachers_only: bool = False,
) -> Dict[str, int]:
    """Statement 저장값 기준으로 정산 요약 금액을 조회한다."""
    query = db.query(
        func.coalesce(func.sum(Statement.deducted_tax), 0).label("deducted_tax"),
        func.coalesce(func.sum(Statement.deducted_local_tax), 0).label("deducted_local_tax"),
        func.coalesce(func.sum(Statement.net_amount), 0).label("net_amount"),
    ).filter(
        Statement.year == year,
        Statement.month == month,
    )

    if user_id is not None:
        query = query.filter(Statement.user_id == user_id)

    if company_id is not None:
        query = query.filter(Statement.company_id == company_id)

    if teachers_only:
        query = query.join(User, User.user_id == Statement.user_id).filter(
            User.role_id == 3,
            User.is_active.is_(True),
        )

    row = query.one()
    return {
        "deducted_tax": int(row.deducted_tax or 0),
        "deducted_local_tax": int(row.deducted_local_tax or 0),
        "net_amount": int(row.net_amount or 0),
    }

def get_settlement_overview_content(request: Request) -> str:
    """정산 개요 콘텐츠"""
    notice_html = ""
    db = SessionLocal()
    try:
        live_notices = fetch_live_notices(db)
        notice_html = render_notice_banner_html(live_notices)
    finally:
        db.close()

    return f"""
    {notice_html}
    <div style='padding:2rem;'>
        <h2 style='margin:0 0 1rem;'>정산 개요</h2>
        <div style='margin-bottom:1rem;'>
            <select id='settlementOverviewYearFilter'
                style='padding:0.45rem 0.7rem; border:1px solid #ccc; border-radius:4px; font-size:0.85rem; background:#fff; cursor:pointer; min-width:140px;'>
                <!-- 옵션은 JavaScript로 로드 -->
            </select>
        </div>
        <table style='width:100%; border-collapse:collapse; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,0.1);' id='settlementOverviewTable'>
            <thead>
                <tr style='background:#f5f5f5; border-bottom:1px solid #ddd;'>
                    <th style='padding:1rem; text-align:left; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>정산일</th>
                    <th style='padding:1rem; text-align:right; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>판매 총액</th>
                    <th style='padding:1rem; text-align:right; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>사용된 적립금 총액</th>
                    <th style='padding:1rem; text-align:right; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>결제 총액</th>
                    <th style='padding:1rem; text-align:right; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>정산예정금액</th>
                    <th style='padding:1rem; text-align:right; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>지급총액(공제전)</th>
                </tr>
            </thead>
            <tbody id='settlementOverviewTableBody'>
                <!-- 데이터는 JavaScript로 로드 -->
            </tbody>
        </table>
    </div>
    """


# 정산 진행 현황: 최근 6개월 월별 건수/금액 추세
def get_settlement_status_content() -> str:
    """정산 현황 콘텐츠"""
    # 월 필터 추가 - 동적으로 최근 12개월 생성
    from datetime import datetime, timedelta
    today = datetime.now()
    months = ["전체"]
    for i in range(12):
        month_date = today - timedelta(days=30*i)
        months.append(month_date.strftime("%Y-%m"))
    
    import json
    months_json = json.dumps(months, ensure_ascii=False)
    return f"""
    <div style='padding:2rem;'>
        <h2 style='margin:0 0 1rem;'>정산 현황</h2>
        <div style='margin-bottom:1rem;'>
            <select id='settlementStatusMonthFilter' data-status-month-values='{months_json}'
                style='padding:0.45rem 0.7rem; border:1px solid #ccc; border-radius:4px; font-size:0.85rem; background:#fff; cursor:pointer; min-width:140px;'>
                {''.join(f"<option value='{m}'>{m}</option>" for m in months)}
            </select>
        </div>
        <div class='card'>
            <table class="table table-vcenter" id='settlementStatusTable' style="border-collapse: collapse;">
                    <thead style="background-color: #f8f9fa;">
                        <tr>
                            <th style="text-align: center; font-size: 1.1rem; font-weight: bold; border: 1px solid #dee2e6;">No</th>
                            <th style="font-size: 1.1rem; font-weight: bold; border: 1px solid #dee2e6;">Name</th>
                            <th style="font-size: 1.1rem; font-weight: bold; border: 1px solid #dee2e6;">Nick</th>
                            <th style="text-align: right; font-size: 1.1rem; font-weight: bold; border: 1px solid #dee2e6;">소비자가 총액</th>
                            <th style="text-align: right; font-size: 1.1rem; font-weight: bold; border: 1px solid #dee2e6;">판매가 총액</th>
                            <th style="text-align: right; font-size: 1.1rem; font-weight: bold; border: 1px solid #dee2e6;">배송비 총액</th>
                            <th style="text-align: right; font-size: 1.1rem; font-weight: bold; border: 1px solid #dee2e6;">사용된 적립금 총액</th>
                            <th style="text-align: right; font-size: 1.1rem; font-weight: bold; border: 1px solid #dee2e6;">실결제총액</th>
                        </tr>
                    </thead>
                    <tbody id='settlementStatusTableBody'>
                        <tr><td colspan="8" style="text-align:center; padding:2rem; color:#999;">데이터를 불러오는 중...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    """
    


def get_settlement_statement_list(request: Request) -> str:
    """정산서 목록 - 연도별 월 선택 (데이터 기반)"""
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return """
            <div class="alert alert-warning" role="alert">
                로그인이 필요합니다.
            </div>
            """
        
        db = SessionLocal()
        try:
            # 사용자 정보 조회
            user = db.query(User).filter(User.user_id == int(user_id)).first()
            if not user:
                return """
                <div class="alert alert-warning" role="alert">
                    사용자 정보를 찾을 수 없습니다.
                </div>
                """
            
            user_id_int = int(user_id)
            role_id = int(getattr(user, 'role_id', 3))
            available_months = []
            
            # role_id별로 다른 테이블에서 조회
            if role_id == 3:  # 원장
                from sqlalchemy import func, extract
                records = db.query(
                    extract('year', Settlement.settlement_date).label('year'),
                    extract('month', Settlement.settlement_date).label('month')
                ).filter(
                    Settlement.user_id == user_id_int,
                    Settlement.settlement_type == 'monthly'
                ).distinct().order_by(
                    extract('year', Settlement.settlement_date).desc(),
                    extract('month', Settlement.settlement_date).desc()
                ).all()
                
                available_months = [
                    {"year": int(r[0]), "month": int(r[1])} for r in records
                ]
            
            elif role_id == 2:  # 지사장
                company_id = int(getattr(user, 'company_id', 0))
                from sqlalchemy import extract
                records = db.query(
                    SettlementCompanyMonthlyAggregate.year,
                    SettlementCompanyMonthlyAggregate.month
                ).filter(
                    SettlementCompanyMonthlyAggregate.company_id == company_id
                ).distinct().order_by(
                    SettlementCompanyMonthlyAggregate.year.desc(),
                    SettlementCompanyMonthlyAggregate.month.desc()
                ).all()
                
                available_months = [
                    {"year": int(r[0]), "month": int(r[1])} for r in records
                ]
            
            elif role_id == 1:  # 관리자
                from sqlalchemy import extract
                records = db.query(
                    extract('year', Settlement.settlement_date).label('year'),
                    extract('month', Settlement.settlement_date).label('month')
                ).filter(
                    Settlement.settlement_type == 'monthly'
                ).distinct().order_by(
                    extract('year', Settlement.settlement_date).desc(),
                    extract('month', Settlement.settlement_date).desc()
                ).all()
                
                available_months = [
                    {"year": int(r[0]), "month": int(r[1])} for r in records
                ]
            
            from app.services.monthly_settlement_summary_service import (
                filter_confirmable_month_entries,
                max_confirmable_settlement_period,
            )
            from zoneinfo import ZoneInfo

            now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
            available_months = filter_confirmable_month_entries(available_months, now_kst)

            # 데이터가 없으면 - 확인 가능한 최근 월만 표시 (당월 제외)
            if not available_months:
                max_y, max_m = max_confirmable_settlement_period(now_kst)
                available_months = []
                year, month = max_y, max_m
                for _ in range(12):
                    available_months.append({"year": year, "month": month})
                    month -= 1
                    if month == 0:
                        month = 12
                        year -= 1
            
            # 년도별로 그룹화
            months_by_year = {}
            for m in available_months:
                year = m['year']
                month = m['month']
                if year not in months_by_year:
                    months_by_year[year] = []
                months_by_year[year].append(month)
            
            # HTML 생성
            html = """
            <div class="row row-deck row-cards">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h2 style='margin:0 0 1rem;'>정산서</h2>
                        </div>
                        <div class="card-body">
                            <div class="alert alert-info settlement-confirmation-notice mb-4 py-2" role="status">
                                <div><strong>정산서 확인 기간 :</strong> 매달 10일~15일</div>
                                <div class="mb-0 mt-1" style="font-size: 0.92rem;">
                                    → 기간 내 확인 시 정산금 정상 지급처리 / 이후 확인 시 정산금 ‘이월’ 지급됨
                                </div>
                            </div>
            """
            
            # 년도별로 섹션 생성 (최신순)
            for year in sorted(months_by_year.keys(), reverse=True):
                months = sorted(months_by_year[year], reverse=True)
                html += f"""
                    <div class="mb-4">
                        <h5 class="mb-3" style="font-weight: 600; font-size: 1.1rem;">{year}년</h5>
                        <div style="display: flex; flex-wrap: wrap; gap: 10px;">
                """
                
                month_names = ['', '1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']
                for month in months:
                    month_name = month_names[month]
                    html += f'<button class="btn btn-outline-primary" onclick="loadSettlementDetail({year}, {month})" style="width: 80px;">{month_name}</button>\n'
                
                html += """
                        </div>
                    </div>
                """
            
            html += """
                        </div>
                    </div>
                </div>
            </div>
            """
            
            return html
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"[get_settlement_statement_list] Error: {str(e)}", exc_info=True)
        return f"""
        <div class="alert alert-danger" role="alert">
            정산서 목록 로드 중 오류 발생: {str(e)}
        </div>
        """


def get_settlement_statement_detail(request: Request, year: int, month: int, company_id_param: Optional[int] = None) -> str:
    """정산서 상세 - 바빠 스마트 클래스 정산서 형식"""
    try:
        user_id_str = request.session.get("user_id")
        if not user_id_str:
            return '<div class="alert alert-warning">로그인 필요</div>'
        
        user_id = int(user_id_str)
        
        db = SessionLocal()
        try:
            from app.models import Company
            
            current_user = db.query(User).filter(User.user_id == user_id).first()
            if not current_user:
                return '<div class="alert alert-warning">사용자 정보 없음</div>'
            
            role_id = int(getattr(current_user, 'role_id', 3))

            from app.services.monthly_settlement_summary_service import (
                is_company_monthly_statement_issued,
                is_settlement_period_confirmable,
                max_confirmable_settlement_period,
            )
            from zoneinfo import ZoneInfo

            now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
            if role_id in {1, 2} and not is_settlement_period_confirmable(year, month, now_kst):
                max_y, max_m = max_confirmable_settlement_period(now_kst)
                return (
                    f'<div class="alert alert-warning">'
                    f'{year}년 {month:02d}월 정산서는 아직 확인할 수 없습니다. '
                    f'({max_y}년 {max_m:02d}월까지 가능)'
                    f'</div>'
                )

            company_id = int(getattr(current_user, 'company_id', 0))
            user_name = getattr(current_user, 'name', '미등록') or '미등록'
            user_code = getattr(current_user, 'code', 0) or 0
            user_bank = getattr(current_user, 'bank_name', '미등록') or '미등록'
            user_account = getattr(current_user, 'bank_account', '') or ''
            statement_subject_user = current_user
            
            # 홈에서 전달된 company_id가 있으면 사용 (본사 관리자가 지사 정산서 조회 시)
            if company_id_param and role_id == 1:
                company_id = company_id_param

            statement_issued = is_company_monthly_statement_issued(
                db, company_id=company_id, year=year, month=month
            )
            # 지사장: 미발행 정산서는 상세·확인 불가 (URL 직접 접속 차단)
            if role_id == 2 and not statement_issued:
                return (
                    f'<div class="alert alert-warning">'
                    f'{year}년 {month:02d}월 정산서가 아직 발행되지 않았습니다. '
                    f'발행 후 확인할 수 있습니다.'
                    f'</div>'
                )
            
            if role_id in {1, 2}:
                branch_manager = db.query(User).filter(
                    User.company_id == company_id,
                    User.role_id == 2,
                ).order_by(User.user_id.asc()).first()
                if branch_manager:
                    statement_subject_user = branch_manager
                    if role_id == 1:
                        user_name = getattr(branch_manager, 'name', '미등록') or '미등록'
                        user_code = getattr(branch_manager, 'code', 0) or 0
                        user_bank = getattr(branch_manager, 'bank_name', '미등록') or '미등록'
                        user_account = getattr(branch_manager, 'bank_account', '') or ''
            
            from app.services.monthly_settlement_summary_service import (
                format_settlement_type_statement_display,
            )
            settlement_type_display = format_settlement_type_statement_display(statement_subject_user)
            
            # 회사 정보 조회
            company = db.query(Company).filter(Company.company_id == company_id).first()
            company_name = getattr(company, 'name', '미등록') if company else '미등록'
            company_name = company_name or '미등록'
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}", exc_info=True)
        role_id = 3
        company_id = 0
        user_id = 0
        user_name = '미등록'
        user_code = 0
        user_bank = '미등록'
        user_account = ''
        company_name = '미등록'
        settlement_type_display = '-'
    
    month_name = ['', '1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'][month]

    confirmation_section = ""
    if role_id == 2:
        confirmation_section = """
                    <!-- 서명란 -->
                    <div class=\"mt-4 pt-3\" style=\"text-align: right;\">
                        <button class=\"btn btn-success btn-lg\" onclick=\"confirmSettlement()\">정산서를 확인하였습니다.</button>
                    </div>
        """
    
    # Statement 정보 조회
    statement_info = {"number": "", "status": "DRAFT", "issued_at": "", "confirmed_at": ""}
    statement_summary = {"deducted_tax": 0, "deducted_local_tax": 0, "net_amount": 0}
    db_statement = SessionLocal()
    try:
        if role_id == 3:
            statement = db_statement.query(Statement).filter(
                Statement.user_id == user_id,
                Statement.year == year,
                Statement.month == month
            ).first()

            if statement:
                statement_info["number"] = getattr(statement, 'statement_number', '')
                statement_info["status"] = 'CONFIRMED' if bool(getattr(statement, 'is_confirmed', False)) else 'ISSUED'
                issued_at = getattr(statement, 'issued_at', None)
                confirmed_at = getattr(statement, 'confirmed_at', None)
                statement_info["issued_at"] = issued_at.strftime('%Y-%m-%d') if issued_at else ''
                statement_info["confirmed_at"] = confirmed_at.strftime('%Y-%m-%d') if confirmed_at else ''
                statement_summary = {
                    "deducted_tax": int(getattr(statement, 'deducted_tax', 0) or 0),
                    "deducted_local_tax": int(getattr(statement, 'deducted_local_tax', 0) or 0),
                    "net_amount": int(getattr(statement, 'net_amount', 0) or 0),
                }
        else:
            statement_summary = get_statement_summary_amounts(
                db_statement,
                year=year,
                month=month,
                company_id=company_id,
                teachers_only=True,
            )
    except Exception as e:
        logger.error(f"Error loading statement: {str(e)}", exc_info=True)
    finally:
        db_statement.close()
    
    # 데이터베이스에서 실제 정산 데이터 조회
    db_for_settlement = SessionLocal()
    settlement_html = ""
    grand_total_amount = 0
    grand_total_commission = 0
    
    try:
        from sqlalchemy import extract
        import json
        from collections import defaultdict
        
        # role_id별 처리
        if role_id in [1, 2]:  # 본사(1) 또는 지사장(2) - 소속 원장들의 정산 데이터 표시
            # 같은 company_id를 가진 role_id=3인 원장들 조회
            teachers = db_for_settlement.query(User).filter(
                User.company_id == company_id,
                User.role_id == 3
            ).all()
            
            # 모든 원장들의 정산 데이터를 commission type별로 그룹화
            all_commission_details = []
            
            for teacher in teachers:
                settlement = db_for_settlement.query(Settlement).filter(
                    Settlement.user_id == teacher.user_id,
                    Settlement.settlement_type == 'monthly',
                    extract('year', Settlement.settlement_date) == year,
                    extract('month', Settlement.settlement_date) == month
                ).first()
                
                if settlement and settlement.commission_details:
                    try:
                        commission_details_str = str(settlement.commission_details)
                        details = json.loads(commission_details_str)
                        for detail in details:
                            # 정산액이 0원인 항목은 표시하지 않음
                            if detail.get('commission', 0) == 0:
                                continue
                            detail['user_name'] = getattr(teacher, 'name', '미등록')
                            detail['user_code'] = getattr(teacher, 'code', '')
                            all_commission_details.append(detail)
                    except Exception as e:
                        logger.error(f"Error parsing commission_details for teacher {teacher.user_id}: {str(e)}")
            
            # commission type별로 그룹화 (날짜순 정렬을 위해 모든 항목 수집)
            type_groups = defaultdict(list)
            for detail in all_commission_details:
                type_name = detail.get('type_name', '기타')
                type_groups[type_name].append(detail)
            
            # 각 타입별로 HTML 생성
            for type_name, items in sorted(type_groups.items()):
                type_total_amount = 0
                type_total_commission = 0
                type_html = ""
                
                # 날짜순 정렬 (ordernum 기준 오름차순)
                sorted_items = sorted(items, key=lambda x: x.get('ordernum', ''))
                
                for item in sorted_items:
                    order_date = item.get('ordernum', '')[:8]  # ordernum의 앞 8자리가 날짜
                    if len(order_date) == 8:
                        order_date = f"{order_date[:4]}-{order_date[4:6]}-{order_date[6:8]}"
                    else:
                        order_date = f"{year}-{str(month).zfill(2)}-01"
                    
                    user_code_val = item.get('user_code', '')
                    user_name_val = item.get('user_name', '미등록')
                    actual_payment = item.get('actual_payment', 0)
                    rate = item.get('rate', 0)
                    commission = item.get('commission', 0)
                    
                    # 수수료율을 정수로 표시
                    rate_int = int(rate) if rate else 0
                    
                    type_total_amount += actual_payment
                    type_total_commission += commission
                    
                    type_html += f"""
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{order_date}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{type_name}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{user_code_val}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{user_name_val}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{actual_payment:,}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px; text-align: center;">{rate_int}%</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{commission:,}</td>
                    </tr>
                    """
                
                # 타입별 소계 추가
                settlement_html += type_html
                settlement_html += f"""
                <tr style="background-color: #fffacd; font-weight: bold;">
                    <td colspan="4" style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">소계</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{type_total_amount:,}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: center;">{int(rate) if items else 0}%</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{type_total_commission:,}</td>
                </tr>
                """
                
                grand_total_amount += type_total_amount
                grand_total_commission += type_total_commission
                
        elif role_id == 3:  # 원장 - 본인의 정산 데이터만 표시
            settlement = db_for_settlement.query(Settlement).filter(
                Settlement.user_id == int(user_id),
                Settlement.settlement_type == 'monthly',
                extract('year', Settlement.settlement_date) == year,
                extract('month', Settlement.settlement_date) == month
            ).first()
            
            if settlement and settlement.commission_details:
                try:
                    details = json.loads(settlement.commission_details)
                    
                    # 정산액이 0원인 항목은 제외
                    details = [detail for detail in details if detail.get('commission', 0) > 0]
                    
                    # commission type별로 그룹화
                    type_groups = defaultdict(list)
                    for detail in details:
                        type_name = detail.get('type_name', '기타')
                        type_groups[type_name].append(detail)
                    
                    # 각 타입별로 HTML 생성
                    for type_name, items in sorted(type_groups.items()):
                        type_total_amount = 0
                        type_total_commission = 0
                        type_html = ""
                        
                        # 날짜순 정렬 (ordernum 기준 오름차순)
                        sorted_items = sorted(items, key=lambda x: x.get('ordernum', ''))
                        
                        for item in sorted_items:
                            order_date = item.get('ordernum', '')[:8]
                            if len(order_date) == 8:
                                order_date = f"{order_date[:4]}-{order_date[4:6]}-{order_date[6:8]}"
                            else:
                                order_date = f"{year}-{str(month).zfill(2)}-01"
                            
                            actual_payment = item.get('actual_payment', 0)
                            rate = item.get('rate', 0)
                            commission = item.get('commission', 0)
                            
                            # 수수료율을 정수로 표시
                            rate_int = int(rate) if rate else 0
                            
                            type_total_amount += actual_payment
                            type_total_commission += commission
                            
                            type_html += f"""
                            <tr>
                                <td style="border: 1px solid #dee2e6; padding: 8px;">{order_date}</td>
                                <td style="border: 1px solid #dee2e6; padding: 8px;">{type_name}</td>
                                <td style="border: 1px solid #dee2e6; padding: 8px;">{user_code}</td>
                                <td style="border: 1px solid #dee2e6; padding: 8px;">{user_name}</td>
                                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{actual_payment:,}</td>
                                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: center;">{rate_int}%</td>
                                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{commission:,}</td>
                            </tr>
                            """
                        
                        # 타입별 소계 추가
                        settlement_html += type_html
                        settlement_html += f"""
                        <tr style="background-color: #fffacd; font-weight: bold;">
                            <td colspan="4" style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">소계</td>
                            <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{type_total_amount:,}</td>
                            <td style="border: 1px solid #dee2e6; padding: 8px; text-align: center;">{int(rate) if items else 0}%</td>
                            <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{type_total_commission:,}</td>
                        </tr>
                        """
                        
                        grand_total_amount += type_total_amount
                        grand_total_commission += type_total_commission
                except Exception as e:
                    logger.error(f"Error parsing commission_details: {str(e)}", exc_info=True)
                    
    except Exception as e:
        logger.error(f"Error loading settlement data: {str(e)}", exc_info=True)
    finally:
        db_for_settlement.close()

    # 소득세 3%, 지방세(지방소득세) = 소득세의 10% — 십 단위 절사
    display_deducted_tax, display_deducted_local_tax, display_net_amount = calc_settlement_taxes(grand_total_commission)

    return """
    <div class="row row-deck row-cards">
        <div class="col-12">
            <div class="card">
                <div class="card-body">
                    <!-- 정산서 헤더 -->
                    <div class="text-center mb-4 pb-3 border-bottom" style="position: relative;">
                        <h3 class="mb-1">바빠 스마트 클래스 """ + month_name + """ 정산서</h3>
                        <p class="text-muted small mb-0">정산연월: """ + str(year) + """년 """ + month_name + """</p>
                        """ + (f'''
                        <div class="mt-2">
                            <span class="badge bg-primary">정산서 번호: {statement_info["number"]}</span>
                            <span class="badge bg-{"success" if statement_info["status"] == "CONFIRMED" else "info" if statement_info["status"] == "ISSUED" else "warning"}">{statement_info["status"]}</span>
                            {f'<span class="badge bg-secondary">발행일: {statement_info["issued_at"]}</span>' if statement_info["issued_at"] else ''}
                            {f'<span class="badge bg-success">확인일: {statement_info["confirmed_at"]}</span>' if statement_info["confirmed_at"] else ''}
                        </div>
                        ''' if statement_info["number"] else '') + """
                        <!-- 엑셀 다운로드 버튼 (헤더 우측 상단) -->
                        <div style="position: absolute; top: 10px; right: 12px;">
                            <button class="btn btn-outline-secondary btn-sm" onclick="downloadExcel()">
                                <i class="ti ti-download"></i> 엑셀 다운로드
                            </button>
                        </div>
                    </div>

                    <!-- 정산자 정보 -->
                    <div class="row mb-4">
                        <div class="col-md-6">
                            <table class="table table-sm" style="border: 1px solid #dee2e6;">
                                <tbody>
                                    <tr>
                                        <td style="width: 30%; background-color: #f8f9fa;"><strong>정산연월</strong></td>
                                        <td>""" + str(year) + """년 """ + month_name + """</td>
                                    </tr>
                                    <tr>
                                        <td style="background-color: #f8f9fa;"><strong>지사코드</strong></td>
                                        <td>""" + str(user_code) + """</td>
                                    </tr>
                                    <tr>
                                        <td style="background-color: #f8f9fa;"><strong>은행</strong></td>
                                        <td>""" + user_bank + """</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <table class="table table-sm" style="border: 1px solid #dee2e6;">
                                <tbody>
                                    <tr>
                                        <td style="width: 30%; background-color: #f8f9fa;"><strong>지사장명</strong></td>
                                        <td>""" + user_name + """</td>
                                    </tr>
                                    <tr>
                                        <td style="background-color: #f8f9fa;"><strong>지역</strong></td>
                                        <td>""" + company_name + """</td>
                                    </tr>
                                    <tr>
                                        <td style="background-color: #f8f9fa;"><strong>계좌번호</strong></td>
                                        <td>""" + user_account + """</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- 정산 유형 -->
                    <div class="mb-3 px-3 py-2 border" style="background-color: #f8f9fa;">
                        <strong>정산 유형:</strong> """ + settlement_type_display + """
                    </div>

                    <!-- 정산 내역 테이블 -->
                    <div class="mb-4">
                        <table class="table" style="border: 1px solid #dee2e6;">
                            <thead style="background-color: #fffacd;">
                                <tr>
                                    <th style="border: 1px solid #dee2e6; padding: 8px; font-size: 1.0rem; font-weight: bold;">수수료발생일</th>
                                    <th style="border: 1px solid #dee2e6; padding: 8px; font-size: 1.0rem; font-weight: bold;">결제종류</th>
                                    <th style="border: 1px solid #dee2e6; padding: 8px; font-size: 1.0rem; font-weight: bold;">코드</th>
                                    <th style="border: 1px solid #dee2e6; padding: 8px; font-size: 1.0rem; font-weight: bold;">결제자</th>
                                    <th style="border: 1px solid #dee2e6; padding: 8px; font-size: 1.0rem; font-weight: bold;">정산대상금액</th>
                                    <th style="border: 1px solid #dee2e6; padding: 8px; font-size: 1.0rem; font-weight: bold;">수수료율</th>
                                    <th style="border: 1px solid #dee2e6; padding: 8px; font-size: 1.0rem; font-weight: bold;">정산액</th>
                                </tr>
                            </thead>
                            <tbody>
                                """ + settlement_html + """
                                <tr style="background-color: #e6f3ff;">
                                    <td colspan="6" style="border: 1px solid #dee2e6; padding: 8px;"><strong>총 합계</strong></td>
                                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;"><strong>""" + f"{grand_total_commission:,}" + """</strong></td>
                                </tr>
                                <tr style="background-color: #e6f3ff;">
                                    <td colspan="6" style="border: 1px solid #dee2e6; padding: 8px;"><strong>소득세</strong></td>
                                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;"><strong>""" + f"{display_deducted_tax:,}" + """</strong></td>
                                </tr>
                                <tr style="background-color: #e6f3ff;">
                                    <td colspan="6" style="border: 1px solid #dee2e6; padding: 8px;"><strong>지방세</strong></td>
                                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;"><strong>""" + f"{display_deducted_local_tax:,}" + """</strong></td>
                                </tr>
                                <tr style="background-color: #e6f3ff;">
                                    <td colspan="6" style="border: 1px solid #dee2e6; padding: 8px;"><strong>공제 후 지급액</strong></td>
                                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;"><strong>""" + f"{display_net_amount:,}" + """</strong></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    """ + confirmation_section + """

                    <!-- 문의처 -->
                    <div style="text-align: right; margin-top: 10px;">
                        <p class="text-muted small mb-0">정산 보고서, 지급에 대한 문의처: babba@easyspub.co.kr</p>
                    </div>

                    <!-- 하단 설명 -->
                    <div class="text-muted mt-4 pt-3 border-top" style="text-align: left; font-size: 0.95rem;">
                        <ul class="mb-0" style="text-align: left; padding-left: 1.5rem;">
                            <li><strong>바스클 교재 수수료: 25%</strong></li>
                            <li><strong>바빠 시리즈 교재 수수료: 15%</strong></li>
                            <li><strong>쿠폰 구매 수수료: 15%</strong></li>
                            <li>정산서는 매월 발행되며, 수수료율은 상품 및 계약에 따라 달라집니다.</li>
                            <li>지사 계약 첫해: 지사 계약 3개월 이내 최소 5개 교육원을 모집해야 지사로 인정합니다. 계약 후 1년 안에 총 10개 원을 모집.</li>
                            <li>지사 계약 2년 차: 교육원 모집과 교재 매출을 합하여 연간 최저 600만 원을 달성하여야 합니다.</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def get_teachers_list_content(request: Request) -> str:
    """소속 원장 리스트 콘텐츠 (HTML 반환)

    """
    import html
    import json

    from app.services.teachers_list_service import fetch_teachers_list_data

    # 권한 확인
    user_id = request.session.get("user_id")
    role_id = request.session.get("role_id")
    if not user_id or role_id not in {1, 2}:
        return "<div style='padding:2rem;'><h3>접근 권한이 없습니다</h3></div>"

    db = SessionLocal()
    try:
        current_user = db.query(User).filter(User.user_id == user_id).first()
        if not current_user:
            return "<div style='padding:2rem;'><h3>사용자 정보를 찾을 수 없습니다</h3></div>"

        company_id_param = request.query_params.get("company_id")
        try:
            target_company_id = int(company_id_param) if company_id_param else current_user.company_id
        except (TypeError, ValueError):
            target_company_id = current_user.company_id

        if role_id == 2 and target_company_id != current_user.company_id:
            return "<div style='padding:2rem;'><h3>접근 권한이 없습니다</h3></div>"

        teachers_data = fetch_teachers_list_data(db, target_company_id)
        if not teachers_data:
            return (
                """
                <div style='padding:2rem;'>
                  <h2 style='margin-top:0;'>소속 원장 리스트</h2>
                  <p style='color:#999; margin-top:1rem;'>소속 원장이 없습니다.</p>
                  <a href='/admin/user/list' style='display:inline-block; margin-top:1rem; padding:0.55rem 1rem; background:#007bff; color:#fff; text-decoration:none; border-radius:4px;'>회원 관리로 이동</a>
                </div>
                """
            )

        rows_html_parts: List[str] = []
        for idx, td in enumerate(teachers_data, 1):
            d_day_style = f"color:{td['d_day_color']};" if td.get("d_day_color") else ""
            rows_html_parts.append(
                f"""
                <tr>
                  <td style='padding:0.7rem; text-align:center; border:1px solid #dee2e6;'>{idx}</td>
                  <td style='padding:0.7rem; border:1px solid #dee2e6; text-align:left;'>{html.escape(str(td['name']))}</td>
                  <td style='padding:0.7rem; text-align:center; border:1px solid #dee2e6;'>{td['purchase_count']}</td>
                  <td style='padding:0.7rem; text-align:right; border:1px solid #dee2e6;'>{html.escape(str(td['yearly_payment_display']))}</td>
                  <td style='padding:0.7rem; text-align:center; border:1px solid #dee2e6; font-weight:bold; {d_day_style}'>{html.escape(str(td['d_day']))}</td>
                  <td style='padding:0.7rem; border:1px solid #dee2e6; text-align:left;'>{html.escape(str(td['join_date']))}</td>
                  <td style='padding:0.7rem; border:1px solid #dee2e6; text-align:left;'>{html.escape(str(td['contact']))}</td>
                </tr>
                """
            )
        rows_html = "".join(rows_html_parts)
        teachers_json = html.escape(json.dumps(teachers_data, ensure_ascii=False), quote=True)

        html = f"""
        <div style='padding:2rem;'>
          <div style='margin-bottom:1.4rem;'>
            <h2 style='margin:0;'>소속 원장 리스트</h2>
          </div>
          <div style='margin-bottom:1.1rem;'>
            <select id='teachersSortFilter' style='padding:0.45rem 0.7rem; border:1px solid #ccc; border-radius:4px; font-size:0.85rem; background:#fff; cursor:pointer; min-width:140px;'>
              <option value='all'>전체</option>
              <option value='name'>이름순</option>
              <option value='join_date'>가입일순</option>
              <option value='purchase_count'>구매건순</option>
              <option value='yearly_payment'>누적액순</option>
              <option value='d_day'>D-day순</option>
            </select>
          </div>
                    <table id='teachersTable' data-teachers='{teachers_json}' style='width:100%; border-collapse:collapse; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,0.08);'>
                        <thead>
                            <tr style='background:#f5f5f5;'>
                                <th style='padding:1rem; text-align:center; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6; width:55px;'>No</th>
                                <th style='padding:1rem; text-align:left; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>이름</th>
                                <th style='padding:1rem; text-align:center; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>최근 6개월 구매 건수</th>
                                <th style='padding:1rem; text-align:right; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>1년간 결제 누적액</th>
                                <th style='padding:1rem; text-align:center; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>계약종료 D-day</th>
                                <th style='padding:1rem; text-align:left; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>가입일</th>
                                <th style='padding:1rem; text-align:left; font-size:1.1rem; font-weight:bold; border:1px solid #dee2e6;'>연락처</th>
                            </tr>
                        </thead>
            <tbody id='teachersTableBody'>
              {rows_html}
            </tbody>
          </table>
          <div style='margin-top:1.2rem; padding:0.65rem 0.8rem; background:#f9f9f9; border-radius:4px; border-left:4px solid #007bff;'>
            <p style='margin:0 0 0.5rem; color:#555; font-size:0.75rem;'>최근 6개월 구매 건수는 지난 180일 동안의 결제 완료 주문 건수입니다.</p>
            <p style='margin:0; color:#555; font-size:0.75rem; font-weight:bold;'>1년간 결제 누적액은 당해 년도 1월부터 매달 누적되는 결제액(가입비 제외)입니다. 다음달 1일에 전월 누적액이 업데이트 됩니다.</p>
          </div>
        </div>
        """
        return html
    except Exception as e:
        logger.error(f"[get_teachers_list_content] Error: {e}", exc_info=True)
        return f"<div style='padding:2rem;'><h3>오류 발생</h3><p>{str(e)}</p></div>"
    finally:
        try:
            db.close()
        except Exception:
            pass


def get_data_tools_content() -> str:
    """Data Tools - Google Sheet 임포트 콘텐츠"""
    return """
    <div class="row row-deck row-cards">
        <div class="col-12">
            <div class="card">
                <div class="card-header">
                    <h3 class="card-title">🛠️ Data Tools</h3>
                    <p class="text-muted small">공개된 Google Sheet를 CSV로 변환하여 DB에 적재합니다.</p>
                </div>
                <div class="card-body">
                    <form id="sheetImportForm" class="sheet-import-form">
                        <div class="mb-3">
                            <label class="form-label">Sheet URL (필수)</label>
                            <input class="form-control" type="url" id="sheet_url" placeholder="https://docs.google.com/spreadsheets/d/..." required/>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Sheet 이름 (옵션)</label>
                            <input class="form-control" type="text" id="sheet_name" placeholder="예: 데이터" />
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">테이블명 (옵션, 기본: sheet_*)</label>
                            <input class="form-control" type="text" id="table_name" placeholder="예: sheet_sales_2025" />
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-check">
                                <input type="checkbox" id="truncate_before" class="form-check-input"/>
                                <span class="form-check-label">적재 전 테이블 비우기 (TRUNCATE)</span>
                            </label>
                        </div>
                        
                        <button class="btn btn-success btn-lg" type="submit">📤 Sheet 임포트 실행</button>
                    </form>
                    
                    <pre id="sheetResult" style="display: none; margin-top: 1rem; background: #1e1e1e; color: #00ff00; padding: 1rem; border-radius: 4px; font-family: 'Courier New'; max-height: 400px; overflow-y: auto;"></pre>
                </div>
            </div>
        </div>
    </div>
    <script>
    (function() {
        // 이벤트 위임을 사용하여 동적으로 로드된 폼도 처리
        document.addEventListener('submit', function(e) {
            if (e.target.matches('.sheet-import-form') || e.target.id === 'sheetImportForm') {
                e.preventDefault();
                handleSheetImport(e);
            }
        }, true);
        
        async function handleSheetImport(e) {
            const form = e.target;
            const button = form.querySelector('button[type="submit"]');
            button.disabled = true;
            button.textContent = "⏳ 진행 중...";
            
            try {
                const body = {
                    sheet_url: document.getElementById('sheet_url').value,
                    sheet_name: document.getElementById('sheet_name').value || null,
                    table_name: document.getElementById('table_name').value || null,
                    truncate_before: document.getElementById('truncate_before').checked
                };
                
                const res = await fetch('/admin-api/sheets/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                
                const data = await res.json();
                const resultDiv = document.getElementById('sheetResult');
                resultDiv.style.display = 'block';
                
                if (res.ok) {
                    resultDiv.style.color = '#00ff00';
                    resultDiv.textContent = '✅ 임포트 성공!\\n\\n' + JSON.stringify(data, null, 2);
                } else {
                    resultDiv.style.color = '#ff6b6b';
                    resultDiv.textContent = '❌ 오류 발생\\n\\n' + JSON.stringify(data, null, 2);
                }
            } catch (error) {
                const resultDiv = document.getElementById('sheetResult');
                resultDiv.style.display = 'block';
                resultDiv.style.color = '#ff6b6b';
                resultDiv.textContent = '❌ 요청 실패\\n\\n' + error.message;
            } finally {
                button.disabled = false;
                button.textContent = "📤 Sheet 임포트 실행";
            }
        }
    })();
    </script>
    """


@router.get("/settlement-content/{view_name}")
async def get_settlement_content(view_name: str, request: Request, year: Optional[int] = None, month: Optional[int] = None, company_id: Optional[int] = None):  # type: ignore
    """정산 관련 콘텐츠를 JSON으로 반환 (AJAX용)"""
    # 권한 확인
    access_check = check_admin_access(request)
    if not access_check.get("allowed"):
        return JSONResponse({"error": access_check.get("reason")}, status_code=403)
    
    content_map: Dict[str, Any] = {
        "settlement-overview": get_settlement_overview_content,
        "settlement-status": get_settlement_status_content,
        "settlement-statement": get_settlement_statement_list,
        "settlement-statement-detail": get_settlement_statement_detail,
        "teachers-list": get_teachers_list_content,
        # "commission-quick-seed": get_commission_quick_seed_content,
        # "data-tools": get_data_tools_content,  # ToolsAdmin이 처리
    }
    
    if view_name not in content_map:
        return JSONResponse({"error": "Invalid view"}, status_code=404)
    
    try:
        if view_name == "settlement-statement-detail":
            if year is None or month is None:
                return JSONResponse({"error": "year and month are required"}, status_code=400)
            html_content = content_map[view_name](request, year, month, company_id)  # type: ignore
        elif view_name == "settlement-statement":
            # settlement-statement는 request 객체 필요
            html_content = content_map[view_name](request)  # type: ignore
        elif view_name == "teachers-list":
            # teachers-list는 request 객체 필요
            html_content = content_map[view_name](request)  # type: ignore
        elif view_name == "settlement-overview":
            html_content = content_map[view_name](request)  # type: ignore
        else:
            html_content = content_map[view_name]()  # type: ignore
        return JSONResponse({"html": html_content})
    except Exception as e:
        logger.error(f"[get_settlement_content] Error: {e}", exc_info=True)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/settlement/aggregate-orders")
async def aggregate_completed_orders_to_settlement(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None,
    settlement_type: str = "monthly"
):  # type: ignore
    """
    결제 완료된 주문을 사용자별, 월별로 집계하여 Settlement 테이블에 적재
    
    Query Parameters:
        year: 대상 연도 (기본: 현재 연도)
        month: 대상 월 (기본: 현재 월, 1-12)
        settlement_type: 정산 타입 ('daily', 'monthly', 'yearly')
    
    Returns:
        {
            'status': 'success' | 'error',
            'message': str,
            'created_count': int,
            'updated_count': int,
            'total_amount': int,
            'details': list
        }
    """
    # 인증 요구 없음 (배치 작업용으로 공개)
    
    try:
        from app.services.settlement_service import SettlementService
        
        db = SessionLocal()
        try:
            logger.info(f"[aggregate_completed_orders] Start: year={year}, month={month}, type={settlement_type}")
            
            result: Dict[str, Any] = SettlementService.aggregate_completed_orders_to_settlement(
                db=db,
                year=year,  # type: ignore
                month=month,  # type: ignore
                settlement_type=settlement_type
            )
            
            logger.info(f"[aggregate_completed_orders] Result: {result}")
            return JSONResponse(result)
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"[aggregate_completed_orders] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": f"Error: {str(e)}",
            "created_count": 0,
            "updated_count": 0,
            "total_amount": 0,
            "details": []
        }, status_code=500)


@router.get("/settlement/summary")
async def get_settlement_summary(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None
):  # type: ignore
    """
    정산 요약 정보 조회
    
    Query Parameters:
        year: 대상 연도 (기본: 현재 연도)
        month: 대상 월 (기본: 현재 월)
    
    Returns:
        {
            'status': 'success' | 'error',
            'year': int,
            'month': int,
            'total_records': int,
            'total_commission': int,
            'total_deducted_tax': int,
            'total_net_amount': int,
            'paid_count': int,
            'unpaid_count': int
        }
    """
    # 권한 확인
    access_check = check_admin_access(request)
    if not access_check.get("allowed"):
        return JSONResponse({"error": access_check.get("reason")}, status_code=403)
    
    try:
        from app.services.settlement_service import SettlementService
        
        db = SessionLocal()
        try:
            result: Dict[str, Any] = SettlementService.get_settlement_summary(
                db=db,
                year=year,  # type: ignore
                month=month  # type: ignore
            )
            return JSONResponse(result)
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"[get_settlement_summary] Error: {str(e)}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)




@router.get("/settlement/company-monthly-aggregate")
async def get_company_monthly_aggregate(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None,
    company_id: Optional[int] = None,
):  # type: ignore
    """회사 월별 정산 집계 (role_id != 2 사용자 포함)"""
    # 인증 요구 없음
    db = SessionLocal()
    try:
        q = db.query(SettlementCompanyMonthlyAggregate)
        if year:
            q = q.filter(SettlementCompanyMonthlyAggregate.year == year)
        if month:
            q = q.filter(SettlementCompanyMonthlyAggregate.month == month)
        if company_id:
            q = q.filter(SettlementCompanyMonthlyAggregate.company_id == company_id)
        rows = q.order_by(SettlementCompanyMonthlyAggregate.year.desc(), SettlementCompanyMonthlyAggregate.month.desc()).all()
        data = [
            {
                "company_id": r.company_id,
                "year": r.year,
                "month": r.month,
                "total_orders": r.total_orders,
                "total_items": r.total_items,
                "total_amount": r.total_amount,
                "total_commission": r.total_commission,
                "deducted_tax": r.deducted_tax,
                "deducted_local_tax": r.deducted_local_tax,
                "net_settlement_amount": r.net_settlement_amount,
            }
            for r in rows
        ]
        return JSONResponse({"status": "success", "count": len(data), "records": data})
    except Exception as e:
        logger.error(f"[get_company_monthly_aggregate] Error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        try:
            db.close()
        except Exception:
            pass


@router.get("/settlement/available-months")
async def get_settlement_available_months(request: Request):  # type: ignore
    """
    사용자가 속한 회사의 정산 데이터가 있는 모든 년/월 조회
    
    Returns:
        {
            "available_months": [
                {"year": 2025, "month": 11},
                {"year": 2025, "month": 10},
                ...
            ]
        }
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return JSONResponse({"status": "error", "message": "로그인 필요"}, status_code=401)
        
        db = SessionLocal()
        try:
            # 사용자 정보 조회
            user = db.query(User).filter(User.user_id == int(user_id)).first()
            if not user:
                return JSONResponse({"status": "error", "message": "사용자 정보 없음"}, status_code=404)
            
            user_id_int = int(user_id)
            role_id = int(getattr(user, 'role_id', 3))
            
            # role_id별로 다른 테이블에서 조회
            available_months = []
            
            if role_id == 3:  # 원장
                # Settlement에서 이 사용자의 년/월 조회
                from sqlalchemy import extract
                records = db.query(
                    extract('year', Settlement.settlement_date).label('year'),
                    extract('month', Settlement.settlement_date).label('month')
                ).filter(
                    Settlement.user_id == user_id_int
                ).distinct().order_by(
                    extract('year', Settlement.settlement_date).desc(),
                    extract('month', Settlement.settlement_date).desc()
                ).all()
                
                available_months = [
                    {"year": int(r[0]), "month": int(r[1])} for r in records
                ]
            
            elif role_id == 2:  # 지사장
                # SettlementCompanyMonthlyAggregate에서 이 회사의 년/월 조회
                company_id = int(getattr(user, 'company_id', 0))
                records = db.query(
                    SettlementCompanyMonthlyAggregate.year,
                    SettlementCompanyMonthlyAggregate.month
                ).filter(
                    SettlementCompanyMonthlyAggregate.company_id == company_id
                ).distinct().order_by(
                    SettlementCompanyMonthlyAggregate.year.desc(),
                    SettlementCompanyMonthlyAggregate.month.desc()
                ).all()
                
                available_months = [
                    {"year": int(r[0]), "month": int(r[1])} for r in records
                ]
            
            elif role_id == 1:  # 관리자
                # 모든 정산 데이터의 년/월 조회
                from sqlalchemy import extract
                records = db.query(
                    extract('year', Settlement.settlement_date).label('year'),
                    extract('month', Settlement.settlement_date).label('month')
                ).distinct().order_by(
                    extract('year', Settlement.settlement_date).desc(),
                    extract('month', Settlement.settlement_date).desc()
                ).all()
                
                available_months = [
                    {"year": int(r[0]), "month": int(r[1])} for r in records
                ]

            from app.services.monthly_settlement_summary_service import (
                filter_confirmable_month_entries,
            )
            from zoneinfo import ZoneInfo

            available_months = filter_confirmable_month_entries(
                available_months,
                datetime.now(ZoneInfo("Asia/Seoul")),
            )
            
            return JSONResponse({
                "status": "success",
                "available_months": available_months
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[get_settlement_available_months] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/settlement/statement-month-grid")
async def get_statement_month_grid(
    request: Request,
    year: Optional[int] = None,
    company_id: Optional[int] = None,
):  # type: ignore
    """
    정산서 월 선택 그리드용 데이터 (12개월 고정)
    - is_issued: 해당 월 정산서 발행 여부
    - gross_amount: 공제 전 정산 금액 (total_commission 합계)
    """
    access_check = check_admin_access(request)
    if not access_check.get("allowed"):
        return JSONResponse({"status": "error", "message": access_check.get("reason")}, status_code=403)

    try:
        user_id = request.session.get("user_id")
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.user_id == int(user_id)).first()
            if not user:
                return JSONResponse({"status": "error", "message": "사용자 정보 없음"}, status_code=404)

            role_id = int(getattr(user, "role_id", 0))
            if role_id == 1 and company_id:
                target_company_id = int(company_id)
            elif role_id == 2:
                target_company_id = int(getattr(user, "company_id", 0))
            elif role_id == 1:
                target_company_id = int(getattr(user, "company_id", 0))
            else:
                return JSONResponse({"status": "error", "message": "접근 권한이 없습니다"}, status_code=403)

            if not target_company_id:
                return JSONResponse({"status": "error", "message": "회사 정보를 찾을 수 없습니다"}, status_code=400)

            now = datetime.now()
            target_year = int(year) if year else now.year

            # 조회 가능 연도: 집계/정산 데이터가 있는 연도 + 올해
            year_rows = (
                db.query(SettlementCompanyMonthlyAggregate.year)
                .filter(SettlementCompanyMonthlyAggregate.company_id == target_company_id)
                .distinct()
                .all()
            )
            available_years = {int(r[0]) for r in year_rows if r[0]}
            available_years.add(now.year)
            available_years = sorted(available_years, reverse=True)

            from app.services.monthly_settlement_summary_service import (
                is_company_monthly_statement_issued,
            )

            months_payload: List[Dict[str, Any]] = []
            for month in range(1, 13):
                gross_row = (
                    db.query(func.coalesce(func.sum(Settlement.total_commission), 0))
                    .join(User, User.user_id == Settlement.user_id)
                    .filter(
                        User.company_id == target_company_id,
                        User.role_id == 3,
                        Settlement.settlement_type == "monthly",
                        extract("year", Settlement.settlement_date) == target_year,
                        extract("month", Settlement.settlement_date) == month,
                    )
                    .scalar()
                )
                gross_amount = int(gross_row or 0)

                is_issued = is_company_monthly_statement_issued(
                    db,
                    company_id=target_company_id,
                    year=target_year,
                    month=month,
                )

                months_payload.append({
                    "month": month,
                    "is_issued": is_issued,
                    "gross_amount": gross_amount,
                })

            return JSONResponse({
                "status": "success",
                "year": target_year,
                "company_id": target_company_id,
                "available_years": available_years,
                "months": months_payload,
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[get_statement_month_grid] Error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/settlement/user-statement")
async def get_user_settlement_statement(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None,
):  # type: ignore
    """
    로그인한 사용자의 월별 정산 정보 조회
    
    Args:
        year: 대상 연도 (기본값: 현재 연도)
        month: 대상 월 (기본값: 현재 월)
    
    Returns:
        정산 데이터 및 사용자 정보
    """
    try:
        user_id = request.session.get("user_id")
        if not user_id:
            return JSONResponse({"status": "error", "message": "로그인 필요"}, status_code=401)
        
        # 기본값 설정
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        db = SessionLocal()
        try:
            # 사용자 정보 조회
            user = db.query(User).filter(User.user_id == int(user_id)).first()
            if not user:
                return JSONResponse({"status": "error", "message": "사용자 정보 없음"}, status_code=404)
            
            # 사용자의 월별 정산 조회 (role_id별로)
            from sqlalchemy import extract
            user_settlement = db.query(Settlement).filter(
                Settlement.user_id == int(user_id),
                extract('year', Settlement.settlement_date) == year,
                extract('month', Settlement.settlement_date) == month,
            ).first()
            
            # 회사의 월별 정산 조회 (만약 지사장이면)
            company_settlement = None
            if int(getattr(user, 'role_id', 3)) == 2:  # 지사장 (role_id=2)
                company_settlement = db.query(SettlementCompanyMonthlyAggregate).filter(
                    SettlementCompanyMonthlyAggregate.company_id == int(getattr(user, 'company_id', 0)),
                    SettlementCompanyMonthlyAggregate.year == year,
                    SettlementCompanyMonthlyAggregate.month == month,
                ).first()
            
            # 사용자별 상품정산 조회 (role_id=3)
            user_order_items = []
            if int(getattr(user, 'role_id', 3)) == 3:
                # Order 테이블에서 직접 상품별 통계 계산
                user_login_id = str(getattr(user, 'login_id', ''))
                
                # 해당 월의 주문 조회
                orders = db.query(Order).filter(
                    Order.member_id == user_login_id,
                    Order.order_status == 'Y',
                    Order.pay_status == 'Y'
                ).all()
                
                # 해당 월의 주문만 필터링
                month_orders = []
                for order in orders:
                    try:
                        order_date_str = str(getattr(order, 'order_date', '') or '')
                        if ' ' in order_date_str:
                            order_date_str = order_date_str.replace('-', '').replace(':', '').replace(' ', '')
                        
                        if len(order_date_str) >= 6:
                            order_year = int(order_date_str[:4])
                            order_month = int(order_date_str[4:6])
                            
                            if order_year == year and order_month == month:
                                month_orders.append(order)
                    except (ValueError, TypeError):
                        continue
                
                # 상품별 집계
                product_stats = {}  # {product_uid: {product_name, orders_set, quantity, amount}}
                
                for order in month_orders:
                    items = db.query(OrderItem).filter(OrderItem.ordernum == order.ordernum).all()
                    for item in items:
                        product_uid = str(getattr(item, 'product_uid', ''))
                        product_name = str(getattr(item, 'product_name', ''))
                        quantity = int(getattr(item, 'basket_stock', 1))
                        unit_price = int(getattr(item, 'sell_price', 0))
                        
                        if product_uid not in product_stats:
                            product_stats[product_uid] = {
                                'product_name': product_name,
                                'orders_set': set(),
                                'quantity': 0,
                                'amount': 0
                            }
                        
                        product_stats[product_uid]['orders_set'].add(order.ordernum)
                        product_stats[product_uid]['quantity'] += quantity
                        product_stats[product_uid]['amount'] += quantity * unit_price
                
                # 리스트로 변환
                user_order_items = [
                    {
                        'product_uid': uid,
                        'product_name': stats['product_name'],
                        'total_orders': len(stats['orders_set']),
                        'total_quantity': stats['quantity'],
                        'total_amount': stats['amount']
                    }
                    for uid, stats in product_stats.items()
                ]
            
            return JSONResponse({
                "status": "success",
                "user": {
                    "user_id": int(getattr(user, 'user_id', 0)),
                    "name": getattr(user, 'name', ''),
                    "code": getattr(user, 'code', None),
                    "email": getattr(user, 'email', ''),
                    "company_id": int(getattr(user, 'company_id', 0)),
                    "role_id": int(getattr(user, 'role_id', 3)),
                    "main_contact": getattr(user, 'main_contact', ''),
                },
                "settlement": {
                    "year": year,
                    "month": month,
                    "total_orders": int(getattr(user_settlement, 'total_orders', 0)) if user_settlement else 0,
                    "total_items": int(getattr(user_settlement, 'total_items', 0)) if user_settlement else 0,
                    "total_amount": int(getattr(user_settlement, 'total_amount', 0)) if user_settlement else 0,
                    "total_commission": int(getattr(user_settlement, 'total_commission', 0)) if user_settlement else 0,
                    "deducted_tax": int(getattr(user_settlement, 'deducted_tax', 0)) if user_settlement else 0,
                    "deducted_local_tax": int(getattr(user_settlement, 'deducted_local_tax', 0)) if user_settlement else 0,
                    "net_settlement_amount": int(getattr(user_settlement, 'net_settlement_amount', 0)) if user_settlement else 0,
                },
                "company_settlement": {
                    "total_orders": int(getattr(company_settlement, 'total_orders', 0)) if company_settlement else None,
                    "total_items": int(getattr(company_settlement, 'total_items', 0)) if company_settlement else None,
                    "total_amount": int(getattr(company_settlement, 'total_amount', 0)) if company_settlement else None,
                } if company_settlement else None,
                "order_items": [
                    {
                        "product_uid": item['product_uid'],
                        "product_name": item['product_name'],
                        "total_orders": item['total_orders'],
                        "total_quantity": item['total_quantity'],
                        "total_amount": item['total_amount'],
                    }
                    for item in (user_order_items or [])
                ],
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[get_user_settlement_statement] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.post("/settlement/confirm-statement")
async def confirm_settlement_statement(request: Request):
    """정산서 확인 API - 확인 시점이 유효 기간 내/외인지 함께 반환."""
    try:
        user_id_str = request.session.get("user_id")
        if not user_id_str:
            return JSONResponse(
                {"status": "error", "message": "로그인 필요"},
                status_code=401,
            )

        user_id = int(user_id_str)

        # JSON 본문에서 year, month 추출
        try:
            data = await request.json()
            year = int(data.get("year"))
            month = int(data.get("month"))
        except (ValueError, KeyError, AttributeError):
            return JSONResponse(
                {"status": "error", "message": "year와 month 파라미터가 필요합니다"},
                status_code=400,
            )

        from app.services.monthly_settlement_summary_service import (
            is_settlement_period_confirmable,
            max_confirmable_settlement_period,
        )
        from zoneinfo import ZoneInfo

        now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
        if not is_settlement_period_confirmable(year, month, now_kst):
            max_y, max_m = max_confirmable_settlement_period(now_kst)
            return JSONResponse(
                {
                    "status": "error",
                    "message": (
                        f"{year}년 {month:02d}월 정산서는 아직 확인할 수 없습니다. "
                        f"({max_y}년 {max_m:02d}월까지 확인 가능)"
                    ),
                },
                status_code=400,
            )

        db = SessionLocal()
        try:
            from sqlalchemy import extract
            from datetime import datetime as dt
            from app.models import Statement
            from app.services.monthly_settlement_summary_service import (
                compute_confirmation_category,
                is_company_monthly_statement_issued,
                resolve_confirmation_window,
                resolve_statement_company_id_for_user,
                KST as CONF_KST,
            )

            current_user = db.query(User).filter(User.user_id == user_id).first()
            if not current_user:
                return JSONResponse(
                    {"status": "error", "message": "사용자 정보 없음"},
                    status_code=404,
                )

            # 해당 월 정산 레코드 조회 (발행일 기반 유효 기간 계산에 사용)
            settlement = (
                db.query(Settlement)
                .filter(
                    Settlement.user_id == user_id,
                    Settlement.settlement_type == "monthly",
                    extract("year", Settlement.settlement_date) == year,
                    extract("month", Settlement.settlement_date) == month,
                )
                .first()
            )

            issued_at = getattr(settlement, "statement_issued_at", None) if settlement else None
            window_start, deadline, carryover_start = resolve_confirmation_window(
                issued_at, year, month
            )
            now_kst = datetime.now(CONF_KST)

            # 기존 확인 기록이 있는지 확인
            existing = (
                db.query(SettlementStatementConfirmation)
                .filter(
                    SettlementStatementConfirmation.user_id == user_id,
                    SettlementStatementConfirmation.year == year,
                    SettlementStatementConfirmation.month == month,
                )
                .first()
            )

            if existing:
                confirmed_at_value = existing.confirmed_at
                stored_category = getattr(existing, "confirmation_category", None)
                if stored_category in ("지급", "이월"):
                    resolved_category = stored_category
                elif confirmed_at_value:
                    resolved_category = compute_confirmation_category(
                        confirmed_at_value, year, month
                    )
                else:
                    resolved_category = "이월"
                category = "within" if resolved_category == "지급" else "overdue"
                popup_message = (
                    "이미 기간 내에 정산서를 확인하셨습니다."
                    if category == "within"
                    else "이미 정산 확인 기간이 지난 후에 정산서를 확인하셨습니다.\n정산금 지급은 다음달로 이월됩니다."
                )
                return JSONResponse(
                    {
                        "status": "success",
                        "message": "이미 확인된 정산서입니다",
                        "confirmed_at": confirmed_at_value.isoformat()
                        if confirmed_at_value
                        else None,
                        "window": {
                            "category": category,
                            "issued_at": issued_at.isoformat() if issued_at else None,
                            "window_start": window_start.isoformat(),
                            "deadline": deadline.isoformat(),
                            "carryover_start": carryover_start.isoformat(),
                        },
                        "popup_message": popup_message,
                    }
                )

            company_id = resolve_statement_company_id_for_user(current_user)
            if not company_id or not is_company_monthly_statement_issued(
                db, company_id=company_id, year=year, month=month
            ):
                return JSONResponse(
                    {
                        "status": "error",
                        "message": (
                            f"{year}년 {month:02d}월 정산서가 아직 발행되지 않아 "
                            "확인할 수 없습니다."
                        ),
                    },
                    status_code=400,
                )

            confirmation_category = compute_confirmation_category(now_kst, year, month)
            category = "within" if confirmation_category == "지급" else "overdue"

            # 새로운 확인 기록 생성
            confirmation = SettlementStatementConfirmation(
                user_id=user_id,
                year=year,
                month=month,
                confirmation_category=confirmation_category,
            )
            db.add(confirmation)

            # Settlement 테이블의 상태도 업데이트
            if settlement:
                setattr(settlement, "statement_status", "CONFIRMED")
                setattr(settlement, "statement_confirmed_at", dt.now())
                db.add(settlement)
                logger.info(
                    f"[confirm_settlement_statement] Updated settlement status to CONFIRMED for user {user_id}, {year}-{month:02d}"
                )

            # Statement 테이블도 업데이트
            statement = (
                db.query(Statement)
                .filter(
                    Statement.user_id == user_id,
                    Statement.year == year,
                    Statement.month == month,
                )
                .first()
            )

            if statement:
                setattr(statement, "is_confirmed", True)
                setattr(statement, "confirmed_at", dt.now())
                db.add(statement)
                logger.info(
                    f"[confirm_settlement_statement] Updated statement is_confirmed to True for user {user_id}, {year}-{month:02d}"
                )

            db.commit()
            db.refresh(confirmation)

            confirmed_at_value = getattr(confirmation, "confirmed_at", None)
            popup_message = (
                "기간 내에 정산서를 확인하셨습니다."
                if category == "within"
                else "정산 확인 기간이 지났습니다.\n정산금 지급은 다음달로 이월됩니다."
            )

            return JSONResponse(
                {
                    "status": "success",
                    "message": "정산서 확인이 저장되었습니다",
                    "confirmed_at": confirmed_at_value.isoformat()
                    if confirmed_at_value
                    else None,
                    "window": {
                        "category": category,
                        "issued_at": issued_at.isoformat() if issued_at else None,
                        "window_start": window_start.isoformat(),
                        "deadline": deadline.isoformat(),
                        "carryover_start": carryover_start.isoformat(),
                    },
                    "popup_message": popup_message,
                }
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(
            f"[confirm_settlement_statement] Error: {str(e)}", exc_info=True
        )
        return JSONResponse(
            {"status": "error", "message": str(e)},
            status_code=500,
        )


@router.get("/settlement/check-statement-confirmation")
async def check_settlement_confirmation(request: Request, year: int, month: int):
    """정산서 확인 상태 확인 API - 확인 여부 및 유효 기간 상태(미시작/기간 내/기간 경과)를 반환."""
    try:
        user_id_str = request.session.get("user_id")
        if not user_id_str:
            return JSONResponse({
                "status": "error",
                "message": "로그인 필요"
            }, status_code=401)
        
        user_id = int(user_id_str)
        
        db = SessionLocal()
        try:
            from sqlalchemy import extract

            # 확인 기록 조회
            confirmation = (
                db.query(SettlementStatementConfirmation)
                .filter(
                    SettlementStatementConfirmation.user_id == user_id,
                    SettlementStatementConfirmation.year == year,
                    SettlementStatementConfirmation.month == month,
                )
                .first()
            )

            # 정산서 발행일 기준 유효 기간 계산
            settlement = (
                db.query(Settlement)
                .filter(
                    Settlement.user_id == user_id,
                    Settlement.settlement_type == "monthly",
                    extract("year", Settlement.settlement_date) == year,
                    extract("month", Settlement.settlement_date) == month,
                )
                .first()
            )

            from app.services.monthly_settlement_summary_service import (
                KST,
                is_company_monthly_statement_issued,
                resolve_confirmation_window,
                resolve_statement_company_id_for_user,
            )

            current_user = db.query(User).filter(User.user_id == user_id).first()
            company_id = (
                resolve_statement_company_id_for_user(current_user) if current_user else None
            )
            is_issued = bool(
                company_id
                and is_company_monthly_statement_issued(
                    db, company_id=company_id, year=year, month=month
                )
            )

            issued_at = getattr(settlement, "statement_issued_at", None) if settlement else None
            window_start, deadline, carryover_start = resolve_confirmation_window(
                issued_at, year, month
            )

            now = datetime.now(KST)

            is_confirmed = confirmation is not None

            if now < window_start:
                window_state = "before"
            elif now <= deadline:
                window_state = "within"
            else:
                window_state = "after"

            is_overdue = (window_state == "after") and not is_confirmed

            return JSONResponse(
                {
                    "status": "success",
                    "is_confirmed": is_confirmed,
                    "is_issued": is_issued,
                    "is_overdue": is_overdue,
                    "window_state": window_state,
                    "issued_at": issued_at.isoformat() if issued_at else None,
                    "window_start": window_start.isoformat(),
                    "deadline": deadline.isoformat(),
                    "carryover_start": carryover_start.isoformat(),
                    "confirmed_at": confirmation.confirmed_at.isoformat()
                    if confirmation
                    else None,
                }
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[check_settlement_confirmation] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/settlement/user-purchase-stats")
async def get_user_purchase_stats(
    request: Request, 
    user_id: Optional[int] = None,
    months: int = 6
):
    """
    사용자의 최근 N개월 구매 건수 및 통계 조회 (Order/OrderItem 테이블 직접 쿼리)
    
    Query Parameters:
    - user_id: 조회할 사용자 ID (없으면 본인)
    - months: 조회할 개월 수 (기본 6개월)
    
    Returns:
    - monthly_stats: 월별 구매 통계 [{year, month, order_count, item_count, total_amount}, ...]
    - total_stats: 전체 합계 {total_orders, total_items, total_amount}
    """
    try:
        # 세션에서 사용자 정보 확인
        session_user_id = request.session.get("user_id")
        session_role_id = request.session.get("role_id")
        
        if not session_user_id:
            return JSONResponse({
                "status": "error",
                "message": "로그인 필요"
            }, status_code=401)
        
        session_user_id = int(session_user_id)
        
        # user_id가 지정되지 않으면 본인
        target_user_id = user_id if user_id else session_user_id
        
        db = SessionLocal()
        try:
            # 권한 확인: role_id=1(본사)은 모든 사용자, role_id=2(지사장)는 같은 회사, role_id=3(원장)은 본인만
            if session_role_id == 3 and target_user_id != session_user_id:
                return JSONResponse({
                    "status": "error",
                    "message": "본인의 정보만 조회할 수 있습니다"
                }, status_code=403)
            
            if session_role_id == 2:
                # 지사장: 같은 회사 사용자만 조회 가능
                session_user = db.query(User).filter(User.user_id == session_user_id).first()
                target_user = db.query(User).filter(User.user_id == target_user_id).first()
                
                if not session_user or not target_user:
                    return JSONResponse({
                        "status": "error",
                        "message": "사용자를 찾을 수 없습니다"
                    }, status_code=404)
                
                if target_user.company_id != session_user.company_id:
                    return JSONResponse({
                        "status": "error",
                        "message": "같은 회사의 사용자만 조회할 수 있습니다"
                    }, status_code=403)
            
            # 대상 사용자 정보 조회
            target_user = db.query(User).filter(User.user_id == target_user_id).first()
            if not target_user:
                return JSONResponse({
                    "status": "error",
                    "message": "사용자를 찾을 수 없습니다"
                }, status_code=404)
            
            # User.login_id 가져오기 (Order.member_id와 매칭)
            target_login_id = str(target_user.login_id)
            
            # 최근 N개월 계산
            now = datetime.now()
            current_year = now.year
            current_month = now.month
            
            # 월별 통계 조회
            monthly_stats = []
            total_orders = 0
            total_items = 0
            total_amount = 0
            
            for i in range(months):
                # 월 계산 (현재 월부터 과거로)
                month_offset = i
                target_month = current_month - month_offset
                target_year = current_year
                
                while target_month <= 0:
                    target_month += 12
                    target_year -= 1
                
                # Order 테이블에서 직접 조회 (order_status='Y', pay_status='Y')
                # order_date 형식: YYYYMMDDHHMMSS 또는 'YYYY-MM-DD HH:MM:SS'
                from app.models import OrderItem
                
                # 해당 월의 주문 조회
                orders = db.query(Order).filter(
                    Order.member_id == target_login_id,
                    Order.order_status == 'Y',
                    Order.pay_status == 'Y'
                ).all()
                
                # 해당 월의 주문만 필터링
                month_orders = []
                for order in orders:
                    try:
                        order_date_str = str(getattr(order, 'order_date', '') or '')
                        # YYYY-MM-DD HH:MM:SS 형식 처리
                        if ' ' in order_date_str:
                            order_date_str = order_date_str.replace('-', '').replace(':', '').replace(' ', '')
                        
                        if len(order_date_str) >= 6:
                            order_year = int(order_date_str[:4])
                            order_month = int(order_date_str[4:6])
                            
                            if order_year == target_year and order_month == target_month:
                                month_orders.append(order)
                    except (ValueError, TypeError):
                        continue
                
                # 해당 월의 통계 계산
                order_count = len(month_orders)
                item_count = 0
                amount = 0
                
                for order in month_orders:
                    # OrderItem 개수 계산
                    items = db.query(OrderItem).filter(OrderItem.ordernum == order.ordernum).all()
                    for item in items:
                        quantity = int(getattr(item, 'basket_stock', 1))
                        unit_price = int(getattr(item, 'sell_price', 0))
                        item_count += quantity
                        amount += quantity * unit_price
                
                monthly_stats.append({
                    "year": target_year,
                    "month": target_month,
                    "order_count": order_count,
                    "item_count": item_count,
                    "total_amount": amount
                })
                
                total_orders += order_count
                total_items += item_count
                total_amount += amount
            
            # 최신 월이 먼저 오도록 정렬 (과거 → 현재)
            monthly_stats.reverse()
            
            return JSONResponse({
                "status": "success",
                "user_id": target_user_id,
                "user_name": target_user.name,
                "login_id": target_login_id,
                "months": months,
                "monthly_stats": monthly_stats,
                "total_stats": {
                    "total_orders": total_orders,
                    "total_items": total_items,
                    "total_amount": total_amount
                }
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[get_user_purchase_stats] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/settlement/overview-years")
async def get_settlement_overview_years(request: Request):
    """정산 개요 연도 목록 조회 - 실제 데이터가 있는 연도 반환"""
    try:
        db = SessionLocal()
        try:
            # 요청자 세션에서 user_id를 가져와 company_id 확인
            try:
                session_user_id = request.session.get('user_id')
            except Exception:
                session_user_id = None

            if not session_user_id:
                return JSONResponse({"status": "error", "message": "로그인이 필요합니다"}, status_code=401)

            # 세션 user_id로 User 조회하여 company_id 얻기
            session_user = db.query(User).filter(User.user_id == int(session_user_id)).first()
            if not session_user:
                return JSONResponse({"status": "error", "message": "사용자 정보를 찾을 수 없습니다"}, status_code=404)
            
            session_company_id = session_user.company_id
            
            # 해당 회사의 원장(role_id=3) Settlement에서 연도 추출
            from sqlalchemy import distinct
            years_query = db.query(distinct(extract('year', Settlement.settlement_date))).join(
                User, Settlement.user_id == User.user_id
            ).filter(
                User.company_id == int(session_company_id),
                User.role_id == 3,
                Settlement.settlement_date.isnot(None)
            ).order_by(extract('year', Settlement.settlement_date).desc())
            
            years = [int(row[0]) for row in years_query.all() if row[0]]
            
            # "전체" 옵션 추가
            year_options = ["전체"] + [str(year) for year in years]
            
            return JSONResponse({
                "status": "success",
                "years": year_options
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[get_settlement_overview_years] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/settlement/overview-data")
async def get_settlement_overview_data(
    request: Request,
    year: Optional[str] = None
):
    """정산 개요 데이터 조회 - 회사 원장들의 월별 합산 데이터"""
    try:
        db = SessionLocal()
        try:
            # 요청자 세션에서 user_id를 가져와 company_id 확인
            try:
                session_user_id = request.session.get('user_id')
            except Exception:
                session_user_id = None

            if not session_user_id:
                return JSONResponse({"status": "error", "message": "로그인이 필요합니다"}, status_code=401)

            # 세션 user_id로 User 조회하여 company_id 얻기
            session_user = db.query(User).filter(User.user_id == int(session_user_id)).first()
            if not session_user:
                return JSONResponse({"status": "error", "message": "사용자 정보를 찾을 수 없습니다"}, status_code=404)
            
            session_company_id = session_user.company_id
            
            # 1. 해당 회사의 원장(role_id=3) Settlement 조회
            query = db.query(Settlement).join(User, Settlement.user_id == User.user_id)
            query = query.filter(User.company_id == int(session_company_id), User.role_id == 3)
            
            # 연도 필터링
            if year and year != "전체":
                query = query.filter(extract('year', Settlement.settlement_date) == int(year))
            
            settlements = select_canonical_settlements(query.all())
            
            if not settlements:
                return JSONResponse({
                    "status": "success",
                    "data": [],
                    "summary": {
                        "sell_price_total": 0,
                        "used_reserve_total": 0,
                        "actual_payment_total": 0,
                        "commission_total": 0,
                        "net_settlement_total": 0
                    }
                })
            
            # 2. 관련된 모든 주문번호 추출
            all_order_nums = set()
            for settlement in settlements:
                if settlement.commission_details:
                    import json
                    try:
                        details = json.loads(settlement.commission_details)
                        for detail in details:
                            ordernum = detail.get('ordernum')
                            if ordernum:
                                all_order_nums.add(ordernum)
                    except Exception:
                        pass
            
            # 3. 모든 Order를 한 번에 조회 (배치 조회)
            orders_map = {}
            if all_order_nums:
                orders = db.query(Order).filter(Order.ordernum.in_(list(all_order_nums))).all()
                for order in orders:
                    orders_map[order.ordernum] = order
            
            # 4. 월별 그룹화 (YYYY-MM 형식)
            from collections import defaultdict
            
            month_aggregates = defaultdict(lambda: {
                'sell_price_total': 0,
                'used_reserve_total': 0,
                'actual_payment_total': 0,
                'commission_total': 0,
                'processed_orders': set()
            })
            
            for settlement in settlements:
                if not settlement.settlement_date:
                    continue
                
                # 월 키 생성 (YYYY-MM)
                month_key = settlement.settlement_date.strftime("%Y-%m")
                agg = month_aggregates[month_key]
                
                if settlement.commission_details:
                    import json
                    try:
                        details = json.loads(settlement.commission_details)
                        
                        for detail in details:
                            # 정산액이 0원인 항목은 제외
                            commission = detail.get('commission', 0)
                            if commission == 0:
                                continue
                            
                            ordernum = detail.get('ordernum')
                            
                            # Order 정보 합산 (중복 제거)
                            if ordernum and ordernum in orders_map and ordernum not in agg['processed_orders']:
                                order = orders_map[ordernum]
                                agg['used_reserve_total'] += int(getattr(order, 'used_reserve', 0) or 0)
                                agg['actual_payment_total'] += int(getattr(order, 'pay_price', 0) or 0)
                                agg['processed_orders'].add(ordernum)
                            
                            # payment_amount와 commission 합산
                            payment_amount = detail.get('payment_amount', 0)
                            agg['sell_price_total'] += payment_amount
                            agg['commission_total'] += commission
                    except Exception as e:
                        logger.error(f"Error parsing commission_details: {e}")
            
            # 5. 결과 배열 생성
            result_data = []
            
            # 정렬: 월 내림차순 (최신순)
            sorted_months = sorted(month_aggregates.keys(), reverse=True)
            
            # 전체 합계 계산
            total_sell_price = 0
            total_used_reserve = 0
            total_actual_payment = 0
            total_commission = 0
            
            for month_key in sorted_months:
                agg = month_aggregates[month_key]
                
                # 지급총액(공제전) = 정산예정금액 (commission_total과 동일)
                net_settlement = agg['commission_total']
                
                result_data.append({
                    "settlement_date": month_key,
                    "sell_price_total": agg['sell_price_total'],
                    "used_reserve_total": agg['used_reserve_total'],
                    "actual_payment_total": agg['actual_payment_total'],
                    "commission_total": agg['commission_total'],
                    "net_settlement_total": net_settlement
                })
                
                # 합계 누적
                total_sell_price += agg['sell_price_total']
                total_used_reserve += agg['used_reserve_total']
                total_actual_payment += agg['actual_payment_total']
                total_commission += agg['commission_total']
            
            return JSONResponse({
                "status": "success",
                "data": result_data,
                "summary": {
                    "sell_price_total": total_sell_price,
                    "used_reserve_total": total_used_reserve,
                    "actual_payment_total": total_actual_payment,
                    "commission_total": total_commission,
                    "net_settlement_total": total_commission
                }
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[get_settlement_overview_data] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/settlement/status-data")
async def get_settlement_status_data(
    request: Request,
    month: Optional[str] = None
):
    """정산 현황 데이터 조회 - 회사 원장들의 월별 데이터 (원장별 행) - 최적화 버전"""
    import json
    from collections import defaultdict
    
    try:
        db = SessionLocal()
        try:
            # 요청자 세션에서 user_id를 가져와 company_id 확인
            session_user_id = request.session.get('user_id')
            if not session_user_id:
                return JSONResponse({"status": "error", "message": "로그인이 필요합니다"}, status_code=401)

            # 세션 user_id로 User 조회하여 company_id 얻기
            session_user = db.query(User).filter(User.user_id == int(session_user_id)).first()
            if not session_user:
                return JSONResponse({"status": "error", "message": "사용자 정보를 찾을 수 없습니다"}, status_code=404)
            
            session_company_id = session_user.company_id
            
            # 1. 해당 회사의 원장(role_id=3) 목록을 미리 조회 (N+1 방지)
            teachers = db.query(User).filter(
                User.company_id == int(session_company_id),
                User.role_id == 3,
                User.is_active.is_(True),
            ).all()
            
            if not teachers:
                return JSONResponse({"status": "success", "data": []})
            
            # User ID -> User 맵 생성
            users_map = {u.user_id: u for u in teachers}
            teacher_ids = list(users_map.keys())
            
            # 2. Settlement 조회 (한 번에)
            query = db.query(Settlement).filter(Settlement.user_id.in_(teacher_ids))
            
            # 월 필터링
            if month and month != "전체":
                year, mon = month.split("-")
                query = query.filter(
                    extract('year', Settlement.settlement_date) == int(year),
                    extract('month', Settlement.settlement_date) == int(mon)
                )
            
            settlements = select_canonical_settlements(query.all())
            
            if not settlements:
                return JSONResponse({"status": "success", "data": []})
            
            # 3. commission_details 파싱 및 주문번호 추출 (한 번만)
            all_order_nums = set()
            parsed_details = {}  # settlement.id -> parsed details
            
            for settlement in settlements:
                if settlement.commission_details:
                    try:
                        details = json.loads(settlement.commission_details)
                        parsed_details[settlement.id] = details
                        for detail in details:
                            ordernum = detail.get('ordernum')
                            if ordernum:
                                all_order_nums.add(ordernum)
                    except Exception:
                        parsed_details[settlement.id] = []
            
            # 4. 모든 Order를 한 번에 조회 (배치 조회)
            orders_map = {}
            if all_order_nums:
                orders = db.query(Order).filter(Order.ordernum.in_(list(all_order_nums))).all()
                orders_map = {order.ordernum: order for order in orders}
            
            # 5. 결과 데이터 생성 (원장별 그룹화)
            user_aggregates = defaultdict(lambda: {
                'sell_price_total': 0,
                'delivery_total': 0,
                'used_reserve_total': 0,
                'actual_payment_total': 0,
                'processed_orders': set(),
                'settlement_months': set()
            })
            
            for settlement in settlements:
                user_id = settlement.user_id
                if user_id not in users_map:
                    continue
                
                agg = user_aggregates[user_id]
                
                # 월 추적
                if settlement.settlement_date:
                    agg['settlement_months'].add(settlement.settlement_date.strftime("%Y-%m"))
                
                # 미리 파싱된 details 사용
                details = parsed_details.get(settlement.id, [])
                for detail in details:
                    # 정산액이 0원인 항목은 제외
                    if detail.get('commission', 0) == 0:
                        continue
                    
                    ordernum = detail.get('ordernum')
                    
                    # Order 정보 합산 (중복 제거)
                    if ordernum and ordernum in orders_map and ordernum not in agg['processed_orders']:
                        order = orders_map[ordernum]
                        agg['delivery_total'] += int(getattr(order, 'deli_price', 0) or 0)
                        agg['used_reserve_total'] += int(getattr(order, 'used_reserve', 0) or 0)
                        agg['actual_payment_total'] += int(getattr(order, 'pay_price', 0) or 0)
                        agg['processed_orders'].add(ordernum)
                    
                    # payment_amount 합산
                    agg['sell_price_total'] += detail.get('payment_amount', 0)
            
            # 6. 결과 배열 생성
            result_data = []
            idx = 1
            
            # 정렬: 이름 오름차순
            sorted_user_ids = sorted(
                user_aggregates.keys(),
                key=lambda uid: users_map[uid].name if uid in users_map and users_map[uid].name else ''
            )
            
            # 합계 계산
            total_consumer_price = 0
            total_sell_price = 0
            total_delivery = 0
            total_used_reserve = 0
            total_actual_payment = 0
            
            for user_id in sorted_user_ids:
                agg = user_aggregates[user_id]
                user = users_map.get(user_id)
                
                if not user:
                    continue
                
                # 소비자가는 판매가와 동일
                consumer_price_total = agg['sell_price_total']
                
                result_data.append({
                    "no": idx,
                    "user_id": user.user_id,
                    "name": user.name or "",
                    "nickname": user.login_id or "",
                    "consumer_price_total": consumer_price_total,
                    "sell_price_total": agg['sell_price_total'],
                    "delivery_total": agg['delivery_total'],
                    "used_reserve_total": agg['used_reserve_total'],
                    "actual_payment_total": agg['actual_payment_total'],
                    "settlement_date": ", ".join(sorted(agg['settlement_months'], reverse=True)) if agg['settlement_months'] else ""
                })
                
                # 합계 누적
                total_consumer_price += consumer_price_total
                total_sell_price += agg['sell_price_total']
                total_delivery += agg['delivery_total']
                total_used_reserve += agg['used_reserve_total']
                total_actual_payment += agg['actual_payment_total']
                
                idx += 1
            
            return JSONResponse({
                "status": "success",
                "data": result_data,
                "summary": {
                    "consumer_price_total": total_consumer_price,
                    "sell_price_total": total_sell_price,
                    "delivery_total": total_delivery,
                    "used_reserve_total": total_used_reserve,
                    "actual_payment_total": total_actual_payment
                }
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[get_settlement_status_data] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/settlement/status-excel")
async def download_settlement_status_excel(
    request: Request,
    month: Optional[str] = None,
    year: Optional[str] = None,
    sort_by: Optional[str] = "amount_desc",
    company_id: Optional[int] = None
):
    """소속 원장별 월매출 엑셀 다운로드"""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from app.services.settlement_status_service import get_settlement_status_data

    try:
        session_user_id = request.session.get("user_id")
        role_id = int(request.session.get("role_id", 0))
        if not session_user_id:
            return JSONResponse({"status": "error", "message": "로그인 필요"}, status_code=401)

        db = SessionLocal()
        try:
            session_user = db.query(User).filter(User.user_id == int(session_user_id)).first()
            if not session_user:
                return JSONResponse({"status": "error", "message": "사용자 정보를 찾을 수 없습니다"}, status_code=404)

            target_company_id = session_user.company_id
            if company_id and role_id == 1:
                target_company_id = int(company_id)

            rows, _summary, _branch_manager_user_id = get_settlement_status_data(
                db,
                int(target_company_id),
                month,
                year,
                sort_by or "amount_desc",
            )

            # Excel 생성
            wb = Workbook()
            ws = wb.active

            period_label = month if month and month != "전체" else "누적 총액"
            if month == "전체" and year:
                period_label = f"{year}년 누적 총액"
            ws.title = "소속 원장별 월매출"

            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="2196F3", end_color="2196F3", fill_type="solid")
            center_align = Alignment(horizontal="center", vertical="center")
            right_align = Alignment(horizontal="right", vertical="center")

            headers = ["순번", "이름", "연락처", "판매가 총액", "배송비 총액", "사용된 적립금", "실결제총액"]
            for col, h in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=h)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = center_align

            manager_fill = PatternFill(start_color="FAE5E5", end_color="FAE5E5", fill_type="solid")
            total_sell = total_delivery = total_reserve = total_actual = 0
            row_num = 2
            for row_data in rows:
                actual = row_data["actual_payment_total"]
                display_name = row_data["name"]
                if row_data.get("is_branch_manager"):
                    display_name = f"{display_name} (지사장)"
                ws.cell(row=row_num, column=1, value=row_data["no"]).alignment = center_align
                ws.cell(row=row_num, column=2, value=display_name)
                ws.cell(row=row_num, column=3, value=row_data["phone"])
                ws.cell(row=row_num, column=4, value=row_data["sell_price_total"]).alignment = right_align
                ws.cell(row=row_num, column=5, value=row_data["delivery_total"]).alignment = right_align
                ws.cell(row=row_num, column=6, value=row_data["used_reserve_total"]).alignment = right_align
                ws.cell(row=row_num, column=7, value=actual).alignment = right_align
                if row_data.get("is_branch_manager"):
                    for col in range(1, 8):
                        ws.cell(row=row_num, column=col).fill = manager_fill
                total_sell += row_data["sell_price_total"]
                total_delivery += row_data["delivery_total"]
                total_reserve += row_data["used_reserve_total"]
                total_actual += actual
                row_num += 1

            # 합계 행
            sum_fill = PatternFill(start_color="FFFACD", end_color="FFFACD", fill_type="solid")
            sum_font = Font(bold=True)
            for col in range(1, 8):
                ws.cell(row=row_num, column=col).fill = sum_fill
                ws.cell(row=row_num, column=col).font = sum_font
            ws.cell(row=row_num, column=1, value="합계").alignment = center_align
            ws.cell(row=row_num, column=4, value=total_sell).alignment = right_align
            ws.cell(row=row_num, column=5, value=total_delivery).alignment = right_align
            ws.cell(row=row_num, column=6, value=total_reserve).alignment = right_align
            ws.cell(row=row_num, column=7, value=total_actual).alignment = right_align

            # 열 너비 조정
            ws.column_dimensions['A'].width = 8
            ws.column_dimensions['B'].width = 12
            ws.column_dimensions['C'].width = 18
            ws.column_dimensions['D'].width = 16
            ws.column_dimensions['E'].width = 14
            ws.column_dimensions['F'].width = 14
            ws.column_dimensions['G'].width = 16

            # 숫자 포맷
            for row in ws.iter_rows(min_row=2, max_row=row_num, min_col=4, max_col=7):
                for cell in row:
                    cell.number_format = '#,##0'

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            # BytesIO 내용을 bytes로 읽어서 반환 (안전성 증가)
            excel_data = output.getvalue()
            output.close()

            filename = f"원장별_매출액_{period_label}.xlsx"
            from urllib.parse import quote
            
            # RFC 5987을 따르는 올바른 인코딩 (브라우저 호환성)
            encoded_filename = quote(filename.encode('utf-8'), safe='')
            
            # 폴백용 ASCII 파일명
            fallback_filename = "settlement_status.xlsx"

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
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[download_settlement_status_excel] Error: {str(e)}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.get("/settlement/status-detail/{user_id}")
async def get_settlement_status_detail(
    request: Request,
    user_id: int,
    month: Optional[str] = None,
    year: Optional[str] = None,
    company_id: Optional[int] = None
):
    """정산 현황 상세 내역 - 특정 원장의 주문별 상세 데이터 (monthly만, mtd 중복 제외)."""
    try:
        db = SessionLocal()
        try:
            # 요청자 세션에서 user_id를 가져와 company_id 확인
            try:
                session_user_id = request.session.get('user_id')
            except Exception:
                session_user_id = None

            if not session_user_id:
                return JSONResponse({"status": "error", "message": "로그인이 필요합니다"}, status_code=401)

            # 세션 user_id로 User 조회하여 company_id 얻기
            session_user = db.query(User).filter(User.user_id == int(session_user_id)).first()
            if not session_user:
                return JSONResponse({"status": "error", "message": "사용자 정보를 찾을 수 없습니다"}, status_code=404)
            
            session_company_id = session_user.company_id
            
            # role_id=1(본사관리자)인 경우 URL 파라미터에서 받은 company_id 사용
            if session_user.role_id == 1 and company_id:
                session_company_id = company_id
            
            # 대상 원장 조회 및 권한 확인
            target_user = db.query(User).filter(User.user_id == user_id).first()
            if not target_user:
                return JSONResponse({"status": "error", "message": "원장 정보를 찾을 수 없습니다"}, status_code=404)
            
            # 같은 회사 확인
            if target_user.company_id != session_company_id:
                return JSONResponse({"status": "error", "message": "권한이 없습니다"}, status_code=403)
            
            # monthly만 사용 (mtd/daily 중복 합산 방지)
            query = db.query(Settlement).filter(
                Settlement.user_id == user_id,
                Settlement.settlement_type == "monthly",
            )
            
            # 월 필터링
            if month and month != "전체":
                year_val, mon = month.split("-")
                query = query.filter(
                    extract('year', Settlement.settlement_date) == int(year_val),
                    extract('month', Settlement.settlement_date) == int(mon)
                )
            else:
                # 누적(전체): 선택 연도로 한정 (미전달 시 올해)
                resolved_year = year
                if not resolved_year and month and month != "전체" and "-" in str(month):
                    resolved_year = str(month).split("-")[0]
                if not resolved_year:
                    from zoneinfo import ZoneInfo
                    resolved_year = str(datetime.now(ZoneInfo("Asia/Seoul")).year)
                query = query.filter(
                    extract('year', Settlement.settlement_date) == int(resolved_year)
                )
            
            settlements = query.all()
            
            if not settlements:
                return JSONResponse({
                    "status": "success",
                    "data": []
                })
            
            # 2. commission_details에서 주문별 상세 데이터 추출
            import json
            detail_items = []
            
            for settlement in settlements:
                if not settlement.commission_details:
                    continue
                
                try:
                    details = json.loads(settlement.commission_details)
                    for detail in details:
                        detail_items.append({
                            "ordernum": detail.get('ordernum', ''),
                            "order_date": detail.get('ordernum', '')[:8] if detail.get('ordernum') else '',
                            "product_name": detail.get('product_name', ''),
                            "type_name": detail.get('type_name', '기타'),
                            "commission_type_id": detail.get('commission_type_id'),
                            "quantity": detail.get('quantity', 0),
                            "unit_price": detail.get('unit_price', 0),
                            "payment_amount": detail.get('payment_amount', 0),
                            "actual_payment": detail.get('actual_payment', 0),
                            "rate": detail.get('rate', 0),
                            "commission": detail.get('commission', 0),
                        })
                except Exception as e:
                    logger.error(f"Error parsing commission_details: {e}")
            
            # 3. 정렬: commission_type_id, 주문날짜 순
            detail_items.sort(key=lambda x: (
                x['commission_type_id'] if x['commission_type_id'] is not None else 999,
                x['ordernum']
            ))
            
            return JSONResponse({
                "status": "success",
                "user": {
                    "user_id": target_user.user_id,
                    "name": target_user.name,
                    "login_id": target_user.login_id
                },
                "data": detail_items
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[get_settlement_status_detail] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/settlement/statement-status/{year}/{month}")
async def get_statement_status(request: Request, year: int, month: int):
    """
    정산서 상태 조회 API
    
    Returns:
        {
            "status": "success",
            "statement": {
                "statement_number": "ST-202501-A001-001",
                "statement_status": "ISSUED|CONFIRMED|PAID",
                "statement_issued_at": "2025-01-01T09:00:00",
                "statement_confirmed_at": "2025-01-05T14:30:00",
                "total_commission": 150000,
                "net_settlement_amount": 135000
            }
        }
    """
    try:
        user_id_str = request.session.get("user_id")
        if not user_id_str:
            return JSONResponse({
                "status": "error",
                "message": "로그인 필요"
            }, status_code=401)
        
        user_id = int(user_id_str)
        
        db = SessionLocal()
        try:
            from sqlalchemy import extract
            
            # Settlement 조회
            settlement = db.query(Settlement).filter(
                Settlement.user_id == user_id,
                Settlement.settlement_type == 'monthly',
                extract('year', Settlement.settlement_date) == year,
                extract('month', Settlement.settlement_date) == month
            ).first()
            
            if not settlement:
                return JSONResponse({
                    "status": "error",
                    "message": "정산서를 찾을 수 없습니다"
                }, status_code=404)
            
            # 정산서 정보 반환
            statement_issued_at = getattr(settlement, 'statement_issued_at', None)
            statement_confirmed_at = getattr(settlement, 'statement_confirmed_at', None)
            
            return JSONResponse({
                "status": "success",
                "statement": {
                    "statement_number": getattr(settlement, 'statement_number', None),
                    "statement_status": getattr(settlement, 'statement_status', 'DRAFT'),
                    "statement_issued_at": statement_issued_at.isoformat() if statement_issued_at else None,
                    "statement_confirmed_at": statement_confirmed_at.isoformat() if statement_confirmed_at else None,
                    "total_commission": getattr(settlement, 'total_commission', 0),
                    "net_settlement_amount": getattr(settlement, 'net_settlement_amount', 0),
                    "is_paid": getattr(settlement, 'is_paid', False)
                }
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[get_statement_status] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.post("/settlement/statement-issue/{year}/{month}")
async def issue_statement(request: Request, year: int, month: int):
    """
    정산서 수동 발행 API (관리자용)
    기존 DRAFT 상태의 정산서를 ISSUED로 변경
    """
    try:
        user_id_str = request.session.get("user_id")
        if not user_id_str:
            return JSONResponse({
                "status": "error",
                "message": "로그인 필요"
            }, status_code=401)
        
        user_id = int(user_id_str)
        
        # 관리자 권한 확인 (role_id = 1)
        db = SessionLocal()
        try:
            current_user = db.query(User).filter(User.user_id == user_id).first()
            if not current_user or getattr(current_user, 'role_id', 3) != 1:
                return JSONResponse({
                    "status": "error",
                    "message": "관리자 권한이 필요합니다"
                }, status_code=403)
            
            from sqlalchemy import extract
            from datetime import datetime as dt
            
            # 대상 사용자 ID (쿼리 파라미터로 받거나 전체)
            data = await request.json()
            target_user_id = data.get("target_user_id")
            
            if target_user_id:
                # 특정 사용자의 정산서만 발행
                settlements = db.query(Settlement).filter(
                    Settlement.user_id == target_user_id,
                    Settlement.settlement_type == 'monthly',
                    extract('year', Settlement.settlement_date) == year,
                    extract('month', Settlement.settlement_date) == month,
                    Settlement.statement_status == 'DRAFT'
                ).all()
            else:
                # 모든 DRAFT 정산서 발행
                settlements = db.query(Settlement).filter(
                    Settlement.settlement_type == 'monthly',
                    extract('year', Settlement.settlement_date) == year,
                    extract('month', Settlement.settlement_date) == month,
                    Settlement.statement_status == 'DRAFT'
                ).all()
            
            if not settlements:
                return JSONResponse({
                    "status": "error",
                    "message": "발행할 정산서가 없습니다"
                }, status_code=404)
            
            # 상태 업데이트
            issued_count = 0
            for settlement in settlements:
                setattr(settlement, 'statement_status', 'ISSUED')
                setattr(settlement, 'statement_issued_at', dt.now())
                db.add(settlement)
                issued_count += 1
            
            db.commit()
            
            return JSONResponse({
                "status": "success",
                "message": f"{issued_count}개의 정산서가 발행되었습니다",
                "issued_count": issued_count
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[issue_statement] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


# ========================================
# Statement 관리 API (2단계)
# ========================================

@router.get("/statement/list")
async def list_statements(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """
    정산서 목록 조회 API
    사용자 자신의 정산서 목록을 조회
    """
    try:
        user_id_str = request.session.get("user_id")
        if not user_id_str:
            return JSONResponse({
                "status": "error",
                "message": "로그인 필요"
            }, status_code=401)
        
        user_id = int(user_id_str)
        
        db = SessionLocal()
        try:
            from app.models import Statement
            
            query = db.query(Statement).filter(Statement.user_id == user_id)
            
            if year:
                query = query.filter(Statement.year == year)
            if month:
                query = query.filter(Statement.month == month)
            
            statements = query.order_by(Statement.year.desc(), Statement.month.desc()).all()
            
            statement_list = []
            for stmt in statements:
                statement_list.append({
                    "statement_id": getattr(stmt, 'statement_id'),
                    "statement_number": getattr(stmt, 'statement_number'),
                    "year": getattr(stmt, 'year'),
                    "month": getattr(stmt, 'month'),
                    "total_commission": getattr(stmt, 'total_commission', 0),
                    "net_amount": getattr(stmt, 'net_amount', 0),
                    "is_confirmed": getattr(stmt, 'is_confirmed', False),
                    "issued_at": getattr(stmt, 'issued_at').isoformat() if getattr(stmt, 'issued_at', None) else None,
                    "confirmed_at": getattr(stmt, 'confirmed_at').isoformat() if getattr(stmt, 'confirmed_at', None) else None,
                })
            
            return JSONResponse({
                "status": "success",
                "statements": statement_list
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[list_statements] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/statement/detail/{statement_id}")
async def get_statement_detail(request: Request, statement_id: int):
    """
    정산서 상세 조회 API
    """
    try:
        user_id_str = request.session.get("user_id")
        if not user_id_str:
            return JSONResponse({
                "status": "error",
                "message": "로그인 필요"
            }, status_code=401)
        
        user_id = int(user_id_str)
        
        db = SessionLocal()
        try:
            from app.models import Statement
            
            statement = db.query(Statement).filter(
                Statement.statement_id == statement_id,
                Statement.user_id == user_id
            ).first()
            
            if not statement:
                return JSONResponse({
                    "status": "error",
                    "message": "정산서를 찾을 수 없습니다"
                }, status_code=404)
            
            # 연결된 Settlement 정보 조회
            settlements = db.query(Settlement).filter(
                Settlement.statement_id == statement_id
            ).all()
            
            settlement_list = []
            for s in settlements:
                settlement_list.append({
                    "settlement_id": getattr(s, 'settlement_id'),
                    "total_commission": getattr(s, 'total_commission', 0),
                    "deducted_tax": getattr(s, 'deducted_tax', 0),
                    "deducted_local_tax": getattr(s, 'deducted_local_tax', 0),
                    "net_settlement_amount": getattr(s, 'net_settlement_amount', 0),
                })
            
            issued_at = getattr(statement, 'issued_at', None)
            confirmed_at = getattr(statement, 'confirmed_at', None)
            
            return JSONResponse({
                "status": "success",
                "statement": {
                    "statement_id": getattr(statement, 'statement_id'),
                    "statement_number": getattr(statement, 'statement_number'),
                    "year": getattr(statement, 'year'),
                    "month": getattr(statement, 'month'),
                    "total_commission": getattr(statement, 'total_commission', 0),
                    "deducted_tax": getattr(statement, 'deducted_tax', 0),
                    "deducted_local_tax": getattr(statement, 'deducted_local_tax', 0),
                    "net_amount": getattr(statement, 'net_amount', 0),
                    "is_confirmed": getattr(statement, 'is_confirmed', False),
                    "issued_at": issued_at.isoformat() if issued_at else None,
                    "confirmed_at": confirmed_at.isoformat() if confirmed_at else None,
                    "settlements": settlement_list
                }
            })
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[get_statement_detail] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)

@router.get("/settlement/export-statement-xlsx")
async def export_settlement_statement_xlsx(request: Request, year: int, month: int, company_id: Optional[int] = None):
    """
    정산서 상세를 엑셀(xlsx)로 다운로드합니다.
    - role_id 1(본사)일 경우 company_id 파라미터로 지사 지정 가능
    - role_id 2(지사장) 또는 3(원장)은 세션의 company_id를 사용
    """
    try:
        user_id_str = request.session.get("user_id")
        if not user_id_str:
            return JSONResponse({"status": "error", "message": "로그인 필요"}, status_code=401)

        user_id = int(user_id_str)
        role_id = int(request.session.get("role_id", 3))

        db = SessionLocal()
        try:
            import io, json
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
            from sqlalchemy import extract
            from collections import defaultdict

            from app.services.monthly_settlement_summary_service import (
                format_settlement_type_statement_display,
            )

            # determine company_id context
            current_user = db.query(User).filter(User.user_id == user_id).first()
            if role_id in (1,) and company_id:
                target_company_id = int(company_id)
            else:
                target_company_id = int(getattr(current_user, 'company_id', 0) or 0)

            statement_subject_user = current_user
            if role_id in (1, 2):
                branch_manager = db.query(User).filter(
                    User.company_id == target_company_id,
                    User.role_id == 2,
                ).order_by(User.user_id.asc()).first()
                if branch_manager:
                    statement_subject_user = branch_manager
            settlement_type_display = format_settlement_type_statement_display(statement_subject_user)

            statement_summary = get_statement_summary_amounts(
                db,
                year=year,
                month=month,
                user_id=user_id if role_id == 3 else None,
                company_id=target_company_id if role_id in (1, 2) else None,
                teachers_only=role_id in (1, 2),
            )

            all_commission_details = []

            if role_id in [1, 2]:
                # gather all teachers in company
                teachers = db.query(User).filter(
                    User.company_id == target_company_id,
                    User.role_id == 3,
                    User.is_active.is_(True),
                ).all()
                for teacher in teachers:
                    settlement = db.query(Settlement).filter(
                        Settlement.user_id == teacher.user_id,
                        Settlement.settlement_type == 'monthly',
                        extract('year', Settlement.settlement_date) == year,
                        extract('month', Settlement.settlement_date) == month
                    ).first()
                    if not settlement or not settlement.commission_details:
                        continue
                    try:
                        details = json.loads(str(settlement.commission_details))
                    except Exception:
                        continue
                    for d in details:
                        if d.get('commission', 0) == 0:
                            continue
                        d['user_name'] = getattr(teacher, 'name', '미등록')
                        d['user_code'] = getattr(teacher, 'code', '')
                        all_commission_details.append(d)

            else:
                # role_id == 3 (teacher) - only own settlement
                settlement = db.query(Settlement).filter(
                    Settlement.user_id == int(user_id),
                    Settlement.settlement_type == 'monthly',
                    extract('year', Settlement.settlement_date) == year,
                    extract('month', Settlement.settlement_date) == month
                ).first()
                if settlement and settlement.commission_details:
                    try:
                        details = json.loads(str(settlement.commission_details))
                    except Exception:
                        details = []
                    for d in details:
                        if d.get('commission', 0) == 0:
                            continue
                        d['user_name'] = getattr(current_user, 'name', '')
                        d['user_code'] = getattr(current_user, 'code', '')
                        all_commission_details.append(d)

            # Group by commission type
            type_groups = defaultdict(list)
            for detail in all_commission_details:
                type_name = detail.get('type_name', '기타')
                type_groups[type_name].append(detail)

            # Build xlsx with type grouping
            wb = Workbook()
            ws = wb.active
            ws.title = f"{year}-{str(month).zfill(2)}"
            
            # Header styling
            headers = ['수수료발생일', '결제종류', '코드', '결제자', '정산대상금액', '수수료율(%)', '정산액']
            header_fill = PatternFill(start_color="FFFACD", end_color="FFFACD", fill_type="solid")
            header_font = Font(bold=True)

            ws.append([f"정산 유형: {settlement_type_display}"])
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
            ws["A1"].font = Font(bold=True)
            ws.append([])
            
            ws.append(headers)
            header_row_idx = ws.max_row
            for cell in ws[header_row_idx]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")
            
            grand_total_amount = 0
            grand_total_commission = 0
            
            # Write data grouped by type
            for type_name, items in sorted(type_groups.items()):
                # Sort by ordernum
                sorted_items = sorted(items, key=lambda x: x.get('ordernum', ''))
                
                type_total_amount = 0
                type_total_commission = 0
                
                for item in sorted_items:
                    order_date = item.get('ordernum', '')[:8]
                    if len(order_date) == 8:
                        order_date = f"{order_date[:4]}-{order_date[4:6]}-{order_date[6:8]}"
                    else:
                        order_date = f"{year}-{str(month).zfill(2)}-01"
                    
                    user_code_val = item.get('user_code', '')
                    user_name_val = item.get('user_name', '미등록')
                    actual_payment = int(item.get('actual_payment', 0))
                    rate = float(item.get('rate', 0))
                    commission = int(item.get('commission', 0))
                    
                    type_total_amount += actual_payment
                    type_total_commission += commission
                    
                    row = [order_date, type_name, user_code_val, user_name_val, actual_payment, int(rate), commission]
                    ws.append(row)
                
                # Subtotal row for this type
                rate_int = int(sorted_items[0].get('rate', 0)) if sorted_items else 0
                subtotal_row = ['', '', '', '소계', type_total_amount, rate_int, type_total_commission]
                ws.append(subtotal_row)
                
                # Style subtotal row
                last_row = ws.max_row
                subtotal_fill = PatternFill(start_color="FFFACD", end_color="FFFACD", fill_type="solid")
                subtotal_font = Font(bold=True)
                for cell in ws[last_row]:
                    cell.fill = subtotal_fill
                    cell.font = subtotal_font
                
                grand_total_amount += type_total_amount
                grand_total_commission += type_total_commission
            
            # Grand total row
            ws.append(['', '', '', '총 합계', '', '', grand_total_commission])
            last_row = ws.max_row
            total_fill = PatternFill(start_color="E6F3FF", end_color="E6F3FF", fill_type="solid")
            total_font = Font(bold=True)
            for cell in ws[last_row]:
                cell.fill = total_fill
                cell.font = total_font
            
            # Tax and net amount rows (십 단위 절사)
            income_tax, local_tax, net_amount = calc_settlement_taxes(grand_total_commission)
            
            ws.append(['', '', '', '소득세', '', '', income_tax])
            last_row = ws.max_row
            for cell in ws[last_row]:
                cell.fill = total_fill
                cell.font = total_font
            
            ws.append(['', '', '', '지방세', '', '', local_tax])
            last_row = ws.max_row
            for cell in ws[last_row]:
                cell.fill = total_fill
                cell.font = total_font
            
            ws.append(['', '', '', '공제 후 지급액', '', '', net_amount])
            last_row = ws.max_row
            for cell in ws[last_row]:
                cell.fill = total_fill
                cell.font = total_font
            
            # Set column widths
            ws.column_dimensions['A'].width = 15
            ws.column_dimensions['B'].width = 15
            ws.column_dimensions['C'].width = 12
            ws.column_dimensions['D'].width = 15
            ws.column_dimensions['E'].width = 15
            ws.column_dimensions['F'].width = 12
            ws.column_dimensions['G'].width = 15

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)

            # Get user info for filename
            from app.models import Company as CompanyModel
            from urllib.parse import quote
            
            target_company = db.query(CompanyModel).filter(CompanyModel.company_id == target_company_id).first()
            target_company_name = getattr(target_company, 'name', '미등록') if target_company else '미등록'
            
            # 지사장(role_id=2) 이름 조회
            branch_mgr = db.query(User).filter(
                User.company_id == target_company_id,
                User.role_id == 2
            ).first()
            mgr_name = getattr(branch_mgr, 'name', '미등록') if branch_mgr else '미등록'
            
            # 파일명에 / 가 포함되면 OS에서 디렉토리로 인식되므로 치환
            safe_company = target_company_name.replace('/', '_')
            safe_mgr = mgr_name.replace('/', '_')
            filename = f"정산서_{safe_company}_{safe_mgr}_{year}_{str(month).zfill(2)}.xlsx"
            encoded_filename = quote(filename.encode('utf-8'), safe='')
            headers_dict = {"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
            return StreamingResponse(output, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', headers=headers_dict)

        finally:
            db.close()
    except Exception as e:
        logger.error(f"[export_settlement_statement_xlsx] Error: {str(e)}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.post("/api/statement/create")
def create_statement_from_settlement(request: Request, year: int, month: int):
    """
    Settlement 데이터로부터 Statement 생성
    """
    from app.services.settlement_service import SettlementService
    
    access = check_admin_access(request)
    if not access["allowed"]:
        return JSONResponse({"status": "error", "message": access["reason"]}, status_code=403)
    
    db = SessionLocal()
    try:
        user_id = request.session.get("user_id")
        
        # 사용자 정보 조회
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return JSONResponse({"status": "error", "message": "사용자를 찾을 수 없습니다"}, status_code=404)
        
        # Statement 생성
        statement = SettlementService.create_statement(
            db=db,
            user_id=user_id,
            company_id=user.company_id,
            year=year,
            month=month
        )
        
        db.commit()
        
        return JSONResponse({
            "status": "success",
            "message": f"정산서가 생성되었습니다: {statement.statement_number}",
            "statement_id": statement.statement_id,
            "statement_number": statement.statement_number
        })
    except Exception as e:
        db.rollback()
        logger.error(f"[create_statement_from_settlement] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)
    finally:
        db.close()


@router.post("/settlement/clear-all", tags=["Settlement"])
async def clear_all_settlement_data(
    request: Request,
    body: Optional[SettlementClearRequest] = Body(None)
):
    """
    정산 데이터 삭제 (전체 또는 특정 연월). 기존 전체 삭제 기능을 유지하면서
    `year` 및 `month`가 지정된 경우 해당 기간에 속하는 데이터만 제거합니다.

    삭제 대상:
    - settlements (settlement_date 기준)
    - settlement_statement_confirmations (year/month 기준)
    - settlement_company_monthly_aggregates (year/month 기준)
    - statements (year/month 기준)

    Note: 권한 체크 없이 실행 (개발/테스트용)
    """
    target_year = body.year if body else None
    target_month = body.month if body else None
    if (target_year is None) ^ (target_month is None):
        return JSONResponse({
            "status": "error",
            "message": "연도와 월은 함께 지정하거나 모두 생략해야 합니다"
        }, status_code=400)

    period_label = (
        f"{target_year}-{target_month:02d}" if (target_year is not None and target_month is not None) else "전체"
    )
    db = SessionLocal()
    try:
        settlement_query = db.query(Settlement)
        aggregate_query = db.query(SettlementCompanyMonthlyAggregate)
        confirmation_query = db.query(SettlementStatementConfirmation)
        statement_query = db.query(Statement)

        if target_year is not None and target_month is not None:
            settlement_query = settlement_query.filter(
                extract("year", Settlement.settlement_date) == target_year,
                extract("month", Settlement.settlement_date) == target_month,
            )
            aggregate_query = aggregate_query.filter(
                SettlementCompanyMonthlyAggregate.year == target_year,
                SettlementCompanyMonthlyAggregate.month == target_month,
            )
            confirmation_query = confirmation_query.filter(
                SettlementStatementConfirmation.year == target_year,
                SettlementStatementConfirmation.month == target_month,
            )
            statement_query = statement_query.filter(
                Statement.year == target_year,
                Statement.month == target_month,
            )

        deleted_settlements = settlement_query.delete(synchronize_session=False)
        deleted_aggregates = aggregate_query.delete(synchronize_session=False)
        deleted_confirmations = confirmation_query.delete(synchronize_session=False)
        deleted_statements = statement_query.delete(synchronize_session=False)

        db.commit()

        logger.info(
            f"[clear_all_settlement_data] [{period_label}] Deleted settlements={deleted_settlements}, aggregates={deleted_aggregates}"
        )

        return JSONResponse({
            "status": "success",
            "message": f"정산 데이터 삭제 완료 ({period_label})",
            "period": period_label,
            "deleted": {
                "settlements": deleted_settlements,
                "company_aggregates": deleted_aggregates,
                "statement_confirmations": deleted_confirmations,
                "statements": deleted_statements,
            },
        })

    except Exception as e:
        db.rollback()
        logger.error(f"[clear_all_settlement_data] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)
    finally:
        db.close()


@router.post("/settlement/run", tags=["Settlement"])
async def run_settlement(body: SettlementRunRequest):
    """
    정산 실행 API
    
    - **year**: 정산 연도 (예: 2025)
    - **month**: 정산 월 (1-12)
    - **settlement_type**: 정산 유형 (daily, monthly, yearly) - 기본값: monthly
    
    Note: 권한 체크 없이 실행 (개발/테스트용)
    """
    db = SessionLocal()
    try:
        year = body.year
        month = body.month
        settlement_type = body.settlement_type
        
        # 정산 실행
        from app.services.settlement_service import SettlementService
        
        logger.info(f"[run_settlement] Starting settlement for {year}-{month:02d}, type={settlement_type}")
        
        result = SettlementService.aggregate_completed_orders_to_settlement(
            db, year, month, settlement_type
        )
        
        logger.info(f"[run_settlement] Result: {result.get('status')}, created={result.get('created_count')}, updated={result.get('updated_count')}")
        
        return JSONResponse({
            "status": result.get("status", "unknown"),
            "message": result.get("message", ""),
            "year": year,
            "month": month,
            "settlement_type": settlement_type,
            "created_count": result.get("created_count", 0),
            "updated_count": result.get("updated_count", 0),
            "total_amount": result.get("total_amount", 0)
        })
    
    except Exception as e:
        logger.error(f"[run_settlement] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)
    finally:
        db.close()


@router.get("/settlement/skip-records")
async def get_settlement_skip_records(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None,
    skip_reason: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    정산 스킵 기록 조회
    
    정산 중 건너뛰어진 주문/항목들의 상세 정보를 조회합니다.
    
    Query Parameters:
    - year: 정산 연도 (옵션)
    - month: 정산 월 (옵션)
    - skip_reason: 스킵 사유 필터 (optional)
      * USER_NOT_FOUND: 메이크샵 member_id → 사용자 미매핑
      * INVALID_COMPANY_ID: 매핑된 사용자의 회사ID가 유효하지 않음
      * INVALID_COMPANY_ID_BASCLE: BASCLE 수수료 계산 중 invalid company_id
      * NO_ORDER_ITEMS: 주문에 포함된 상품 항목이 없음
      * NO_COMMISSION_TYPE: 상품 카테고리에 해당하는 수수료 타입이 없음
      * NO_PRODUCT: 상품 정보를 찾을 수 없음
    - limit: 반환 항목 수 (기본 100)
    - offset: 오프셋 (기본 0)
    
    응답:
    - records[].skip_reason: 스킵 사유
    - records[].skip_detail: 상세한 사유 설명
    - records[].order_info: 주문 정보 스냅샷 (ordernum, member_id, sender, phone, pay_price 등)
    """

    db = SessionLocal()
    try:
        query = db.query(SettlementSkipRecord)
        
        # 필터링
        if year and month:
            query = query.filter(
                SettlementSkipRecord.settlement_year == year,
                SettlementSkipRecord.settlement_month == month
            )
        elif year:
            query = query.filter(SettlementSkipRecord.settlement_year == year)
        
        if skip_reason:
            query = query.filter(SettlementSkipRecord.skip_reason == skip_reason)
        
        # 총 개수
        total_count = query.count()
        
        # 정렬 및 페이징
        records = query.order_by(SettlementSkipRecord.recorded_at.desc()).limit(limit).offset(offset).all()
        
        # 응답 데이터 구성
        skip_records_list = []
        for record in records:
            skip_records_list.append({
                "skip_id": record.skip_id,
                "ordernum": record.ordernum,
                "item_id": record.item_id,
                "member_id": record.member_id,
                "user_id": record.user_id,
                "company_id": record.company_id,
                "skip_reason": record.skip_reason,
                "skip_detail": record.skip_detail,
                "order_info": record.order_info,
                "recorded_at": record.recorded_at.isoformat() if record.recorded_at else None,
                "period": f"{record.settlement_year}-{record.settlement_month:02d}"
            })
        
        return JSONResponse({
            "status": "success",
            "total_count": total_count,
            "returned_count": len(skip_records_list),
            "limit": limit,
            "offset": offset,
            "records": skip_records_list
        })
    
    except Exception as e:
        logger.error(f"[get_settlement_skip_records] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)
    finally:
        db.close()


@router.get("/settlement/skip-statistics")
async def get_settlement_skip_statistics(request: Request, year: Optional[int] = None, month: Optional[int] = None):
    """
    정산 스킵 통계
    
    정산 기간별 스킵 사유별 집계 통계를 반환합니다.
    
    Query Parameters:
    - year: 정산 연도 (옵션)
    - month: 정산 월 (옵션)
    """
    db = SessionLocal()
    try:
        query = db.query(SettlementSkipRecord)
        
        # 필터링
        if year and month:
            query = query.filter(
                SettlementSkipRecord.settlement_year == year,
                SettlementSkipRecord.settlement_month == month
            )
        elif year:
            query = query.filter(SettlementSkipRecord.settlement_year == year)
        
        records = query.all()
        
        # 스킵 사유별 통계
        skip_reason_stats = {}
        period_stats = {}
        
        for record in records:
            # 사유별 통계
            reason = record.skip_reason
            if reason not in skip_reason_stats:
                skip_reason_stats[reason] = 0
            skip_reason_stats[reason] += 1
            
            # 기간별 통계
            period = f"{record.settlement_year}-{record.settlement_month:02d}"
            if period not in period_stats:
                period_stats[period] = {}
            if reason not in period_stats[period]:
                period_stats[period][reason] = 0
            period_stats[period][reason] += 1
        
        return JSONResponse({
            "status": "success",
            "total_skip_count": len(records),
            "skip_reason_summary": skip_reason_stats,
            "period_summary": period_stats
        })
    
    except Exception as e:
        logger.error(f"[get_settlement_skip_statistics] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)
    finally:
        db.close()


@router.get("/settlement/enrollment-items")
async def get_enrollment_items(
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None
):
    """
    ENROLLMENT (commission_type_id=1) 정산 항목만 조회
    
    Query Parameters:
        year: 정산 연도 (기본: 현재 연도)
        month: 정산 월 (기본: 현재 월)
    
    Returns:
        {
            'status': 'success',
            'year': int,
            'month': int,
            'total_records': int,
            'total_commission': int,
            'data': [
                {
                    'settlement_id': int,
                    'user_id': int,
                    'user_name': str,
                    'company_name': str,
                    'ordernum': str,
                    'product_uid': str,
                    'product_name': str,
                    'quantity': int,
                    'unit_price': int,
                    'payment_amount': int,
                    'actual_payment': int,
                    'rate': float,
                    'commission': int
                }
            ]
        }
    """
    try:
        db = SessionLocal()
        try:
            # 기본값 설정
            now = datetime.now()
            target_year = year or now.year
            target_month = month or now.month
            
            # 정산 대상 월 계산
            settlement_date = datetime(target_year, target_month, 1)
            
            # Settlement 조회 (해당 월)
            query = db.query(Settlement).filter(
                Settlement.settlement_type == "monthly",
                Settlement.settlement_date == settlement_date
            )
            
            settlements = query.all()
            
            if not settlements:
                return JSONResponse({
                    "status": "success",
                    "year": target_year,
                    "month": target_month,
                    "total_records": 0,
                    "total_commission": 0,
                    "data": []
                })
            
            # Settlement에서 commission_details 파싱 및 ENROLLMENT만 추출
            import json
            enrollment_items = []
            total_commission = 0
            
            for settlement in settlements:
                if not settlement.commission_details:
                    continue
                
                try:
                    details = json.loads(settlement.commission_details)
                    
                    for detail in details:
                        # commission_type_id == 1 (ENROLLMENT)만 필터
                        if detail.get('commission_type_id') != 1:
                            continue
                        
                        # User 정보 조회
                        user = db.query(User).filter(User.user_id == settlement.user_id).first()
                        user_name = user.name if user else "Unknown"
                        company_name = user.company.name if user and user.company else "Unknown"
                        
                        commission = detail.get('commission', 0)
                        total_commission += commission
                        
                        enrollment_items.append({
                            'settlement_id': settlement.settlement_id,
                            'user_id': settlement.user_id,
                            'user_name': user_name,
                            'company_name': company_name,
                            'ordernum': detail.get('ordernum'),
                            'product_uid': detail.get('product_uid'),
                            'product_name': detail.get('product_name'),
                            'cate1': detail.get('cate1'),
                            'quantity': detail.get('quantity'),
                            'unit_price': detail.get('unit_price'),
                            'payment_amount': detail.get('payment_amount'),
                            'actual_payment': detail.get('actual_payment'),
                            'rate': detail.get('rate'),
                            'commission': commission,
                            'type_name': detail.get('type_name')
                        })
                
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse commission_details for settlement {settlement.settlement_id}: {e}")
                    continue
            
            return JSONResponse({
                "status": "success",
                "year": target_year,
                "month": target_month,
                "total_records": len(enrollment_items),
                "total_commission": total_commission,
                "data": enrollment_items
            })
        
        finally:
            db.close()
    
    except Exception as e:
        logger.error(f"[get_enrollment_items] Error: {str(e)}", exc_info=True)
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@router.get("/settlement/export-all-statements-zip")
async def export_all_statements_zip(request: Request):
    """
    최근 년/월 정산서를 모든 지사별 엑셀 파일로 생성하여 ZIP으로 다운로드합니다.
    - role_id=1 (본사 관리자) 전용
    - 자동으로 가장 최근 정산 년/월을 탐지
    - 파일명: 정산서_지사지역_지사장명_년_월.xlsx
    """
    try:
        user_id_str = request.session.get("user_id")
        role_id = int(request.session.get("role_id", 0))
        if not user_id_str or role_id != 1:
            return JSONResponse({"status": "error", "message": "본사 관리자만 사용 가능합니다"}, status_code=403)

        import io
        import json
        import zipfile
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from collections import defaultdict
        from urllib.parse import quote
        from app.models import Company
        from app.services.monthly_settlement_summary_service import (
            format_settlement_type_statement_display,
        )

        db = SessionLocal()
        try:
            # 1) 최근 년/월 자동 탐지 (Statement 테이블에서)
            latest = db.query(
                func.max(Statement.year * 100 + Statement.month)
            ).scalar()
            if not latest:
                return JSONResponse({"status": "error", "message": "정산서 데이터가 없습니다"}, status_code=404)
            target_year = int(latest) // 100
            target_month = int(latest) % 100

            # 2) 모든 BRANCH 회사 조회
            branches = db.query(Company).filter(
                Company.company_type.in_(['HQ', 'BRANCH'])
            ).order_by(Company.name).all()

            zip_buffer = io.BytesIO()
            file_count = 0

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for company in branches:
                    company_id = company.company_id
                    company_name = company.name or '미등록'

                    # 해당 지사의 지사장(role_id=2) 조회
                    branch_manager = db.query(User).filter(
                        User.company_id == company_id,
                        User.role_id == 2
                    ).first()
                    manager_name = getattr(branch_manager, 'name', '미등록') if branch_manager else '미등록'
                    settlement_type_display = format_settlement_type_statement_display(branch_manager)

                    # 해당 지사 소속 원장(role_id=3)들의 정산 데이터 수집
                    teachers = db.query(User).filter(
                        User.company_id == company_id,
                        User.role_id == 3,
                        User.is_active.is_(True),
                    ).all()

                    statement_summary = get_statement_summary_amounts(
                        db,
                        year=target_year,
                        month=target_month,
                        company_id=company_id,
                        teachers_only=True,
                    )

                    all_commission_details: list = []
                    for teacher in teachers:
                        settlement = db.query(Settlement).filter(
                            Settlement.user_id == teacher.user_id,
                            Settlement.settlement_type == 'monthly',
                            extract('year', Settlement.settlement_date) == target_year,
                            extract('month', Settlement.settlement_date) == target_month
                        ).first()
                        if not settlement or not settlement.commission_details:
                            continue
                        try:
                            details = json.loads(str(settlement.commission_details))
                        except Exception:
                            continue
                        for d in details:
                            if d.get('commission', 0) == 0:
                                continue
                            d['user_name'] = getattr(teacher, 'name', '미등록')
                            d['user_code'] = getattr(teacher, 'code', '')
                            all_commission_details.append(d)

                    if not all_commission_details:
                        continue  # 정산 데이터 없으면 스킵

                    # 엑셀 생성 (기존 패턴 재사용)
                    wb = Workbook()
                    ws = wb.active
                    ws.title = f"{target_year}-{str(target_month).zfill(2)}"

                    headers = ['수수료발생일', '결제종류', '코드', '결제자', '정산대상금액', '수수료율(%)', '정산액']
                    header_fill = PatternFill(start_color="FFFACD", end_color="FFFACD", fill_type="solid")
                    header_font = Font(bold=True)

                    ws.append([f"정산 유형: {settlement_type_display}"])
                    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
                    ws["A1"].font = Font(bold=True)
                    ws.append([])

                    ws.append(headers)
                    header_row_idx = ws.max_row
                    for cell in ws[header_row_idx]:
                        cell.fill = header_fill
                        cell.font = header_font
                        cell.alignment = Alignment(horizontal="center")

                    # 타입별 그룹화
                    type_groups: dict = defaultdict(list)
                    for detail in all_commission_details:
                        type_name = detail.get('type_name', '기타')
                        type_groups[type_name].append(detail)

                    grand_total_amount = 0
                    grand_total_commission = 0

                    for type_name, items in sorted(type_groups.items()):
                        sorted_items = sorted(items, key=lambda x: x.get('ordernum', ''))
                        type_total_amount = 0
                        type_total_commission = 0

                        for item in sorted_items:
                            order_date = item.get('ordernum', '')[:8]
                            if len(order_date) == 8:
                                order_date = f"{order_date[:4]}-{order_date[4:6]}-{order_date[6:8]}"
                            else:
                                order_date = f"{target_year}-{str(target_month).zfill(2)}-01"

                            actual_payment = int(item.get('actual_payment', 0))
                            rate = float(item.get('rate', 0))
                            commission = int(item.get('commission', 0))
                            type_total_amount += actual_payment
                            type_total_commission += commission

                            ws.append([
                                order_date, type_name,
                                item.get('user_code', ''), item.get('user_name', '미등록'),
                                actual_payment, int(rate), commission
                            ])

                        # 소계
                        rate_int = int(sorted_items[0].get('rate', 0)) if sorted_items else 0
                        ws.append(['', '', '', '소계', type_total_amount, rate_int, type_total_commission])
                        last_row = ws.max_row
                        subtotal_fill = PatternFill(start_color="FFFACD", end_color="FFFACD", fill_type="solid")
                        for cell in ws[last_row]:
                            cell.fill = subtotal_fill
                            cell.font = Font(bold=True)

                        grand_total_amount += type_total_amount
                        grand_total_commission += type_total_commission

                    # 총합계 및 세금
                    total_fill = PatternFill(start_color="E6F3FF", end_color="E6F3FF", fill_type="solid")
                    total_font = Font(bold=True)
                    _income_tax, _local_tax, _net_amount = calc_settlement_taxes(grand_total_commission)
                    for label, value in [
                        ('총 합계', grand_total_commission),
                        ('소득세', _income_tax),
                        ('지방세', _local_tax),
                        ('공제 후 지급액', _net_amount),
                    ]:
                        ws.append(['', '', '', label, '', '', value])
                        for cell in ws[ws.max_row]:
                            cell.fill = total_fill
                            cell.font = total_font

                    # 컬럼 폭
                    for col, width in [('A', 15), ('B', 15), ('C', 12), ('D', 15), ('E', 15), ('F', 12), ('G', 15)]:
                        ws.column_dimensions[col].width = width

                    # BytesIO로 저장 후 ZIP에 추가
                    xlsx_buffer = io.BytesIO()
                    wb.save(xlsx_buffer)
                    xlsx_buffer.seek(0)

                    # 파일명에 / 가 포함되면 ZIP 내 디렉토리로 인식되므로 치환
                    safe_company = company_name.replace('/', '_')
                    safe_manager = manager_name.replace('/', '_')
                    filename = f"정산서_{safe_company}_{safe_manager}_{target_year}_{str(target_month).zfill(2)}.xlsx"
                    zf.writestr(filename, xlsx_buffer.getvalue())
                    file_count += 1

            if file_count == 0:
                return JSONResponse({"status": "error", "message": f"{target_year}년 {target_month}월 정산 데이터가 없습니다"}, status_code=404)

            zip_buffer.seek(0)
            zip_filename = f"정산서_전체_{target_year}_{str(target_month).zfill(2)}.zip"
            encoded_zip = quote(zip_filename.encode('utf-8'), safe='')
            return StreamingResponse(
                zip_buffer,
                media_type='application/zip',
                headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_zip}"}
            )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"[export_all_statements_zip] Error: {str(e)}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@router.get("/settlement/company-monthly-sales")
async def get_company_monthly_sales(
    request: Request,
    year: int,
    month: int,
    company_id: int
):
    """
    특정 년/월, 회사의 monthly_sales 산출 과정(Type2 및 Type3 실결제액) 및 구성 로그 조회
    """
    try:
        from app.services.settlement_service import SettlementService
        
        db = SessionLocal()
        try:
            result = SettlementService.calculate_company_monthly_sales(
                db=db,
                year=year,
                month=month,
                target_company_id=company_id
            )
            return JSONResponse({"status": "success", "data": result})
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"[get_company_monthly_sales] Error: {str(e)}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
