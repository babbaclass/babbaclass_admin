"""Drop unused product-related tables

Revision ID: 035
Revises: 034
Create Date: 2025-11-19

Changes:
- Drop brands table (not used in current codebase)
- Drop product_brands table (relationship with brands)
- Drop product_option_groups table (options feature not implemented)
- Drop product_option_values table (part of options feature)
- Drop product_stock_option_values table (relationship table)
- Drop product_stock table (advanced inventory not used)
- Drop product_discount table (discount feature not implemented)
- Drop product_delivery table (replaced by Order.shipping_address)
- Drop product_color table (color feature not implemented)
- Drop product_coupon_exceptions table (coupon system not implemented)

Reason: Clean up database schema by removing tables that are defined in models.py
but not actually used in the application code.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '035'
down_revision = '034'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop unused product-related tables"""
    
    print("\n========== MIGRATION 035: Drop unused product-related tables ==========")
    
    unused_tables = [
        'product_stock_option_values',  # Must drop first (has FK to product_option_values)
        'product_option_values',        # Has FK to product_option_groups
        'product_option_groups',        # Has FK to products
        'product_stock',                # Has FK to products
        'product_discount',             # Has FK to products
        'product_delivery',             # Has FK to products
        'product_color',                # Has FK to products
        'product_coupon_exceptions',    # Has FK to products
        'product_brands',               # Has FK to brands and products
        'brands'                        # Independent table
    ]
    
    for table_name in unused_tables:
        try:
            print(f"🗑️  Dropping {table_name}...")
            op.drop_table(table_name)
            print(f"✓ Dropped {table_name}")
        except Exception as e:
            print(f"⚠️  Could not drop {table_name}: {e}")
    
    print("========== MIGRATION 035: Complete ==========\n")


def downgrade() -> None:
    """Recreate all dropped tables (for rollback purposes)"""
    
    print("\n========== MIGRATION 035: Downgrade (Recreating dropped tables) ==========")
    
    try:
        # Recreate brands table
        print("🔄 Recreating brands table...")
        op.create_table(
            'brands',
            sa.Column('brand_id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('name', sa.String(100), nullable=False, index=True),
            sa.Column('brand_mid', sa.Integer(), nullable=True),
            sa.Column('brand_sid', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
        )
        print("✓ Recreated brands table")
    except Exception as e:
        print(f"⚠️  Could not recreate brands: {e}")
    
    try:
        # Recreate product_brands table
        print("🔄 Recreating product_brands table...")
        op.create_table(
            'product_brands',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('brand_id', sa.BigInteger(), sa.ForeignKey('brands.brand_id'), nullable=False, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
        )
        print("✓ Recreated product_brands table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_brands: {e}")
    
    try:
        # Recreate product_option_groups table
        print("🔄 Recreating product_option_groups table...")
        op.create_table(
            'product_option_groups',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('source_opt_id', sa.Integer(), nullable=False),
            sa.Column('opt_type', sa.String(20), nullable=True),
            sa.Column('opt_name', sa.String(100), nullable=True),
            sa.Column('opt_use', sa.String(1), nullable=True),
            sa.Column('opt_mix', sa.String(1), nullable=True),
            sa.Column('opt_mandatory', sa.String(1), nullable=True),
            sa.Column('opt_oneclick', sa.String(1), nullable=True),
            sa.Column('position', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
        )
        print("✓ Recreated product_option_groups table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_option_groups: {e}")
    
    try:
        # Recreate product_option_values table
        print("🔄 Recreating product_option_values table...")
        op.create_table(
            'product_option_values',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('group_id', sa.BigInteger(), sa.ForeignKey('product_option_groups.id'), nullable=False, index=True),
            sa.Column('value_index', sa.Integer(), nullable=False),
            sa.Column('value_text', sa.String(100), nullable=True),
            sa.Column('extra_price', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
        )
        print("✓ Recreated product_option_values table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_option_values: {e}")
    
    try:
        # Recreate product_stock table
        print("🔄 Recreating product_stock table...")
        op.create_table(
            'product_stocks',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('source_sto_id', sa.Integer(), nullable=False),
            sa.Column('sto_type', sa.String(20), nullable=True),
            sa.Column('sto_price', sa.Integer(), nullable=True),
            sa.Column('sto_provide_price', sa.Integer(), nullable=True),
            sa.Column('sto_real_stock', sa.BigInteger(), nullable=True),
            sa.Column('sto_unlimit', sa.String(1), nullable=True),
            sa.Column('sto_stop_use', sa.String(1), nullable=True),
            sa.Column('sto_stop_stock', sa.Integer(), nullable=True),
            sa.Column('sto_order_stock', sa.Integer(), nullable=True),
            sa.Column('sto_state_code', sa.String(20), nullable=True, index=True),
            sa.Column('sto_option_code', sa.String(50), nullable=True, index=True),
            sa.Column('composed_key_hash', sa.String(64), nullable=True, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
        )
        print("✓ Recreated product_stocks table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_stocks: {e}")
    
    try:
        # Recreate product_stock_option_values table
        print("🔄 Recreating product_stock_option_values table...")
        op.create_table(
            'product_stock_option_values',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('stock_id', sa.BigInteger(), sa.ForeignKey('product_stocks.id'), nullable=False, index=True),
            sa.Column('value_id', sa.BigInteger(), sa.ForeignKey('product_option_values.id'), nullable=False, index=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_stock_option_values table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_stock_option_values: {e}")
    
    try:
        # Recreate product_discount table
        print("🔄 Recreating product_discount table...")
        op.create_table(
            'product_discounts',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('source_discount_uid', sa.Integer(), nullable=True),
            sa.Column('sale_type', sa.String(30), nullable=True),
            sa.Column('title', sa.String(255), nullable=True),
            sa.Column('user_type', sa.String(1), nullable=True),
            sa.Column('view_type', sa.String(1), nullable=True),
            sa.Column('device', sa.String(50), nullable=True),
            sa.Column('discount_price', sa.Integer(), nullable=True),
            sa.Column('unit', sa.String(20), nullable=True),
            sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('cut_option', sa.String(20), nullable=True),
            sa.Column('cut_position', sa.Integer(), nullable=True),
            sa.Column('option_discount', sa.String(1), nullable=True),
            sa.Column('product_coupon_except', sa.String(1), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_discounts table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_discounts: {e}")
    
    try:
        # Recreate product_delivery table
        print("🔄 Recreating product_delivery table...")
        op.create_table(
            'product_delivery',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('deli_type', sa.String(5), nullable=True),
            sa.Column('deli_price', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_delivery table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_delivery: {e}")
    
    try:
        # Recreate product_color table
        print("🔄 Recreating product_color table...")
        op.create_table(
            'product_colors',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('color_type', sa.String(20), nullable=True),
            sa.Column('color_code', sa.String(20), nullable=True),
            sa.Column('color_name', sa.String(50), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_colors table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_colors: {e}")
    
    try:
        # Recreate product_coupon_exceptions table
        print("🔄 Recreating product_coupon_exceptions table...")
        op.create_table(
            'product_coupon_exceptions',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('except_code', sa.String(100), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_coupon_exceptions table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_coupon_exceptions: {e}")
    
    print("========== MIGRATION 035: Downgrade Complete ==========\n")
