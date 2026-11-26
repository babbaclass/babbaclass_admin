"""Drop additional unused product-related tables

Revision ID: 036
Revises: 035
Create Date: 2025-11-19

Changes:
- Drop product_packages table (package/bundle feature not implemented)
- Drop product_package_items table (related to product_packages)
- Drop product_add_compositions table (add composition feature not implemented)
- Drop product_regular_delivery table (regular delivery feature not implemented)
- Drop product_info_notices table (product info notices not used)
- Drop product_info_notice_details table (related to product_info_notices)

Reason: Further schema cleanup - these product extension tables are defined in models.py
but are never instantiated or queried in application code.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '036'
down_revision = '035'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop additional unused product-related tables"""
    
    print("\n========== MIGRATION 036: Drop additional unused product tables ==========")
    
    unused_tables = [
        'product_info_notice_details',  # Must drop first (has FK to product_info_notices)
        'product_info_notices',         # Has FK to products
        'product_regular_delivery',     # Has FK to products
        'product_add_compositions',     # Has FK to products
        'product_package_items',        # Has FK to product_packages
        'product_packages'              # Has FK to products
    ]
    
    for table_name in unused_tables:
        try:
            print(f"🗑️  Dropping {table_name}...")
            op.drop_table(table_name)
            print(f"✓ Dropped {table_name}")
        except Exception as e:
            print(f"⚠️  Could not drop {table_name}: {e}")
    
    print("========== MIGRATION 036: Complete ==========\n")


def downgrade() -> None:
    """Recreate all dropped tables (for rollback purposes)"""
    
    print("\n========== MIGRATION 036: Downgrade (Recreating dropped tables) ==========")
    
    try:
        # Recreate product_packages table
        print("🔄 Recreating product_packages table...")
        op.create_table(
            'product_packages',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('discount_unit', sa.String(20), nullable=True),
            sa.Column('discount_price', sa.Integer(), nullable=True),
            sa.Column('discount_type', sa.String(30), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_packages table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_packages: {e}")
    
    try:
        # Recreate product_package_items table
        print("🔄 Recreating product_package_items table...")
        op.create_table(
            'product_package_items',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('package_id', sa.BigInteger(), sa.ForeignKey('product_packages.id'), nullable=False, index=True),
            sa.Column('sort', sa.Integer(), nullable=True),
            sa.Column('child_source_uid', sa.BigInteger(), nullable=True),
            sa.Column('child_product_name', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_package_items table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_package_items: {e}")
    
    try:
        # Recreate product_add_compositions table
        print("🔄 Recreating product_add_compositions table...")
        op.create_table(
            'product_add_compositions',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('sort', sa.Integer(), nullable=True),
            sa.Column('child_source_uid', sa.BigInteger(), nullable=True),
            sa.Column('child_product_name', sa.String(255), nullable=True),
            sa.Column('extra_require', sa.String(1), nullable=True),
            sa.Column('min_quantity', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_add_compositions table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_add_compositions: {e}")
    
    try:
        # Recreate product_regular_delivery table
        print("🔄 Recreating product_regular_delivery table...")
        op.create_table(
            'product_regular_delivery',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('use_calendar', sa.String(1), nullable=True),
            sa.Column('discount_str', sa.String(20), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_regular_delivery table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_regular_delivery: {e}")
    
    try:
        # Recreate product_info_notices table
        print("🔄 Recreating product_info_notices table...")
        op.create_table(
            'product_info_notices',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('products.id'), nullable=False, index=True),
            sa.Column('notice_source_id', sa.String(50), nullable=True),
            sa.Column('notice_type', sa.String(20), nullable=True),
            sa.Column('title', sa.String(255), nullable=True),
            sa.Column('product_name_raw', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_info_notices table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_info_notices: {e}")
    
    try:
        # Recreate product_info_notice_details table
        print("🔄 Recreating product_info_notice_details table...")
        op.create_table(
            'product_info_notice_details',
            sa.Column('id', sa.BigInteger(), nullable=False, primary_key=True, index=True),
            sa.Column('notice_id', sa.BigInteger(), sa.ForeignKey('product_info_notices.id'), nullable=False, index=True),
            sa.Column('name', sa.String(100), nullable=True),
            sa.Column('content', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
        )
        print("✓ Recreated product_info_notice_details table")
    except Exception as e:
        print(f"⚠️  Could not recreate product_info_notice_details: {e}")
    
    print("========== MIGRATION 036: Downgrade Complete ==========\n")
