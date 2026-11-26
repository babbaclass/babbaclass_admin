"""Add remark column to monthly_settlement_payment_status

Revision ID: 089
Revises: 088
Create Date: 2026-05-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '089'
down_revision = '088'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'monthly_settlement_payment_status' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('monthly_settlement_payment_status')}
    if 'remark' not in columns:
        op.add_column(
            'monthly_settlement_payment_status',
            sa.Column('remark', sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'monthly_settlement_payment_status' not in inspector.get_table_names():
        return
    columns = {col['name'] for col in inspector.get_columns('monthly_settlement_payment_status')}
    if 'remark' in columns:
        op.drop_column('monthly_settlement_payment_status', 'remark')
