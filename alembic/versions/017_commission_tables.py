"""Create commission tables (types and rate windows)

Revision ID: 017_commission_tables
Revises: 016_user_code
Create Date: 2025-11-10
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = '017_commission_tables'
down_revision = '016_user_code'
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

    # 1) commission_types
    if not _has_table(conn, 'commission_types'):
        op.create_table(
            'commission_types',
            sa.Column('commission_type_id', sa.Integer(), primary_key=True),
            sa.Column('code', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('display_order', sa.Integer(), server_default='0'),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('code', name='uq_commission_types_code'),
        )
        op.create_index('ix_commission_types_code', 'commission_types', ['code'])
        op.create_index('ix_commission_types_id', 'commission_types', ['commission_type_id'])

    # 2) commission_rate_windows
    if not _has_table(conn, 'commission_rate_windows'):
        op.create_table(
            'commission_rate_windows',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('commission_type_id', sa.Integer(), nullable=False),
            sa.Column('start_year', sa.Integer(), nullable=False),
            sa.Column('start_month', sa.Integer(), nullable=False),
            sa.Column('end_year', sa.Integer(), nullable=True),
            sa.Column('end_month', sa.Integer(), nullable=True),
            sa.Column('rate_percent', sa.Numeric(5, 2), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=True),
            sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['commission_type_id'], ['commission_types.commission_type_id'], name='fk_ratewin_type'),
            sa.ForeignKeyConstraint(['company_id'], ['companies.company_id'], name='fk_ratewin_company'),
        )
        op.create_index('ix_ratewin_type', 'commission_rate_windows', ['commission_type_id'])
        op.create_index('ix_ratewin_company', 'commission_rate_windows', ['company_id'])
        op.create_index('ix_ratewin_window', 'commission_rate_windows', ['start_year', 'start_month', 'end_year', 'end_month'])

    # Seed commission types (idempotent)
    # Codes: ENROLLMENT, BASCLE, AEGIS_EDU, OTHER
    if _has_table(conn, 'commission_types'):
        existing_codes = {r[0] for r in conn.execute(sa.text('SELECT code FROM commission_types')).fetchall()}
        seeds = [
            ('ENROLLMENT', '가입비', 1),
            ('BASCLE', '바스클 교재', 2),
            ('AEGIS_EDU', '이지스에듀교재', 3),
            ('OTHER', '기타', 99),
        ]
        for code, name, order in seeds:
            if code not in existing_codes:
                conn.execute(sa.text('INSERT INTO commission_types (code, name, display_order, is_active) VALUES (:c, :n, :o, 1)'),
                             {'c': code, 'n': name, 'o': order})



def downgrade() -> None:
    conn = op.get_bind()

    if _has_table(conn, 'commission_rate_windows'):
        op.drop_table('commission_rate_windows')
    if _has_table(conn, 'commission_types'):
        op.drop_table('commission_types')
