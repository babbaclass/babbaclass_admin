"""
SQLAlchemy ORM models for babba-api

SQLAlchemy 2.0과 sqladmin 0.21.0 호환성 설정
조직 구조 관리: 본사/지사와 사용자/직책의 분리
"""

from __future__ import annotations

from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, Text, ForeignKey, Numeric, UniqueConstraint, JSON, text, select
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship, column_property
from sqlalchemy.sql import func
from app.database import Base

class Grade(Base):
    """Company grade master (e.g., 새싹, 활성화 지사, 우수 지사, 최우수 지사)"""
    __tablename__ = "grades"

    grade_id = Column(Integer, primary_key=True, index=True)
    grade_name = Column(String(100), unique=True, index=True, nullable=False)
    display_order = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Grade(grade_id={self.grade_id}, grade_name={self.grade_name})>"


class Company(Base):
    """Company model for managing headquarters and branches (simplified: no contact linkage)"""
    __tablename__ = "companies"

    company_id = Column(Integer, primary_key=True, index=True)
    company_type = Column(String(50), nullable=False, index=True)  # 'HQ' or 'BRANCH'
    hq_company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=True, index=True)
    grade_id = Column(Integer, ForeignKey("grades.grade_id"), nullable=True, index=True)
    code = Column(String(50), nullable=False, unique=True, index=True)  # 회사 코드 (private, 필수)
    name = Column(String(255), nullable=True, index=True)  # 회사명 (옵셔널)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    from sqlalchemy.orm import relationship
    grade = relationship("Grade")

    def __repr__(self):
        return f"<Company(company_id={self.company_id}, company_type={self.company_type}, code={self.code}, name={self.name})>"

    @property
    def grade_name(self) -> str | None:
        try:
            g = getattr(self, "grade", None)
            return getattr(g, "grade_name", None) if g is not None else None
        except Exception:
            return None

    @property
    def grade_value(self) -> str | None:
        """Display-friendly grade label for admin lists.

        Note: We avoid exposing raw numeric grade_id in lists; this returns the
        associated Grade.grade_name when available.
        """
        try:
            g = getattr(self, "grade", None)
            return getattr(g, "grade_name", None) if g is not None else None
        except Exception:
            return None


# Contact model removed: simplified contact handling migrated to user main/sub contact fields.


class Role(Base):
    """Role model for managing user roles and titles"""
    __tablename__ = "roles"

    role_id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(100), nullable=False, unique=True, index=True)  # 예: '본사 관리자', '지사장', '원장'
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Role(role_id={self.role_id}, role_name={self.role_name})>"



class User(Base):
    """User model simplified: main_contact and sub_contact inline columns"""
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=True, index=True)  # 사용자 코드 (leading zero 보존을 위해 String으로)
    login_id = Column(String(255), unique=True, index=True, nullable=True)  # 로그인용 ID (가입 전은 NULL)
    name = Column(String(255), nullable=False, index=True)  # 사용자 이름
    email = Column(String(255), index=True, nullable=True)  # nullable, unique 제약 제거
    password_hash = Column(String(255), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    main_contact = Column(String(255), nullable=True)
    bank_name = Column(String(100), nullable=True)  # 은행명
    bank_account = Column(String(50), nullable=True)  # 계좌번호
    address = Column(String(255), nullable=True)  # 주소
    business_name = Column(String(255), nullable=True)  # 사업자명
    contracted_at = Column(String(10), nullable=True, index=True)  # 계약일 (YYYY-MM-DD 형식)
    settlement_personal = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))  # 개인 정산
    settlement_business = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))  # 사업자 정산
    doc_contract = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))  # 서류: 계약서 전문
    doc_bankbook = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))  # 서류: 통장사본
    doc_personal_info = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))  # 서류: 개인정보사본
    doc_business_registration = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))  # 서류: 사업자등록증 사본
    is_register = Column(Boolean, nullable=False, default=True, index=True)  # 가입 상태: True(가입 완료), False(가입 전)
    is_active = Column(Boolean, default=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0, server_default=text("0"))
    locked_until = Column(DateTime(timezone=True), nullable=True)
    password_change_required = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    role = relationship("Role")
    company = relationship("Company")
    statements = relationship("Statement", back_populates="user")
    contract_endings = relationship("ContractEnd", back_populates="user")

    def __repr__(self):
        return f"<User(user_id={self.user_id}, name={self.name}, email={self.email}, company_id={self.company_id})>"

    @property
    def company_name(self) -> str | None:
        try:
            c = getattr(self, "company", None)
            return getattr(c, "name", None) if c is not None else None
        except Exception:
            return None

    @property
    def role_name(self) -> str | None:
        try:
            r = getattr(self, "role", None)
            return getattr(r, "role_name", None) if r is not None else None
        except Exception:
            return None


