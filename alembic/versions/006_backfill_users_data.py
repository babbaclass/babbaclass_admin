"""Backfill users data to align with new schema defaults

Revision ID: 006_backfill_users_data
Revises: 005_align_users_schema
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

# revision identifiers, used by Alembic.
revision = '006_backfill_users_data'
down_revision = '005_align_users_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn: Connection = op.get_bind()

    insp = sa.inspect(conn)
    tables = set(insp.get_table_names())
    if 'users' not in tables:
        return

    user_cols = {c['name'] for c in insp.get_columns('users')}

    # 1) Ensure default Company (HQ / 본사)
    if 'companies' in tables:
        result = conn.execute(sa.text("SELECT company_id FROM companies WHERE company_group=:g AND name=:n LIMIT 1"),
                              {"g": "HQ", "n": "본사"}).fetchone()
        if result is None:
            conn.execute(sa.text(
                "INSERT INTO companies (company_group, name, is_active) VALUES (:g, :n, 1)"
            ), {"g": "HQ", "n": "본사"})
            result = conn.execute(sa.text("SELECT company_id FROM companies WHERE company_group=:g AND name=:n LIMIT 1"),
                                  {"g": "HQ", "n": "본사"}).fetchone()
        default_company_id = int(result[0]) if result else None
    else:
        default_company_id = None

    # 2) Ensure default Role (본사 사용자)
    if 'roles' in tables:
        r = conn.execute(sa.text("SELECT role_id FROM roles WHERE role_name=:rn LIMIT 1"),
                         {"rn": "본사 사용자"}).fetchone()
        if r is None:
            conn.execute(sa.text(
                "INSERT INTO roles (role_name, description, is_active) VALUES (:rn, :desc, 1)"
            ), {"rn": "본사 사용자", "desc": "기본 사용자 역할"})
            r = conn.execute(sa.text("SELECT role_id FROM roles WHERE role_name=:rn LIMIT 1"),
                             {"rn": "본사 사용자"}).fetchone()
        default_role_id = int(r[0]) if r else None
    else:
        default_role_id = None

    # 3) Backfill name from username if missing
    if 'name' in user_cols:
        # name NULL/empty and username present
        if 'username' in user_cols:
            conn.execute(sa.text(
                "UPDATE users SET name = username WHERE (name IS NULL OR name = '') AND username IS NOT NULL"
            ))

    # 4) Backfill is_active where NULL
    if 'is_active' in user_cols:
        conn.execute(sa.text("UPDATE users SET is_active = 1 WHERE is_active IS NULL"))

    # 5) Set company_id / role_id defaults where NULL
    if default_company_id is not None and 'company_id' in user_cols:
        conn.execute(sa.text("UPDATE users SET company_id = :cid WHERE company_id IS NULL"),
                     {"cid": default_company_id})
    if default_role_id is not None and 'role_id' in user_cols:
        conn.execute(sa.text("UPDATE users SET role_id = :rid WHERE role_id IS NULL"),
                     {"rid": default_role_id})

    # Note: We do not attempt to backfill email or password_hash automatically for security reasons.


def downgrade() -> None:
    # Non-destructive; leave data as improved.
    pass
