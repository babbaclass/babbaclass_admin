"""Align Product and Member table columns with Makeshop API field names

Revision ID: 027
Revises: 026_remove_member_id_from_users
Create Date: 2025-01-14

This migration aligns both product and member table columns with Makeshop API response field names
for consistency and easier maintenance:

Product columns:
- makeshop_product_id → uid
- name → product_name
- price → sellprice
- cost → buyprice
- consumer_price → consumerprice
- keyword_raw → keyword
- product_content_raw → product_content

Member columns:
- name → hname
- phone → mobile
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '027'
down_revision = '026_remove_member_id_from_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename columns to match Makeshop API field names"""
    
    # ===== Product table columns =====
    # Rename makeshop_product_id to uid (if it exists)
    try:
        op.alter_column('products', 'makeshop_product_id', new_column_name='uid')
    except Exception:
        # Column may not exist or already renamed, skip
        pass
    
    # Rename name to product_name (if it exists)
    try:
        op.alter_column('products', 'name', new_column_name='product_name')
    except Exception:
        pass
    
    # Rename price to sellprice (if it exists)
    try:
        op.alter_column('products', 'price', new_column_name='sellprice')
    except Exception:
        pass
    
    # Rename cost to buyprice (if it exists)
    try:
        op.alter_column('products', 'cost', new_column_name='buyprice')
    except Exception:
        pass
    
    # Rename consumer_price to consumerprice (if it exists)
    try:
        op.alter_column('products', 'consumer_price', new_column_name='consumerprice')
    except Exception:
        pass
    
    # Rename keyword_raw to keyword (if it exists)
    try:
        op.alter_column('products', 'keyword_raw', new_column_name='keyword')
    except Exception:
        pass
    
    # Rename product_content_raw to product_content (if it exists)
    try:
        op.alter_column('products', 'product_content_raw', new_column_name='product_content')
    except Exception:
        pass
    
    # ===== Member table columns =====
    # Rename name to hname (if it exists)
    try:
        op.alter_column('members', 'name', new_column_name='hname')
    except Exception:
        pass
    
    # Rename phone to mobile (if it exists)
    try:
        op.alter_column('members', 'phone', new_column_name='mobile')
    except Exception:
        pass


def downgrade() -> None:
    """Revert column names to original names"""
    
    # ===== Product table columns =====
    # Rename uid back to makeshop_product_id
    try:
        op.alter_column('products', 'uid', new_column_name='makeshop_product_id')
    except Exception:
        pass
    
    # Rename product_name back to name
    try:
        op.alter_column('products', 'product_name', new_column_name='name')
    except Exception:
        pass
    
    # Rename sellprice back to price
    try:
        op.alter_column('products', 'sellprice', new_column_name='price')
    except Exception:
        pass
    
    # Rename buyprice back to cost
    try:
        op.alter_column('products', 'buyprice', new_column_name='cost')
    except Exception:
        pass
    
    # Rename consumerprice back to consumer_price
    try:
        op.alter_column('products', 'consumerprice', new_column_name='consumer_price')
    except Exception:
        pass
    
    # Rename keyword back to keyword_raw
    try:
        op.alter_column('products', 'keyword', new_column_name='keyword_raw')
    except Exception:
        pass
    
    # Rename product_content back to product_content_raw
    try:
        op.alter_column('products', 'product_content', new_column_name='product_content_raw')
    except Exception:
        pass
    
    # ===== Member table columns =====
    # Rename hname back to name
    try:
        op.alter_column('members', 'hname', new_column_name='name')
    except Exception:
        pass
    
    # Rename mobile back to phone
    try:
        op.alter_column('members', 'mobile', new_column_name='phone')
    except Exception:
        pass
