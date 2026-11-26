"""
Remove legacy users.username column (idempotent)

Revision ID: 009_remove_username_column
Revises: 008_remove_reports_to_user_id
Create Date: 2025-11-06
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '009_remove_username_column'
down_revision = '008_remove_reports_to_user_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if column exists
    col_exists = conn.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'username'
            """
        )
    ).scalar()

    if not col_exists:
        return

    # Drop any indexes referencing username
    indexes = conn.execute(
        sa.text(
            """
            SELECT DISTINCT INDEX_NAME
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'username'
            """
        )
    ).fetchall()

    for (idx_name,) in indexes:
        if idx_name and idx_name != 'PRIMARY':
            conn.execute(sa.text(f"ALTER TABLE users DROP INDEX `{idx_name}`"))

    # Drop the column
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN `username`"))


def downgrade() -> None:
    # Recreate the column as nullable for downgrade
    conn = op.get_bind()
    col_exists = conn.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'username'
            """
        )
    ).scalar()

    if not col_exists:
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN `username` VARCHAR(255) NULL"))
