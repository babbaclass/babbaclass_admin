"""Remove birth_date and sub_contact columns from users table

Revision ID: 039
Revises: 038
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '039'
down_revision = '038'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove birth_date and sub_contact columns"""
    # Drop birth_date column
    op.drop_column('users', 'birth_date')
    
    # Drop sub_contact column
    op.drop_column('users', 'sub_contact')


def downgrade() -> None:
    """Restore birth_date and sub_contact columns if needed"""
    # Add sub_contact column back
    op.add_column('users', sa.Column('sub_contact', sa.String(255), nullable=True))
    
    # Add birth_date column back
    op.add_column('users', sa.Column('birth_date', sa.String(20), nullable=False, server_default=''))