class LoginHistory(Base):
    """Record of user login events for auditing and dashboard reporting."""

    __tablename__ = "login_history"

    login_history_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    login_id = Column(String(255), nullable=True)
    user_name = Column(String(255), nullable=True)
    role_id = Column(Integer, nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)
    source = Column(String(64), nullable=True)
    login_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<LoginHistory(id={self.login_history_id}, user_id={self.user_id}, "
            f"login_at={self.login_at}, ip={self.ip_address})>"
        )


class ContractEnd(Base):
    """계약 종료 관리 - 지사별 계약 종료 예정 정보를 저장합니다"""
    __tablename__ = "contract_end"

    contract_end_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False, index=True)
    contract_end_date = Column(Date, nullable=True, index=True)
    renewal_count = Column(Integer, nullable=False, default=0, server_default="0")  # 계약 연장 횟수 (0~20)
    memo = Column(Text, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="contract_endings")
    company = relationship("Company")

    def __repr__(self) -> str:
        return (
            f"<ContractEnd(id={self.contract_end_id}, user_id={self.user_id}, "
            f"contract_end_date={self.contract_end_date})>"
        )

User.contract_end_date = column_property(
    select(ContractEnd.contract_end_date)
    .where(ContractEnd.user_id == User.user_id)
    .order_by(ContractEnd.contract_end_id.desc())
    .limit(1)
    .scalar_subquery()
)

User.contract_end_memo = column_property(
    select(ContractEnd.memo)
    .where(ContractEnd.user_id == User.user_id)
    .order_by(ContractEnd.contract_end_id.desc())
    .limit(1)
    .scalar_subquery()
)


