"""Makeshop Product Batch1 tables

Revision ID: 020_makeshop_batch1
Revises: 019_extend_member_fields
Create Date: 2025-11-10
"""

from alembic import op
import sqlalchemy as sa
from typing import Optional, List, Any

revision = '020_makeshop_batch1'
down_revision = '019_extend_member_fields'
branch_labels = None
depends_on = None


def _create_table_if_missing(table_name: str, columns: List[Any], indexes: Optional[List[Any]] = None):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table_name in insp.get_table_names():
        return
    op.create_table(table_name, *columns)
    if indexes:
        for idx in indexes:
            # Alembic op.create_index expects a sequence of column names (strings) or text clauses,
            # but SQLAlchemy Index.expressions may contain Column objects. Normalize to names.
            exprs = getattr(idx, 'expressions', []) or []
            cols: list[str] = []
            for expr in exprs:
                # strings pass through
                if isinstance(expr, str):
                    cols.append(expr)
                    continue
                # Column or ColumnElement with .name
                name = getattr(expr, 'name', None)
                if isinstance(name, str) and name:
                    cols.append(name)
                    continue
                # Fallback to key if available
                key = getattr(expr, 'key', None)
                if isinstance(key, str) and key:
                    cols.append(key)
            if cols:
                op.create_index(idx.name, table_name, cols, unique=getattr(idx, 'unique', False))


