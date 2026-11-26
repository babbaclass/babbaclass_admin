"""simplify statement status to is_confirmed

Revision ID: 056_simplify_statement_status
Revises: 055_create_statement_table
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '056_simplify_statement_status'
down_revision = '055_create_statement_table'
branch_labels = None
depends_on = None


def upgrade():
    """Replace status, approved_at, paid_at with is_confirmed"""
    
    # 1. Add is_confirmed column
    op.add_column('statements', sa.Column('is_confirmed', sa.Boolean(), nullable=False, server_default='0'))
    op.create_index(op.f('ix_statements_is_confirmed'), 'statements', ['is_confirmed'], unique=False)
    
    # 2. Migrate existing data: CONFIRMED/APPROVED/PAID -> True, ISSUED -> False
    op.execute("UPDATE statements SET is_confirmed = TRUE WHERE status IN ('CONFIRMED', 'APPROVED', 'PAID')")
    op.execute("UPDATE statements SET is_confirmed = FALSE WHERE status = 'ISSUED'")
    
    # 3. Drop old columns
    op.drop_index('ix_statements_status', table_name='statements')
    op.drop_column('statements', 'status')
    op.drop_column('statements', 'approved_at')
    op.drop_column('statements', 'paid_at')


def downgrade():
    """Restore status, approved_at, paid_at from is_confirmed"""
    
    # 1. Add back old columns
    op.add_column('statements', sa.Column('status', sa.String(20), nullable=False, server_default='ISSUED'))
    op.add_column('statements', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('statements', sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_statements_status', 'statements', ['status'], unique=False)
    
    # 2. Migrate data back: True -> CONFIRMED, False -> ISSUED
    op.execute("UPDATE statements SET status = 'CONFIRMED' WHERE is_confirmed = TRUE")
    op.execute("UPDATE statements SET status = 'ISSUED' WHERE is_confirmed = FALSE")
    
    # 3. Drop is_confirmed
    op.drop_index(op.f('ix_statements_is_confirmed'), table_name='statements')
    op.drop_column('statements', 'is_confirmed')
