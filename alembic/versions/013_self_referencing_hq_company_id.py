"""Introduce hq_company_id self-reference and drop company_branches

Revision ID: 013_hq_selfref
Revises: 012_company_type_and_branches
Create Date: 2025-11-07

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '013_hq_selfref'
down_revision = '012_company_type_and_branches'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    # 1) Add hq_company_id column if missing
    if 'companies' in tables:
        cols = {c['name'] for c in inspector.get_columns('companies')}
        if 'hq_company_id' not in cols:
            op.add_column('companies', sa.Column('hq_company_id', sa.Integer(), nullable=True))
            try:
                op.create_foreign_key(
                    constraint_name='fk_companies_hq_company_id',
                    source_table='companies',
                    referent_table='companies',
                    local_cols=['hq_company_id'],
                    remote_cols=['company_id']
                )
            except Exception:
                pass
            try:
                op.create_index('ix_companies_hq_company_id', 'companies', ['hq_company_id'])
            except Exception:
                pass

    # 2) Backfill from company_branches if present
    if 'company_branches' in tables and 'companies' in tables:
        try:
            op.execute(
                """
                UPDATE companies c
                JOIN company_branches cb ON c.company_id = cb.branch_company_id
                SET c.hq_company_id = cb.hq_company_id
                WHERE c.company_type = 'BRANCH'
                """
            )
        except Exception:
            pass

    # 3) Drop company_branches table
    if 'company_branches' in tables:
        try:
            op.drop_table('company_branches')
        except Exception:
            pass

    # 4) Optional: ensure HQ rows do not have hq_company_id set
    try:
        op.execute("UPDATE companies SET hq_company_id = NULL WHERE company_type = 'HQ'")
    except Exception:
        pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    # Recreate company_branches (minimal structure)
    if 'company_branches' not in tables and 'companies' in tables:
        op.create_table(
            'company_branches',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('hq_company_id', sa.Integer(), nullable=False),
            sa.Column('branch_company_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.ForeignKeyConstraint(['hq_company_id'], ['companies.company_id']),
            sa.ForeignKeyConstraint(['branch_company_id'], ['companies.company_id']),
            sa.PrimaryKeyConstraint('id'),
        )
        try:
            op.create_index('ix_company_branches_hq_company_id', 'company_branches', ['hq_company_id'])
            op.create_index('ix_company_branches_branch_company_id', 'company_branches', ['branch_company_id'])
        except Exception:
            pass

    # Populate mapping from hq_company_id
    if 'companies' in tables and 'company_branches' in tables:
        try:
            op.execute(
                """
                INSERT INTO company_branches (hq_company_id, branch_company_id)
                SELECT hq_company_id, company_id FROM companies
                WHERE company_type = 'BRANCH' AND hq_company_id IS NOT NULL
                """
            )
        except Exception:
            pass

    # Drop hq_company_id column
    if 'companies' in tables:
        cols = {c['name'] for c in inspector.get_columns('companies')}
        if 'hq_company_id' in cols:
            try:
                op.drop_index('ix_companies_hq_company_id', table_name='companies')
            except Exception:
                pass
            try:
                op.drop_constraint('fk_companies_hq_company_id', 'companies', type_='foreignkey')
            except Exception:
                pass
            try:
                op.drop_column('companies', 'hq_company_id')
            except Exception:
                pass
