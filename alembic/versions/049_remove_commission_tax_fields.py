"""remove commission and tax fields from settlement_company_monthly_aggregates

Revision ID: 049_remove_commission_tax_fields
Revises: 048
Create Date: 2025-11-26 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '049_remove_commission_tax_fields'
down_revision: Union[str, None] = '048'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # settlement_company_monthly_aggregates 테이블에서 수수료 및 세금 관련 컬럼 제거
    op.drop_column('settlement_company_monthly_aggregates', 'total_commission')
    op.drop_column('settlement_company_monthly_aggregates', 'deducted_tax')
    op.drop_column('settlement_company_monthly_aggregates', 'deducted_local_tax')
    op.drop_column('settlement_company_monthly_aggregates', 'net_settlement_amount')


def downgrade() -> None:
    # 컬럼 복원
    op.add_column('settlement_company_monthly_aggregates', 
                  sa.Column('total_commission', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('settlement_company_monthly_aggregates', 
                  sa.Column('deducted_tax', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('settlement_company_monthly_aggregates', 
                  sa.Column('deducted_local_tax', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('settlement_company_monthly_aggregates', 
                  sa.Column('net_settlement_amount', sa.Integer(), nullable=True, server_default='0'))
