"""Add dynamic conditions to commission_rate_windows

지사 수수료율 동적 조건 추가:
- min_teachers: 최소 소속 원장 수
- min_monthly_sales: 최소 월 매출액
- role_id: 적용 대상 역할 (NULL이면 모든 역할)

조건 예시:
- 기본 25%: min_teachers=NULL, min_monthly_sales=NULL
- 27%: min_teachers=10, min_monthly_sales=1000000
- 30%: min_teachers=20, min_monthly_sales=3000000

Revision ID: 065
Revises: 064_drop_mk_product_tables
Create Date: 2025-12-02
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '065_dynamic_conditions'
down_revision = '064'
branch_labels = None
depends_on = None


def upgrade():
    # commission_rate_windows 테이블에 동적 조건 컬럼 추가
    op.add_column('commission_rate_windows', 
        sa.Column('min_teachers', sa.Integer(), nullable=True, comment='최소 소속 원장 수 (NULL이면 조건 없음)')
    )
    op.add_column('commission_rate_windows', 
        sa.Column('min_monthly_sales', sa.Integer(), nullable=True, comment='최소 월 매출액 (NULL이면 조건 없음)')
    )
    op.add_column('commission_rate_windows', 
        sa.Column('role_id', sa.Integer(), nullable=True, comment='적용 대상 역할 ID (NULL이면 모든 역할)')
    )
    op.add_column('commission_rate_windows', 
        sa.Column('description', sa.String(255), nullable=True, comment='조건 설명')
    )
    
    # role_id에 FK 추가
    op.create_foreign_key(
        'fk_commission_rate_windows_role_id',
        'commission_rate_windows', 'roles',
        ['role_id'], ['role_id']
    )


def downgrade():
    # FK 삭제
    op.drop_constraint('fk_commission_rate_windows_role_id', 'commission_rate_windows', type_='foreignkey')
    
    # 컬럼 삭제
    op.drop_column('commission_rate_windows', 'description')
    op.drop_column('commission_rate_windows', 'role_id')
    op.drop_column('commission_rate_windows', 'min_monthly_sales')
    op.drop_column('commission_rate_windows', 'min_teachers')