def upgrade() -> None:
    # mk_products
    _create_table_if_missing(
        'mk_products',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('source_uid', sa.BigInteger(), nullable=False),
            sa.Column('brandcode', sa.String(length=30), nullable=True),
            sa.Column('cate1', sa.String(length=10), nullable=True),
            sa.Column('cate2', sa.String(length=10), nullable=True),
            sa.Column('virtual_cate', sa.String(length=50), nullable=True),
            sa.Column('category_name', sa.String(length=255), nullable=True),
            sa.Column('product_name', sa.String(length=255), nullable=False),
            sa.Column('consumer_price', sa.Integer(), nullable=True),
            sa.Column('sell_price', sa.Integer(), nullable=True),
            sa.Column('buy_price', sa.Integer(), nullable=True),
            sa.Column('reserve', sa.Integer(), nullable=True),
            sa.Column('keyword_raw', sa.Text(), nullable=True),
            sa.Column('sell_accept', sa.String(length=1), nullable=True),
            sa.Column('display', sa.String(length=1), nullable=True),
            sa.Column('product_type', sa.String(length=30), nullable=True),
            sa.Column('best_product_display', sa.String(length=1), nullable=True),
            sa.Column('best_review_display', sa.String(length=1), nullable=True),
            sa.Column('sellcount', sa.Integer(), nullable=True),
            sa.Column('regdate', sa.DateTime(timezone=True), nullable=True),
            sa.Column('moddate', sa.DateTime(timezone=True), nullable=True),
            sa.Column('quantity_type', sa.String(length=20), nullable=True),
            sa.Column('provide_delivery_price', sa.Integer(), nullable=True),
            sa.Column('max_order_quantity_method', sa.String(length=20), nullable=True),
            sa.Column('min_order_quantity_method', sa.String(length=20), nullable=True),
            sa.Column('vat', sa.String(length=1), nullable=True),
            sa.Column('vat_type', sa.String(length=20), nullable=True),
            sa.Column('product_content_raw', sa.Text(), nullable=True),
            sa.Column('product_content_html', sa.Text(), nullable=True),
            sa.Column('display_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('importune', sa.String(length=1), nullable=True),
            sa.Column('view_count', sa.Integer(), nullable=True),
            sa.Column('cart_count', sa.Integer(), nullable=True),
            sa.Column('is_add_composition', sa.String(length=1), nullable=True),
            sa.Column('ems_type', sa.String(length=30), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    op.create_index('uq_mk_products_source_uid', 'mk_products', ['source_uid'], unique=True)
    op.create_index('ix_mk_products_brandcode', 'mk_products', ['brandcode'], unique=False)
    op.create_index('ix_mk_products_cates', 'mk_products', ['cate1','cate2'], unique=False)
    op.create_index('ix_mk_products_display_sellaccept', 'mk_products', ['display','sell_accept'], unique=False)

    # mk_brands
    _create_table_if_missing(
        'mk_brands',
        [
            sa.Column('brand_id', sa.BigInteger(), primary_key=True),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('brand_mid', sa.Integer(), nullable=True),
            sa.Column('brand_sid', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )

    # mk_product_brands
    _create_table_if_missing(
        'mk_product_brands',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('brand_id', sa.BigInteger(), sa.ForeignKey('mk_brands.brand_id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    op.create_index('ix_mk_product_brands_prod_brand', 'mk_product_brands', ['product_id','brand_id'], unique=True)

    # option groups
    _create_table_if_missing(
        'mk_product_option_groups',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('source_opt_id', sa.Integer(), nullable=False),
            sa.Column('opt_type', sa.String(length=20), nullable=True),
            sa.Column('opt_name', sa.String(length=100), nullable=True),
            sa.Column('opt_use', sa.String(length=1), nullable=True),
            sa.Column('opt_mix', sa.String(length=1), nullable=True),
            sa.Column('opt_mandatory', sa.String(length=1), nullable=True),
            sa.Column('opt_oneclick', sa.String(length=1), nullable=True),
            sa.Column('position', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    op.create_index('uq_mk_opt_groups_prod_src', 'mk_product_option_groups', ['product_id','source_opt_id'], unique=True)

    # option values
    _create_table_if_missing(
        'mk_product_option_values',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('group_id', sa.BigInteger(), sa.ForeignKey('mk_product_option_groups.id'), nullable=False),
            sa.Column('value_index', sa.Integer(), nullable=False),
            sa.Column('value_text', sa.String(length=100), nullable=True),
            sa.Column('extra_price', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    op.create_index('uq_mk_opt_values_group_idx', 'mk_product_option_values', ['group_id','value_index'], unique=True)

    # stocks
    _create_table_if_missing(
        'mk_product_stocks',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('source_sto_id', sa.Integer(), nullable=False),
            sa.Column('sto_type', sa.String(length=20), nullable=True),
            sa.Column('sto_price', sa.Integer(), nullable=True),
            sa.Column('sto_provide_price', sa.Integer(), nullable=True),
            sa.Column('sto_real_stock', sa.BigInteger(), nullable=True),
            sa.Column('sto_unlimit', sa.String(length=1), nullable=True),
            sa.Column('sto_stop_use', sa.String(length=1), nullable=True),
            sa.Column('sto_stop_stock', sa.Integer(), nullable=True),
            sa.Column('sto_order_stock', sa.Integer(), nullable=True),
            sa.Column('sto_state_code', sa.String(length=20), nullable=True),
            sa.Column('sto_option_code', sa.String(length=50), nullable=True),
            sa.Column('composed_key_hash', sa.String(length=64), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    op.create_index('ix_mk_stocks_prod', 'mk_product_stocks', ['product_id'], unique=False)
    op.create_index('ix_mk_stocks_optcode', 'mk_product_stocks', ['sto_option_code'], unique=False)
    op.create_index('ix_mk_stocks_state', 'mk_product_stocks', ['sto_state_code'], unique=False)
    op.create_index('ix_mk_stocks_hash', 'mk_product_stocks', ['composed_key_hash'], unique=False)

    # stock option value link
    _create_table_if_missing(
        'mk_product_stock_option_values',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('stock_id', sa.BigInteger(), sa.ForeignKey('mk_product_stocks.id'), nullable=False),
            sa.Column('value_id', sa.BigInteger(), sa.ForeignKey('mk_product_option_values.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    op.create_index('uq_mk_stock_value', 'mk_product_stock_option_values', ['stock_id','value_id'], unique=True)

    # discounts
    _create_table_if_missing(
        'mk_product_discounts',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('source_discount_uid', sa.Integer(), nullable=True),
            sa.Column('sale_type', sa.String(length=30), nullable=True),
            sa.Column('title', sa.String(length=255), nullable=True),
            sa.Column('user_type', sa.String(length=1), nullable=True),
            sa.Column('view_type', sa.String(length=1), nullable=True),
            sa.Column('device', sa.String(length=50), nullable=True),
            sa.Column('discount_price', sa.Integer(), nullable=True),
            sa.Column('unit', sa.String(length=20), nullable=True),
            sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('cut_option', sa.String(length=20), nullable=True),
            sa.Column('cut_position', sa.Integer(), nullable=True),
            sa.Column('option_discount', sa.String(length=1), nullable=True),
            sa.Column('product_coupon_except', sa.String(length=1), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    op.create_index('ix_mk_discounts_period', 'mk_product_discounts', ['product_id','start_date','end_date'], unique=False)

    # delivery
    _create_table_if_missing(
        'mk_product_delivery',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('deli_type', sa.String(length=5), nullable=True),
            sa.Column('deli_price', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )

    # colors
    _create_table_if_missing(
        'mk_product_colors',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('color_type', sa.String(length=20), nullable=True),
            sa.Column('color_code', sa.String(length=20), nullable=True),
            sa.Column('color_name', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    op.create_index('uq_mk_colors_prod_code', 'mk_product_colors', ['product_id','color_code'], unique=True)

    # coupon exceptions
    _create_table_if_missing(
        'mk_product_coupon_exceptions',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('except_code', sa.String(length=100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    op.create_index('uq_mk_coupon_except', 'mk_product_coupon_exceptions', ['product_id','except_code'], unique=True)

    # optional: packages, add compositions, regular delivery, notices
    _create_table_if_missing(
        'mk_product_packages',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('discount_unit', sa.String(length=20), nullable=True),
            sa.Column('discount_price', sa.Integer(), nullable=True),
            sa.Column('discount_type', sa.String(length=30), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    _create_table_if_missing(
        'mk_product_package_items',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('package_id', sa.BigInteger(), sa.ForeignKey('mk_product_packages.id'), nullable=False),
            sa.Column('sort', sa.Integer(), nullable=True),
            sa.Column('child_source_uid', sa.BigInteger(), nullable=True),
            sa.Column('child_product_name', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    _create_table_if_missing(
        'mk_product_add_compositions',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('sort', sa.Integer(), nullable=True),
            sa.Column('child_source_uid', sa.BigInteger(), nullable=True),
            sa.Column('child_product_name', sa.String(length=255), nullable=True),
            sa.Column('extra_require', sa.String(length=1), nullable=True),
            sa.Column('min_quantity', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    _create_table_if_missing(
        'mk_product_regular_delivery',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('use_calendar', sa.String(length=1), nullable=True),
            sa.Column('discount_str', sa.String(length=20), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    _create_table_if_missing(
        'mk_product_info_notices',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('product_id', sa.BigInteger(), sa.ForeignKey('mk_products.id'), nullable=False),
            sa.Column('notice_source_id', sa.String(length=50), nullable=True),
            sa.Column('notice_type', sa.String(length=20), nullable=True),
            sa.Column('title', sa.String(length=255), nullable=True),
            sa.Column('product_name_raw', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )
    _create_table_if_missing(
        'mk_product_info_notice_details',
        [
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('notice_id', sa.BigInteger(), sa.ForeignKey('mk_product_info_notices.id'), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=True),
            sa.Column('content', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        ],
    )


def downgrade() -> None:
    # Drop created tables in reverse order (best-effort)
    for tbl in [
        'mk_product_info_notice_details',
        'mk_product_info_notices',
        'mk_product_regular_delivery',
        'mk_product_add_compositions',
        'mk_product_package_items',
        'mk_product_packages',
        'mk_product_coupon_exceptions',
        'mk_product_colors',
        'mk_product_delivery',
        'mk_product_discounts',
        'mk_product_stock_option_values',
        'mk_product_stocks',
        'mk_product_option_values',
        'mk_product_option_groups',
        'mk_product_brands',
        'mk_brands',
        'mk_products',
    ]:
        try:
            op.drop_table(tbl)
        except Exception:
            pass
