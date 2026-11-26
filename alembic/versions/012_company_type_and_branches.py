"""Replace company_group_id with company_type and add company_branches

Revision ID: 012_company_type_and_branches
Revises: 011_remove_parent_company_id
Create Date: 2025-11-07

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '012_company_type_and_branches'
down_revision = '011_remove_parent_company_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    table_names = set(inspector.get_table_names())

    # 1) Add company_type to companies and backfill from company_groups if present
    if 'companies' in table_names:
        cols = {c['name'] for c in inspector.get_columns('companies')}
        if 'company_type' not in cols:
            op.add_column('companies', sa.Column('company_type', sa.String(50), nullable=True))
        # Backfill from company_groups if both tables/columns present
        if 'company_groups' in table_names and 'company_group_id' in cols:
            try:
                op.execute(
                    """
                    UPDATE companies c
                    JOIN company_groups g ON c.company_group_id = g.company_group_id
                    SET c.company_type = g.code
                    """
                )
            except Exception:
                pass
        # Default remaining NULLs to 'HQ'
        try:
            op.execute("UPDATE companies SET company_type = 'HQ' WHERE company_type IS NULL OR company_type = ''")
        except Exception:
            pass
        # Make non-nullable if possible
        try:
            op.alter_column('companies', 'company_type', existing_type=sa.String(50), nullable=False)
        except Exception:
            pass
        # Create index
        try:
            op.create_index('ix_companies_company_type', 'companies', ['company_type'])
        except Exception:
            pass

    # 2) Drop FK/index on company_group_id then drop column and drop company_groups table
    if 'companies' in table_names:
        cols = {c['name'] for c in inspector.get_columns('companies')}
        if 'company_group_id' in cols:
            # drop FKs referencing company_group_id
            for fk in inspector.get_foreign_keys('companies'):
                if 'company_group_id' in fk.get('constrained_columns', []):
                    fk_name = fk.get('name')
                    if fk_name:
                        try:
                            op.drop_constraint(fk_name, 'companies', type_='foreignkey')
                        except Exception:
                            pass
            # drop indexes on company_group_id
            for idx in inspector.get_indexes('companies'):
                if 'company_group_id' in idx.get('column_names', []):
                    idx_name = idx.get('name')
                    if idx_name:
                        try:
                            op.drop_index(idx_name, table_name='companies')
                        except Exception:
                            pass
            # drop column
            try:
                op.drop_column('companies', 'company_group_id')
            except Exception:
                pass

    if 'company_groups' in table_names:
        try:
            op.drop_table('company_groups')
        except Exception:
            pass

    # 3) Create company_branches table
    if 'company_branches' not in table_names:
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


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Drop company_branches
    if 'company_branches' in inspector.get_table_names():
        try:
            op.drop_table('company_branches')
        except Exception:
            pass

    # Recreate company_groups table (minimal) and column if needed
    if 'companies' in inspector.get_table_names():
        cols = {c['name'] for c in inspector.get_columns('companies')}
        if 'company_group_id' not in cols:
            op.add_column('companies', sa.Column('company_group_id', sa.Integer(), nullable=True))
            try:
                op.create_foreign_key(
                    constraint_name='fk_companies_company_group_id',
                    source_table='companies',
                    referent_table='company_groups',
                    local_cols=['company_group_id'],
                    remote_cols=['company_group_id']
                )
            except Exception:
                pass
        # Remove company_type column
        if 'company_type' in cols:
            try:
                op.drop_index('ix_companies_company_type', table_name='companies')
            except Exception:
                pass
            try:
                op.drop_column('companies', 'company_type')
            except Exception:
                pass

    if 'company_groups' not in inspector.get_table_names():
        op.create_table(
            'company_groups',
            sa.Column('company_group_id', sa.Integer(), nullable=False),
            sa.Column('code', sa.String(50), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('company_group_id'),
        )
        try:
            op.create_index('ix_company_groups_code', 'company_groups', ['code'])
            op.create_index('ix_company_groups_name', 'company_groups', ['name'])
        except Exception:
            pass
