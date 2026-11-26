"""Create admin user account

Revision ID: 070
Revises: 069
Create Date: 2025-12-12

Creates default admin user account with:
- login_id: admin
- password: admin123 (hashed with passlib bcrypt - 기존 시스템과 동일)
- role_id: 1 (admin role)
- company_id: 1 (HQ company)

비밀번호는 passlib의 bcrypt 함수로 해시됩니다.
기존의 migration 052에서 사용한 방식과 동일합니다.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '070'
down_revision = '069'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # admin123의 bcrypt 해시값 생성 (migration 052와 동일한 방식)
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password_hash = pwd_context.hash("admin123")
    
    # admin 사용자 생성
    op.execute(
        "INSERT INTO users (login_id, name, password_hash, company_id, role_id, is_register, is_active) "
        f"VALUES ('admin', 'Administrator', '{password_hash}', 1, 1, true, true)"
    )


def downgrade() -> None:
    # Admin 사용자 삭제
    op.execute("DELETE FROM users WHERE login_id = 'admin'")
