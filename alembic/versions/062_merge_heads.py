"""merge heads and fix migration history

Revision ID: 062
Revises: 061
Create Date: 2025-01-15

"""

# revision identifiers, used by Alembic.
revision = '062'
down_revision = '061'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge the two branches
    pass


def downgrade() -> None:
    pass
