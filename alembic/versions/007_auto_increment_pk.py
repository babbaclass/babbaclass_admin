"""Ensure AUTO_INCREMENT on primary keys for companies, roles, users

Revision ID: 007_auto_increment_pk
Revises: 006_backfill_users_data
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = '007_auto_increment_pk'
down_revision = '006_backfill_users_data'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn: Connection = op.get_bind()

    # MySQL-specific ALTERs to ensure AUTO_INCREMENT on integer PKs
    statements = [
        "ALTER TABLE companies MODIFY company_id INT NOT NULL AUTO_INCREMENT",
        "ALTER TABLE roles MODIFY role_id INT NOT NULL AUTO_INCREMENT",
        "ALTER TABLE users MODIFY user_id INT NOT NULL AUTO_INCREMENT",
    ]

    for sql in statements:
        try:
            conn.execute(sa.text(sql))
        except Exception:
            # Ignore if already AUTO_INCREMENT or if dialect not supporting this exact syntax
            pass


def downgrade() -> None:
    # No-op; retaining AUTO_INCREMENT is safe
    pass
