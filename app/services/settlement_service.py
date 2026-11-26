"""
Settlement Service - 주문 결제 완료 데이터를 정산 테이블에 적재
"""

from datetime import date, datetime, timedelta
from sqlalchemy import func, case, or_, and_
from typing import Dict, Tuple, Any, Optional, cast
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import (
    Order,
    OrderItem,
    Settlement,
    Statement,
    User,
    Company,
    SettlementCompanyMonthlyAggregate,
    SettlementSkipRecord,
    CommissionType,
    CommissionRateWindow,
    Product,
)
import json
import logging

from app.settlement_tax import calc_settlement_taxes

logger = logging.getLogger(__name__)

# [바빠 시리즈] > [바빠 시리즈 교사용]: 상품명 [교사용] 접두사 + type3 cate1 코드로 제외
BABBA_TEACHER_PRODUCT_NAME_PREFIX = "[교사용]"


class SettlementService:
    """정산 데이터 관리 서비스"""

    # 정산 사전 검증 결과 인메모리 캐시 (성능 최적화)
    # 캐시가 있으면 대시보드는 여기서 읽고,
    # 캐시가 없으면 DB에서 로드하여 표시
    _pre_validation_cache: Optional[Dict[str, Any]] = None
    _pre_validation_cached_at: Optional[datetime] = None

    @staticmethod
    def is_babba_teacher_series_excluded(
        product: Any | None,
        order_item: Any | None = None,
        type3_cate1_codes: frozenset[str] | set[str] | None = None,
    ) -> bool:
        """[교사용] 상품명 + 바빠 시리즈(type3) cate1 코드 → 수수료 정산 제외."""
        if not type3_cate1_codes:
            return False

        product_name = ""
        order_item_name = ""
        cate1_code = ""

        if product is not None:
            product_name = str(getattr(product, "product_name", "") or "")
            cate1_code = str(getattr(product, "cate1", "") or "")
        if order_item is not None:
            order_item_name = str(getattr(order_item, "product_name", "") or "")
            if not cate1_code:
                cate1_code = str(getattr(order_item, "cate1", "") or "")

        has_teacher_prefix = any(
            name.strip().startswith(BABBA_TEACHER_PRODUCT_NAME_PREFIX)
            for name in (product_name, order_item_name)
            if name
        )
        if not has_teacher_prefix:
            return False
        return bool(cate1_code and cate1_code in type3_cate1_codes)

    @staticmethod
    def generate_statement_number(
        db: Session,
        user_id: int,
        year: int,
        month: int,
        reserved: Optional[set[str]] = None,
    ) -> str:
        """
        정산서 번호 생성
        
        형식: ST-{YYYYMM}-{user_code}-{seq}
        예: ST-202501-A001-001

        seq는 기존 번호의 최대값+1을 사용한다.
        (count+1은 삭제/공백 시퀀스에서 중복을 만들 수 있음)

        같은 user.code를 쓰는 사용자가 한 배치에서 여러 명일 때,
        미flush INSERT가 안 보여 동일 seq가 재발급되지 않도록
        reserved(이번 실행에서 이미 할당된 번호)와 flush를 함께 사용한다.
        """
        try:
            # 같은 세션의 pending statement_number도 조회에 포함
            try:
                db.flush()
            except Exception:
                # flush 실패 시에도 번호 생성은 시도 (폴백 경로로 이어질 수 있음)
                logger.warning(
                    "[SettlementService] flush before statement_number generation failed",
                    exc_info=True,
                )

            # 사용자 코드 조회
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                user_code = "XXXX"
            else:
                raw_code = getattr(user, 'code', None)
                user_code = str(raw_code).strip() if raw_code is not None and str(raw_code).strip() != "" else f"U{user_id:04d}"
            
            prefix = f"ST-{year:04d}{month:02d}-{user_code}-"
            existing_numbers = db.query(Settlement.statement_number).filter(
                Settlement.statement_number.like(f"{prefix}%")
            ).all()

            max_seq = 0
            prefix_len = len(prefix)
            for (number,) in existing_numbers:
                if not number or len(str(number)) <= prefix_len:
                    continue
                suffix = str(number)[prefix_len:]
                if suffix.isdigit():
                    max_seq = max(max_seq, int(suffix))

            if reserved:
                for number in reserved:
                    if not number or not str(number).startswith(prefix):
                        continue
                    suffix = str(number)[prefix_len:]
                    if suffix.isdigit():
                        max_seq = max(max_seq, int(suffix))

            seq = max_seq + 1
            while True:
                statement_number = f"{prefix}{seq:03d}"
                if reserved is None or statement_number not in reserved:
                    break
                seq += 1

            if reserved is not None:
                reserved.add(statement_number)
            
            logger.debug(f"[SettlementService] Generated statement_number: {statement_number}")
            return statement_number
            
        except Exception as e:
            logger.error(f"[SettlementService] Error generating statement_number: {str(e)}", exc_info=True)
            # 폴백: 타임스탬프 + user_id 기반 (중복 가능성 최소화)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            statement_number = f"ST-{year:04d}{month:02d}-{user_id}-{timestamp}"
            if reserved is not None:
                reserved.add(statement_number)
            return statement_number
    
    @staticmethod
    def create_statement(
        db: Session,
        user_id: int,
        company_id: int,
        year: int,
        month: int,
        settlement_ids: Optional[list[int]] = None
    ) -> Statement:
        """
        정산서 생성 - Settlement 데이터를 기반으로 Statement 문서 생성
        
        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            company_id: 회사 ID
            year: 연도
            month: 월
            settlement_ids: Statement와 연결할 Settlement ID 리스트
        
        Returns:
            Statement: 생성된 정산서
        """
        try:
            from sqlalchemy import extract
            
            # 1. 기존 정산서 확인
            existing = db.query(Statement).filter(
                Statement.user_id == user_id,
                Statement.year == year,
                Statement.month == month
            ).first()
            
            if existing:
                logger.debug(f"[SettlementService] Statement already exists: {existing.statement_number}")
                return existing
            
            # 2. 해당 월의 Settlement 데이터 조회
            settlements = db.query(Settlement).filter(
                Settlement.user_id == user_id,
                Settlement.settlement_type == 'monthly',
                extract('year', Settlement.settlement_date) == year,
                extract('month', Settlement.settlement_date) == month
            ).all()
            
            if not settlements:
                raise ValueError(f"No settlements found for user {user_id}, {year}-{month:02d}")
            
            # 3. 정산 금액 합산
            total_commission = sum(getattr(s, 'total_commission', 0) or 0 for s in settlements)
            deducted_tax = sum(getattr(s, 'deducted_tax', 0) or 0 for s in settlements)
            deducted_local_tax = sum(getattr(s, 'deducted_local_tax', 0) or 0 for s in settlements)
            net_amount = sum(getattr(s, 'net_settlement_amount', 0) or 0 for s in settlements)
            
            # 4. 정산서 번호: Settlement에 이미 발급된 번호를 재사용
            # (재생성 시 동일 user.code 사용자들과 seq 충돌·번호 불일치 가능)
            existing_settlement_numbers = [
                str(getattr(s, "statement_number", "") or "")
                for s in settlements
                if getattr(s, "statement_number", None)
            ]
            if existing_settlement_numbers:
                statement_number = existing_settlement_numbers[0]
            else:
                statement_number = SettlementService.generate_statement_number(
                    db=db,
                    user_id=user_id,
                    year=year,
                    month=month,
                )
            
            # 5. Statement 생성
            statement = Statement(
                statement_number=statement_number,
                user_id=user_id,
                company_id=company_id,
                year=year,
                month=month,
                total_commission=total_commission,
                deducted_tax=deducted_tax,
                deducted_local_tax=deducted_local_tax,
                net_amount=net_amount,
                is_confirmed=False,
                issued_at=datetime.now()
            )
            db.add(statement)
            db.flush()  # statement_id 생성
            
            # 6. Settlement에 statement_id 연결
            for settlement in settlements:
                setattr(settlement, 'statement_id', statement.statement_id)
                db.add(settlement)
            
            db.commit()
            db.refresh(statement)
            
            logger.debug(f"[SettlementService] Created statement: {statement_number} for user {user_id}")
            return statement
            
        except Exception as e:
            db.rollback()
            logger.error(f"[SettlementService] Error creating statement: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def record_skip(
        db: Session,
        year: int,
        month: int,
        ordernum: str,
        skip_reason: str,
        skip_detail: str = "",
        item_id: Optional[int] = None,
        member_id: Optional[str] = None,
        user_id: Optional[int] = None,
        company_id: Optional[int] = None,
        order_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        정산 스킵 기록 저장
        
        Args:
            db: 데이터베이스 세션
            year: 정산 연도
            month: 정산 월
            ordernum: 주문번호
            skip_reason: 스킵 사유 (INVALID_COMPANY, NO_RATE_WINDOW, CONDITION_MISMATCH, NO_PRODUCT, USER_NOT_FOUND, INVALID_COMPANY_ID)
            skip_detail: 상세 이유
            item_id: OrderItem ID (선택사항)
            member_id: 메이크샵 회원ID
            user_id: 매핑된 사용자 ID
            company_id: 조건에 맞지 않은 회사ID
            order_info: 주문 정보 스냅샷
        """
        try:
            skip_record = SettlementSkipRecord(
                settlement_year=year,
                settlement_month=month,
                ordernum=ordernum,
                item_id=item_id,
                member_id=member_id,
                user_id=user_id,
                company_id=company_id,
                skip_reason=skip_reason,
                skip_detail=skip_detail,
                order_info=order_info
            )
            db.add(skip_record)
            db.flush()
            logger.debug(
                f"[SettlementService] Recorded skip: ordernum={ordernum}, reason={skip_reason}, detail={skip_detail}"
            )
        except Exception as e:
            logger.error(
                f"[SettlementService] Error recording skip: {str(e)}", exc_info=True
            )
            # skip 기록 실패는 정산 처리를 막지 않음
    
    @staticmethod
    def get_dynamic_commission_rate(
        db: Session,
        commission_type_id: int,
        company_id: int,
        year: int,
        month: int,
        monthly_sales: int,
    ) -> float:
        """CommissionRateWindow 테이블 기반으로 동적 수수료율 결정

        조건 우선순위 (priority 높은 순):
        1. 기간(year/month) 매칭
        2. commission_type_id 매칭
        3. 동적 조건(min_teachers) 충족
        4. 회사 일치 (NULL이면 모든 회사)

        Args:
            db: 데이터베이스 세션
            commission_type_id: 수수료 타입 ID
            company_id: 회사 ID
            year: 정산 연도
            month: 정산 월
            monthly_sales: 해당 월 총 매출액

        Returns:
            수수료율 (%)
        """
        try:
            # 1. 소속 원장 수 조회 (해당 회사의 role_id=3 원장 총 수)
            teachers_count = db.query(func.count(User.user_id)).filter(
                User.company_id == company_id,
                User.role_id == 3  # 원장
            ).scalar() or 0
            
            logger.debug(f"[Dynamic Rate] Company {company_id}, {year}-{month:02d}: "
                       f"Teachers={teachers_count}, Sales={monthly_sales:,}원, "
                       f"CommissionType={commission_type_id}")
            
            # 2. CommissionRateWindow에서 조건에 맞는 rate 조회
            # 기간 조건 + commission_type_id + 활성화 필터
            base_query = db.query(CommissionRateWindow).filter(
                CommissionRateWindow.commission_type_id == commission_type_id,
                CommissionRateWindow.is_active.is_(True),
                # 시작 기간 체크
                ((CommissionRateWindow.start_year < year) |
                 ((CommissionRateWindow.start_year == year) & (CommissionRateWindow.start_month <= month))),
                # 종료 기간 체크 (NULL이면 무기한)
                ((CommissionRateWindow.end_year.is_(None)) |
                 (CommissionRateWindow.end_year > year) |
                 ((CommissionRateWindow.end_year == year) & (CommissionRateWindow.end_month >= month)))
            )
            base_query = base_query.filter(
                or_(
                    CommissionRateWindow.company_id == company_id,
                    CommissionRateWindow.company_id.is_(None)
                )
            )

            company_pref = case(
                (CommissionRateWindow.company_id == company_id, 0),
                else_=1
            )

            # 3. 모든 후보 조회 후 조건 매칭
            candidates = base_query.order_by(
                company_pref.asc(),
                CommissionRateWindow.priority.desc()
            ).all()
            
            matched_rate = None
            matched_window = None
            
            logger.info(f"[Dynamic Rate] Testing {len(candidates)} windows: teachers={teachers_count}, sales={monthly_sales}")
            
            for window in candidates:
                if getattr(window, 'company_id', None) == company_id:
                    rate_percent = cast(Optional[Decimal], getattr(window, 'rate_percent', None))
                    if rate_percent is None:
                        logger.info(f"  Window ID {getattr(window, 'id', 'unknown')}: Skip override (rate_percent NULL)")
                        continue
                    matched_rate = float(rate_percent)
                    matched_window = window
                    logger.info(f"  Window ID {getattr(window, 'id', 'unknown')}: COMPANY OVERRIDE → Rate {matched_rate}% (Priority: {getattr(window, 'priority', 'unknown')})")
                    break

                min_teachers = cast(Optional[int], getattr(window, 'min_teachers', None))
                if min_teachers is not None and teachers_count < min_teachers:
                    logger.info(f"  Window ID {getattr(window, 'id', 'unknown')}: Skip (teachers {teachers_count} < min {min_teachers})")
                    continue

                min_amount = cast(Optional[int], getattr(window, 'min_amount', None))
                if min_amount is not None and monthly_sales < min_amount:
                    logger.info(f"  Window ID {getattr(window, 'id', 'unknown')}: Skip (sales {monthly_sales} < min {min_amount})")
                    continue

                max_amount = cast(Optional[int], getattr(window, 'max_amount', None))
                if max_amount is not None and monthly_sales >= max_amount:
                    logger.info(f"  Window ID {getattr(window, 'id', 'unknown')}: Skip (sales {monthly_sales} >= max {max_amount})")
                    continue

                rate_percent = cast(Optional[Decimal], getattr(window, 'rate_percent', None))
                if rate_percent is None:
                    logger.info(f"  Window ID {getattr(window, 'id', 'unknown')}: Skip (rate_percent NULL)")
                    continue

                matched_rate = float(rate_percent)
                matched_window = window
                logger.info(f"  Window ID {getattr(window, 'id', 'unknown')}: MATCH! Rate {matched_rate}% (Priority: {getattr(window, 'priority', 'unknown')})")
                break
            
            if matched_rate is not None:
                desc = getattr(matched_window, 'description', None) or f"Window ID {getattr(matched_window, 'id', 'unknown')}"
                logger.info(f"[Dynamic Rate] → {matched_rate}% ({desc})")
                return matched_rate
            
            # 매칭 없으면 기본값 25%
            logger.debug("[Dynamic Rate] → 25% (기본, 매칭 없음)")
            return 25.0
            
        except Exception as e:
            logger.error(f"[SettlementService] Error getting dynamic commission rate: {str(e)}", exc_info=True)
            return 25.0  # 에러 시 기본값
    
    @staticmethod
    def get_company_bascle_rate(
        db: Session,
        company_id: int,
        year: int,
        month: int,
        bascle_total_amount: int
    ) -> float:
        """
        회사(지사)별 BASCLE 수수료율 결정 (CommissionRateWindow 테이블 기반)
        
        CommissionRateWindow 테이블에서 동적 조건(min_teachers, min_monthly_sales)을 사용하여
        수수료율을 결정합니다.
        
        Args:
            db: 데이터베이스 세션
            company_id: 회사 ID
            year: 정산 연도
            month: 정산 월
            bascle_total_amount: 해당 월 BASCLE 총 매출액
        
        Returns:
            수수료율 (%)
        """
        # BASCLE commission_type_id 조회
        bascle_type = db.query(CommissionType).filter(
            CommissionType.code == 'BASCLE',
            CommissionType.is_active.is_(True)
        ).first()
        
        if not bascle_type:
            logger.warning("[BASCLE Rate] BASCLE CommissionType not found, using default 25%")
            return 25.0
        
        # 동적 수수료율 조회
        return SettlementService.get_dynamic_commission_rate(
            db=db,
            commission_type_id=int(getattr(bascle_type, 'commission_type_id', 0)),
            company_id=company_id,
            year=year,
            month=month,
            monthly_sales=bascle_total_amount,
        )
    
    @staticmethod
    def get_commission_rate_for_item(
        db: Session,
        order_item: OrderItem,
        year: int,
        month: int,
        amount: int
    ) -> Tuple[float, Optional[int], Optional[str]]:
        """
        OrderItem의 product_uid로 Product를 조회하여 cate1을 기반으로 CommissionType과 해당 수수료율을 조회
        cate1='006'인 경우 product_name도 cate1_name_list와 비교
        
        Args:
            db: 데이터베이스 세션
            order_item: 주문 상품
            year: 정산 연도
            month: 정산 월
            amount: 정산 대상 금액
        
        Returns:
            (rate_percent, commission_type_id, type_name) 튜플
        """
        # OrderItem의 product_uid로 Product를 조회하여 cate1 가져오기
        product = None
        product_uid = str(getattr(order_item, 'product_uid', '') or '')
        
        if product_uid:
            try:
                product = db.query(Product).filter(Product.uid == product_uid).first()
            except Exception as e:
                logger.warning(f"[SettlementService] Failed to query Product for product_uid={product_uid}: {e}")
        
        cate1 = str(getattr(product, 'cate1', '') or '') if product else ''
        product_name = str(getattr(product, 'product_name', '') or '') if product else str(getattr(order_item, 'product_name', '') or '')

        type3_type = db.query(CommissionType).filter(
            CommissionType.commission_type_id == 3,
            CommissionType.is_active.is_(True),
        ).first()
        type3_cate1_codes = frozenset(
            str(c) for c in (getattr(type3_type, "cate1_code_list", None) or []) if c
        )
        if SettlementService.is_babba_teacher_series_excluded(
            product, order_item, type3_cate1_codes=type3_cate1_codes
        ):
            logger.debug(
                "[SettlementService] Excluded babba teacher series product from commission: "
                f"uid={product_uid}, name={product_name}"
            )
            return (0.0, None, "바빠시리즈교사용(정산제외)")
        
        # 기본값으로 사용할 commission_type_id=4 (기타) 조회
        def get_default_commission_type():
            try:
                default_type = db.query(CommissionType).filter(
                    CommissionType.commission_type_id == 4,
                    CommissionType.is_active.is_(True)
                ).first()
                if default_type:
                    return (15.0, 4, str(getattr(default_type, 'name')))
            except Exception:
                pass
            return (15.0, None, '기타')
        
        if not cate1:
            logger.warning(f"[SettlementService] No cate1 found for order item: {order_item.id}, product_uid: {product_uid}")
            return get_default_commission_type()
        
        try:
            # cate1_code_list에 해당 cate1이 포함된 CommissionType 찾기
            # MySQL JSON_CONTAINS 함수 사용
            from sqlalchemy import text
            
            commission_types = db.query(CommissionType).filter(
                CommissionType.is_active.is_(True),
                text(f"JSON_CONTAINS(cate1_code_list, '\"{cate1}\"')")
            ).all()
            
            if not commission_types:
                # No CommissionType matched for this cate1. Per requirement,
                # show the cate1 code as the payment type instead of a generic 'DEFAULT'.
                # 수수료율을 0%로 설정 (commission_type_id가 없는 경우)
                logger.warning(f"[SettlementService] No CommissionType found for cate1={cate1}, will return cate1 as type_name with 0% rate")
                return (0.0, None, cate1)
            
            if cate1 == '006':
                matched_type = None
                # commission_type_id=1 (ENROLLMENT)을 먼저 찾기
                enrollment_type = None
                other_type = None
                
                for comm_type in commission_types:
                    comm_type_id = int(getattr(comm_type, 'commission_type_id'))
                    if comm_type_id == 1:
                        enrollment_type = comm_type
                    elif comm_type_id == 4:
                        other_type = comm_type
                
                # product_name이 ENROLLMENT의 cate1_name_list와 일치하는지 확인
                if enrollment_type:
                    cate1_name_list = getattr(enrollment_type, 'cate1_name_list', None)
                    if cate1_name_list and isinstance(cate1_name_list, list):
                        for cate1_name in cate1_name_list:
                            if cate1_name and cate1_name in product_name:
                                matched_type = enrollment_type
                                logger.debug(f"[SettlementService] cate1=006, product_name='{product_name}' matched with cate1_name='{cate1_name}' -> commission_type_id=1 (ENROLLMENT)")
                                break
                
                # 매칭되지 않으면 commission_type_id=4 (OTHER) 사용
                if not matched_type:
                    if other_type:
                        matched_type = other_type
                        logger.debug(f"[SettlementService] cate1=006, product_name='{product_name}' not matched -> commission_type_id=4 (OTHER)")
                    else:
                        logger.warning("[SettlementService] cate1=006 but commission_type_id=4 (OTHER) not found, using default")
                        return get_default_commission_type()
                
                commission_type = matched_type
            elif cate1 == '004':
                easys_type = None
                fallback_type = None
                for comm_type in commission_types:
                    code = str(getattr(comm_type, 'code', '') or '')
                    if code == 'EASYS_EDU':
                        easys_type = comm_type
                    elif fallback_type is None:
                        fallback_type = comm_type

                if easys_type:
                    cate1_name_list = getattr(easys_type, 'cate1_name_list', None)
                    matched_phrase = None
                    if cate1_name_list and isinstance(cate1_name_list, list):
                        for cate1_name in cate1_name_list:
                            if cate1_name and cate1_name in product_name:
                                matched_phrase = cate1_name
                                break
                    if matched_phrase:
                        commission_type = easys_type
                        logger.debug(f"[SettlementService] cate1=004, product_name='{product_name}' matched EASYS_EDU phrase '{matched_phrase}' -> commission_type=EASYS_EDU")
                    else:
                        commission_type = fallback_type or easys_type
                        logger.debug(f"[SettlementService] cate1=004, product_name='{product_name}' did not match EASYS_EDU phrases -> commission_type_id={getattr(commission_type, 'commission_type_id') if commission_type else 'unknown'}")
                else:
                    commission_type = commission_types[0]
                    logger.debug(f"[SettlementService] cate1=004 but EASYS_EDU not configured, defaulting to commission_type_id={getattr(commission_type, 'commission_type_id')}")
            else:
                # cate1이 006, 004가 아니면 첫 번째 매칭된 CommissionType 사용
                commission_type = commission_types[0]
            
            commission_type_id = int(getattr(commission_type, 'commission_type_id'))
            type_name = str(getattr(commission_type, 'name'))
            
            # commission_type_id=4 (기타)인 경우 cate1_name_list 확인
            # product_name이 cate1_name_list에 있으면 수수료율 15% 적용 + "보너스 포인트"를 type_name으로 사용
            if commission_type_id == 4:
                cate1_name_list = getattr(commission_type, 'cate1_name_list', None)
                if cate1_name_list and isinstance(cate1_name_list, list):
                    for cate1_name in cate1_name_list:
                        if cate1_name and cate1_name in product_name:
                            logger.debug(f"[SettlementService] commission_type_id=4, product_name='{product_name}' matched with cate1_name='{cate1_name}' -> applying 15% rate, type_name='보너스 포인트'")
                            return (15.0, commission_type_id, "보너스 포인트")  # type_name을 "보너스 포인트"로 사용
            
            # 해당 CommissionType의 기간별, 금액별 수수료율 조회
            start_condition = or_(
                CommissionRateWindow.start_year < year,
                and_(
                    CommissionRateWindow.start_year == year,
                    CommissionRateWindow.start_month <= month
                )
            )

            rate_windows = db.query(CommissionRateWindow).filter(
                CommissionRateWindow.commission_type_id == commission_type_id,
                CommissionRateWindow.is_active.is_(True),
                start_condition,
                # 종료 기간 체크 (NULL이면 무기한)
                ((CommissionRateWindow.end_year.is_(None)) | 
                 (CommissionRateWindow.end_year > year) |
                 ((CommissionRateWindow.end_year == year) & (CommissionRateWindow.end_month >= month))),
            ).order_by(
                CommissionRateWindow.priority.desc()  # 우선순위 높은 것부터
            ).all()
            
            # 금액 티어에 맞는 rate 찾기
            for window in rate_windows:
                min_amt = int(getattr(window, 'min_amount', 0) or 0)
                max_amt_value = getattr(window, 'max_amount', None)
                max_amt = int(max_amt_value) if max_amt_value is not None else None
                
                # 금액 범위 체크
                if min_amt <= amount and (max_amt is None or amount <= max_amt):
                    rate_value = float(getattr(window, 'rate_percent'))
                    logger.debug(f"[SettlementService] CommissionRateWindow matched for cate1={cate1}, commission_type_id={commission_type_id}, amount={amount}, min_amt={min_amt}, max_amt={max_amt}, rate={rate_value}%")
                    return (rate_value, commission_type_id, type_name)
            
            # 매칭되는 rate window가 없으면 기본 15%
            logger.warning(f"[SettlementService] No matching rate window for cate1={cate1}, commission_type_id={commission_type_id}, amount={amount}. rate_windows count={len(rate_windows)}, using default 15%")
            return (15.0, commission_type_id, type_name)
        
        except Exception as e:
            logger.error(f"[SettlementService] Error getting commission rate: {str(e)}", exc_info=True)
            # If cate1 is present, return it as the type name so the UI shows the cate1
            if cate1:
                return (15.0, None, cate1)
            return get_default_commission_type()
    
    @staticmethod
    def calculate_item_settlement(
        order_item: OrderItem,
        commission_rate: float,
        order_total_product_price: int,
        order_actual_payment: int,
        order_deli_price: int = 0
    ) -> Dict[str, Any]:
        """
        스크린샷 로직에 따른 상품별 정산 계산
        Order에 여러 OrderItem이 있는 경우 실결제액을 금액 비율로 배분
        
        Args:
            order_item: 주문 상품
            commission_rate: 수수료율 (%)
            order_total_product_price: 주문 전체 상품 금액 (모든 item의 합계, 배송비 제외)
            order_actual_payment: 주문 전체 실결제액 (배송비 포함, 적립금 차감 후)
            order_deli_price: 배송비 (배분 제외, 별도 처리용)
        
        Returns:
            정산 계산 결과 dict
        """
        # 1. 해당 상품의 결제액 (공급가)
        # 메이크샵: sell_price가 이미 총액(단가×수량)임
        quantity = int(getattr(order_item, 'basket_stock', 1))
        item_payment_amount = int(getattr(order_item, 'sell_price', 0))  # sell_price = 총액
        unit_price = item_payment_amount // quantity if quantity > 0 else item_payment_amount  # 단가 역산
        
        # 2. 전체 주문 금액 대비 이 상품의 비율 계산
        # 배송비 제외: 상품 금액만 기준으로 비율 계산
        if order_total_product_price > 0:
            item_ratio = item_payment_amount / order_total_product_price
        else:
            item_ratio = 1.0  # 안전장치
        
        # 3. 실결제액을 비율에 따라 배분
        # 배송비를 제외한 실결제액 = order_actual_payment - deli_price
        actual_payment_without_deli = order_actual_payment - order_deli_price
        item_actual_payment = int(actual_payment_without_deli * item_ratio)
        
        # 4. 적립금 계산 (역산)
        # 적립금 = 결제액 × 적립금 비율
        points_rate = 0.2498  # 24.98%
        item_points_amount = int(item_payment_amount * points_rate)
        
        # 5. 적립금 사용분 계산 (역산)
        # 적립금 사용분 = 적립금 - 실결제액
        item_points_used = item_points_amount - item_actual_payment
        
        # 6. 정산액 = 실결제액 × 정산비율
        settlement_rate = commission_rate / 100.0
        settlement_amount = int(item_actual_payment * settlement_rate)
        
        return {
            'payment_amount': item_payment_amount,          # 결제액 (공급가)
            'points_rate': points_rate,                     # 적립금 비율
            'points_amount': item_points_amount,            # 적립금
            'points_used': item_points_used,                # 적립금 사용분
            'actual_payment': item_actual_payment,          # 실결제액 (배송비 제외 후 비율 배분)
            'commission_rate': commission_rate,             # 정산비율 (%)
            'settlement_amount': settlement_amount,         # 정산액
            'quantity': quantity,
            'unit_price': unit_price,
            'item_ratio': item_ratio,                       # 전체 대비 비율
        }
    
    @staticmethod
    def aggregate_completed_orders_to_settlement(
        db: Session,
        year: Optional[int] = None,
        month: Optional[int] = None,
        settlement_type: str = "monthly",
        end_day: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        결제 완료된 주문(order_status='Y', pay_status='Y')을 사용자별, 월별로 집계하여 Settlement에 저장
        
        Args:
            db: 데이터베이스 세션
            year: 대상 연도 (None: 현재 연도)
            month: 대상 월 (None: 현재 월, 1-12)
            settlement_type: 정산 타입 ('daily', 'monthly', 'yearly', 'mtd')
            end_day: MTD 스냅샷 기준일(일). settlement_type='mtd'일 때 해당 월 1일~기준일까지 집계
        
        Returns:
            dict: {
                'status': 'success' | 'error',
                'message': str,
                'created_count': int,
                'updated_count': int,
                'total_amount': int,
                'details': list[dict]
            }
        """
        try:
            # 기본값 설정
            now = datetime.now()
            if year is None:
                year = now.year
            if month is None:
                month = now.month
            
            logger.info(f"[SettlementService] Starting aggregation: {year}-{month:02d} ({settlement_type})")
            
            # 1. 결제 완료된 주문 조회
            # order_status='Y' (발송완료) 또는 'P' (부분배송) + pay_status='Y' (결제완료)
            # 대상 월의 주문만 조회 (order_date가 YYYY-MM-DD HH:MM:SS 형식)
            period_start = date(year, month, 1)
            if end_day is not None:
                period_end = date(year, month, end_day) + timedelta(days=1)
            elif month == 12:
                period_end = date(year + 1, 1, 1)
            else:
                period_end = date(year, month + 1, 1)
            start_date = period_start.isoformat()
            end_date = period_end.isoformat()
            
            completed_orders = db.query(Order).filter(
                Order.order_status.in_(["Y", "P"]),
                Order.pay_status == "Y",
                Order.order_date >= start_date,
                Order.order_date < end_date
            ).all()
            
            logger.info(f"[SettlementService] Found {len(completed_orders)} completed orders for {year}-{month:02d}")
            
            # 2. 사용자 매핑 준비 (Order.member_id → User.login_id)
            # 모든 User 조회
            all_users = db.query(User).all()
            user_login_map: Dict[str, User] = {str(u.login_id): u for u in all_users}  # type: ignore
            
            # 2-1. name + phone 기반 매핑 (하이픈 제거한 전화번호)
            def normalize_phone(phone: str) -> str:
                """전화번호에서 하이픈 제거"""
                if not phone:
                    return ''
                return phone.replace('-', '').strip()
            
            # {(name, normalized_phone): User} 매핑 생성
            user_name_phone_map: Dict[Tuple[str, str], User] = {}
            for u in all_users:
                u_name = str(getattr(u, 'name', '') or '').strip()
                u_phone = normalize_phone(str(getattr(u, 'main_contact', '') or ''))
                if u_name and u_phone:
                    user_name_phone_map[(u_name, u_phone)] = u
            
            logger.info(f"[SettlementService] Loaded {len(all_users)} system users for mapping (login_id: {len(user_login_map)}, name+phone: {len(user_name_phone_map)})")

            # 2-2. 유효한 company_id 목록 미리 로드 (루프 내에서 반복 쿼리 방지)
            all_company_ids = db.query(Company.company_id).all()
            valid_company_ids: set = {cid[0] for cid in all_company_ids}  # type: ignore
            logger.info(f"[SettlementService] Loaded {len(valid_company_ids)} valid company IDs")

            # 3. 사용자별, 월별로 주문 그룹핑
            user_month_data: Dict[Tuple[int,int,int,int], Dict[str, Any]] = {}  # type: ignore
            company_role_month_data: Dict[Tuple[int,int,int,int], Dict[str, Any]] = {}  # type: ignore
            user_month_agg: Dict[Tuple[int,int,int], Dict[str, Any]] = {}
            company_month_agg: Dict[Tuple[int,int,int], Dict[str, Any]] = {}
            
            for order in completed_orders:
                # 주문 금액 계산 (총 상품가 + 배송비 - 사용 적립금)
                order_total = (order.total_product_price or 0) + (order.deli_price or 0) - (order.used_reserve or 0)
                
                # Order.member_id → User.login_id 매핑 (1차 시도)
                member_id_value = str(getattr(order, 'member_id', '') or '')
                
                # User 조회 (1차: member_id → login_id)
                user_obj = user_login_map.get(member_id_value)
                
                # 1차 매핑 실패 시 2차 시도: name + phone 매칭
                if not user_obj:
                    order_sender = str(getattr(order, 'sender', '') or '').strip()
                    order_phone = normalize_phone(str(getattr(order, 'phone', '') or ''))
                    if order_sender and order_phone:
                        user_obj = user_name_phone_map.get((order_sender, order_phone))
                        if user_obj:
                            logger.debug(f"[SettlementService] Matched order {order.ordernum} by name+phone: {order_sender}, {order_phone}")
                
                if not user_obj:
                    # 매핑 실패시 스킵 (다음 주문으로 진행)
                    order_info_snap: Dict[str, Any] = {
                        'ordernum': str(order.ordernum),
                        'member_id': member_id_value,
                        'sender': str(getattr(order, 'sender', '') or ''),
                        'phone': str(getattr(order, 'phone', '') or ''),
                        'pay_price': int(getattr(order, 'pay_price', 0) or 0),
                    }
                    SettlementService.record_skip(
                        db=db,
                        year=year,
                        month=month,
                        ordernum=str(order.ordernum),
                        skip_reason="USER_NOT_FOUND",
                        skip_detail=f"User not found for member_id={member_id_value}",
                        member_id=member_id_value,
                        order_info=order_info_snap
                    )
                    continue

                # 비활성 사용자는 정산(정산서/수수료)에서 제외
                if getattr(user_obj, "is_active", True) is not True:
                    order_info_snap: Dict[str, Any] = {
                        "ordernum": str(order.ordernum),
                        "member_id": member_id_value,
                        "user_id": int(getattr(user_obj, "user_id", 0) or 0),
                        "sender": str(getattr(order, "sender", "") or ""),
                        "phone": str(getattr(order, "phone", "") or ""),
                        "pay_price": int(getattr(order, "pay_price", 0) or 0),
                    }
                    SettlementService.record_skip(
                        db=db,
                        year=year,
                        month=month,
                        ordernum=str(order.ordernum),
                        skip_reason="USER_INACTIVE",
                        skip_detail="User is inactive (excluded from settlement)",
                        member_id=member_id_value,
                        user_id=int(getattr(user_obj, "user_id", 0) or 0),
                        order_info=order_info_snap,
                    )
                    continue
                
                company_id = int(getattr(user_obj, 'company_id'))
                user_id = int(getattr(user_obj, 'user_id'))
                role_id = int(getattr(user_obj, 'role_id'))
                
                # item_count 계산 (배송 대상: D%, T17, T27)
                item_cnt = db.query(func.count(OrderItem.id)).filter(
                    OrderItem.ordernum == order.ordernum,
                    or_(
                        OrderItem.basket_status.ilike('D%'),
                        OrderItem.basket_status.in_(['T17', 'T27'])
                    )
                ).scalar() or 0
                
                # ========================================
                # 1. 사용자 월별 집계 (role_id == 3 인 경우만)
                # company_id 검증 불필요! (SettlementUserMonthlyAggregate에 company_id FK가 없음)
                # ========================================
                if role_id == 3:
                    u_key = (user_id, year, month)
                    if u_key not in user_month_agg:
                        user_month_agg[u_key] = {
                            'order_count': 0,
                            'item_count': 0,
                            'total_amount': 0,
                        }
                    user_month_agg[u_key]['order_count'] += 1
                    user_month_agg[u_key]['item_count'] += item_cnt
                    user_month_agg[u_key]['total_amount'] += order_total
                
                # ========================================
                # 2. Settlement & Company/Role 롤업: company_id 검증 필요
                # Settlement 테이블에 company_id FK가 있음
                # ========================================
                if company_id not in valid_company_ids:
                    # company_id가 유효하지 않으면 Settlement/company_role_month 집계만 건너뛰고
                    # 사용자 월별 집계는 이미 위에서 처리됨
                    logger.warning(f"[SettlementService] Skipping invalid company_id={company_id} for order {order.ordernum}")
                    order_info_snap = {
                        'ordernum': str(order.ordernum),
                        'member_id': member_id_value,
                        'user_id': user_id,
                        'sender': str(getattr(order, 'sender', '') or ''),
                        'phone': str(getattr(order, 'phone', '') or ''),
                        'pay_price': int(getattr(order, 'pay_price', 0) or 0),
                    }
                    SettlementService.record_skip(
                        db=db,
                        year=year,
                        month=month,
                        ordernum=str(order.ordernum),
                        skip_reason="INVALID_COMPANY_ID",
                        skip_detail=f"Company ID {company_id} not in valid company IDs",
                        member_id=member_id_value,
                        user_id=user_id,
                        company_id=company_id,
                        order_info=order_info_snap
                    )
                    continue
                
                # Settlement 레벨 데이터 수집
                key = (user_id, company_id, year, month)
                if key not in user_month_data:  # type: ignore
                    user_month_data[key] = {
                        'orders': [],
                        'total_amount': 0,
                        'member_id': member_id_value,
                        'role_id': role_id,
                    }
                user_month_data[key]['orders'].append(order)  # type: ignore
                user_month_data[key]['total_amount'] += order_total  # type: ignore

                # 회사/역할 월별 롤업 데이터 수집
                cr_key = (company_id, role_id, year, month)
                if cr_key not in company_role_month_data:  # type: ignore
                    company_role_month_data[cr_key] = {
                        'order_count': 0,
                        'item_count': 0,
                        'total_amount': 0,
                    }
                company_role_month_data[cr_key]['order_count'] += 1  # type: ignore
                company_role_month_data[cr_key]['total_amount'] += order_total  # type: ignore
                company_role_month_data[cr_key]['item_count'] += item_cnt  # type: ignore

                # 회사 월별 집계 (role_id != 2 제외 조건 적용)
                if role_id != 2:
                    c_key = (company_id, year, month)
                    if c_key not in company_month_agg:
                        company_month_agg[c_key] = {
                            'order_count': 0,
                            'item_count': 0,
                            'total_amount': 0,
                        }
                    company_month_agg[c_key]['order_count'] += 1
                    company_month_agg[c_key]['item_count'] += item_cnt
                    company_month_agg[c_key]['total_amount'] += order_total
            
            logger.info(f"[SettlementService] Grouped into {len(user_month_data)} user-month combinations and {len(company_role_month_data)} company-role-month combinations")
            
            # ========================================
            # STEP 0: 회사별 commission_type_id=2(BASCLE), 3의 총 매출액 미리 계산
            # ========================================
            company_bascle_amounts: Dict[int, int] = {}  # company_id -> total_bascle_amount
            company_type23_amounts: Dict[int, int] = {}  # company_id -> total type2+type3 amount
            
            # commission_type_id=2, 3 조회
            bascle_type = db.query(CommissionType).filter(
                CommissionType.code == 'BASCLE',
                CommissionType.is_active.is_(True)
            ).first()
            
            type3_type = db.query(CommissionType).filter(
                CommissionType.commission_type_id == 3,
                CommissionType.is_active.is_(True)
            ).first()
            type3_cate1_codes = getattr(type3_type, 'cate1_code_list', []) or [] if type3_type else []
            type3_cate1_codes_frozen = frozenset(str(c) for c in type3_cate1_codes if c)
            
            if bascle_type:
                bascle_cate1_codes = getattr(bascle_type, 'cate1_code_list', []) or []
                bascle_cate1_name_list = getattr(bascle_type, 'cate1_name_list', []) or []
                
                # 모든 주문(completed_orders)에 대해 회사별 commission_type 별 매출액 계산
                for order in completed_orders:
                    order_items = db.query(OrderItem).filter(
                        OrderItem.ordernum == order.ordernum,
                        or_(
                            OrderItem.basket_status.ilike('D%'),
                            OrderItem.basket_status.in_(['T17', 'T27'])
                        )
                    ).all()
                    if not order_items:
                        logger.warning(f"[SettlementService] No order items found for order {order.ordernum}")
                        order_info_snap: Dict[str, Any] = {
                            'ordernum': str(order.ordernum),
                            'sender': str(getattr(order, 'sender', '') or ''),
                            'phone': str(getattr(order, 'phone', '') or ''),
                            'pay_price': int(getattr(order, 'pay_price', 0) or 0),
                        }
                        SettlementService.record_skip(
                            db=db,
                            year=year,
                            month=month,
                            ordernum=str(order.ordernum),
                            skip_reason="NO_ORDER_ITEMS",
                            skip_detail="No OrderItem records found for this order",
                            order_info=order_info_snap
                        )
                        continue
                    
                    # 메이크샵: sell_price가 이미 총액(단가×수량)임
                    item_prices = []
                    for item in order_items:
                        item_price = int(getattr(item, 'sell_price', 0))  # sell_price = 총액
                        item_prices.append(item_price)
                    
                    calculated_total = sum(item_prices)
                    order_actual_payment = int(order.pay_price or 0)
                    order_deli_price = int(order.deli_price or 0)
                    
                    # 배송비를 제외한 실결제액
                    actual_payment_without_deli = order_actual_payment - order_deli_price
                    
                    # 비율 배분 (배송비 제외)
                    if calculated_total > 0:
                        raw_shares = [(price * actual_payment_without_deli) / calculated_total for price in item_prices]
                        allocated_payments = [int(share) for share in raw_shares]
                        fractions = [(raw_shares[i] - allocated_payments[i], i) for i in range(len(raw_shares))]
                        fractions.sort(reverse=True, key=lambda x: x[0])
                        remainder = actual_payment_without_deli - sum(allocated_payments)
                        for idx_temp in range(min(remainder, len(fractions))):
                            _, item_idx_temp = fractions[idx_temp]
                            allocated_payments[item_idx_temp] += 1
                    else:
                        allocated_payments = [actual_payment_without_deli // len(order_items)] * len(order_items)
                        remainder = actual_payment_without_deli - sum(allocated_payments)
                        for i in range(remainder):
                            allocated_payments[i] += 1
                    
                    # 주문의 user를 조회하여 company_id 획득
                    member_id_value = str(getattr(order, 'member_id', '') or '')
                    user_obj = user_login_map.get(member_id_value)
                    
                    # 1차 매핑 실패 시 2차 시도
                    if not user_obj:
                        order_sender = str(getattr(order, 'sender', '') or '').strip()
                        order_phone = normalize_phone(str(getattr(order, 'phone', '') or ''))
                        if order_sender and order_phone:
                            user_obj = user_name_phone_map.get((order_sender, order_phone))
                    
                    if not user_obj:
                        continue
                    
                    company_id = int(getattr(user_obj, 'company_id'))
                    
                    # company_id 검증
                    if company_id not in valid_company_ids:
                        logger.warning(f"[SettlementService] Skipping invalid company_id={company_id} for BASCLE calculation (order {order.ordernum})")
                        member_id_value = str(getattr(order, 'member_id', '') or '')
                        order_info_snap = {
                            'ordernum': str(order.ordernum),
                            'member_id': member_id_value,
                            'sender': str(getattr(order, 'sender', '') or ''),
                            'phone': str(getattr(order, 'phone', '') or ''),
                            'pay_price': int(getattr(order, 'pay_price', 0) or 0),
                        }
                        SettlementService.record_skip(
                            db=db,
                            year=year,
                            month=month,
                            ordernum=str(order.ordernum),
                            skip_reason="INVALID_COMPANY_ID_BASCLE",
                            skip_detail=f"Company ID {company_id} not in valid company IDs (BASCLE calculation)",
                            member_id=member_id_value,
                            company_id=company_id,
                            order_info=order_info_snap
                        )
                        continue
                    
                    # commission_type별 실결제액 합산
                    for idx, item in enumerate(order_items):
                        product = db.query(Product).filter(Product.uid == str(getattr(item, 'product_uid', ''))).first()

                        if SettlementService.is_babba_teacher_series_excluded(
                            product, item, type3_cate1_codes=type3_cate1_codes_frozen
                        ):
                            logger.debug(
                                f"[SettlementService] STEP 0: Exclude babba teacher series "
                                f"item {getattr(item, 'product_uid', '')}"
                            )
                            continue

                        if not product:
                            continue

                        cate1 = str(getattr(product, 'cate1', ''))
                        product_name = str(getattr(product, 'product_name', '') or '')

                        # BASCLE (commission_type_id=2)
                        # cate1='004'인 경우 cate1_name_list에 있는 문구가 product_name에 포함되면 BASCLE에서 제외
                        should_exclude_from_bascle = False
                        if cate1 == '004' and bascle_cate1_name_list:
                            for name in bascle_cate1_name_list:
                                if name and name in product_name:
                                    should_exclude_from_bascle = True
                                    logger.debug(f"[SettlementService] STEP 0: Exclude cate1=004 product '{product_name}' from BASCLE (matched with cate1_name='{name}')")
                                    break
                        
                        is_bascle = False
                        is_type3 = False
                        
                        if cate1 in bascle_cate1_codes and not should_exclude_from_bascle:
                            is_bascle = True
                            
                        if cate1 in type3_cate1_codes:
                            is_type3 = True
                            
                        if is_bascle:
                            if company_id not in company_bascle_amounts:
                                company_bascle_amounts[company_id] = 0
                            company_bascle_amounts[company_id] += allocated_payments[idx]
                            
                        if is_bascle or is_type3:
                            if company_id not in company_type23_amounts:
                                company_type23_amounts[company_id] = 0
                            company_type23_amounts[company_id] += allocated_payments[idx]
                
                logger.info(f"[SettlementService] Calculated company BASCLE amounts: {company_bascle_amounts}")
                logger.info(f"[SettlementService] Calculated company Type2+Type3 amounts: {company_type23_amounts}")
            
            # 3. Settlement 레코드 생성 또는 업데이트
            created_count = 0
            updated_count = 0
            from typing import List
            details: List[Dict[str, Any]] = []
            total_settlement_amount = 0
            # 동일 user.code 사용자들이 한 배치에서 같은 statement_number를
            # 받지 않도록 이번 실행에서 할당한 번호를 추적한다.
            reserved_statement_numbers: set[str] = set()
            
            for (user_id, company_id, settle_year, settle_month), data in user_month_data.items():
                try:
                    # 정산 날짜 설정
                    if settlement_type == "mtd":
                        snapshot_day = end_day or (period_end - timedelta(days=1)).day
                        settlement_date = datetime(settle_year, settle_month, snapshot_day)
                    elif settlement_type == "daily":
                        settlement_date = datetime(settle_year, settle_month, 1)
                    elif settlement_type == "monthly":
                        settlement_date = datetime(settle_year, settle_month, 1)
                    else:  # yearly
                        settlement_date = datetime(settle_year, 1, 1)
                    
                    # 기존 Settlement 확인
                    existing = db.query(Settlement).filter(
                        Settlement.user_id == user_id,
                        Settlement.company_id == company_id,
                        Settlement.settlement_type == settlement_type,
                        Settlement.settlement_date == settlement_date,
                    ).first()
                    
                    # 수수료 계산 (OrderItem별로 cate1 기반 계산)
                    # Order별로 처리 (실결제액 비율 배분을 위해)
                    commission_details_list = []
                    total_commission = 0
                    
                    # ========================================
                    # STEP 1: 미리 계산된 회사별 BASCLE/Type3 총 매출액 사용
                    # monthly_sales = commission_type_id=2(BASCLE) + commission_type_id=3의 실결제액 합계
                    # ========================================
                    bascle_total_amount = company_bascle_amounts.get(company_id, 0)
                    type23_total_amount = company_type23_amounts.get(company_id, 0)
                    monthly_sales = type23_total_amount  # commission_type_id=2,3의 합계
                    
                    # 회사별 BASCLE 수수료율 결정 (monthly_sales 기반)
                    company_bascle_rate = SettlementService.get_company_bascle_rate(
                        db, company_id, settle_year, settle_month, monthly_sales
                    )
                    
                    logger.info(f"[Settlement] Company {company_id}: BASCLE amount={bascle_total_amount}, "
                               f"Type2+Type3 total (monthly_sales)={monthly_sales}, BASCLE rate={company_bascle_rate}%")
                    
                    # ========================================
                    # STEP 2: 각 주문 아이템 정산 계산
                    # ========================================
                    
                    for order in data['orders']:
                        # 해당 Order의 모든 items 가져오기
                        order_items = db.query(OrderItem).filter(
                            OrderItem.ordernum == order.ordernum,
                            or_(
                                OrderItem.basket_status.ilike('D%'),
                                OrderItem.basket_status.in_(['T17', 'T27'])
                            )
                        ).all()
                        
                        if not order_items:
                            continue
                        
                        # 메이크샵: sell_price가 이미 총액(단가×수량)임
                        item_prices = []
                        for item in order_items:
                            item_price = int(getattr(item, 'sell_price', 0))  # sell_price = 총액
                            item_prices.append(item_price)
                        
                        # OrderItem들의 실제 합계
                        calculated_total = sum(item_prices)
                        
                        # Order의 실제 결제 금액 (pay_price: 실제로 결제된 금액)
                        order_actual_payment = int(order.pay_price or 0)
                        order_deli_price = int(order.deli_price or 0)
                        
                        # 배송비를 제외한 실결제액 (상품 구매에만 해당)
                        actual_payment_without_deli = order_actual_payment - order_deli_price
                        
                        # ========================================
                        # 비율 배분 알고리즘
                        # 배송비를 제외한 실결제액을 OrderItem 합계 기준 비율로 배분
                        # ========================================
                        if calculated_total > 0:
                            # 1. 각 아이템의 raw share 계산 (실수)
                            raw_shares = [(price * actual_payment_without_deli) / calculated_total for price in item_prices]
                            
                            # 2. 정수 부분 (floor)
                            allocated_payments = [int(share) for share in raw_shares]
                            
                            # 3. 소수 부분 계산 및 정렬
                            fractions = [(raw_shares[i] - allocated_payments[i], i) for i in range(len(raw_shares))]
                            fractions.sort(reverse=True, key=lambda x: x[0])  # 소수 부분 내림차순
                            
                            # 4. 잔여분 계산 및 분배
                            remainder = actual_payment_without_deli - sum(allocated_payments)
                            for idx in range(min(remainder, len(fractions))):
                                _, item_idx = fractions[idx]
                                allocated_payments[item_idx] += 1
                            
                            # 검증: 합계가 정확히 실결제액과 일치하는지 확인
                            # 데이터 불일치 시 경고만 출력하고 계속 진행
                            if sum(allocated_payments) != actual_payment_without_deli:
                                logger.warning(f"[SettlementService] Payment allocation mismatch for order {order.ordernum}: {sum(allocated_payments)} != {actual_payment_without_deli}, using allocated values")
                        else:
                            # 안전장치: 상품 금액이 0이면 균등 배분
                            allocated_payments = [actual_payment_without_deli // len(order_items)] * len(order_items)
                            remainder = actual_payment_without_deli - sum(allocated_payments)
                            for i in range(remainder):
                                allocated_payments[i] += 1
                        
                        # ========================================
                        # 각 OrderItem 정산 계산 (allocated_payment 사용)
                        # ========================================
                        for idx, item in enumerate(order_items):
                            allocated_payment = allocated_payments[idx]

                            product_for_item = db.query(Product).filter(
                                Product.uid == str(getattr(item, "product_uid", ""))
                            ).first()
                            if SettlementService.is_babba_teacher_series_excluded(
                                product_for_item,
                                item,
                                type3_cate1_codes=type3_cate1_codes_frozen,
                            ):
                                logger.debug(
                                    f"[SettlementService] Skip commission for babba teacher series item "
                                    f"{getattr(item, 'product_uid', '')}"
                                )
                                continue
                            
                            # commission_type 결정
                            rate, comm_type_id, type_name = SettlementService.get_commission_rate_for_item(
                                db, item, settle_year, settle_month, allocated_payment
                            )
                            
                            # BASCLE인 경우 회사별로 결정된 수수료율 사용
                            if bascle_type and comm_type_id == getattr(bascle_type, 'commission_type_id', None):
                                rate = company_bascle_rate
                                logger.debug(f"[Settlement] Using company BASCLE rate: {rate}% for item {getattr(item, 'product_uid', '')} (commission_type_id={comm_type_id})")
                            
                            # 정산 계산
                            # 메이크샵: sell_price가 이미 총액(단가×수량)임
                            item_price = item_prices[idx]
                            quantity = int(getattr(item, 'basket_stock', 1))
                            sell_price_total = int(getattr(item, 'sell_price', 0))  # sell_price = 총액
                            unit_price = sell_price_total // quantity if quantity > 0 else sell_price_total  # 단가 역산
                            
                            # 포인트 계산 (결제액 기준)
                            points_rate = 0.2498  # 24.98%
                            points_amount = int(item_price * points_rate)
                            
                            # 포인트 사용분 = 결제액 - 실결제액
                            points_used = item_price - allocated_payment
                            
                            # 정산액 = 실결제액 × 수수료율
                            settlement_rate = rate / 100.0
                            settlement_amount = int(allocated_payment * settlement_rate)
                            
                            # 총 수수료 = rate 적용 후 commission 합계
                            total_commission += settlement_amount
                            
                            commission_details_list.append({
                                'commission_type_id': comm_type_id,
                                'type_name': type_name,
                                'ordernum': order.ordernum,
                                'product_uid': str(getattr(item, 'product_uid', '')),
                                'product_name': str(getattr(item, 'product_name', '')),
                                'cate1': str(getattr(item, 'cate1', '')),
                                'quantity': quantity,
                                'unit_price': unit_price,
                                'payment_amount': item_price,
                                'item_ratio': item_price / calculated_total if calculated_total > 0 else 0,
                                'points_rate': points_rate,
                                'points_amount': points_amount,
                                'points_used': points_used,
                                'actual_payment': allocated_payment,  # 비율 배분된 실결제액
                                'rate': rate,
                                'commission': settlement_amount,
                            })
                    
                    # 세금 계산 (소득세 3%, 지방세 10% — 십 단위 절사)
                    # total_commission: 공제 전 지급액, net_settlement_amount: 세후 실지급액
                    deducted_tax, deducted_local_tax, _ = calc_settlement_taxes(total_commission)
                    net_settlement_amount = total_commission - deducted_tax - deducted_local_tax
                    
                    # 정렬 전 디버깅
                    before_sort = [x.get('commission_type_id', 'None') for x in commission_details_list]
                    logger.debug(f"User {user_id} - Before sort: {before_sort}")
                    
                    # commission_details를 commission_type_id 순으로 정렬 (1, 2, 3, 4)
                    # commission_type_id가 None인 경우 999로 처리하여 맨 뒤로 보냄
                    commission_details_list.sort(key=lambda x: x['commission_type_id'] if x['commission_type_id'] is not None else 999)
                    
                    # 정렬 후 디버깅
                    after_sort = [x.get('commission_type_id', 'None') for x in commission_details_list]
                    logger.debug(f"User {user_id} - After sort: {after_sort}")
                    
                    # commission_details JSON 생성
                    commission_details = json.dumps(commission_details_list)
                    
                    if existing:
                        # 업데이트
                        existing.total_commission = total_commission  # type: ignore
                        existing.deducted_tax = deducted_tax  # type: ignore
                        existing.deducted_local_tax = deducted_local_tax  # type: ignore
                        existing.net_settlement_amount = net_settlement_amount  # type: ignore
                        existing.commission_details = commission_details  # type: ignore
                        db.add(existing)
                        updated_count += 1
                        logger.debug(f"[SettlementService] Updated settlement for user {user_id}, company {company_id}")
                    else:
                        # 신규 생성
                        # MTD/daily는 일별 스냅샷이므로 정산서 번호를 붙이지 않는다.
                        # (월 단위 statement_number unique와 충돌해 전체 commit이 롤백됨)
                        is_snapshot = settlement_type in ("mtd", "daily")
                        statement_number = None
                        statement_status = None
                        statement_issued_at = None
                        if not is_snapshot:
                            statement_number = SettlementService.generate_statement_number(
                                db=db,
                                user_id=user_id,
                                year=settle_year,
                                month=settle_month,
                                reserved=reserved_statement_numbers,
                            )
                            statement_status = "ISSUED"
                            statement_issued_at = datetime.now()

                        new_settlement = Settlement(
                            user_id=user_id,
                            company_id=company_id,
                            settlement_type=settlement_type,
                            settlement_date=settlement_date,
                            total_commission=total_commission,
                            deducted_tax=deducted_tax,
                            deducted_local_tax=deducted_local_tax,
                            net_settlement_amount=net_settlement_amount,
                            commission_details=commission_details,
                            is_paid=False,
                            statement_number=statement_number,
                            statement_status=statement_status,
                            statement_issued_at=statement_issued_at,
                        )
                        db.add(new_settlement)
                        # 다음 사용자 번호 생성 시 이 INSERT가 보이도록 flush
                        db.flush()
                        created_count += 1
                        logger.debug(
                            f"[SettlementService] Created settlement for user {user_id}, "
                            f"company {company_id}, type={settlement_type}, "
                            f"statement_number={statement_number}"
                        )
                    
                    total_settlement_amount += net_settlement_amount
                    
                    details.append({
                        'user_id': user_id,
                        'company_id': company_id,
                        'role_id': data['role_id'],
                        'member_id': data['member_id'],
                        'order_count': len(data['orders']),
                        'total_amount': data['total_amount'],
                        'commission': total_commission,
                        'net_amount': net_settlement_amount,
                    })
                
                except Exception as e:
                    logger.error(f"[SettlementService] Error processing settlement for user {user_id}: {str(e)}", exc_info=True)
                    continue
            
            # 4. 회사 월별 집계 저장 (role_id != 2)
            for (c_company_id, c_year, c_month), c_data in company_month_agg.items():
                existing_company_rollup = db.query(SettlementCompanyMonthlyAggregate).filter(
                    SettlementCompanyMonthlyAggregate.company_id == c_company_id,
                    SettlementCompanyMonthlyAggregate.year == c_year,
                    SettlementCompanyMonthlyAggregate.month == c_month,
                ).first()
                
                if existing_company_rollup:
                    existing_company_rollup.total_orders = c_data['order_count']
                    existing_company_rollup.total_items = c_data['item_count']
                    existing_company_rollup.total_amount = c_data['total_amount']
                    db.add(existing_company_rollup)
                else:
                    db.add(SettlementCompanyMonthlyAggregate(
                        company_id=c_company_id,
                        year=c_year,
                        month=c_month,
                        total_orders=c_data['order_count'],
                        total_items=c_data['item_count'],
                        total_amount=c_data['total_amount'],
                    ))

            # 커밋
            db.commit()
            
            # ========================================
            # 5. Statement 자동 생성 (월별 확정분만)
            # ========================================
            statements_created = 0
            if settlement_type == "monthly":
                for (user_id, company_id, settle_year, settle_month) in user_month_data.keys():
                    try:
                        statement = SettlementService.create_statement(
                            db=db,
                            user_id=user_id,
                            company_id=company_id,
                            year=settle_year,
                            month=settle_month
                        )
                        statements_created += 1
                        logger.debug(
                            f"[SettlementService] Created statement for user {user_id}: "
                            f"{statement.statement_number}"
                        )
                    except Exception as e:
                        logger.error(
                            f"[SettlementService] Error creating statement for user {user_id}: {str(e)}",
                            exc_info=True,
                        )
                        # 정산서 생성 실패해도 정산 데이터는 유지
                        continue
            
            result: Dict[str, Any] = {
                'status': 'success',
                'message': f'Successfully aggregated {len(user_month_data)} user-month settlements, {len(company_role_month_data)} company-role-role rollups, {len(user_month_agg)} user monthly aggregates (role=3), {len(company_month_agg)} company monthly aggregates, and {statements_created} statements created',
                'created_count': created_count,
                'updated_count': updated_count,
                'statements_created': statements_created,
                'total_settlement_amount': total_settlement_amount,
                'details': details,
            }
            
            logger.info(f"[SettlementService] Aggregation completed: created={created_count}, updated={updated_count}, total_amount={total_settlement_amount}")
            return result
        
        except Exception as e:
            db.rollback()
            logger.error(f"[SettlementService] Error during aggregation: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Error during aggregation: {str(e)}',
                'created_count': 0,
                'updated_count': 0,
                'total_settlement_amount': 0,
                'details': [],
            }
    
    
    @staticmethod
    def get_settlement_summary(db: Session, year: Optional[int] = None, month: Optional[int] = None) -> Dict[str, Any]:
        """
        정산 요약 정보 조회
        
        Args:
            db: 데이터베이스 세션
            year: 대상 연도
            month: 대상 월
        
        Returns:
            dict: 정산 요약 정보
        """
        try:
            now = datetime.now()
            if year is None:
                year = now.year
            if month is None:
                month = now.month
            
            query = db.query(Settlement).filter(
                func.year(Settlement.settlement_date) == year,
                func.month(Settlement.settlement_date) == month,
            )
            
            settlements = query.all()
            
            total_commission = sum(s.total_commission or 0 for s in settlements)
            total_deducted_tax = sum(s.deducted_tax or 0 for s in settlements)
            total_net_amount = sum(s.net_settlement_amount or 0 for s in settlements)
            
            return {
                'status': 'success',
                'year': year,
                'month': month,
                'total_records': len(settlements),
                'total_commission': total_commission,
                'total_deducted_tax': total_deducted_tax,
                'total_net_amount': total_net_amount,
                'paid_count': sum(1 for s in settlements if bool(getattr(s, 'is_paid', False))),
                'unpaid_count': sum(1 for s in settlements if not bool(getattr(s, 'is_paid', False))),
            }
        
        except Exception as e:
            logger.error(f"[SettlementService] Error getting summary: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Error getting summary: {str(e)}',
            }

    @staticmethod
    def pre_validate_orders(
        db: Session,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        정산 사전 검증 (dry-run) — 매일 주문 동기화 후 호출하여 정산 불가 주문을 조기 발견

        실제 Settlement을 생성하지 않고, aggregate_completed_orders_to_settlement()과
        동일한 검증 로직을 실행하여 스킵될 주문/아이템 목록만 반환합니다.

        검증 항목:
        1. USER_NOT_FOUND — Order.member_id / name+phone → User 매핑 불가
        2. INVALID_COMPANY_ID — 매핑된 User의 company_id가 companies 테이블에 없음
        3. NO_ORDER_ITEMS — 결제 완료 주문에 OrderItem이 없음
        4. NO_PRODUCT — OrderItem.product_uid에 해당 Product가 없음
        5. NO_COMMISSION_TYPE — Product.cate1에 매칭되는 CommissionType이 없음

        Args:
            db: 데이터베이스 세션
            year: 대상 연도 (None: 현재 연도)
            month: 대상 월 (None: 현재 월)

        Returns:
            dict: {
                'status': 'success',
                'year': int, 'month': int,
                'total_completed_orders': int,
                'settleable_count': int,
                'issue_count': int,
                'issues': [
                    {
                        'reason': str,
                        'ordernum': str,
                        'detail': str,
                        'order_info': dict | None,
                    }, ...
                ],
                'summary_by_reason': { reason: count, ... },
            }
        """
        try:
            from sqlalchemy import text

            now = datetime.now()
            if year is None:
                year = now.year
            if month is None:
                month = now.month

            logger.info(f"[PreValidate] Starting pre-validation for {year}-{month:02d}")

            # 대상 기간
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"

            # 1. 결제 완료 주문 조회
            completed_orders = db.query(Order).filter(
                Order.order_status.in_(["Y", "P"]),
                Order.pay_status == "Y",
                Order.order_date >= start_date,
                Order.order_date < end_date,
            ).all()

            total_completed = len(completed_orders)
            logger.info(f"[PreValidate] Found {total_completed} completed orders for {year}-{month:02d}")

            # 2. 매핑 테이블 준비 (aggregate 로직과 동일)
            all_users = db.query(User).all()
            user_login_map: Dict[str, User] = {}
            for u in all_users:
                lid = getattr(u, 'login_id', None)
                if lid:
                    user_login_map[str(lid)] = u

            def normalize_phone(phone: str) -> str:
                if not phone:
                    return ''
                return phone.replace('-', '').strip()

            user_name_phone_map: Dict[tuple, User] = {}
            for u in all_users:
                u_name = str(getattr(u, 'name', '') or '').strip()
                u_phone = normalize_phone(str(getattr(u, 'main_contact', '') or ''))
                if u_name and u_phone:
                    user_name_phone_map[(u_name, u_phone)] = u

            all_company_ids = db.query(Company.company_id).all()
            valid_company_ids: set = {cid[0] for cid in all_company_ids}

            # 3. CommissionType cate1 매핑 캐시
            all_commission_types = db.query(CommissionType).filter(
                CommissionType.is_active.is_(True)
            ).all()
            # cate1_code → CommissionType 매핑
            cate1_to_commission: Dict[str, CommissionType] = {}
            for ct in all_commission_types:
                codes = getattr(ct, 'cate1_code_list', None) or []
                if isinstance(codes, list):
                    for code in codes:
                        if code and code not in cate1_to_commission:
                            cate1_to_commission[code] = ct

            # 3-1. 대상 주문번호에 해당하는 OrderItem을 한 번에 배치 조회
            order_nums_list = [str(o.ordernum) for o in completed_orders]
            all_order_items: list = []
            if order_nums_list:
                # 500개씩 나눠서 IN 쿼리 실행 (MySQL IN절 제한 방지)
                for i in range(0, len(order_nums_list), 500):
                    chunk = order_nums_list[i:i+500]
                    items_chunk = db.query(OrderItem).filter(
                        OrderItem.ordernum.in_(chunk),
                        or_(
                            OrderItem.basket_status.ilike('D%'),
                            OrderItem.basket_status.in_(['T17', 'T27'])
                        ),
                    ).all()
                    all_order_items.extend(items_chunk)

            # ordernum → [OrderItem, ...] 매핑
            order_items_map: Dict[str, list] = {}
            for item in all_order_items:
                onum = str(item.ordernum)
                if onum not in order_items_map:
                    order_items_map[onum] = []
                order_items_map[onum].append(item)

            # 3-2. 관련 Product를 한 번에 배치 조회
            product_uids_needed = set()
            for item in all_order_items:
                uid = str(getattr(item, 'product_uid', '') or '')
                if uid:
                    product_uids_needed.add(uid)

            product_map: Dict[str, Any] = {}
            if product_uids_needed:
                uid_list = list(product_uids_needed)
                for i in range(0, len(uid_list), 500):
                    chunk = uid_list[i:i+500]
                    products_chunk = db.query(Product).filter(
                        Product.uid.in_(chunk)
                    ).all()
                    for p in products_chunk:
                        product_map[str(p.uid)] = p

            # 4. 주문별 검증
            issues: list[Dict[str, Any]] = []
            settleable_ordernums: set = set()

            for order in completed_orders:
                ordernum = str(order.ordernum)
                member_id_value = str(getattr(order, 'member_id', '') or '')

                # --- CHECK 1: USER_NOT_FOUND ---
                user_obj = user_login_map.get(member_id_value)
                if not user_obj:
                    order_sender = str(getattr(order, 'sender', '') or '').strip()
                    order_phone = normalize_phone(str(getattr(order, 'phone', '') or ''))
                    if order_sender and order_phone:
                        user_obj = user_name_phone_map.get((order_sender, order_phone))

                if not user_obj:
                    sender_name = str(getattr(order, 'sender', '') or '')
                    order_phone = str(getattr(order, 'phone', '') or '')
                    pay_price = int(getattr(order, 'pay_price', 0) or 0)
                    order_date_val = getattr(order, 'order_date', '')
                    issues.append({
                        'reason': 'USER_NOT_FOUND',
                        'reason_kr': '사용자 매핑 불가',
                        'ordernum': ordernum,
                        'detail': (
                            f"[사용자 매핑 불가] 주문번호 {ordernum} — "
                            f"주문자: {sender_name or '(없음)'}, 연락처: {order_phone or '(없음)'}, "
                            f"회원ID: {member_id_value or '(없음)'}, "
                            f"결제금액: {pay_price:,}원, 주문일: {order_date_val}. "
                            f"login_id 매핑 실패 후 이름+전화번호 fallback 매핑도 실패. "
                            f"DB users 테이블에 해당 사용자를 등록하거나 login_id를 확인하세요."
                        ),
                        'order_info': {
                            'ordernum': ordernum,
                            'member_id': member_id_value,
                            'sender': sender_name,
                            'phone': order_phone,
                            'pay_price': pay_price,
                            'order_date': str(order_date_val),
                        },
                    })
                    continue

                # --- CHECK 1-1: USER_INACTIVE ---
                if getattr(user_obj, "is_active", True) is not True:
                    issues.append({
                        'reason': 'USER_INACTIVE',
                        'reason_kr': '비활성 사용자 제외',
                        'ordernum': ordernum,
                        'detail': (
                            f"[비활성 사용자 제외] 주문번호 {ordernum} — "
                            f"회원ID: {member_id_value or '(없음)'} 이(가) 비활성(is_active=False) 상태라 정산에서 제외됩니다."
                        ),
                        'order_info': {
                            'ordernum': ordernum,
                            'member_id': member_id_value,
                            'user_id': int(getattr(user_obj, 'user_id', 0) or 0),
                        },
                    })
                    continue

                # --- CHECK 2: INVALID_COMPANY_ID ---
                company_id = int(getattr(user_obj, 'company_id'))
                user_name = str(getattr(user_obj, 'name', '') or '')
                user_login = str(getattr(user_obj, 'login_id', '') or '')
                if company_id not in valid_company_ids:
                    issues.append({
                        'reason': 'INVALID_COMPANY_ID',
                        'reason_kr': '회사ID 오류',
                        'ordernum': ordernum,
                        'detail': (
                            f"[회사ID 오류] 주문번호 {ordernum} — "
                            f"매핑된 사용자: {user_name} (login_id: {user_login}, user_id: {user_obj.user_id}), "
                            f"소속 company_id={company_id}이(가) companies 테이블에 존재하지 않음. "
                            f"사용자의 소속 회사 정보를 수정하거나 companies 테이블에 해당 회사를 등록하세요."
                        ),
                        'order_info': {
                            'ordernum': ordernum,
                            'user_id': getattr(user_obj, 'user_id', None),
                            'user_name': user_name,
                            'login_id': user_login,
                            'company_id': company_id,
                        },
                    })
                    continue

                # --- CHECK 3: NO_ORDER_ITEMS ---
                order_items = order_items_map.get(ordernum, [])

                if not order_items:
                    sender_name_val = str(getattr(order, 'sender', '') or '')
                    pay_price_val = int(getattr(order, 'pay_price', 0) or 0)
                    order_date_str = str(getattr(order, 'order_date', '') or '')
                    issues.append({
                        'reason': 'NO_ORDER_ITEMS',
                        'reason_kr': '주문 상품 없음',
                        'ordernum': ordernum,
                        'detail': (
                            f"[주문 상품 없음] 주문번호 {ordernum} — "
                            f"주문자: {sender_name_val or '(없음)'}, 결제금액: {pay_price_val:,}원, "
                            f"주문일: {order_date_str}. "
                            f"결제 완료 주문이지만 배송 상태(basket_status='D%', 'T17', 'T27')인 OrderItem이 없습니다. "
                            f"Makeshop에서 주문 상세 데이터가 동기화되지 않았을 수 있습니다."
                        ),
                        'order_info': {
                            'ordernum': ordernum,
                            'sender': sender_name_val,
                            'pay_price': pay_price_val,
                            'order_date': order_date_str,
                            'user_name': user_name,
                            'company_id': company_id,
                        },
                    })
                    continue

                # --- CHECK 4 & 5: NO_PRODUCT / NO_COMMISSION_TYPE per item ---
                order_has_issue = False
                for item in order_items:
                    product_uid = str(getattr(item, 'product_uid', '') or '')
                    item_name = str(getattr(item, 'product_name', '') or getattr(item, 'pname', '') or '')
                    item_price = int(getattr(item, 'price', 0) or 0)
                    item_qty = int(getattr(item, 'ea', 0) or getattr(item, 'quantity', 0) or 0)
                    product = product_map.get(product_uid) if product_uid else None

                    if not product:
                        issues.append({
                            'reason': 'NO_PRODUCT',
                            'reason_kr': '상품 정보 없음',
                            'ordernum': ordernum,
                            'detail': (
                                f"[상품 정보 없음] 주문번호 {ordernum} — "
                                f"상품명: {item_name or '(없음)'}, 상품UID: {product_uid or '(없음)'}, "
                                f"단가: {item_price:,}원, 수량: {item_qty}, "
                                f"주문자: {user_name} (company_id: {company_id}). "
                                f"products 테이블에 해당 상품(uid={product_uid})이 없습니다. "
                                f"Makeshop 상품 동기화를 먼저 실행하세요."
                            ),
                            'order_info': {
                                'ordernum': ordernum,
                                'product_uid': product_uid,
                                'item_name': item_name,
                                'item_price': item_price,
                                'item_qty': item_qty,
                                'user_name': user_name,
                                'company_id': company_id,
                            },
                        })
                        order_has_issue = True
                        continue

                    cate1 = str(getattr(product, 'cate1', '') or '')
                    product_name = str(getattr(product, 'product_name', '') or '')
                    if cate1 and cate1 not in cate1_to_commission:
                        issues.append({
                            'reason': 'NO_COMMISSION_TYPE',
                            'reason_kr': '수수료 타입 미설정',
                            'ordernum': ordernum,
                            'detail': (
                                f"[수수료 타입 미설정] 주문번호 {ordernum} — "
                                f"상품명: {product_name}, 상품UID: {product_uid}, "
                                f"카테고리1 코드: '{cate1}', 단가: {item_price:,}원, "
                                f"주문자: {user_name} (company_id: {company_id}). "
                                f"해당 cate1 코드에 매칭되는 CommissionType이 없습니다. "
                                f"관리자 패널 > 수수료 타입에서 cate1_code_list에 '{cate1}'을(를) 추가하세요."
                            ),
                            'order_info': {
                                'ordernum': ordernum,
                                'product_uid': product_uid,
                                'product_name': product_name,
                                'cate1': cate1,
                                'item_price': item_price,
                                'user_name': user_name,
                                'company_id': company_id,
                            },
                        })
                        order_has_issue = True

                if not order_has_issue:
                    settleable_ordernums.add(ordernum)

            # 5. 요약
            summary_by_reason: Dict[str, int] = {}
            for issue in issues:
                reason = issue['reason']
                summary_by_reason[reason] = summary_by_reason.get(reason, 0) + 1

            result = {
                'status': 'success',
                'year': year,
                'month': month,
                'total_completed_orders': total_completed,
                'settleable_count': len(settleable_ordernums),
                'issue_count': len(issues),
                'issues': issues,
                'summary_by_reason': summary_by_reason,
            }

            logger.info(
                f"[PreValidate] Done: {total_completed} orders, "
                f"{len(settleable_ordernums)} settleable, "
                f"{len(issues)} issues — {summary_by_reason}"
            )

            # 캐시에 저장 (홈 대시보드 빠른 조회용)
            SettlementService._pre_validation_cache = result.copy()
            SettlementService._pre_validation_cached_at = datetime.now()

            # DB에 스킵 기록 저장 (정산 안된 내역 페이지에서 조회 가능하도록)
            try:
                # 해당 월의 사전 검증 기록 삭제 (중복 방지)
                db.query(SettlementSkipRecord).filter(
                    SettlementSkipRecord.settlement_year == year,
                    SettlementSkipRecord.settlement_month == month,
                    SettlementSkipRecord.skip_reason.in_([
                        'USER_NOT_FOUND', 'INVALID_COMPANY_ID',
                        'NO_ORDER_ITEMS', 'NO_PRODUCT', 'NO_COMMISSION_TYPE',
                    ]),
                ).delete(synchronize_session=False)

                if issues:
                    for issue in issues:
                        order_info = issue.get('order_info')
                        skip_rec = SettlementSkipRecord(
                            settlement_year=year,
                            settlement_month=month,
                            ordernum=issue.get('ordernum', ''),
                            member_id=order_info.get('member_id') if order_info else None,
                            user_id=order_info.get('user_id') if order_info else None,
                            company_id=order_info.get('company_id') if order_info else None,
                            skip_reason=issue.get('reason', ''),
                            skip_detail=issue.get('detail', ''),
                            order_info=order_info,
                        )
                        db.add(skip_rec)

                db.commit()
                logger.info(f"[PreValidate] Saved {len(issues)} skip records to DB for {year}-{month:02d}")
            except Exception as save_err:
                db.rollback()
                logger.error(f"[PreValidate] Failed to save skip records: {save_err}", exc_info=True)

            return result

        except Exception as e:
            logger.error(f"[PreValidate] Error: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'message': f'Pre-validation error: {str(e)}',
                'year': year,
                'month': month,
                'total_completed_orders': 0,
                'settleable_count': 0,
                'issue_count': 0,
                'issues': [],
                'summary_by_reason': {},
            }

    @staticmethod
    def get_cached_pre_validation() -> Optional[Dict[str, Any]]:
        """
        캐시된 정산 사전 검증 결과를 반환합니다.
        홈 대시보드에서 매번 DB를 조회하지 않고 마지막 동기화 시 저장된 결과를 사용합니다.

        Returns:
            dict | None: 캐시된 검증 결과 + cached_at 시간, 또는 캐시 없으면 None
        """
        if SettlementService._pre_validation_cache is None:
            return None

        result = dict(SettlementService._pre_validation_cache)
        cached_at = SettlementService._pre_validation_cached_at
        result['cached_at'] = cached_at.strftime('%Y-%m-%d %H:%M:%S') if cached_at else None
        return result

    @staticmethod
    def get_pre_validation_from_db(db: Session, year: Optional[int] = None, month: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        정산 사전 검증 결과를 반환합니다 (캐시 우선).
        
        조회 우선순위:
        1. 캐시가 있고 요청 연월과 일치 → 캐시에서 반환 (성능 최적화)
        2. 그 외 → DB의 settlement_skip_records에서 조회
        
        홈 대시보드 배너 표시용.

        Args:
            db: 데이터베이스 세션
            year: 대상 연도 (None이면 현재 연도)
            month: 대상 월 (None이면 현재 월)

        Returns:
            dict | None: 검증 결과 요약
        """
        try:
            now = datetime.now()
            if year is None:
                year = now.year
            if month is None:
                month = now.month

            # 1) 캐시 우선: 캐시가 있고 연월이 일치하면 캐시에서 반환
            if (SettlementService._pre_validation_cache is not None and 
                SettlementService._pre_validation_cache.get('year') == year and
                SettlementService._pre_validation_cache.get('month') == month):
                return SettlementService.get_cached_pre_validation()

            # 2) DB에서 조회: 사전 검증 사유에 해당하는 스킵 기록만 조회
            pre_validate_reasons = [
                'USER_NOT_FOUND', 'INVALID_COMPANY_ID',
                'NO_ORDER_ITEMS', 'NO_PRODUCT', 'NO_COMMISSION_TYPE',
            ]

            records = db.query(SettlementSkipRecord).filter(
                SettlementSkipRecord.settlement_year == year,
                SettlementSkipRecord.settlement_month == month,
                SettlementSkipRecord.skip_reason.in_(pre_validate_reasons),
            ).all()

            if not records:
                # 기록이 없으면 None 반환 (검증 미실행 또는 이슈 0건)
                return None

            # 사유별 집계
            summary_by_reason: Dict[str, int] = {}
            for r in records:
                reason = r.skip_reason or 'UNKNOWN'
                summary_by_reason[reason] = summary_by_reason.get(reason, 0) + 1

            # 가장 최근 recorded_at을 마지막 검증 시각으로 사용
            latest_at = max(r.recorded_at for r in records if r.recorded_at)
            cached_at_str = None
            if latest_at:
                from zoneinfo import ZoneInfo
                seoul_tz = ZoneInfo("Asia/Seoul")
                if latest_at.tzinfo is None:
                    from datetime import timezone
                    latest_at = latest_at.replace(tzinfo=timezone.utc)
                cached_at_str = latest_at.astimezone(seoul_tz).strftime('%Y-%m-%d %H:%M:%S')

            return {
                'status': 'success',
                'year': year,
                'month': month,
                'issue_count': len(records),
                'summary_by_reason': summary_by_reason,
                'cached_at': cached_at_str,
            }

        except Exception as e:
            logger.error(f"[PreValidate] DB read error: {e}", exc_info=True)
            return None

    
    @staticmethod
    def calculate_company_monthly_sales(db: Session, year: int, month: int, target_company_id: int) -> Dict[str, Any]:
        """
        특정 년/월, 회사의 monthly_sales (Type2+Type3 실결제 합계) 값을 계산하고 구성 로그를 함께 반환.
        """
        logger.info(f"[Calculate Monthly Sales] Start for company_id={target_company_id} at {year}-{month}")
        
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        completed_orders = db.query(Order).filter(
            Order.order_status.in_(["Y", "P"]),
            Order.pay_status == "Y",
            Order.order_date >= start_date,
            Order.order_date < end_date,
        ).all()
        
        # User 매핑
        all_users = db.query(User).all()
        user_login_map = {str(getattr(u, 'login_id', '')): u for u in all_users if getattr(u, 'login_id', None)}
        
        def normalize_phone(phone: str) -> str:
            return phone.replace('-', '').strip() if phone else ''
            
        user_name_phone_map = {}
        for u in all_users:
            u_name = str(getattr(u, 'name', '') or '').strip()
            u_phone = normalize_phone(str(getattr(u, 'main_contact', '') or ''))
            if u_name and u_phone:
                user_name_phone_map[(u_name, u_phone)] = u

        # Commission Type 조회
        bascle_type = db.query(CommissionType).filter(
            CommissionType.code == 'BASCLE', CommissionType.is_active.is_(True)
        ).first()
        type3_type = db.query(CommissionType).filter(
            CommissionType.commission_type_id == 3, CommissionType.is_active.is_(True)
        ).first()

        bascle_cate1_codes = getattr(bascle_type, 'cate1_code_list', []) or []
        bascle_cate1_name_list = getattr(bascle_type, 'cate1_name_list', []) or []
        type3_cate1_codes = getattr(type3_type, 'cate1_code_list', []) or [] if type3_type else []
        type3_cate1_codes_frozen = frozenset(str(c) for c in type3_cate1_codes if c)

        bascle_amount = 0
        type3_amount = 0
        total_monthly_sales = 0
        logs = []

        for order in completed_orders:
            member_id_value = str(getattr(order, 'member_id', '') or '')
            user_obj = user_login_map.get(member_id_value)
            if not user_obj:
                order_sender = str(getattr(order, 'sender', '') or '').strip()
                order_phone = normalize_phone(str(getattr(order, 'phone', '') or ''))
                if order_sender and order_phone:
                    user_obj = user_name_phone_map.get((order_sender, order_phone))
            
            if not user_obj:
                continue
                
            company_id = int(getattr(user_obj, 'company_id'))
            if company_id != target_company_id:
                continue

            order_items = db.query(OrderItem).filter(
                OrderItem.ordernum == order.ordernum,
                or_(
                    OrderItem.basket_status.ilike('D%'),
                    OrderItem.basket_status.in_(['T17', 'T27'])
                )
            ).all()
            if not order_items:
                continue

            item_prices = [int(getattr(item, 'sell_price', 0)) for item in order_items]
            calculated_total = sum(item_prices)
            actual_payment_without_deli = int(order.pay_price or 0) - int(order.deli_price or 0)

            # 결제액 배분
            if calculated_total > 0:
                raw_shares = [(price * actual_payment_without_deli) / calculated_total for price in item_prices]
                allocated_payments = [int(share) for share in raw_shares]
                fractions = [(raw_shares[i] - allocated_payments[i], i) for i in range(len(raw_shares))]
                fractions.sort(reverse=True, key=lambda x: x[0])
                remainder = actual_payment_without_deli - sum(allocated_payments)
                for idx_temp in range(min(remainder, len(fractions))):
                    _, item_idx_temp = fractions[idx_temp]
                    allocated_payments[item_idx_temp] += 1
            else:
                allocated_payments = [actual_payment_without_deli // len(order_items)] * len(order_items)
                remainder = actual_payment_without_deli - sum(allocated_payments)
                for i in range(remainder):
                    allocated_payments[i] += 1

            for idx, item in enumerate(order_items):
                product = db.query(Product).filter(Product.uid == str(getattr(item, 'product_uid', ''))).first()
                if product:
                    cate1 = str(getattr(product, 'cate1', ''))
                    product_name = str(getattr(product, 'product_name', '') or '')
                    allocated_val = allocated_payments[idx]
                    
                    is_bascle = False
                    is_type3 = False

                    # Check Bascle
                    should_exclude_from_bascle = False
                    if cate1 == '004' and bascle_cate1_name_list:
                        for name in bascle_cate1_name_list:
                            if name and name in product_name:
                                should_exclude_from_bascle = True
                                break
                    if cate1 in bascle_cate1_codes and not should_exclude_from_bascle:
                        is_bascle = True
                        
                    # Check Type3
                    if SettlementService.is_babba_teacher_series_excluded(
                        product, item, type3_cate1_codes=type3_cate1_codes_frozen
                    ):
                        continue

                    if cate1 in type3_cate1_codes:
                        is_type3 = True

                    if is_bascle or is_type3:
                        if is_bascle:
                            bascle_amount += allocated_val
                        if is_type3:
                            type3_amount += allocated_val
                            
                        total_monthly_sales += allocated_val
                        logs.append({
                            'ordernum': str(order.ordernum),
                            'product_uid': str(item.product_uid),
                            'product_name': str(product_name),
                            'cate1': cate1,
                            'item_sell_price': item_prices[idx],
                            'order_actual_payment': actual_payment_without_deli,
                            'allocated_payment': allocated_val,
                            'matched_types': [t for t, match in zip(['BASCLE', 'TYPE3'], [is_bascle, is_type3]) if match]
                        })
                        
        return {
            "year": year,
            "month": month,
            "company_id": target_company_id,
            "bascle_amount": bascle_amount,
            "type3_amount": type3_amount,
            "total_monthly_sales": total_monthly_sales,
            "order_item_logs": logs
        }
