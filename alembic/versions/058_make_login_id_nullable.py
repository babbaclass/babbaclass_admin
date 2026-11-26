"""make login_id nullable

Revision ID: 058_make_login_id_nullable
Revises: 057_add_company_code
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '058_make_login_id_nullable'
down_revision = '057_add_company_code'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make login_id nullable to allow unregistered users (is_register=false)
    op.alter_column('users', 'login_id',
                    existing_type=sa.String(255),
                    nullable=True,
                    existing_nullable=False)


def downgrade() -> None:
    # Revert login_id back to NOT NULL
    # Note: This may fail if there are NULL values in the database
    op.alter_column('users', 'login_id',
                    existing_type=sa.String(255),
                    nullable=False,
                    existing_nullable=True)
