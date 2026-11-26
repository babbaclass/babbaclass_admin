"""
Remove reports_to_user_id from users (safe, idempotent)

Revision ID: 008_remove_reports_to_user_id
Revises: 007_auto_increment_pk
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_remove_reports_to_user_id'
down_revision = '007_auto_increment_pk'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Check if column exists
    col_exists = conn.execute(
        sa.text(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'reports_to_user_id'
            """
        )
    ).scalar()

    if not col_exists:
        return

    # Drop foreign key constraint referencing reports_to_user_id if any
    fk_name = conn.execute(
        sa.text(
            """
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'reports_to_user_id'
              AND REFERENCED_TABLE_NAME IS NOT NULL
            LIMIT 1
            """
        )
    ).scalar()

    if fk_name:
        conn.execute(sa.text("ALTER TABLE users DROP FOREIGN KEY `" + fk_name + "`"))

    # Drop any index on the column (MySQL auto-creates index for FK)
    idx_name = conn.execute(
        sa.text(
            """
            SELECT INDEX_NAME
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'reports_to_user_id'
            LIMIT 1
            """
        )
    ).scalar()

    if idx_name and idx_name != 'PRIMARY':
        conn.execute(sa.text("ALTER TABLE users DROP INDEX `" + idx_name + "`"))

    # Finally drop the column
    conn.execute(sa.text("ALTER TABLE users DROP COLUMN `reports_to_user_id`"))


def downgrade() -> None:
    # Optional: re-create the column (without constraints)
    conn = op.get_bind()

    col_exists = conn.execute(
        sa.text(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'users'
              AND COLUMN_NAME = 'reports_to_user_id'
            """
        )
    ).scalar()

    if not col_exists:
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN `reports_to_user_id` INT NULL"))
