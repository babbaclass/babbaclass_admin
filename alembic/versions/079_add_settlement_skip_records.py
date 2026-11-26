"""Add settlement skip records table

Revision ID: 079
Revises: 078
Create Date: 2026-02-15 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '079'
down_revision = '078'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'settlement_skip_records',
        sa.Column('skip_id', sa.Integer(), primary_key=True),
        sa.Column('settlement_year', sa.Integer(), nullable=False),
        sa.Column('settlement_month', sa.Integer(), nullable=False),
        sa.Column('ordernum', sa.String(length=100), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=True),
        sa.Column('member_id', sa.String(length=100), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=True),
        sa.Column('skip_reason', sa.String(length=50), nullable=False),
        sa.Column('skip_detail', sa.Text(), nullable=True),
        sa.Column('order_info', sa.JSON(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    
    # 인덱스 생성
    op.create_index(
        'ix_settlement_skip_records_period',
        'settlement_skip_records',
        ['settlement_year', 'settlement_month'],
        unique=False
    )
    op.create_index(
        'ix_settlement_skip_records_ordernum',
        'settlement_skip_records',
        ['ordernum'],
        unique=False
    )
    op.create_index(
        'ix_settlement_skip_records_skip_reason',
        'settlement_skip_records',
        ['skip_reason'],
        unique=False
    )
    op.create_index(
        'ix_settlement_skip_records_user_id',
        'settlement_skip_records',
        ['user_id'],
        unique=False
    )
    op.create_index(
        'ix_settlement_skip_records_company_id',
        'settlement_skip_records',
        ['company_id'],
        unique=False
    )
    op.create_index(
        'ix_settlement_skip_records_member_id',
        'settlement_skip_records',
        ['member_id'],
        unique=False
    )
    
    # 외래키 추가
    op.create_foreign_key(
        'fk_settlement_skip_records_user_id',
        'settlement_skip_records', 'users',
        ['user_id'], ['user_id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_settlement_skip_records_user_id', 'settlement_skip_records', type_='foreignkey')
    op.drop_index('ix_settlement_skip_records_period', table_name='settlement_skip_records')
    op.drop_index('ix_settlement_skip_records_ordernum', table_name='settlement_skip_records')
    op.drop_index('ix_settlement_skip_records_skip_reason', table_name='settlement_skip_records')
    op.drop_index('ix_settlement_skip_records_user_id', table_name='settlement_skip_records')
    op.drop_index('ix_settlement_skip_records_company_id', table_name='settlement_skip_records')
    op.drop_index('ix_settlement_skip_records_member_id', table_name='settlement_skip_records')
    op.drop_table('settlement_skip_records')
