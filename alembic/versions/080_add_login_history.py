"""Add login_history table for tracking user logins

Revision ID: 080
Revises: 079
Create Date: 2026-01-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '080'
down_revision = '079'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'login_history',
        sa.Column('login_history_id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('login_id', sa.String(length=255), nullable=True),
        sa.Column('user_name', sa.String(length=255), nullable=True),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('login_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    )
    op.create_index('ix_login_history_user_id', 'login_history', ['user_id'])
    op.create_index('ix_login_history_role_id', 'login_history', ['role_id'])
    op.create_index('ix_login_history_login_at', 'login_history', ['login_at'])


def downgrade() -> None:
    op.drop_index('ix_login_history_login_at', table_name='login_history')
    op.drop_index('ix_login_history_role_id', table_name='login_history')
    op.drop_index('ix_login_history_user_id', table_name='login_history')
    op.drop_table('login_history')
