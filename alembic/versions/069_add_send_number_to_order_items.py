"""Add send_number field to OrderItem table

Revision ID: 069
Revises: 068
Create Date: 2025-12-12

Adds send_number column (tracking number) to the order_items table.
This field will store the shipping tracking number for each order item,
matching the send_number field in the orders table.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '069'
down_revision = '068'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add send_number column to order_items table
    op.add_column('order_items', sa.Column('send_number', sa.String(255), nullable=True))


def downgrade() -> None:
    # Remove send_number column if needed (for rollback)
    op.drop_column('order_items', 'send_number')
