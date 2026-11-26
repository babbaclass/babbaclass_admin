"""Rename stock column to quantity in products table

Revision ID: 031
Revises: 030
Create Date: 2025-11-18

Changes:
- Rename stock → quantity (matches Makeshop API field name)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename stock to quantity"""
    
    print("\n========== MIGRATION 031: Rename stock to quantity ==========")
    
    try:
        # MySQL requires the full type specification for ALTER COLUMN
        op.alter_column('products', 'stock', new_column_name='quantity', 
                        existing_type=sa.Integer(), existing_nullable=True)
        print("✓ Renamed: products.stock → quantity")
    except Exception as e:
        print(f"✗ Failed to rename stock to quantity: {e}")
        raise
    
    print("========== MIGRATION 031: Complete ==========\n")


def downgrade() -> None:
    """Revert rename: quantity to stock"""
    
    print("\n========== MIGRATION 031: Downgrade ==========")
    
    try:
        op.alter_column('products', 'quantity', new_column_name='stock',
                        existing_type=sa.Integer(), existing_nullable=True)
        print("✓ Reverted: products.quantity → stock")
    except Exception:
        pass
    
    print("========== MIGRATION 031: Downgrade Complete ==========\n")
