"""Add organization models (Company, Role, User)

Revision ID: 003_organization_models
Revises:
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_organization_models'
down_revision = None
branch_labels = None
depends_on = None


def _ensure_indexes(conn, table_name: str, indexes: list[tuple[str, list[str]]]) -> None:
    inspector = sa.inspect(conn)
    existing = {idx['name'] for idx in inspector.get_indexes(table_name)}
    cols_present = {c['name'] for c in inspector.get_columns(table_name)}
    for idx_name, cols in indexes:
        # Create index only if all columns exist
        if all(c in cols_present for c in cols):
            if idx_name not in existing:
                op.create_index(idx_name, table_name, cols)


def upgrade() -> None:
    """Create organization tables: Company, Role, User (idempotent)"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # grades (for fresh setup)
    if 'grades' not in inspector.get_table_names():
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
        _ensure_indexes(conn, 'grades', [
            ('ix_grades_grade_name', ['grade_name']),
        ])

    # companies
    if 'companies' not in inspector.get_table_names():
        op.create_table(
            'companies',
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('company_type', sa.String(50), nullable=False),
            sa.Column('hq_company_id', sa.Integer(), nullable=True),
            sa.Column('grade_id', sa.Integer(), nullable=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('address', sa.String(500), nullable=True),
            sa.Column('phone_number', sa.String(20), nullable=True),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.ForeignKeyConstraint(['grade_id'], ['grades.grade_id']),
            sa.ForeignKeyConstraint(['hq_company_id'], ['companies.company_id']),
            sa.PrimaryKeyConstraint('company_id'),
        )
        _ensure_indexes(conn, 'companies', [
            ('ix_companies_company_type', ['company_type']),
            ('ix_companies_hq_company_id', ['hq_company_id']),
            ('ix_companies_grade_id', ['grade_id']),
            ('ix_companies_name', ['name']),
        ])
    else:
        _ensure_indexes(conn, 'companies', [
            ('ix_companies_company_type', ['company_type']) if 'company_type' in {c['name'] for c in inspector.get_columns('companies')} else ('noop', []),
            ('ix_companies_hq_company_id', ['hq_company_id']) if 'hq_company_id' in {c['name'] for c in inspector.get_columns('companies')} else ('noop', []),
            ('ix_companies_grade_id', ['grade_id']) if 'grade_id' in {c['name'] for c in inspector.get_columns('companies')} else ('noop', []),
            ('ix_companies_name', ['name']),
        ])

    # roles
    if 'roles' not in inspector.get_table_names():
        op.create_table(
            'roles',
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.Column('role_name', sa.String(100), nullable=False, unique=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.PrimaryKeyConstraint('role_id'),
        )
        _ensure_indexes(conn, 'roles', [
            ('ix_roles_role_name', ['role_name']),
        ])
    else:
        _ensure_indexes(conn, 'roles', [
            ('ix_roles_role_name', ['role_name']),
        ])

    # users
    if 'users' not in inspector.get_table_names():
        op.create_table(
            'users',
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('email', sa.String(255), nullable=False, unique=True),
            sa.Column('password_hash', sa.String(255), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.Column('is_active', sa.Boolean(), default=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.ForeignKeyConstraint(['company_id'], ['companies.company_id']),
            sa.ForeignKeyConstraint(['role_id'], ['roles.role_id']),
            sa.PrimaryKeyConstraint('user_id'),
        )
        _ensure_indexes(conn, 'users', [
            ('ix_users_name', ['name']),
            ('ix_users_email', ['email']),
        ])
    else:
        # Ensure required columns exist (migrate legacy schema)
        user_cols = {c['name'] for c in inspector.get_columns('users')}
        # Add name column if missing; backfill from username when available
        if 'name' not in user_cols:
            op.add_column('users', sa.Column('name', sa.String(255), nullable=True))
            user_cols.add('name')
            if 'username' in user_cols:
                op.execute("UPDATE users SET name = username WHERE (name IS NULL OR name = '') AND username IS NOT NULL")
            # Make non-null if possible (will succeed only if no NULLs remain)
            try:
                op.alter_column('users', 'name', existing_type=sa.String(255), nullable=False)
            except Exception:
                # Leave nullable if data prevents tightening constraint
                pass
        # Ensure email column exists
        if 'email' not in user_cols:
            op.add_column('users', sa.Column('email', sa.String(255), nullable=True))
        _ensure_indexes(conn, 'users', [
            ('ix_users_name', ['name']),
            ('ix_users_email', ['email']),
        ])

    # company_branches 제거: 자체참조(hq_company_id) 사용


def downgrade() -> None:
    """Drop organization tables (if exist)"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    for tbl in ['users', 'roles', 'companies']:
        if tbl in inspector.get_table_names():
            op.drop_table(tbl)