class Product(Base):
    """Product 통합 모델 - Makeshop API 필드와 완벽 동기화"""
    __tablename__ = "products"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # 기본 필드 (Makeshop API에서 제공)
    uid = Column(String(100), unique=True, index=True, nullable=False)  # API: uid (상품ID)
    product_name = Column(String(255), nullable=False, index=True)      # API: product_name (상품명)
    sellprice = Column(Integer, nullable=False)                         # API: sellprice (판매가)
    buyprice = Column(Integer, nullable=True)                           # API: buyprice (원가)
    consumerprice = Column(Integer, nullable=True)                      # API: consumerprice (소비자가)
    quantity = Column(Integer, default=0)                               # API: quantity (재고) - 'Unlimited'는 -1로 저장
    status = Column(String(50), default="active")                       # API: status (상품상태)
    
    # 카테고리 관련 필드
    brandcode = Column(String(30), nullable=True, index=True)           # API: brandcode (브랜드코드)
    cate1 = Column(String(10), nullable=True, index=True)               # API: cate1 (대분류)
    cate2 = Column(String(10), nullable=True, index=True)               # API: cate2 (중분류)
    virtual_cate = Column(String(50), nullable=True)                    # API: virtual_cate (가상분류)
    
    # 판매 관련 필드
    reserve = Column(String(255), nullable=True)                        # API: reserve (적립금)
    sell_accept = Column(String(1), nullable=True, index=True)          # API: sell_accept (판매승인)
    display = Column(String(1), nullable=True, index=True)              # API: display (표시여부)
    product_type = Column(String(30), nullable=True, index=True)        # API: product_type (상품유형)
    
    # 프로모션 관련 필드
    best_product_display = Column(String(1), nullable=True)             # API: best_product_display (BEST상품표시)
    best_review_display = Column(String(1), nullable=True)              # API: best_review_display (베스트리뷰표시)
    sellcount = Column(Integer, nullable=True)                          # API: sellcount (판매수)
    
    # 날짜 필드
    regdate = Column(DateTime(timezone=True), nullable=True, index=True) # API: regdate (등록일)
    moddate = Column(DateTime(timezone=True), nullable=True)            # API: moddate (수정일)
    
    # 배송 관련 필드
    provide_delivery_price = Column(Integer, nullable=True)             # API: provide_delivery_price (배송료)
    max_order_quantity_method = Column(String(20), nullable=True)       # API: max_order_quantity_method (최대주문수량방식)
    min_order_quantity_method = Column(String(20), nullable=True)       # API: min_order_quantity_method (최소주문수량방식)
    
    # 세금 관련 필드
    vat = Column(String(1), nullable=True)                              # API: vat (부가세)
    vat_type = Column(String(20), nullable=True)                        # API: vat_type (과세구분)
    
    # 상품 설명 필드
    keyword = Column(Text, nullable=True)                               # API: keyword (검색어)
    product_content = Column(LONGTEXT, nullable=True)                   # API: product_content (상품설명) - LONGTEXT for large content
    
    # 기타 필드
    display_date = Column(DateTime(timezone=True), nullable=True)       # API: display_date (표시시작일)
    importune = Column(String(1), nullable=True)                        # API: importune (수입상품표시)
    view_count = Column(Integer, nullable=True)                         # API: view_count (조회수)
    cart_count = Column(Integer, nullable=True)                         # API: cart_count (장바구니담기수)
    is_add_composition = Column(String(1), nullable=True)               # API: is_add_composition (조합상품여부)
    ems_type = Column(String(30), nullable=True)                        # API: ems_type (EMS배송유형)
    
    # 시스템 필드
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Product(id={self.id}, uid={self.uid}, product_name={self.product_name})>"


