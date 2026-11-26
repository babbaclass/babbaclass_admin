"""add cate lists to commission types

Revision ID: 046
Revises: 045
Create Date: 2025-11-25

CommissionType 테이블에 cate1_code_list, cate1_name_list JSON 배열 컬럼 추가
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '046'
down_revision = '045'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    CommissionType 테이블에 JSON 배열 컬럼 추가:
    - cate1_code_list: 카테고리 코드 목록 (예: ['001', '007'])
    - cate1_name_list: 카테고리 이름 목록 (예: ['[가입] 혼합형(수학+문해력)', '[가입] 수학형(기본)'])
    """
    # commission_types 테이블에 JSON 컬럼 추가
    op.add_column('commission_types', 
        sa.Column('cate1_code_list', sa.JSON(), nullable=True, comment='카테고리 코드 목록'))
    op.add_column('commission_types', 
        sa.Column('cate1_name_list', sa.JSON(), nullable=True, comment='카테고리 이름 목록'))


def downgrade() -> None:
    """
    추가된 컬럼 제거
    """
    op.drop_column('commission_types', 'cate1_name_list')
    op.drop_column('commission_types', 'cate1_code_list')
