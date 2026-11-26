"""Contact cleanup and ensure user contact columns

Revision ID: 015_contact_cleanup
Revises: 014_seed_branches
Create Date: 2025-11-09

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '015_contact_cleanup'
down_revision = '014_seed_branches'
branch_labels = None
depends_on = None


def _has_table(conn, table_name: str) -> bool:
    inspector = sa.inspect(conn)
    return table_name in set(inspector.get_table_names())


def _has_column(conn, table: str, column: str) -> bool:
    inspector = sa.inspect(conn)
    if table not in set(inspector.get_table_names()):
        return False
    cols = {c['name'] for c in inspector.get_columns(table)}
    return column in cols


def upgrade() -> None:
    conn = op.get_bind()

    # 1) Ensure users.main_contact and users.sub_contact exist
    if _has_table(conn, 'users'):
        if not _has_column(conn, 'users', 'main_contact'):
            op.add_column('users', sa.Column('main_contact', sa.String(length=255), nullable=True))
        if not _has_column(conn, 'users', 'sub_contact'):
            op.add_column('users', sa.Column('sub_contact', sa.String(length=255), nullable=True))

    # 2) Drop legacy contacts table if present
    if _has_table(conn, 'contacts'):
        op.drop_table('contacts')

    # 3) Drop legacy companies.contacts column if present
    if _has_table(conn, 'companies') and _has_column(conn, 'companies', 'contacts'):
        op.drop_column('companies', 'contacts')


def downgrade() -> None:
    conn = op.get_bind()

    # Best-effort rollback: remove added user contact columns if they exist
    if _has_table(conn, 'users') and _has_column(conn, 'users', 'sub_contact'):
        op.drop_column('users', 'sub_contact')
    if _has_table(conn, 'users') and _has_column(conn, 'users', 'main_contact'):
        op.drop_column('users', 'main_contact')

    # NOTE: We intentionally do not recreate the legacy contacts table or
    # companies.contacts column due to schema deprecation and data discard policy.
