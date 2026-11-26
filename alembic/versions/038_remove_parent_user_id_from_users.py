"""remove parent_user_id column from users table (hierarchical organization not needed)

Revision ID: 038
Revises: 037
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '038'
down_revision = '037'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove parent_user_id column and related constraints"""
    # Drop the foreign key constraint first
    op.drop_constraint('fk_users_parent_user_id', 'users', type_='foreignkey')
    
    # Drop the index on parent_user_id
    op.drop_index('ix_users_parent_user_id', table_name='users')
    
    # Drop the column
    op.drop_column('users', 'parent_user_id')


def downgrade() -> None:
    """Restore parent_user_id column if needed"""
    # Add the column back
    op.add_column('users', sa.Column('parent_user_id', sa.Integer(), nullable=True))
    
    # Create index on parent_user_id
    op.create_index('ix_users_parent_user_id', 'users', ['parent_user_id'])
    
    # Create foreign key constraint (self-referencing)
    op.create_foreign_key(
        'fk_users_parent_user_id',
        'users', 'users',
        ['parent_user_id'], ['user_id']
    )
