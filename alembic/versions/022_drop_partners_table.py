"""Drop partners/partner table if exists

Revision ID: 022_drop_partners_table
Revises: 021_unprefix_makeshop_tables
Create Date: 2025-11-10
"""
from alembic import op
import sqlalchemy as sa

revision = '022_drop_partners_table'
down_revision = '021_unprefix_makeshop_tables'
branch_labels = None
depends_on = None


def _table_exists(bind, name: str) -> bool:
    try:
        inspector = sa.inspect(bind)
        return name in inspector.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    for tbl in ('partners', 'partner'):
        if _table_exists(bind, tbl):
            try:
                op.drop_table(tbl)
            except Exception:
                # Fallback: attempt raw drop
                try:
                    bind.execute(sa.text(f"DROP TABLE IF EXISTS {tbl}"))
                except Exception:
                    pass


def downgrade() -> None:
    # Best-effort: recreate minimal partners table (id, name)
    bind = op.get_bind()
    if not _table_exists(bind, 'partners'):
        try:
            op.create_table(
                'partners',
                sa.Column('id', sa.Integer(), primary_key=True),
                sa.Column('name', sa.String(length=255), nullable=True),
                sa.Column('created_at', sa.DateTime(timezone=True)),
            )
        except Exception:
            pass
