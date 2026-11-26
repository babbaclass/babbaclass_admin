"""Extend members table with external JSON mapped fields

Revision ID: 019_extend_member_fields
Revises: 018_add_amount_tiers
Create Date: 2025-11-10
"""

from alembic import op
import sqlalchemy as sa

revision = '019_extend_member_fields'
down_revision = '018_add_amount_tiers'
branch_labels = None
depends_on = None


def _add_col_if_missing(table, column, coltype, **kwargs):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return
    cols = {c['name'] for c in insp.get_columns(table)}
    if column not in cols:
        op.add_column(table, sa.Column(column, coltype, **kwargs))


def upgrade() -> None:
    # Strings
    _add_col_if_missing('members', 'mem_type', sa.String(length=50), nullable=True)
    _add_col_if_missing('members', 'simple_type', sa.String(length=50), nullable=True)
    _add_col_if_missing('members', 'grade', sa.Integer(), nullable=True)
    _add_col_if_missing('members', 'reserve', sa.Integer(), nullable=True)
    _add_col_if_missing('members', 'email_receive', sa.String(length=1), nullable=True)
    _add_col_if_missing('members', 'sms_receive', sa.String(length=1), nullable=True)
    _add_col_if_missing('members', 'login_date', sa.DateTime(timezone=True), nullable=True)
    _add_col_if_missing('members', 'mod_date', sa.DateTime(timezone=True), nullable=True)
    _add_col_if_missing('members', 'reg_date', sa.DateTime(timezone=True), nullable=True)
    _add_col_if_missing('members', 'birth_day', sa.String(length=20), nullable=True)
    _add_col_if_missing('members', 'birth_day_year', sa.String(length=20), nullable=True)
    _add_col_if_missing('members', 'birth_format', sa.String(length=10), nullable=True)
    _add_col_if_missing('members', 'sex', sa.String(length=5), nullable=True)
    _add_col_if_missing('members', 'group_id', sa.String(length=50), nullable=True)
    _add_col_if_missing('members', 'group_name', sa.String(length=100), nullable=True)
    _add_col_if_missing('members', 'post', sa.String(length=20), nullable=True)
    _add_col_if_missing('members', 'address_detail', sa.Text(), nullable=True)
    _add_col_if_missing('members', 'push_receive', sa.String(length=1), nullable=True)
    _add_col_if_missing('members', 'point', sa.Integer(), nullable=True)
    _add_col_if_missing('members', 'emoney', sa.Integer(), nullable=True)
    _add_col_if_missing('members', 'is_app_use', sa.String(length=1), nullable=True)
    _add_col_if_missing('members', 'extension_period', sa.DateTime(timezone=True), nullable=True)
    _add_col_if_missing('members', 'order_count', sa.Integer(), nullable=True)
    _add_col_if_missing('members', 'company_name', sa.String(length=255), nullable=True)
    _add_col_if_missing('members', 'company_owner', sa.String(length=255), nullable=True)
    _add_col_if_missing('members', 'company_num', sa.String(length=100), nullable=True)
    _add_col_if_missing('members', 'company_corp', sa.String(length=100), nullable=True)
    _add_col_if_missing('members', 'company_biz', sa.String(length=100), nullable=True)
    _add_col_if_missing('members', 'company_item', sa.String(length=100), nullable=True)
    _add_col_if_missing('members', 'company_post', sa.String(length=20), nullable=True)
    _add_col_if_missing('members', 'company_addr', sa.Text(), nullable=True)


def downgrade() -> None:
    # Best-effort: drop columns (optional)
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'members' in insp.get_table_names():
        for col in [
            'mem_type','simple_type','grade','reserve','email_receive','sms_receive','login_date','mod_date','reg_date','birth_day','birth_day_year','birth_format','sex','group_id','group_name','post','address_detail','push_receive','point','emoney','is_app_use','extension_period','order_count','company_name','company_owner','company_num','company_corp','company_biz','company_item','company_post','company_addr'
        ]:
            try:
                op.drop_column('members', col)
            except Exception:
                pass
