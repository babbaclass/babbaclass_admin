"""remove member_id column and member relationship from users table

Revision ID: 026_remove_member_id_from_users
Revises: 025_add_parent_user_id
Create Date: 2025-01-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '026_remove_member_id_from_users'
down_revision = '025_add_parent_user_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the foreign key constraint first
    op.drop_constraint('fk_users_member_id_members', 'users', type_='foreignkey')
    
    # Drop the index on member_id
    op.drop_index('ix_users_member_id', table_name='users')
    
    # Drop the column
    op.drop_column('users', 'member_id')


def downgrade() -> None:
    # Add the column back
    op.add_column('users', sa.Column('member_id', sa.Integer(), nullable=True))
    
    # Create index on member_id
    op.create_index('ix_users_member_id', 'users', ['member_id'])
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_users_member_id_members',
        'users', 'members',
        ['member_id'], ['id']
    )
