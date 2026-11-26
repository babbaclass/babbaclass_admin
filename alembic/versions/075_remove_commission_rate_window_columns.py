"""Remove columns from commission_rate_windows table

Revision ID: 075
Revises: 074
Create Date: 2025-12-18 12:00:00.000000

"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '075'
down_revision = '074'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get the connection and cursor
    conn = op.get_bind()
    
    # Get foreign key constraints for role_id and company_id
    query_text = text('''SELECT CONSTRAINT_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
               WHERE TABLE_NAME = 'commission_rate_windows' AND COLUMN_NAME IN ('role_id', 'company_id')
               AND CONSTRAINT_NAME != 'PRIMARY' ''')
    
    result = conn.execute(query_text)
    fks = result.fetchall()
    
    # Drop foreign key constraints first
    for fk in fks:
        try:
            op.execute(text(f'ALTER TABLE commission_rate_windows DROP FOREIGN KEY {fk[0]}'))
        except Exception:
            pass
    
    # Drop indexes if they exist
    try:
        op.execute(text('ALTER TABLE commission_rate_windows DROP INDEX ix_commission_rate_windows_role_id'))
    except Exception:
        pass
    
    try:
        op.execute(text('ALTER TABLE commission_rate_windows DROP INDEX ix_commission_rate_windows_company_id'))
    except Exception:
        pass
    
    # Drop the columns
    try:
        op.execute(text('ALTER TABLE commission_rate_windows DROP COLUMN role_id'))
    except Exception:
        pass
    
    try:
        op.execute(text('ALTER TABLE commission_rate_windows DROP COLUMN company_id'))
    except Exception:
        pass
    
    try:
        op.execute(text('ALTER TABLE commission_rate_windows DROP COLUMN max_teachers'))
    except Exception:
        pass
    
    try:
        op.execute(text('ALTER TABLE commission_rate_windows DROP COLUMN min_monthly_sales'))
    except Exception:
        pass


def downgrade() -> None:
    # This migration removes columns, so downgrade would try to add them back
    # However, since those columns are legacy and not used, we keep them removed
    # Uncomment the lines below if you really need to restore them
    pass
    # op.add_column('commission_rate_windows', sa.Column('company_id', sa.INTEGER(), nullable=True))
    # op.add_column('commission_rate_windows', sa.Column('role_id', sa.INTEGER(), nullable=True))
    # op.add_column('commission_rate_windows', sa.Column('min_monthly_sales', sa.INTEGER(), nullable=True))
    # op.add_column('commission_rate_windows', sa.Column('max_teachers', sa.INTEGER(), nullable=True))
    # op.create_index('ix_commission_rate_windows_company_id', 'commission_rate_windows', ['company_id'], unique=False)
    # op.create_index('ix_commission_rate_windows_role_id', 'commission_rate_windows', ['role_id'], unique=False)
    # op.create_foreign_key('commission_rate_windows_ibfk_3', 'commission_rate_windows', 'companies', ['company_id'], ['company_id'])
    # op.create_foreign_key('commission_rate_windows_ibfk_2', 'commission_rate_windows', 'roles', ['role_id'], ['role_id'])
