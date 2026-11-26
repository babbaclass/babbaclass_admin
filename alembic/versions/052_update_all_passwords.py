"""update_all_passwords_to_default

Revision ID: 052_update_all_passwords
Revises: 051_update_reg_to_done
Create Date: 2025-11-27 02:20:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '052_update_all_passwords'
down_revision = '051_update_reg_to_done'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 모든 사용자의 비밀번호를 'babba1234'로 업데이트
    # 비밀번호는 bcrypt로 해싱되어 저장됨
    # passlib를 사용하여 'babba1234' 해싱: $2b$12$BmKW3.x7LkYdlNQn6xP.huP4vvJdDOGx7RfFu0vGMpWvE8vSczcVK
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash("babba1234")
    
    op.execute(f"UPDATE users SET password_hash = '{hashed_password}'")


def downgrade() -> None:
    # 롤백 시에는 비밀번호를 복원할 수 없으므로 아무것도 하지 않음
    pass
