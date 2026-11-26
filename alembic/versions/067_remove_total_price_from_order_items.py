"""Remove total_price column from order_items table

Revision ID: 067
Revises: 066
Create Date: 2025-12-02

The total_price column was incorrectly calculated (sell_price * basket_stock).
The sell_price field already contains the actual payment amount from Makeshop API,
so total_price is redundant and causes data inconsistency.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '067'
down_revision = '066_seed_dynamic_rates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the total_price column from order_items table if it exists
    # Using raw SQL to safely handle the case where column might not exist
    try:
        op.execute('ALTER TABLE order_items DROP COLUMN total_price')
    except Exception:
        # Column might already be dropped or doesn't exist
        pass


def downgrade() -> None:
    # Re-add total_price column if needed (for rollback)
    op.add_column('order_items', sa.Column('total_price', sa.Integer(), nullable=False, server_default='0'))
