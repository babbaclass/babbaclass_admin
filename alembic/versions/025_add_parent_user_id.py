"""add parent_user_id to users table for hierarchical organization (manager-teacher relationship)

Revision ID: 025_add_parent_user_id
Revises: 024_add_login_id_to_user
Create Date: 2025-11-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '025_add_parent_user_id'
down_revision = '024_add_login_id_to_user'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add parent_user_id column to users table
    # This creates a self-referencing foreign key for hierarchical organization
    # Allows teachers (원장) to have a manager (지사장) as parent_user_id
    op.add_column('users', sa.Column('parent_user_id', sa.Integer(), nullable=True))
    
    # Create index on parent_user_id for faster lookups
    op.create_index('ix_users_parent_user_id', 'users', ['parent_user_id'])
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_users_parent_user_id',
        'users', 'users',
        ['parent_user_id'], ['user_id']
    )


def downgrade() -> None:
    # Drop the foreign key constraint
    op.drop_constraint('fk_users_parent_user_id', 'users', type_='foreignkey')
    
    # Drop the index
    op.drop_index('ix_users_parent_user_id', table_name='users')
    
    # Drop the column
    op.drop_column('users', 'parent_user_id')
