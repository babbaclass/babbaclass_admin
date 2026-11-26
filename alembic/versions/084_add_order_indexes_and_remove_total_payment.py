"""Add indexes for order query performance and remove unused total_payment_last_year column

Revision ID: 084
Revises: 083
Create Date: 2026-02-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '084'
down_revision = '083'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Order 테이블 인덱스 추가 (성능 최적화)
    # order_date 필터링 + member_id 조인을 위한 복합 인덱스
    op.create_index(
        'idx_order_date_member',
        'orders',
        ['order_date', 'member_id'],
        unique=False
    )
    
    # pay_price 집계 쿼리 최적화
    op.create_index(
        'idx_pay_price_date',
        'orders',
        ['pay_price', 'order_date'],
        unique=False
    )
    
    # 2. User 테이블 인덱스 추가
    # login_id로 조인 시 사용 (이미 있을 수 있음)
    try:
        op.create_index(
            'idx_user_login_id',
            'users',
            ['login_id'],
            unique=True
        )
    except Exception:
        # 이미 존재할 수 있으므로 무시
        pass
    
    # 3. ContractEnd 테이블에서 total_payment_last_year 컬럼 제거
    # (더 이상 사용되지 않으며, Order 테이블에서 동적으로 계산)
    op.drop_column('contract_end', 'total_payment_last_year')


def downgrade() -> None:
    # 컬럼 복구
    op.add_column(
        'contract_end',
        sa.Column('total_payment_last_year', sa.Integer(), nullable=True, server_default='0')
    )
    
    # 인덱스 제거
    op.drop_index('idx_user_login_id', table_name='users')
    op.drop_index('idx_pay_price_date', table_name='orders')
    op.drop_index('idx_order_date_member', table_name='orders')
