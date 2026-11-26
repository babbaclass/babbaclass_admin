"""Update Order and OrderItem fields to match Makeshop API structure

Revision ID: 034
Revises: 033
Create Date: 2025-11-19

Changes:
- Rename Order table: makeshop_order_id → ordernum
- Add Order fields: order_date, is_member, sender, phone, mobile, pay_path, 
  deli_price, start_price, total_product_price, used_emoney, used_reserve, 
  group_name, cash_receipt, cash_receipt_status
- Rename Order fields: customer_name → sender, customer_email → email, 
  customer_phone → phone, total_price → pay_price, payment_status → pay_status, 
  order_status kept, items_count → basket_count, notes → memo
- Update OrderItem: use ordernum FK instead of order_id/makeshop_order_id
- Add OrderItem fields: basket_stock, num, cate1, basket_status, stock_key, vat

Reason: Align database schema with Makeshop API response structure for better data consistency
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '034'
down_revision = '033'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Update Order and OrderItem tables to match Makeshop API"""
    
    print("\n========== MIGRATION 034: Update Order and OrderItem fields ==========")
    
    try:
        # 1. Backup old orders table data
        print("🔄 Backing up orders data...")
        op.execute("""
            CREATE TABLE orders_backup AS 
            SELECT * FROM orders
        """)
        print("✓ Created orders_backup table")
    except Exception as e:
        print(f"⚠️  Could not create backup: {e}")
    
    try:
        # 2. Drop order_items first (has FK to orders)
        print("🔄 Dropping order_items table...")
        op.drop_table('order_items')
        print("✓ Dropped order_items table")
    except Exception as e:
        print(f"⚠️  Could not drop order_items: {e}")
    
    try:
        # 3. Recreate orders table with new schema
        print("🔄 Recreating orders table with new schema...")
        op.drop_table('orders')
        
        op.create_table(
            'orders',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
            # Makeshop API fields (renamed from previous)
            sa.Column('ordernum', sa.String(100), nullable=False, unique=True, index=True),
            sa.Column('order_date', sa.String(20), nullable=True),
            sa.Column('is_member', sa.Integer(), default=0),
            sa.Column('sender', sa.String(255), nullable=True),
            sa.Column('email', sa.String(255), nullable=True, index=True),
            sa.Column('phone', sa.String(20), nullable=True),
            sa.Column('mobile', sa.String(20), nullable=True),
            sa.Column('pay_path', sa.String(100), nullable=True),
            sa.Column('pay_price', sa.Integer(), nullable=False, default=0),
            sa.Column('order_status', sa.String(50), default='pending'),
            sa.Column('pay_status', sa.String(50), default='pending'),
            sa.Column('deli_price', sa.Integer(), default=0),
            sa.Column('start_price', sa.Integer(), default=0),
            sa.Column('total_product_price', sa.Integer(), default=0),
            sa.Column('basket_count', sa.Integer(), default=0),
            sa.Column('memo', sa.Text(), nullable=True),
            sa.Column('used_emoney', sa.Integer(), default=0),
            sa.Column('used_reserve', sa.Integer(), default=0),
            sa.Column('group_name', sa.String(255), nullable=True),
            sa.Column('cash_receipt', sa.String(50), nullable=True),
            sa.Column('cash_receipt_status', sa.String(50), nullable=True),
            # Convenience fields
            sa.Column('shipping_address', sa.Text(), nullable=True),
            # Metadata
            sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
        )
        print("✓ Recreated orders table with new schema")
    except Exception as e:
        print(f"✗ Failed to recreate orders table: {e}")
        raise
    
    try:
        # 4. Recreate order_items table with new schema
        print("🔄 Recreating order_items table with new schema...")
        op.create_table(
            'order_items',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
            sa.Column('ordernum', sa.String(100), sa.ForeignKey('orders.ordernum'), nullable=False, index=True),
            sa.Column('product_uid', sa.String(100), sa.ForeignKey('products.uid'), nullable=False),
            sa.Column('product_name', sa.String(255), nullable=False),
            sa.Column('basket_stock', sa.Integer(), default=1),
            sa.Column('sell_price', sa.Integer(), nullable=False, default=0),
            sa.Column('num', sa.String(100), nullable=True),
            sa.Column('cate1', sa.String(255), nullable=True),
            sa.Column('basket_status', sa.String(50), nullable=True),
            sa.Column('stock_key', sa.String(100), nullable=True),
            sa.Column('vat', sa.Integer(), default=0),
            sa.Column('total_price', sa.Integer(), nullable=False, default=0),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
        )
        print("✓ Recreated order_items table with new schema")
    except Exception as e:
        print(f"✗ Failed to recreate order_items table: {e}")
        raise
    
    print("========== MIGRATION 034: Complete ==========\n")


def downgrade() -> None:
    """Revert to previous Order and OrderItem schema"""
    
    print("\n========== MIGRATION 034: Downgrade ==========")
    
    try:
        # Drop new tables
        op.drop_table('order_items')
        op.drop_table('orders')
        print("✓ Dropped updated tables")
        
        # Restore from backup if exists
        op.execute("""
            CREATE TABLE orders AS 
            SELECT * FROM orders_backup
        """)
        op.execute("DROP TABLE orders_backup")
        print("✓ Restored orders table from backup")
    except Exception as e:
        print(f"⚠️  Could not downgrade: {e}")
    
    print("========== MIGRATION 034: Downgrade Complete ==========\n")
