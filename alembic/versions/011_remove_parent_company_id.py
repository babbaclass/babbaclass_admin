"""Remove parent_company_id from companies

Revision ID: 011_remove_parent_company_id
Revises: 010_company_groups_and_grades
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '011_remove_parent_company_id'
down_revision = '010_company_groups_and_grades'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Only proceed if table exists and column exists
    if 'companies' in inspector.get_table_names():
        company_cols = {c['name'] for c in inspector.get_columns('companies')}
        if 'parent_company_id' in company_cols:
            # Drop foreign key constraints referencing parent_company_id
            fks = inspector.get_foreign_keys('companies')
            for fk in fks:
                if 'parent_company_id' in fk.get('constrained_columns', []):
                    try:
                        fk_name = fk.get('name')
                        if fk_name:
                            op.drop_constraint(fk_name, 'companies', type_='foreignkey')
                    except Exception:
                        # Some engines may not report name; attempt best-effort
                        pass
            # Drop indexes if any
            indexes = inspector.get_indexes('companies')
            for idx in indexes:
                if 'parent_company_id' in idx.get('column_names', []):
                    try:
                        idx_name = idx.get('name')
                        if idx_name:
                            op.drop_index(idx_name, table_name='companies')
                    except Exception:
                        pass
            # Finally drop the column
            try:
                op.drop_column('companies', 'parent_company_id')
            except Exception:
                pass


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if 'companies' in inspector.get_table_names():
        company_cols = {c['name'] for c in inspector.get_columns('companies')}
        if 'parent_company_id' not in company_cols:
            try:
                op.add_column('companies', sa.Column('parent_company_id', sa.Integer(), nullable=True))
                # Self-referencing FK (optional, as before)
                op.create_foreign_key(
                    constraint_name='fk_companies_parent_company_id',
                    source_table='companies',
                    referent_table='companies',
                    local_cols=['parent_company_id'],
                    remote_cols=['company_id']
                )
            except Exception:
                pass
