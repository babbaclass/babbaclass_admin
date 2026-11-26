"""Remove address column from companies table

Revision ID: 041
Revises: 040
Create Date: 2025-11-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '041'
down_revision = '040'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the address column from companies table
    op.drop_column('companies', 'address')


def downgrade() -> None:
    # Add the address column back to companies table
    op.add_column('companies', sa.Column('address', sa.String(500), nullable=True))