class Order(Base):
    """Order model for Makeshop orders"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    # Makeshop API fields
    ordernum = Column(String(100), unique=True, index=True, nullable=False)  # API: ordernum
    member_id = Column(String(100), nullable=True, index=True)  # API: id (회원 ID, tester001 같은 형식)
    order_date = Column(String(20), nullable=True)  # API: order_date (YYYYMMDDHHMMSS format)
    is_member = Column(Integer, default=0)  # API: is_member (0=non-member, 1=member)
    sender = Column(String(255), nullable=True)  # API: sender (customer name)
    email = Column(String(255), nullable=True, index=True)  # API: email
    phone = Column(String(20), nullable=True)  # API: phone
    mobile = Column(String(20), nullable=True)  # API: mobile
    pay_path = Column(String(100), nullable=True)  # API: pay_path (payment method)
    pay_price = Column(Integer, nullable=False, default=0)  # API: pay_price (actual paid amount)
    order_status = Column(String(50), default="pending")  # API: order_status
    pay_status = Column(String(50), default="pending")  # API: pay_status (from payment object)
    deli_price = Column(Integer, default=0)  # API: deli_price (shipping cost)
    start_price = Column(Integer, default=0)  # API: start_price
    total_product_price = Column(Integer, default=0)  # API: total_product_price
    basket_count = Column(Integer, default=0)  # API: basket_count (items count)
    memo = Column(Text, nullable=True)  # API: memo (notes)
    used_emoney = Column(Integer, default=0)  # API: used_emoney
    used_reserve = Column(Integer, default=0)  # API: used_reserve
    group_name = Column(String(255), nullable=True)  # API: group_name
    cash_receipt = Column(String(50), nullable=True)  # API: cash_receipt
    cash_receipt_status = Column(String(50), nullable=True)  # API: cash_receipt_status
    send_number = Column(String(255), nullable=True)  # 송장번호 (tracking number)
    regist_delivery = Column(Boolean, default=False)  # 송장 등록 여부
    # Convenience fields (derived from API)
    shipping_address = Column(Text, nullable=True)  # Extracted from product deliveryInfo
    # Metadata
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Order(id={self.id}, ordernum={self.ordernum})>"


class OrderItem(Base):
    """Order item details model"""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    ordernum = Column(String(100), ForeignKey("orders.ordernum"), nullable=False, index=True)  # FK to orders.ordernum
    product_uid = Column(String(100), ForeignKey("products.uid"), nullable=False)  # API: product_uid
    product_name = Column(String(255), nullable=False)  # API: product_name
    basket_stock = Column(Integer, default=1)  # API: basket_stock (quantity)
    sell_price = Column(Integer, nullable=False, default=0)  # API: sell_price (unit price)
    num = Column(String(100), nullable=True)  # API: num (product item number)
    cate1 = Column(String(255), nullable=True)  # API: cate1 (category)
    basket_status = Column(String(50), nullable=True)  # API: basket_status
    stock_key = Column(String(100), nullable=True)  # API: stock_key
    vat = Column(Integer, default=0)  # API: vat
    send_number = Column(String(255), nullable=True)  # 송장번호 (tracking number) - Order와 동일
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<OrderItem(ordernum={self.ordernum}, product_name={self.product_name})>"


class Member(Base):
    """Makeshop Member/Customer model"""
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    makeshop_member_id = Column(String(100), unique=True, index=True, nullable=False)
    hname = Column(String(255), nullable=False, index=True)  # API: hname (회원명)
    email = Column(String(255), nullable=True, index=True)
    mobile = Column(String(20), nullable=True, index=True)  # API: mobile (휴대폰)
    address = Column(Text, nullable=True)
    join_date = Column(DateTime(timezone=True), nullable=True)
    member_level = Column(String(50), nullable=True)  # 회원 등급 (일반, VIP, 등)
    total_purchase_amount = Column(Integer, default=0)  # 총 구매액
    total_orders = Column(Integer, default=0)  # 총 주문 수
    last_purchase_date = Column(DateTime(timezone=True), nullable=True)  # 마지막 구매 날짜
    is_active = Column(Boolean, default=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # Extended fields mapped from external JSON (list[0])
    mem_type = Column(String(50), nullable=True)          # mem_type
    simple_type = Column(String(50), nullable=True)       # simple_type
    grade = Column(Integer, nullable=True)                # grade numeric
    reserve = Column(Integer, nullable=True)              # reserve (예비값/적립?)
    email_receive = Column(String(1), nullable=True)      # Y/N
    sms_receive = Column(String(1), nullable=True)        # Y/N
    login_date = Column(DateTime(timezone=True), nullable=True)
    mod_date = Column(DateTime(timezone=True), nullable=True)
    reg_date = Column(DateTime(timezone=True), nullable=True)
    birth_day = Column(String(20), nullable=True)         # 원본 '200201'
    birth_day_year = Column(String(20), nullable=True)    # 원본 '19200201'
    birth_format = Column(String(10), nullable=True)      # Ymd 등
    sex = Column(String(5), nullable=True)                # W/M
    group_id = Column(String(50), nullable=True)
    group_name = Column(String(100), nullable=True)
    post = Column(String(20), nullable=True)
    address_detail = Column(Text, nullable=True)
    push_receive = Column(String(1), nullable=True)       # Y/N
    point = Column(Integer, nullable=True)
    emoney = Column(Integer, nullable=True)
    is_app_use = Column(String(1), nullable=True)         # Y/N
    extension_period = Column(DateTime(timezone=True), nullable=True)
    order_count = Column(Integer, nullable=True)          # order_count (may map to total_orders separately)
    company_name = Column(String(255), nullable=True)
    company_owner = Column(String(255), nullable=True)
    company_num = Column(String(100), nullable=True)
    company_corp = Column(String(100), nullable=True)
    company_biz = Column(String(100), nullable=True)
    company_item = Column(String(100), nullable=True)
    company_post = Column(String(20), nullable=True)
    company_addr = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Member(id={self.id}, makeshop_member_id={self.makeshop_member_id}, hname={self.hname})>"


# =============================================================
# Commission Models (수수료 타입 + 기간 윈도우별 수수료율)
# =============================================================

class CommissionType(Base):
    """수수료 타입 마스터: 가입비, 바스클 교재, 이지스에듀교재, 기타 등"""
    __tablename__ = "commission_types"

    commission_type_id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, index=True, nullable=False)  # ENROLLMENT, BASCLE, AEGIS_EDU, OTHER
    name = Column(String(255), nullable=False)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    # 카테고리 코드 및 이름 목록 (JSON 배열)
    cate1_code_list = Column(JSON, nullable=True)  # 예: ['001', '007']
    cate1_name_list = Column(JSON, nullable=True)  # 예: ['[가입] 혼합형(수학+문해력)', '[가입] 수학형(기본)']
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<CommissionType(id={self.commission_type_id}, code={self.code}, name={self.name})>"


class CommissionRateWindow(Base):
    """기간(연/월 윈도우) 단위 수수료율 정의. end_year/end_month NULL이면 무기한."""
    __tablename__ = "commission_rate_windows"

    id = Column(Integer, primary_key=True, index=True)
    commission_type_id = Column(Integer, ForeignKey("commission_types.commission_type_id"), nullable=False, index=True)
    # 시작 연/월
    start_year = Column(Integer, nullable=False)
    start_month = Column(Integer, nullable=False)  # 1..12
    # 종료 연/월 (NULL이면 무기한)
    end_year = Column(Integer, nullable=True)
    end_month = Column(Integer, nullable=True)
    rate_percent = Column(Numeric(5, 2), nullable=False)  # % 값(0~100). 소수 허용
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=True, index=True)
    # 금액 티어 (원화 기준): min_amount 이상, max_amount 이하(NULL이면 상한 없음)
    min_amount = Column(Integer, nullable=False, default=0)
    max_amount = Column(Integer, nullable=True)
    priority = Column(Integer, nullable=False, default=0)  # 겹칠 경우 우선순위 높을수록 먼저 선택
    is_active = Column(Boolean, default=True)
    # 동적 조건 (지사 수수료율 결정용)
    min_teachers = Column(Integer, nullable=True)  # 최소 소속 원장 수 (NULL이면 조건 없음)
    description = Column(String(255), nullable=True)  # 조건 설명
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships for admin forms and formatting
    commission_type = relationship("CommissionType")
    company = relationship("Company")

# Makeshop Product Extended & Related (Batch 1)
# =============================================================

## Note: Unused product-related tables have been removed in migration 035
## The following tables were deleted:
## - brands, product_brands (brand management not used)
## - product_option_groups, product_option_values (options feature not implemented)
## - product_stock_option_values (part of options/stock system)
## - product_stock (advanced inventory not used, quantity field in products sufficient)
## - product_discount (discount feature not implemented)
## - product_delivery (replaced by Order.shipping_address)
## - product_color (color feature not implemented)
## - product_coupon_exceptions (coupon system not implemented)
## 
## Additional unused tables deleted in migration 036:
## - product_packages, product_package_items (bundle feature not implemented)
## - product_add_compositions (add composition feature not implemented)
## - product_regular_delivery (regular delivery feature not implemented)
## - product_info_notices, product_info_notice_details (product info notices not used)


class Settlement(Base):
    """정산 데이터: 일별, 월별, 연간 정산 내역 관리"""
    __tablename__ = "settlements"

    settlement_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False, index=True)
    statement_id = Column(Integer, ForeignKey("statements.statement_id"), nullable=True, index=True)  # 정산서 참조
    
    # 정산 기간
    settlement_type = Column(String(20), nullable=False, index=True)  # 'daily', 'mtd', 'monthly', 'yearly'
    settlement_date = Column(DateTime(timezone=True), nullable=False, index=True)  # 일별: 해당 일, 월별: 월 첫날, 연간: 년 첫날
    
    # 정산 금액
    total_commission = Column(Integer, default=0)  # 총 수수료
    deducted_tax = Column(Integer, default=0)  # 소득세 공제액
    deducted_local_tax = Column(Integer, default=0)  # 지방세 공제액
    net_settlement_amount = Column(Integer, default=0)  # 공제 후 실지급액
    
    # 정산 세부 정보
    commission_details = Column(Text, nullable=True)  # JSON: [{commission_type_id, amount, rate}, ...]
    is_paid = Column(Boolean, default=False)  # 지급 완료 여부
    paid_date = Column(DateTime(timezone=True), nullable=True)  # 지급 날짜
    
    # 정산서 관련 필드
    statement_number = Column(String(50), nullable=True, unique=True, index=True)  # 정산서 번호 (예: ST-202501-A001-001)
    statement_status = Column(String(20), default='DRAFT', index=True)  # DRAFT, ISSUED, CONFIRMED, PAID
    statement_issued_at = Column(DateTime(timezone=True), nullable=True)  # 정산서 발행 시각
    statement_confirmed_at = Column(DateTime(timezone=True), nullable=True)  # 정산서 확인 시각
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 관계
    user = relationship("User")
    company = relationship("Company")
    statement = relationship("Statement", back_populates="settlements")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "company_id",
            "settlement_type",
            "settlement_date",
            name="uq_settlements_user_company_type_date",
        ),
    )
    
    def __repr__(self):
        return f"<Settlement(settlement_id={self.settlement_id}, user_id={self.user_id}, settlement_type={self.settlement_type}, settlement_date={self.settlement_date})>"


class SettlementCompanyMonthlyAggregate(Base):
    """월별 회사 단위 정산 집계 (role_id = 3인 사용자만 포함)"""
    __tablename__ = "settlement_company_monthly_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)

    total_orders = Column(Integer, default=0)
    total_items = Column(Integer, default=0)
    total_amount = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    company = relationship("Company")

    def __repr__(self):
        return (
            f"<SettlementCompanyMonthlyAggregate(company_id={self.company_id}, period={self.year}-{self.month:02d}, total_amount={self.total_amount})>"
        )


class Statement(Base):
    """정산서 문서 - 월별 사용자별 정산 요약"""
    __tablename__ = "statements"
    
    statement_id = Column(Integer, primary_key=True, index=True)
    statement_number = Column(String(50), unique=True, nullable=False, index=True)  # 정산서 번호
    
    # 사용자 및 회사 정보
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False, index=True)
    
    # 정산 기간
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)
    
    # 정산 금액 요약
    total_commission = Column(Integer, default=0)  # 총 수수료
    deducted_tax = Column(Integer, default=0)  # 소득세
    deducted_local_tax = Column(Integer, default=0)  # 지방세
    net_amount = Column(Integer, default=0)  # 실지급액
    
    # 정산서 확인 여부
    is_confirmed = Column(Boolean, default=False, index=True, nullable=False)  # 사용자 확인 여부
    
    # 타임스탬프
    issued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 관계
    user = relationship("User", back_populates="statements")
    company = relationship("Company")
    settlements = relationship("Settlement", back_populates="statement")
    
    # 복합 유니크 제약: 같은 사용자, 같은 연월에는 하나의 정산서만
    __table_args__ = (
        UniqueConstraint('user_id', 'year', 'month', name='uq_user_statement_period'),
    )
    
    def __repr__(self):
        return f"<Statement(statement_number={self.statement_number}, user_id={self.user_id}, period={self.year}-{self.month:02d}, is_confirmed={self.is_confirmed})>"


class SettlementStatementConfirmation(Base):
    """정산서 확인 기록 (사용자가 정산서를 확인했을 때)"""
    __tablename__ = "settlement_statement_confirmations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)
    confirmed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmation_category = Column(String(10), nullable=True)  # 지급 / 이월
    __table_args__ = (
        UniqueConstraint('user_id', 'year', 'month', name='uq_settlement_confirmation'),
    )

    user = relationship("User")

    def __repr__(self):
        return f"<SettlementStatementConfirmation(user_id={self.user_id}, period={self.year}-{self.month:02d})>"


class MonthlySettlementPaymentStatus(Base):
    """월 정산 요약표 지급 여부 (지사별 수수료 지급일 메모)"""
    __tablename__ = "monthly_settlement_payment_status"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)
    payment_note = Column(String(255), nullable=True, default="")
    remark = Column(String(255), nullable=True, default="")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("users.user_id"), nullable=True)

    company = relationship("Company")
    updated_by_user = relationship("User", foreign_keys=[updated_by])

    __table_args__ = (
        UniqueConstraint('company_id', 'year', 'month', name='uq_monthly_settlement_payment'),
    )

    def __repr__(self):
        return (
            f"<MonthlySettlementPaymentStatus(company_id={self.company_id}, "
            f"period={self.year}-{self.month:02d})>"
        )


class Notice(Base):
    """관리자 공지사항"""
    __tablename__ = "admin_notices"

    notice_id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    author_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)
    visible_from = Column(Date, nullable=False)
    visible_to = Column(Date, nullable=False)
    is_exposed = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author = relationship("User", foreign_keys=[author_user_id])

    def __repr__(self):
        return f"<Notice(notice_id={self.notice_id}, title={self.title!r})>"


class SettlementSkipRecord(Base):
    """정산 스킵 기록: 주문/항목이 정산에서 건너뛰어진 이유를 기록합니다.
    
    skip_reason 값 설명:
    - USER_NOT_FOUND: 메이크샵 member_id를 사용자 테이블에서 찾을 수 없음
    - INVALID_COMPANY_ID: 매핑된 사용자의 company_id가 유효한 회사 목록에 없음
    - INVALID_COMPANY_ID_BASCLE: BASCLE 수수료 계산 중 invalid company_id
    - NO_ORDER_ITEMS: 주문번호에 대한 OrderItem 레코드가 없음
    - NO_COMMISSION_TYPE: 상품 카테고리에 해당하는 수수료 타입을 찾을 수 없음
    - NO_PRODUCT: 상품 UID에 해당하는 Product를 찾을 수 없음
    """
    __tablename__ = "settlement_skip_records"

    skip_id = Column(Integer, primary_key=True, index=True)
    settlement_year = Column(Integer, nullable=False, index=True)
    settlement_month = Column(Integer, nullable=False, index=True)
    
    # 스킵 대상 식별 정보
    ordernum = Column(String(100), nullable=False, index=True)  # 주문번호
    item_id = Column(Integer, nullable=True)  # OrderItem의 id (주문 전체 스킵 시 NULL)
    
    # 사용자/회사 정보
    member_id = Column(String(100), nullable=True, index=True)  # 메이크샵 회원ID
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True, index=True)  # 매핑된 사용자
    company_id = Column(Integer, nullable=True, index=True)  # 조건에 맞지 않은 회사ID
    
    # 스킵 사유
    skip_reason = Column(String(50), nullable=False, index=True)  # INVALID_COMPANY, NO_RATE_WINDOW, CONDITION_MISMATCH, NO_PRODUCT, USER_NOT_FOUND, INVALID_COMPANY_ID
    skip_detail = Column(Text, nullable=True)  # 상세 이유 (예: "Company 999 not in valid IDs", "No commission rate for window id 5")
    
    # 주문 정보 스냅샷
    order_info = Column(JSON, nullable=True)  # {ordernum, member_id, sender, phone, pay_price, deli_price, ...}
    
    # 타임스탬프
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # 관계
    user = relationship("User")
    
    def __repr__(self):
        return (
            f"<SettlementSkipRecord(ordernum={self.ordernum}, reason={self.skip_reason}, period={self.settlement_year}-{self.settlement_month:02d})>"
        )


class MakeshopInstalledApp(Base):
    """MakeShop APP 설치 온보딩 정보 (APP 설치 콜백 결과)."""

    __tablename__ = "makeshop_installed_apps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shop_uid = Column(String(100), nullable=False, unique=True, index=True)
    client_id = Column(String(100), nullable=True, index=True)
    app_name = Column(String(255), nullable=True)
    app_url = Column(String(500), nullable=True)
    action_type = Column(String(50), nullable=True)
    installed_at = Column(Date, nullable=True)
    expired_at = Column(Date, nullable=True)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<MakeshopInstalledApp(shop_uid={self.shop_uid}, app_name={self.app_name})>"

