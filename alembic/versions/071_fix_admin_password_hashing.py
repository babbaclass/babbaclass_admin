"""Fix admin user password hashing

Revision ID: 071
Revises: 070
Create Date: 2025-12-12

Fixes admin user password hashing to use bcrypt (consistent with existing system).
Deletes incorrectly hashed admin user and recreates with proper bcrypt hashing.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '071'
down_revision = '070'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 admin 사용자 삭제
    op.execute("DELETE FROM users WHERE login_id = 'admin'")
    
    # admin123의 bcrypt 해시값 생성 (migration 052와 동일한 방식)
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password_hash = pwd_context.hash("admin123")
    
    # 올바른 비밀번호 해시로 admin 사용자 재생성
    op.execute(
        "INSERT INTO users (login_id, name, password_hash, company_id, role_id, is_register, is_active) "
        f"VALUES ('admin', 'Administrator', '{password_hash}', 1, 1, true, true)"
    )


def downgrade() -> None:
    # Admin 사용자 삭제
    op.execute("DELETE FROM users WHERE login_id = 'admin'")
