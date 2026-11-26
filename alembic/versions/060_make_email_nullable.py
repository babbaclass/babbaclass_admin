"""make email nullable

Revision ID: 060_make_email_nullable
Revises: 059
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '060_make_email_nullable'
down_revision = '059'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make email nullable
    op.alter_column('users', 'email',
                    existing_type=sa.String(255),
                    nullable=True,
                    existing_nullable=False)


def downgrade() -> None:
    # Revert email back to NOT NULL
    # Note: This may fail if there are NULL values in the database
    op.alter_column('users', 'email',
                    existing_type=sa.String(255),
                    nullable=False,
                    existing_nullable=True)
