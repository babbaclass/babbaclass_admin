"""Unprefix Makeshop tables: merge mk_* into base product & rename related tables

Revision ID: 021_unprefix_makeshop_tables
Revises: 020_makeshop_batch1
Create Date: 2025-11-10
"""
from alembic import op
import sqlalchemy as sa

revision = '021_unprefix_makeshop_tables'
down_revision = '020_makeshop_batch1'
branch_labels = None
depends_on = None

PRODUCT_EXT_COLUMNS = [
    ('brandcode', sa.String(30)),
    ('cate1', sa.String(10)),
    ('cate2', sa.String(10)),
    ('virtual_cate', sa.String(50)),
    ('consumer_price', sa.Integer()),
    ('reserve', sa.Integer()),
    ('keyword_raw', sa.Text()),
    ('sell_accept', sa.String(1)),
    ('display', sa.String(1)),
    ('product_type', sa.String(30)),
    ('best_product_display', sa.String(1)),
    ('best_review_display', sa.String(1)),
    ('sellcount', sa.Integer()),
    ('regdate', sa.DateTime(timezone=True)),
    ('moddate', sa.DateTime(timezone=True)),
    ('quantity_type', sa.String(20)),
    ('provide_delivery_price', sa.Integer()),
    ('max_order_quantity_method', sa.String(20)),
    ('min_order_quantity_method', sa.String(20)),
    ('vat', sa.String(1)),
    ('vat_type', sa.String(20)),
    ('product_content_raw', sa.Text()),
    ('product_content_html', sa.Text()),
    ('display_date', sa.DateTime(timezone=True)),
    ('importune', sa.String(1)),
    ('view_count', sa.Integer()),
    ('cart_count', sa.Integer()),
    ('is_add_composition', sa.String(1)),
    ('ems_type', sa.String(30)),
]

RENAME_MAP = {
    'mk_brands': 'brands',
    'mk_product_brands': 'product_brands',
    'mk_product_option_groups': 'product_option_groups',
    'mk_product_option_values': 'product_option_values',
    'mk_product_stocks': 'product_stocks',
    'mk_product_stock_option_values': 'product_stock_option_values',
    'mk_product_discounts': 'product_discounts',
    'mk_product_delivery': 'product_delivery',
    'mk_product_colors': 'product_colors',
    'mk_product_coupon_exceptions': 'product_coupon_exceptions',
    'mk_product_packages': 'product_packages',
    'mk_product_package_items': 'product_package_items',
    'mk_product_add_compositions': 'product_add_compositions',
    'mk_product_regular_delivery': 'product_regular_delivery',
    'mk_product_info_notices': 'product_info_notices',
    'mk_product_info_notice_details': 'product_info_notice_details',
}


def _table_exists(bind, name: str) -> bool:
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1) Add missing extended columns to products
    existing_cols = {c['name'] for c in insp.get_columns('products')}
    for col_name, col_type in PRODUCT_EXT_COLUMNS:
        if col_name not in existing_cols:
            op.add_column('products', sa.Column(col_name, col_type, nullable=True))
    # Create indexes for frequently queried flags if missing
    for idx_cols in [ ['brandcode'], ['cate1'], ['cate2'], ['sell_accept'], ['display'], ['product_type'], ['regdate'] ]:
        idx_name = 'ix_products_' + '_'.join(idx_cols)
        # Basic existence check: MySQL/MariaDB stores indexes list; fallback try/except
        try:
            op.create_index(idx_name, 'products', idx_cols, unique=False)
        except Exception:
            pass

    # 2) Copy data from mk_products into products extended columns if mk_products exists
    if _table_exists(bind, 'mk_products'):
        # Using raw SQL update with join on makeshop_product_id == source_uid
        # Only copy if target is NULL to avoid overwriting manual edits
        for col_name, _ in PRODUCT_EXT_COLUMNS:
            # brandcode etc; product_name already existed as name
            if col_name in existing_cols:
                stmt = sa.text(f"UPDATE products p JOIN mk_products m ON p.makeshop_product_id = CAST(m.source_uid AS CHAR) SET p.{col_name} = COALESCE(p.{col_name}, m.{col_name})")
                try:
                    bind.execute(stmt)
                except Exception:
                    pass
        # price/cost mapping from sell_price/buy_price (only if price/cost still default 0 / NULL)
        try:
            bind.execute(sa.text("UPDATE products p JOIN mk_products m ON p.makeshop_product_id = CAST(m.source_uid AS CHAR) SET p.price = CASE WHEN p.price = 0 THEN COALESCE(m.sell_price, p.price) ELSE p.price END, p.cost = COALESCE(p.cost, m.buy_price)"))
        except Exception:
            pass

    # 3) Rename mk_* tables to unprefixed names (skip if target already exists)
    for old, new in RENAME_MAP.items():
        if _table_exists(bind, old) and not _table_exists(bind, new):
            try:
                op.rename_table(old, new)
            except Exception:
                pass

    # 4) Drop mk_products if exists (data merged)
    if _table_exists(bind, 'mk_products'):
        try:
            op.drop_table('mk_products')
        except Exception:
            pass


def downgrade() -> None:
    # Downgrade is best-effort: cannot restore mk_products data once merged.
    # We will recreate mk_products minimally and re-prefix tables if possible.
    bind = op.get_bind()

    # 1) Recreate mk_products (empty) if not exists
    if not _table_exists(bind, 'mk_products'):
        op.create_table('mk_products',
            sa.Column('id', sa.BigInteger(), primary_key=True),
            sa.Column('source_uid', sa.BigInteger(), nullable=False),
        )
        op.create_index('uq_mk_products_source_uid', 'mk_products', ['source_uid'], unique=True)

    # 2) Attempt to rename back (only if original mk_* name not exists and new exists)
    for old, new in RENAME_MAP.items():
        if not _table_exists(bind, old) and _table_exists(bind, new):
            try:
                op.rename_table(new, old)
            except Exception:
                pass

    # 3) (Optional) Remove extended columns from products (skip to avoid data loss)
    # Leaving columns as-is for safety.
