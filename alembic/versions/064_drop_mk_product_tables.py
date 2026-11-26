"""Drop mk_product and related tables - No longer used in the application

Revision ID: 064_drop_mk_product_tables
Revises: 063
Create Date: 2025-11-28 10:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '064'
down_revision = '063'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop mk_product related tables as they are no longer used"""
    
    # Drop dependent tables first (those with foreign keys to mk_product tables)
    tables_to_drop = [
        'mk_product_stock_option_values',  # FK to mk_product_option_values
        'mk_product_option_values',         # FK to mk_product_option_groups
        'mk_product_option_groups',         # FK to mk_products
        'mk_product_stocks',                # FK to mk_products
        'mk_product_package_items',         # FK to mk_product_packages
        'mk_product_packages',              # FK to mk_products
        'mk_product_brands',                # FK to mk_products
        'mk_product_discounts',             # FK to mk_products
        'mk_product_delivery',              # FK to mk_products
        'mk_product_colors',                # FK to mk_products
        'mk_product_coupon_exceptions',     # FK to mk_products
        'mk_product_add_compositions',      # FK to mk_products
        'mk_product_regular_delivery',      # FK to mk_products
        'mk_product_info_notices',          # FK to mk_products
        'mk_products',                      # Main table
    ]
    
    for table_name in tables_to_drop:
        try:
            op.drop_table(table_name)
            print(f"✓ Dropped table: {table_name}")
        except Exception as e:
            print(f"⚠ Could not drop {table_name}: {e}")


def downgrade() -> None:
    """Downgrade would require recreating all mk_product tables - not implemented"""
    print("⚠ Downgrade not implemented - mk_product tables are legacy and cannot be restored")
