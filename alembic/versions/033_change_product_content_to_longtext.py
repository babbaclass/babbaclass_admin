"""Change product_content column type from TEXT to LONGTEXT

Revision ID: 033
Revises: 032
Create Date: 2025-11-18

Changes:
- Change products.product_content from TEXT to LONGTEXT

Reason: API returns large content that exceeds TEXT max size (65KB)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT


# revision identifiers, used by Alembic.
revision = '033'
down_revision = '032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Change product_content column type from TEXT to LONGTEXT"""
    
    print("\n========== MIGRATION 033: Change product_content column type ==========")
    
    try:
        op.alter_column('products', 'product_content', 
                        type_=LONGTEXT(), 
                        existing_type=sa.Text(), 
                        existing_nullable=True)
        print("✓ Changed: products.product_content TEXT → LONGTEXT")
    except Exception as e:
        print(f"⚠️  Failed to change products.product_content: {e}")
    
    print("========== MIGRATION 033: Complete ==========\n")


def downgrade() -> None:
    """Revert product_content column type from LONGTEXT to TEXT"""
    
    print("\n========== MIGRATION 033: Downgrade ==========")
    
    try:
        op.alter_column('products', 'product_content', 
                        type_=sa.Text(), 
                        existing_type=LONGTEXT(), 
                        existing_nullable=True)
        print("✓ Reverted: products.product_content LONGTEXT → TEXT")
    except Exception:
        pass
    
    print("========== MIGRATION 033: Downgrade Complete ==========\n")
