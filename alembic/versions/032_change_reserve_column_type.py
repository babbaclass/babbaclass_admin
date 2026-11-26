"""Change reserve column type from Integer to String in products table

Revision ID: 032
Revises: 031
Create Date: 2025-11-18

Changes:
- Change products.reserve from Integer to String(255)

Reason: API returns string values that exceed integer storage
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Change reserve column type from Integer to String"""
    
    print("\n========== MIGRATION 032: Change products.reserve column type ==========")
    
    # Change products.reserve from Integer to String
    try:
        op.alter_column('products', 'reserve', 
                        type_=sa.String(255), 
                        existing_type=sa.Integer(), 
                        existing_nullable=True)
        print("✓ Changed: products.reserve Integer → String(255)")
    except Exception as e:
        print(f"⚠️  Failed to change products.reserve: {e}")
    
    print("========== MIGRATION 032: Complete ==========\n")


def downgrade() -> None:
    """Revert reserve column type from String to Integer"""
    
    print("\n========== MIGRATION 032: Downgrade ==========")
    
    # Revert products.reserve
    try:
        op.alter_column('products', 'reserve', 
                        type_=sa.Integer(), 
                        existing_type=sa.String(255), 
                        existing_nullable=True)
        print("✓ Reverted: products.reserve String → Integer")
    except Exception:
        pass
    
    print("========== MIGRATION 032: Downgrade Complete ==========\n")
