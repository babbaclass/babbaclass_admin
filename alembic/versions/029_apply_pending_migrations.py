"""Apply pending column renames from migrations 027 and 028

This migration applies all the pending column renames that should have been done
by migrations 027 and 028 (which are now skipped).

Revision ID: 029
Revises: 028_member_columns_makeshop_api
Create Date: 2025-11-18

Changes:
- Product table: Rename columns to match Makeshop API field names
  - makeshop_product_id → uid
  - name → product_name
  - price → sellprice
  - cost → buyprice
  - consumer_price → consumerprice
  - keyword_raw → keyword
  - product_content_raw → product_content
  
- Member table: Rename columns to match Makeshop API field names
  - name → hname
  - phone → mobile
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '029'
down_revision = '028_member_columns_makeshop_api'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply all pending column renames from 027 and 028"""
    
    print("\n========== MIGRATION 029: Applying Column Renames ==========")
    
    # ===== Product table columns =====
    # Rename makeshop_product_id to uid (if it exists)
    try:
        op.alter_column('products', 'makeshop_product_id', new_column_name='uid')
        print("✓ Renamed: products.makeshop_product_id → uid")
    except Exception as e:
        print(f"✗ Failed to rename makeshop_product_id: {e}")
    
    # Rename name to product_name (if it exists)
    try:
        op.alter_column('products', 'name', new_column_name='product_name')
        print("✓ Renamed: products.name → product_name")
    except Exception as e:
        print(f"✗ Failed to rename name: {e}")
    
    # Rename price to sellprice (if it exists)
    try:
        op.alter_column('products', 'price', new_column_name='sellprice')
        print("✓ Renamed: products.price → sellprice")
    except Exception as e:
        print(f"✗ Failed to rename price: {e}")
    
    # Rename cost to buyprice (if it exists)
    try:
        op.alter_column('products', 'cost', new_column_name='buyprice')
        print("✓ Renamed: products.cost → buyprice")
    except Exception as e:
        print(f"✗ Failed to rename cost: {e}")
    
    # Rename consumer_price to consumerprice (if it exists)
    try:
        op.alter_column('products', 'consumer_price', new_column_name='consumerprice')
        print("✓ Renamed: products.consumer_price → consumerprice")
    except Exception as e:
        print(f"✗ Failed to rename consumer_price: {e}")
    
    # Rename keyword_raw to keyword (if it exists)
    try:
        op.alter_column('products', 'keyword_raw', new_column_name='keyword')
        print("✓ Renamed: products.keyword_raw → keyword")
    except Exception as e:
        print(f"✗ Failed to rename keyword_raw: {e}")
    
    # Rename product_content_raw to product_content (if it exists)
    try:
        op.alter_column('products', 'product_content_raw', new_column_name='product_content')
        print("✓ Renamed: products.product_content_raw → product_content")
    except Exception as e:
        print(f"✗ Failed to rename product_content_raw: {e}")
    
    # ===== Member table columns =====
    # Rename name to hname (if it exists)
    try:
        op.alter_column('members', 'name', new_column_name='hname')
        print("✓ Renamed: members.name → hname")
    except Exception as e:
        print(f"✗ Failed to rename members.name: {e}")
    
    # Rename phone to mobile (if it exists)
    try:
        op.alter_column('members', 'phone', new_column_name='mobile')
        print("✓ Renamed: members.phone → mobile")
    except Exception as e:
        print(f"✗ Failed to rename members.phone: {e}")
    
    print("========== MIGRATION 029: Complete ==========\n")


def downgrade() -> None:
    """Revert all column renames from 029"""
    
    # Revert Product table columns
    try:
        op.alter_column('products', 'uid', new_column_name='makeshop_product_id')
    except Exception:
        pass
    
    try:
        op.alter_column('products', 'product_name', new_column_name='name')
    except Exception:
        pass
    
    try:
        op.alter_column('products', 'sellprice', new_column_name='price')
    except Exception:
        pass
    
    try:
        op.alter_column('products', 'buyprice', new_column_name='cost')
    except Exception:
        pass
    
    try:
        op.alter_column('products', 'consumerprice', new_column_name='consumer_price')
    except Exception:
        pass
    
    try:
        op.alter_column('products', 'keyword', new_column_name='keyword_raw')
    except Exception:
        pass
    
    try:
        op.alter_column('products', 'product_content', new_column_name='product_content_raw')
    except Exception:
        pass
    
    # Revert Member table columns
    try:
        op.alter_column('members', 'hname', new_column_name='name')
    except Exception:
        pass
    
    try:
        op.alter_column('members', 'mobile', new_column_name='phone')
    except Exception:
        pass
