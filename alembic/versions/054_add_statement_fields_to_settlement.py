"""add statement fields to settlement

Revision ID: 054_add_statement_fields
Revises: 053_convert_to_is_register
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '054_add_statement_fields'
down_revision = '053_convert_to_is_register'
branch_labels = None
depends_on = None


def upgrade():
    """Add statement-related fields to settlements table"""
    # Add statement_number column
    op.add_column('settlements', sa.Column('statement_number', sa.String(50), nullable=True))
    op.create_index(op.f('ix_settlements_statement_number'), 'settlements', ['statement_number'], unique=True)
    
    # Add statement_status column
    op.add_column('settlements', sa.Column('statement_status', sa.String(20), nullable=False, server_default='DRAFT'))
    op.create_index(op.f('ix_settlements_statement_status'), 'settlements', ['statement_status'], unique=False)
    
    # Add statement_issued_at column
    op.add_column('settlements', sa.Column('statement_issued_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add statement_confirmed_at column
    op.add_column('settlements', sa.Column('statement_confirmed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    """Remove statement-related fields from settlements table"""
    op.drop_index(op.f('ix_settlements_statement_status'), table_name='settlements')
    op.drop_index(op.f('ix_settlements_statement_number'), table_name='settlements')
    op.drop_column('settlements', 'statement_confirmed_at')
    op.drop_column('settlements', 'statement_issued_at')
    op.drop_column('settlements', 'statement_status')
    op.drop_column('settlements', 'statement_number')
