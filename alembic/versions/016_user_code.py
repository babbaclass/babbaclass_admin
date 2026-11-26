"""Add code column to users table

Revision ID: 016_user_code
Revises: 015_contact_cleanup_and_user_contacts
Create Date: 2025-11-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# Revision identifiers, used by Alembic.
revision = '016_user_code'
down_revision = '015_contact_cleanup'
branch_labels = None
depends_on = None

def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    for col in inspector.get_columns(table_name):
        if col.get('name') == column_name:
            return True
    return False

def upgrade():
    # Add 'code' column to users if it doesn't exist
    if not _has_column('users', 'code'):
        op.add_column('users', sa.Column('code', sa.Integer(), nullable=True))
        # Optional: index for faster lookups (skip if already exists)
        try:
            op.create_index('ix_users_code', 'users', ['code'])
        except Exception:
            pass


def downgrade():
    # Drop column if exists (MySQL safe pattern)
    if _has_column('users', 'code'):
        try:
            op.drop_index('ix_users_code', table_name='users')
        except Exception:
            pass
        op.drop_column('users', 'code')
