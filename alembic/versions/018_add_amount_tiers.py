"""Add amount tier columns and seed commission windows for 2025-2026

Revision ID: 018_add_amount_tiers
Revises: 017_commission_tables
Create Date: 2025-11-10
"""

from alembic import op
import sqlalchemy as sa

revision = '018_add_amount_tiers'
down_revision = '017_commission_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Add columns if not exist
    if 'commission_rate_windows' in inspector.get_table_names():
        cols = {c['name'] for c in inspector.get_columns('commission_rate_windows')}
        if 'min_amount' not in cols:
            op.add_column('commission_rate_windows', sa.Column('min_amount', sa.Integer(), nullable=False, server_default='0'))
        if 'max_amount' not in cols:
            op.add_column('commission_rate_windows', sa.Column('max_amount', sa.Integer(), nullable=True))

    # Seed windows only if no existing rows (idempotent guard)
    existing = 0
    if 'commission_rate_windows' in inspector.get_table_names():
        existing = conn.execute(sa.text('SELECT COUNT(*) FROM commission_rate_windows')).scalar() or 0

    if existing == 0:
        # Commission type ids lookup by code
        type_map = {}
        if 'commission_types' in inspector.get_table_names():
            rows = conn.execute(sa.text('SELECT commission_type_id, code FROM commission_types')).fetchall()
            type_map = {r.code: r.commission_type_id for r in rows}
        # Helper to insert
        def ins(code, sy, sm, ey, em, rate, min_amt=0, max_amt=None, priority=0):
            tid = type_map.get(code)
            if not tid:
                return
            conn.execute(sa.text('''
                INSERT INTO commission_rate_windows (
                    commission_type_id, start_year, start_month, end_year, end_month,
                    rate_percent, min_amount, max_amount, priority, is_active
                ) VALUES (:tid, :sy, :sm, :ey, :em, :rate, :min_amt, :max_amt, :priority, 1)
            '''), {
                'tid': tid, 'sy': sy, 'sm': sm, 'ey': ey, 'em': em,
                'rate': rate, 'min_amt': min_amt, 'max_amt': max_amt, 'priority': priority
            })
        # Period 1: 2025-01 ~ 2025-10
        for code, rate in [
            ('ENROLLMENT', 30.00),
            ('BASCLE', 25.00),
            ('AEGIS_EDU', 15.00),
            ('OTHER', 15.00),
        ]:
            ins(code, 2025, 1, 2025, 10, rate)
        # Period 2: 2025-11 ~ 2026-12
        # ENROLLMENT flat
        ins('ENROLLMENT', 2025, 11, 2026, 12, 30.00)
        # BASCLE tiers
        ins('BASCLE', 2025, 11, 2026, 12, 25.00, 0, 999999)
        ins('BASCLE', 2025, 11, 2026, 12, 27.00, 1000000, 2999999)
        ins('BASCLE', 2025, 11, 2026, 12, 30.00, 3000000, None)
        # AEGIS_EDU flat
        ins('AEGIS_EDU', 2025, 11, 2026, 12, 15.00)
        # OTHER flat
        ins('OTHER', 2025, 11, 2026, 12, 15.00)

    # Create composite index for amount tiers if not exist
    existing_indexes = {i['name'] for i in inspector.get_indexes('commission_rate_windows')} if 'commission_rate_windows' in inspector.get_table_names() else set()
    if 'ix_ratewin_amount_window' not in existing_indexes:
        op.create_index('ix_ratewin_amount_window', 'commission_rate_windows', ['commission_type_id','start_year','start_month','end_year','end_month','min_amount'])


def downgrade() -> None:
    # Drop columns (data destructive)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'commission_rate_windows' in inspector.get_table_names():
        cols = {c['name'] for c in inspector.get_columns('commission_rate_windows')}
        if 'max_amount' in cols:
            op.drop_column('commission_rate_windows', 'max_amount')
        if 'min_amount' in cols:
            op.drop_column('commission_rate_windows', 'min_amount')
    # Optional: remove seeded rows (skipped to avoid affecting manual additions)
    try:
        op.drop_index('ix_ratewin_amount_window', table_name='commission_rate_windows')
    except Exception:
        pass
