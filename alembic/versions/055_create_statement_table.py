"""create statement table

Revision ID: 055_create_statement_table
Revises: 054_add_statement_fields
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '055_create_statement_table'
down_revision = '054_add_statement_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Create statements table and add statement_id FK to settlements"""
    
    # 1. Create statements table
    op.create_table(
        'statements',
        sa.Column('statement_id', sa.Integer(), nullable=False),
        sa.Column('statement_number', sa.String(50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('total_commission', sa.Integer(), server_default='0'),
        sa.Column('deducted_tax', sa.Integer(), server_default='0'),
        sa.Column('deducted_local_tax', sa.Integer(), server_default='0'),
        sa.Column('net_amount', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='ISSUED'),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('statement_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ),
        sa.ForeignKeyConstraint(['company_id'], ['companies.company_id'], ),
        sa.UniqueConstraint('statement_number', name='uq_statement_number'),
        sa.UniqueConstraint('user_id', 'year', 'month', name='uq_user_statement_period')
    )
    
    # 2. Create indexes on statements table
    op.create_index(op.f('ix_statements_statement_id'), 'statements', ['statement_id'], unique=False)
    op.create_index(op.f('ix_statements_statement_number'), 'statements', ['statement_number'], unique=True)
    op.create_index(op.f('ix_statements_user_id'), 'statements', ['user_id'], unique=False)
    op.create_index(op.f('ix_statements_company_id'), 'statements', ['company_id'], unique=False)
    op.create_index(op.f('ix_statements_year'), 'statements', ['year'], unique=False)
    op.create_index(op.f('ix_statements_month'), 'statements', ['month'], unique=False)
    op.create_index(op.f('ix_statements_status'), 'statements', ['status'], unique=False)
    
    # 3. Add statement_id FK to settlements table
    op.add_column('settlements', sa.Column('statement_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_settlements_statement_id'), 'settlements', ['statement_id'], unique=False)
    op.create_foreign_key('fk_settlements_statement_id', 'settlements', 'statements', ['statement_id'], ['statement_id'])


def downgrade():
    """Remove statement_id FK from settlements and drop statements table"""
    
    # 1. Remove FK and column from settlements
    op.drop_constraint('fk_settlements_statement_id', 'settlements', type_='foreignkey')
    op.drop_index(op.f('ix_settlements_statement_id'), table_name='settlements')
    op.drop_column('settlements', 'statement_id')
    
    # 2. Drop indexes on statements table
    op.drop_index(op.f('ix_statements_status'), table_name='statements')
    op.drop_index(op.f('ix_statements_month'), table_name='statements')
    op.drop_index(op.f('ix_statements_year'), table_name='statements')
    op.drop_index(op.f('ix_statements_company_id'), table_name='statements')
    op.drop_index(op.f('ix_statements_user_id'), table_name='statements')
    op.drop_index(op.f('ix_statements_statement_number'), table_name='statements')
    op.drop_index(op.f('ix_statements_statement_id'), table_name='statements')
    
    # 3. Drop statements table
    op.drop_table('statements')
