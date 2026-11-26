"""Remove DB-only fields from Product and rename stock to quantity

Revision ID: 030
Revises: 029
Create Date: 2025-11-18

Changes:
- Drop columns from products table:
  - category_id (foreign key not used)
  - category_name (API doesn't provide this - only virtual categories)
  - description (API doesn't provide this - only product_content)
  - image_url (API doesn't provide this field)
  - product_content_html (API only provides plain text product_content)
  - is_active (not used - use status column instead)

- Rename stock → quantity (matches Makeshop API field name)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove DB-only fields and rename stock to quantity"""
    
    print("\n========== MIGRATION 030: Clean up Product table ==========")
    
    # Step 1: Drop foreign key constraint on category_id if it exists
    try:
        op.drop_constraint('products_ibfk_1', 'products', type_='foreignkey')
        print("✓ Dropped foreign key constraint on category_id")
    except Exception as e:
        print(f"⚠️  No foreign key to drop (or already dropped): {e}")
    
    # Step 2: Drop unused columns
    columns_to_drop = [
        ('category_id', 'Integer'),
        ('category_name', 'String'),
        ('description', 'Text'),
        ('image_url', 'String'),
        ('product_content_html', 'Text'),
        ('is_active', 'Boolean'),
    ]
    
    for col_name, col_type in columns_to_drop:
        try:
            op.drop_column('products', col_name)
            print(f"✓ Dropped column: products.{col_name}")
        except Exception as e:
            print(f"⚠️  Failed to drop {col_name} (may not exist): {e}")
    
    # Step 3: Rename stock → quantity
    try:
        op.alter_column('products', 'stock', new_column_name='quantity')
        print("✓ Renamed: products.stock → quantity")
    except Exception as e:
        print(f"✗ Failed to rename stock to quantity: {e}")
    
    print("========== MIGRATION 030: Complete ==========\n")


def downgrade() -> None:
    """Restore removed columns and revert rename"""
    
    print("\n========== MIGRATION 030: Downgrade ==========")
    
    # Step 1: Rename quantity → stock
    try:
        op.alter_column('products', 'quantity', new_column_name='stock')
        print("✓ Reverted: products.quantity → stock")
    except Exception:
        pass
    
    # Step 2: Restore removed columns
    columns_to_restore = [
        ('category_id', sa.Integer(), True),  # nullable=True
        ('category_name', sa.String(255), True),
        ('description', sa.Text(), True),
        ('image_url', sa.String(500), True),
        ('product_content_html', sa.Text(), True),
        ('is_active', sa.Boolean(), False),  # nullable=False, default=True
    ]
    
    for col_name, col_type, nullable in columns_to_restore:
        try:
            if col_name == 'is_active':
                op.add_column('products', sa.Column(col_name, col_type, nullable=nullable, server_default=sa.true()))
            else:
                op.add_column('products', sa.Column(col_name, col_type, nullable=nullable))
            print(f"✓ Restored column: products.{col_name}")
        except Exception as e:
            print(f"⚠️  Failed to restore {col_name}: {e}")
    
    print("========== MIGRATION 030: Downgrade Complete ==========\n")
