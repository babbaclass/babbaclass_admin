"""
Add company_groups and grades; migrate companies.company_group -> company_group_id; add companies.grade_id

Revision ID: 010_company_groups_and_grades
Revises: 009_remove_username_column
Create Date: 2025-11-06
"""
from alembic import op
import sqlalchemy as sa

revision = '010_company_groups_and_grades'
down_revision = '009_remove_username_column'
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    insp = sa.inspect(conn)
    return name in insp.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # 1) Create company_groups if not exists
    if not _table_exists(conn, 'company_groups'):
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
        op.create_index('ix_company_groups_code', 'company_groups', ['code'], unique=True)
        op.create_index('ix_company_groups_name', 'company_groups', ['name'])

    # Seed defaults HQ/BRANCH
    # upsert-like: insert if missing
    for code, name in [('HQ', '본사'), ('BRANCH', '지사')]:
        existing = conn.execute(sa.text(
            "SELECT company_group_id FROM company_groups WHERE code = :code"
        ), {"code": code}).fetchone()
        if not existing:
            conn.execute(sa.text(
                "INSERT INTO company_groups(code, name, is_active) VALUES(:code, :name, 1)"
            ), {"code": code, "name": name})

    # 2) Create grades if not exists
    if not _table_exists(conn, 'grades'):
        op.create_table(
            'grades',
            sa.Column('grade_id', sa.Integer(), nullable=False),
            sa.Column('grade_name', sa.String(100), nullable=False),
            sa.Column('display_order', sa.Integer(), nullable=True, server_default='0'),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('grade_id'),
        )
        op.create_index('ix_grades_grade_name', 'grades', ['grade_name'], unique=True)

    # 3) Alter companies: add company_group_id, grade_id
    company_cols = {c['name'] for c in insp.get_columns('companies')} if _table_exists(conn, 'companies') else set()
    if 'companies' in insp.get_table_names():
        if 'company_group_id' not in company_cols:
            op.add_column('companies', sa.Column('company_group_id', sa.Integer(), nullable=True))
        if 'grade_id' not in company_cols:
            op.add_column('companies', sa.Column('grade_id', sa.Integer(), nullable=True))

        # Backfill company_group_id from legacy companies.company_group
        if 'company_group' in company_cols:
            # Map HQ/BRANCH
            conn.execute(sa.text(
                """
                UPDATE companies c
                JOIN company_groups g ON g.code = c.company_group
                SET c.company_group_id = g.company_group_id
                WHERE c.company_group_id IS NULL
                """
            ))
        
        # If still NULL, default to HQ
        conn.execute(sa.text(
            """
            UPDATE companies c
            JOIN company_groups g ON g.code = 'HQ'
            SET c.company_group_id = g.company_group_id
            WHERE c.company_group_id IS NULL
            """
        ))

        # Add FKs and indexes if not present
        # MySQL lacks simple IF NOT EXISTS for add constraint; try/except is fine
        try:
            op.create_foreign_key(None, 'companies', 'company_groups', ['company_group_id'], ['company_group_id'])
        except Exception:
            pass
        try:
            op.create_foreign_key(None, 'companies', 'grades', ['grade_id'], ['grade_id'])
        except Exception:
            pass
        try:
            op.create_index('ix_companies_company_group_id', 'companies', ['company_group_id'])
        except Exception:
            pass
        try:
            op.create_index('ix_companies_grade_id', 'companies', ['grade_id'])
        except Exception:
            pass

        # Make company_group_id NOT NULL if possible
        try:
            op.alter_column('companies', 'company_group_id', existing_type=sa.Integer(), nullable=False)
        except Exception:
            pass

        # Drop legacy column if exists
        company_cols = {c['name'] for c in insp.get_columns('companies')}
        if 'company_group' in company_cols:
            # Drop index if existed
            try:
                conn.execute(sa.text("ALTER TABLE companies DROP INDEX ix_companies_company_group"))
            except Exception:
                pass
            conn.execute(sa.text("ALTER TABLE companies DROP COLUMN `company_group`"))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)

    # Add company_group back (nullable) if needed
    if 'companies' in insp.get_table_names():
        cols = {c['name'] for c in insp.get_columns('companies')}
        if 'company_group' not in cols:
            op.add_column('companies', sa.Column('company_group', sa.String(50), nullable=True))
        # Try to backfill from group code
        conn.execute(sa.text(
            """
            UPDATE companies c
            LEFT JOIN company_groups g ON g.company_group_id = c.company_group_id
            SET c.company_group = g.code
            WHERE c.company_group IS NULL
            """
        ))
        # Drop FKs and columns
        try:
            conn.execute(sa.text("ALTER TABLE companies DROP FOREIGN KEY companies_ibfk_company_group_id"))
        except Exception:
            pass
        try:
            conn.execute(sa.text("ALTER TABLE companies DROP FOREIGN KEY companies_ibfk_grade_id"))
        except Exception:
            pass
        try:
            conn.execute(sa.text("ALTER TABLE companies DROP COLUMN `company_group_id`"))
        except Exception:
            pass
        try:
            conn.execute(sa.text("ALTER TABLE companies DROP COLUMN `grade_id`"))
        except Exception:
            pass

    # Drop master tables (optional)
    if _table_exists(conn, 'grades'):
        op.drop_table('grades')
    if _table_exists(conn, 'company_groups'):
        op.drop_table('company_groups')
