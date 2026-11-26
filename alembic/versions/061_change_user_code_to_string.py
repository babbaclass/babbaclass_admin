"""change user code from integer to string

Revision ID: 061
Revises: 060_make_email_nullable
Create Date: 2025-01-15

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '061'
down_revision = '060_make_email_nullable'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing index on code
    try:
        op.drop_index('ix_users_code', table_name='users')
    except Exception:
        pass
    
    # Modify code column from Integer to String(50)
    # First, convert existing data by casting to string
    op.execute("ALTER TABLE users MODIFY COLUMN code VARCHAR(50) NULL")
    
    # Recreate index
    op.create_index(op.f('ix_users_code'), 'users', ['code'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_users_code', table_name='users')
    
    # Revert to Integer (will fail if there are non-numeric values)
    op.execute("ALTER TABLE users MODIFY COLUMN code INT NULL")
    
    # Recreate index
    op.create_index(op.f('ix_users_code'), 'users', ['code'], unique=False)
