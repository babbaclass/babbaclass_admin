"""Add contracted_at field to users table

Revision ID: 040
Revises: 039
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '040'
down_revision = '039'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add contracted_at column to users table"""
    # Add contracted_at column (YYYY-MM-DD format string, nullable)
    op.add_column('users', sa.Column('contracted_at', sa.String(10), nullable=True))
    
    # Create index on contracted_at for faster lookups
    op.create_index('ix_users_contracted_at', 'users', ['contracted_at'])


def downgrade() -> None:
    """Remove contracted_at column if needed"""
    # Drop the index
    op.drop_index('ix_users_contracted_at', table_name='users')
    
    # Drop the column
    op.drop_column('users', 'contracted_at')
