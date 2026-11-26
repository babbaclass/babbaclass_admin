"""add max_teachers to commission_rate_windows

Revision ID: 073
Revises: 072
Create Date: 2025-12-17 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '073'
down_revision = '072'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add max_teachers column to commission_rate_windows table if not exists."""
    # Check if column exists before adding
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('commission_rate_windows')]
    
    if 'max_teachers' not in columns:
        op.add_column('commission_rate_windows', sa.Column('max_teachers', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove max_teachers column from commission_rate_windows table."""
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('commission_rate_windows')]
    
    if 'max_teachers' in columns:
        op.drop_column('commission_rate_windows', 'max_teachers')
