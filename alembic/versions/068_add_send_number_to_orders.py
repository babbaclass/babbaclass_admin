"""Add send_number field to Order table

Revision ID: 068
Revises: 067
Create Date: 2025-12-11

Adds send_number column (tracking number) to the orders table.
This field will store the shipping tracking number for orders.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '068'
down_revision = '067'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add send_number column to orders table
    op.add_column('orders', sa.Column('send_number', sa.String(255), nullable=True))


def downgrade() -> None:
    # Remove send_number column if needed (for rollback)
    op.drop_column('orders', 'send_number')
