"""add login_id to user table, make birth_date required, add bank and address fields

Revision ID: 024_add_login_id_to_user
Revises: 023_add_settlement
Create Date: 2025-11-13

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '024_add_login_id_to_user'
down_revision = '023_add_settlement'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add login_id column to users table
    op.add_column('users', sa.Column('login_id', sa.String(255), nullable=True))
    
    # Create unique index on login_id
    op.create_unique_constraint('uq_users_login_id', 'users', ['login_id'])
    op.create_index('ix_users_login_id', 'users', ['login_id'])
    
    # Migrate existing data: populate login_id from email (removing domain)
    # This is a data migration - set login_id based on email prefix
    op.execute("""
        UPDATE users 
        SET login_id = CONCAT('user_', user_id) 
        WHERE login_id IS NULL
    """)
    
    # Make login_id NOT NULL after populating data
    op.alter_column('users', 'login_id',
               existing_type=sa.String(255),
               nullable=False)
    
    # Make birth_date required
    op.execute("""
        UPDATE users 
        SET birth_date = '19800101' 
        WHERE birth_date IS NULL OR birth_date = ''
    """)
    
    op.alter_column('users', 'birth_date',
               existing_type=sa.String(20),
               nullable=False)
    
    # Add optional bank and address fields
    op.add_column('users', sa.Column('bank_name', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('bank_account', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('address', sa.String(255), nullable=True))


def downgrade() -> None:
    # Drop the new columns
    op.drop_column('users', 'address')
    op.drop_column('users', 'bank_account')
    op.drop_column('users', 'bank_name')
    
    # Revert birth_date to nullable
    op.alter_column('users', 'birth_date',
               existing_type=sa.String(20),
               nullable=True)
    
    # Drop the login_id column
    op.drop_constraint('uq_users_login_id', 'users', type_='unique')
    op.drop_index('ix_users_login_id', table_name='users')
    op.drop_column('users', 'login_id')
