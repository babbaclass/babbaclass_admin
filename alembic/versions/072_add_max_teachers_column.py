"""add max_teachers column

Revision ID: 072
Revises: 071
Create Date: 2025-12-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '072'
down_revision = '071'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add max_teachers column to commission_rate_windows table."""
    op.add_column('commission_rate_windows', sa.Column('max_teachers', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove max_teachers column from commission_rate_windows table."""
    op.drop_column('commission_rate_windows', 'max_teachers')
