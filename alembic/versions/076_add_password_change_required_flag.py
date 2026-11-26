"""Add password change flag for branch heads

Revision ID: 076
Revises: 075
Create Date: 2025-12-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '076'
down_revision = '075'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column(
            'password_change_required',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('FALSE'),
        ),
    )

    # Force branch heads (role_id=2) to reset their passwords once
    op.execute("UPDATE users SET password_change_required = TRUE WHERE role_id = 2")


def downgrade() -> None:
    op.drop_column('users', 'password_change_required')
