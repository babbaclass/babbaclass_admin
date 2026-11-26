"""Align users table schema to User model

Revision ID: 005_align_users_schema
Revises: 004_merge_heads
Create Date: 2025-11-06

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '005_align_users_schema'
down_revision = '004_merge_heads'
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    insp = sa.inspect(conn)
    return name in insp.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    insp: Inspector = sa.inspect(conn)

    if not _table_exists(conn, 'users'):
        # If users table doesn't exist, nothing to align here
        return

    cols = {c['name']: c for c in insp.get_columns('users')}

    # 1) Ensure primary key column name is user_id
    if 'user_id' not in cols and 'id' in cols:
        # Add user_id nullable first
        op.add_column('users', sa.Column('user_id', sa.Integer(), nullable=True))
        # Backfill user_id from id
        op.execute('UPDATE users SET user_id = id')
        # Drop existing primary key (MySQL uses name PRIMARY)
        try:
            op.drop_constraint('PRIMARY', 'users', type_='primary')
        except Exception:
            # No primary key found or different name; ignore
            pass
        # Set NOT NULL and create new primary key
        op.alter_column('users', 'user_id', existing_type=sa.Integer(), nullable=False)
        try:
            op.create_primary_key('pk_users', 'users', ['user_id'])
        except Exception:
            # Fallback for MySQL naming
            op.execute('ALTER TABLE users ADD PRIMARY KEY (user_id)')
        # Drop old id column
        op.drop_column('users', 'id')
        cols = {c['name']: c for c in insp.get_columns('users')}

    # 2) Ensure required columns exist
    if 'name' not in cols:
        op.add_column('users', sa.Column('name', sa.String(255), nullable=True))
        # If legacy username exists, backfill
        if 'username' in cols:
            op.execute("UPDATE users SET name = username WHERE (name IS NULL OR name = '') AND username IS NOT NULL")
        # Try to enforce NOT NULL if possible
        try:
            op.alter_column('users', 'name', existing_type=sa.String(255), nullable=False)
        except Exception:
            pass
        cols = {c['name']: c for c in insp.get_columns('users')}

    if 'email' not in cols:
        op.add_column('users', sa.Column('email', sa.String(255), nullable=True))
        cols = {c['name']: c for c in insp.get_columns('users')}

    if 'password_hash' not in cols:
        op.add_column('users', sa.Column('password_hash', sa.String(255), nullable=True))
        cols = {c['name']: c for c in insp.get_columns('users')}

    if 'company_id' not in cols:
        op.add_column('users', sa.Column('company_id', sa.Integer(), nullable=True))
        cols = {c['name']: c for c in insp.get_columns('users')}

    if 'role_id' not in cols:
        op.add_column('users', sa.Column('role_id', sa.Integer(), nullable=True))
        cols = {c['name']: c for c in insp.get_columns('users')}

    if 'is_active' not in cols:
        op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('1')))
        cols = {c['name']: c for c in insp.get_columns('users')}

    # 3) Ensure indexes/uniqueness
    indexes = {idx['name']: idx for idx in insp.get_indexes('users')}

    # Ensure email index/unique, only if no duplicates
    try:
        dup = conn.execute(sa.text("SELECT email, COUNT(*) as c FROM users WHERE email IS NOT NULL GROUP BY email HAVING c > 1 LIMIT 1")).fetchone()
        if dup is None:
            # No duplicates; ensure unique index
            if 'ux_users_email' not in indexes:
                op.create_index('ux_users_email', 'users', ['email'], unique=True)
        else:
            # Duplicates exist; create non-unique index if missing
            if 'ix_users_email' not in indexes:
                op.create_index('ix_users_email', 'users', ['email'], unique=False)
    except Exception:
        # On any error, at least try to create non-unique index if missing
        if 'ix_users_email' not in indexes:
            op.create_index('ix_users_email', 'users', ['email'], unique=False)

    # Ensure name index
    if 'ix_users_name' not in indexes and 'name' in cols:
        op.create_index('ix_users_name', 'users', ['name'], unique=False)


def downgrade() -> None:
    # No destructive downgrade: leave schema as aligned
    pass
