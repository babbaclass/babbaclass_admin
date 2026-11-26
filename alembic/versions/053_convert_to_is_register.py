"""convert_registration_status_to_is_register

Revision ID: 053_convert_to_is_register
Revises: 052_update_all_passwords
Create Date: 2025-11-27 02:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '053_convert_to_is_register'
down_revision = '052_update_all_passwords'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 새 컬럼 is_register 추가 (기본값 True)
    op.add_column('users', sa.Column('is_register', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')))
    
    # 2. 기존 데이터 마이그레이션
    # DONE → True, NOT_YET → False
    op.execute("UPDATE users SET is_register = TRUE WHERE registration_status = 'DONE'")
    op.execute("UPDATE users SET is_register = FALSE WHERE registration_status = 'NOT_YET'")
    
    # 3. 인덱스 생성
    op.create_index(op.f('ix_users_is_register'), 'users', ['is_register'], unique=False)
    
    # 4. 기존 registration_status 컬럼 삭제
    op.drop_index('ix_users_registration_status', table_name='users')
    op.drop_column('users', 'registration_status')


def downgrade() -> None:
    # 1. registration_status 컬럼 추가
    op.add_column('users', sa.Column('registration_status', sa.String(20), nullable=False, server_default=sa.text("'DONE'")))
    op.create_index('ix_users_registration_status', 'users', ['registration_status'], unique=False)
    
    # 2. 기존 데이터 복원
    op.execute("UPDATE users SET registration_status = 'DONE' WHERE is_register = TRUE")
    op.execute("UPDATE users SET registration_status = 'NOT_YET' WHERE is_register = FALSE")
    
    # 3. is_register 컬럼 삭제
    op.drop_index(op.f('ix_users_is_register'), table_name='users')
    op.drop_column('users', 'is_register')
