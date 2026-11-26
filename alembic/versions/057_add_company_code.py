"""add company code field

Revision ID: 057_add_company_code
Revises: 056_simplify_statement_status
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '057_add_company_code'
down_revision = '056_simplify_statement_status'
branch_labels = None
depends_on = None


def upgrade():
    """Add code field to companies and make name nullable"""
    
    from sqlalchemy import inspect
    from alembic import op
    
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('companies')]
    
    # 1. Add code column only if it doesn't exist
    if 'code' not in columns:
        op.add_column('companies', sa.Column('code', sa.String(50), nullable=True))
        
        # 2. Generate codes for existing companies based on company_id
        op.execute("""
            UPDATE companies 
            SET code = CONCAT(
                CASE company_type 
                    WHEN 'HQ' THEN 'HQ' 
                    WHEN 'BRANCH' THEN 'BR' 
                    ELSE 'CO' 
                END,
                LPAD(company_id, 3, '0')
            )
            WHERE code IS NULL
        """)
        
        # 3. Make code NOT NULL and add unique constraint
        op.alter_column('companies', 'code',
                        existing_type=sa.String(50),
                        nullable=False)
        op.create_index(op.f('ix_companies_code'), 'companies', ['code'], unique=True)
    
    # 4. Make name nullable
    op.alter_column('companies', 'name',
                    existing_type=sa.String(255),
                    nullable=True)


def downgrade():
    """Remove code field and restore name as required"""
    
    from sqlalchemy import inspect
    from alembic import op
    
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('companies')]
    
    # 1. Make name required again (fill empty names first)
    op.execute("UPDATE companies SET name = CONCAT('Company ', company_id) WHERE name IS NULL OR name = ''")
    op.alter_column('companies', 'name',
                    existing_type=sa.String(255),
                    nullable=False)
    
    # 2. Drop code column and index only if they exist
    if 'code' in columns:
        op.drop_index(op.f('ix_companies_code'), table_name='companies')
        op.drop_column('companies', 'code')
