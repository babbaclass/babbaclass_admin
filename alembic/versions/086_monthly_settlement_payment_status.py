"""Add monthly_settlement_payment_status table

Revision ID: 086
Revises: 085
Create Date: 2026-05-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '086'
down_revision = '085'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if 'monthly_settlement_payment_status' in inspector.get_table_names():
        return
    op.create_table(
        'monthly_settlement_payment_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('payment_note', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.company_id']),
        sa.ForeignKeyConstraint(['updated_by'], ['users.user_id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'year', 'month', name='uq_monthly_settlement_payment'),
        mysql_engine='InnoDB',
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_general_ci',
    )
    op.create_index(
        'ix_monthly_settlement_payment_status_company_id',
        'monthly_settlement_payment_status',
        ['company_id'],
        unique=False,
    )
    op.create_index(
        'ix_monthly_settlement_payment_status_year',
        'monthly_settlement_payment_status',
        ['year'],
        unique=False,
    )
    op.create_index(
        'ix_monthly_settlement_payment_status_month',
        'monthly_settlement_payment_status',
        ['month'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_monthly_settlement_payment_status_month', table_name='monthly_settlement_payment_status')
    op.drop_index('ix_monthly_settlement_payment_status_year', table_name='monthly_settlement_payment_status')
    op.drop_index('ix_monthly_settlement_payment_status_company_id', table_name='monthly_settlement_payment_status')
    op.drop_table('monthly_settlement_payment_status')
