"""
Makeshop API Router
메이크샵 API 연동 엔드포인트
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.services.makeshop_api_gateway import (
    get_delivery_companies as gateway_get_delivery_companies,
    health_check as gateway_health_check,
    process_shipping as gateway_process_shipping,
    register_tracking_by_order as gateway_register_tracking_by_order,
    use_makeshop_rest,
)
from app.services.makeshop_install_service import process_makeshop_install
from app.services.makeshop_rest_client import MakeshopRestAPIError

router = APIRouter(prefix="/makeshop", tags=["Makeshop"])
logger = logging.getLogger(__name__)


# Pydantic 모델
class ShippingProcessItem(BaseModel):
    """배송 처리 항목"""
    order_num: str = Field(..., description="메이크샵 주문 번호")
    num: int = Field(..., description="order_items의 num 값")


class ShippingProcessingRequest(BaseModel):
    """배송 처리 요청"""
    items: List[ShippingProcessItem] = Field(..., description="처리할 항목 리스트")


class TrackingRegistrationRequest(BaseModel):
    """송장 등록 요청"""
    order_id: int = Field(..., description="주문 ID")
    delicom: int = Field(default=3, description="배송사 코드 (기본값: 3=CJ대한통운, 예: 14=CJ대한통운)")
    delinum: str = Field(..., description="송장번호 (예: 1111)")


@router.get(
    "/install",
    summary="APP 설치 콜백 (HMAC 검증 + 온보딩)",
    response_description="설치 검증·온보딩 결과",
)
async def makeshop_install(
    shop_uid: str = Query(..., description="앱을 설치한 상점 ID"),
    timestamp: str = Query(..., description="요청 생성 시각 (Unix ms)"),
    action_type: str = Query(..., description="요청 유형 (install 등)"),
    hmac: str = Query(..., description="HMAC-SHA256 서명 값 (hex)"),
    db: Session = Depends(get_db),
):
    """
    메이크샵 개발자센터 > 개발 정보 관리 > APP URL 에 등록할 엔드포인트.

    Docs: https://developer.makeshop.co.kr/docs/guide/app/install

    예::

        https://your-domain.com/makeshop/install
        ?shop_uid=...&timestamp=...&action_type=install&hmac=...
    """
    try:
        return process_makeshop_install(
            db,
            shop_uid=shop_uid,
            timestamp=timestamp,
            action_type=action_type,
            received_hmac=hmac,
        )
    except ValueError:
        # 가이드: 검증 실패 시 구체 사유를 외부에 노출하지 않음
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request validation.",
        )
    except MakeshopRestAPIError as exc:
        logger.error("[makeshop_install] REST error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch installed app info.",
        ) from exc
    except Exception as exc:
        logger.error("[makeshop_install] Unexpected error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Install onboarding failed.",
        ) from exc


# 엔드포인트
@router.get("/delivery-companies", summary="택배사 목록 조회")
async def get_delivery_companies(db: Session = Depends(get_db)):
    """
    Makeshop에서 사용 가능한 택배사 목록을 조회합니다.
    기본은 신규 Open API(REST). 긴급 롤백 시에만 MAKESHOP_USE_REST=false.
    """
    try:
        companies = gateway_get_delivery_companies(db=db)
        return {
            "status": "success",
            "companies": companies,
            "api_mode": "REST" if use_makeshop_rest() else "legacy",
        }
    except Exception as e:
        logger.error(f"[get_delivery_companies] Error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/register-tracking", summary="송장 등록")
async def register_tracking(
    payload: TrackingRegistrationRequest,
    db: Session = Depends(get_db),
):
    """
    메이크샵에 송장 정보를 등록합니다.
    
    - order_id: 주문 ID
    - delicom: 배송사 코드 (기본값: 3=CJ대한통운, 선택사항)
    - delinum: 송장번호
    
    """
    try:
        result = gateway_register_tracking_by_order(
            order_id=payload.order_id,
            delicom=payload.delicom,
            delinum=payload.delinum,
            db=db,
        )
        logger.info(f"[register_tracking] Order ID: {payload.order_id}, Success: {result.get('success')}")
        return {
            "status": "success" if result.get('success') else "error",
            "message": result.get('error', '송장 등록 완료' if result.get('success') else '송장 등록 실패'),
            "order_id": payload.order_id,
            "results": result.get('results', []),
            "error": result.get('error'),
            "api_mode": "REST" if use_makeshop_rest() else "legacy",
        }
    except Exception as e:
        logger.error(f"[register_tracking] Error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/process-shipping", summary="배송 처리")
async def process_shipping(
    payload: ShippingProcessingRequest,
    db: Session = Depends(get_db),
):
    """
    여러 주문 항목의 배송 처리(발송 상태 반영)를 Makeshop에 요청합니다.
    기본은 신규 Open API(REST). 긴급 롤백 시에만 MAKESHOP_USE_REST=false.
    """
    try:
        items_payload: List[Dict[str, Any]] = [
            {"order_num": item.order_num, "item_num": item.num}
            for item in payload.items
        ]
        result = gateway_process_shipping(items_payload, db=db)
        logger.info(f"[process_shipping] Sent {len(items_payload)} item(s)")
        return {
            "status": "success" if result.get('success') else "error",
            "message": result.get('error', '배송 처리 완료' if result.get('success') else '배송 처리 실패'),
            "results": result.get('results', []),
            "error": result.get('error'),
            "api_mode": "REST" if use_makeshop_rest() else "legacy",
        }
    except Exception as e:
        logger.error(f"[process_shipping] Error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

@router.post("/health", summary="헬스 체크")
async def health_check(db: Session = Depends(get_db)):
    """메이크샵 API 연결 상태를 확인합니다. (기본: 신규 Open API)"""
    try:
        is_healthy = gateway_health_check(db=db)
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "message": "메이크샵 API 정상" if is_healthy else "메이크샵 API 연결 실패",
            "api_mode": "REST" if use_makeshop_rest() else "legacy",
        }
    except Exception as e:
        logger.error(f"[health_check] Error: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}
