"""add password_hash and is_admin fields to User table

Revision ID: 001
Revises: 
Create Date: 2025-11-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add password_hash column to users table
    op.add_column('users', sa.Column('password_hash', sa.String(255), nullable=True))
    
    # Add is_admin column to users table
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    # Remove is_admin column
    op.drop_column('users', 'is_admin')
    
    # Remove password_hash column
    op.drop_column('users', 'password_hash')
