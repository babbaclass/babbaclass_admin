"""Add member_id field to orders table

Revision ID: 037
Revises: 036
Create Date: 2025-11-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '037'
down_revision = '036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add member_id column to orders table
    op.add_column('orders', sa.Column('member_id', sa.String(100), nullable=True))
    
    # Step 2: Create index on member_id for query performance
    op.create_index('ix_orders_member_id', 'orders', ['member_id'], unique=False)


def downgrade() -> None:
    # Step 1: Drop index on member_id
    op.drop_index('ix_orders_member_id', table_name='orders')
    
    # Step 2: Drop member_id column
    op.drop_column('orders', 'member_id')
