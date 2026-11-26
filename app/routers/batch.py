"""
배치 작업 라우터 (Cloud Scheduler 연동)

이 라우터는 GCP Cloud Scheduler에 의해 주기적으로 호출되는 배치 작업들을 정의합니다.
- 월별 정산 집계
- 일별 정산 확인
- 헬스 체크
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.database import SessionLocal
from app.services.settlement_service import SettlementService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch", tags=["batch"])


@router.post("/settlement-monthly-aggregation")
async def settlement_monthly_aggregation(background_tasks: BackgroundTasks):
    """
    월별 정산 집계 배치 작업
    
    ✨ 자동 계산 방식 (옵션 1):
    - 호출 시간을 기준으로 지난달을 자동 계산
    - Cloud Scheduler에서 파라미터 입력 불필요
    - 매월 1일 09:01 KST에 자동 실행
    
    📝 예시:
    - 2025-01-01 호출 → 2024-12월 정산
    - 2025-02-01 호출 → 2025-01월 정산
    
    처리 과정:
    - 지난달의 완료된 주문을 정산 데이터로 집계
    - 사용자별/회사별 월간 정산액 계산
    - 배경 작업으로 비동기 처리 (Cloud Scheduler 타임아웃 방지)
    
    Returns:
        dict: 배치 작업 스케줄 결과
    """
    db = SessionLocal()
    
    try:
        # 지난달 계산
        today = datetime.utcnow().date()
        
        # 1일이 아닌 경우 당월 1일에서 1일 뺀 날짜 = 지난달 마지막 날
        if today.day == 1:
            # 이미 1일이면 지난달 사용
            last_day_of_prev_month = today - timedelta(days=1)
        else:
            # 1일이 아니면 당월 1일에서 1일 뺀 것 = 지난달 마지막 날
            first_of_current = today.replace(day=1)
            last_day_of_prev_month = first_of_current - timedelta(days=1)
        
        year = last_day_of_prev_month.year
        month = last_day_of_prev_month.month
        
        logger.info(f"[배치] 월별 정산 집계 시작: {year}-{month:02d}")
        
        # 배경 작업으로 비동기 처리 (Cloud Scheduler 타임아웃 회피)
        background_tasks.add_task(
            _run_settlement_aggregation,
            year=year,
            month=month
        )
        
        return {
            "status": "success",
            "message": f"Settlement aggregation scheduled for {year}-{month:02d}",
            "target_period": f"{year}-{month:02d}",
            "scheduled_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"[배치] 월별 정산 집계 스케줄 실패: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _run_settlement_aggregation(year: int, month: int):
    """
    실제 월별 정산 집계 처리 (배경 작업)
    
    Args:
        year: 정산 연도
        month: 정산 월 (1-12)
    """
    db = SessionLocal()
    try:
        logger.info(f"[배치] 월별 정산 집계 처리 시작: {year}-{month:02d}")
        
        result = SettlementService.aggregate_completed_orders_to_settlement(
            db=db,
            year=year,
            month=month
        )
        
        logger.info(
            f"[배치] 월별 정산 집계 완료: {year}-{month:02d}",
            extra={
                "result": result,
                "period": f"{year}-{month:02d}"
            }
        )
    except Exception as e:
        logger.error(
            f"[배치] 월별 정산 집계 실패: {str(e)}",
            exc_info=True,
            extra={"period": f"{year}-{month:02d}"}
        )
    finally:
        db.close()


@router.post("/settlement-daily-aggregation")
async def settlement_daily_aggregation(background_tasks: BackgroundTasks):
    """
    이번 달 누적(MTD) 정산 스냅샷 배치

    매일 21:00 (KST) 권장 스케줄
    - 당월 1일~당일 완료 주문을 수수료 기준으로 집계 (settlement_type=mtd)
    - 소속 원장별 일별 매출 화면 갱신용
    """
    try:
        now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
        year = now_kst.year
        month = now_kst.month
        day = now_kst.day

        date_str = f"{year}-{month:02d}-{day:02d}"
        logger.info(f"[배치] MTD 정산 스냅샷 스케줄: {date_str}")

        background_tasks.add_task(
            _run_daily_settlement_aggregation,
            year=year,
            month=month,
            day=day,
        )

        return {
            "status": "success",
            "message": f"MTD settlement snapshot scheduled for {date_str}",
            "target_date": date_str,
            "period": f"{year}-{month:02d}-01 ~ {date_str}",
            "scheduled_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[배치] MTD 정산 스냅샷 스케줄 실패: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _run_daily_settlement_aggregation(year: int, month: int, day: int):
    """이번 달 누적(MTD) 정산 스냅샷 처리 (배경 작업)."""
    db = SessionLocal()
    try:
        date_str = f"{year}-{month:02d}-{day:02d}"
        logger.info(f"[배치] MTD 정산 스냅샷 처리 시작: {date_str}")

        result = SettlementService.aggregate_completed_orders_to_settlement(
            db=db,
            year=year,
            month=month,
            settlement_type="mtd",
            end_day=day,
        )

        if result.get("status") == "success":
            logger.info(
                f"[배치] MTD 정산 스냅샷 완료: {date_str} "
                f"(created={result.get('created_count')}, updated={result.get('updated_count')})",
                extra={"result": result, "period": f"{year}-{month:02d}-01 ~ {date_str}"},
            )
        else:
            logger.error(
                f"[배치] MTD 정산 스냅샷 실패: {date_str} — {result.get('message')}",
                extra={"result": result, "period": f"{year}-{month:02d}-01 ~ {date_str}"},
            )
    except Exception as e:
        logger.error(f"[배치] MTD 정산 스냅샷 실패: {str(e)}", exc_info=True)
    finally:
        db.close()


@router.post("/batch-health-check")
async def batch_health_check():
    """
    배치 작업 상태 확인 (헬스 체크)
    
    Cloud Scheduler가 주기적으로 호출 가능하며,
    서비스가 정상 작동하는지 확인합니다.
    
    Returns:
        dict: 서비스 상태 정보
    """
    return {
        "status": "healthy",
        "service": "babba-api-batch",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@router.post("/settlement-pre-validate")
async def settlement_pre_validate():
    """
    정산 사전 검증 — 당월 결제 완료 주문에 대해 정산 가능 여부를 dry-run으로 확인
    
    주문 동기화 후 자동 호출되며, DB에 쓰지 않고 정산 스킵될 주문만 탐지합니다.
    
    검증 항목:
    - USER_NOT_FOUND: member_id/name+phone → User 매핑 불가
    - INVALID_COMPANY_ID: User.company_id가 유효하지 않음
    - NO_ORDER_ITEMS: 주문에 OrderItem이 없음
    - NO_PRODUCT: product_uid에 해당 Product가 없음
    - NO_COMMISSION_TYPE: Product.cate1에 매칭 CommissionType 없음
    
    Returns:
        dict: 검증 결과 (정산 가능 주문 수, 이슈 건수, 사유별 요약)
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        year = now.year
        month = now.month
        
        logger.info(f"[배치] 정산 사전 검증 시작: {year}-{month:02d}")
        
        result = SettlementService.pre_validate_orders(
            db=db,
            year=year,
            month=month,
        )
        
        logger.info(
            f"[배치] 정산 사전 검증 완료: {year}-{month:02d} — "
            f"총 {result.get('total_completed_orders', 0)}건, "
            f"정산가능 {result.get('settleable_count', 0)}건, "
            f"이슈 {result.get('issue_count', 0)}건"
        )
        
        return result
    
    except Exception as e:
        logger.error(f"[배치] 정산 사전 검증 실패: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        db.close()


@router.get("/batch-status")
async def batch_status():
    """
    배치 시스템 상태 조회 (GET 메서드)
    
    Returns:
        dict: 배치 시스템의 현재 상태
    """
    return {
        "status": "ready",
        "service": "babba-api-batch",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "monthly_aggregation": "POST /api/batch/settlement-monthly-aggregation",
            "daily_aggregation": "POST /api/batch/settlement-daily-aggregation",
            "pre_validate": "POST /api/batch/settlement-pre-validate",
            "health_check": "POST /api/batch/batch-health-check",
            "status": "GET /api/batch/batch-status"
        }
    }
