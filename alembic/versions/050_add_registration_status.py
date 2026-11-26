"""update_registration_status_values

Revision ID: 050_add_reg_status
Revises: 049_remove_commission_tax_fields
Create Date: 2025-11-27 00:10:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '050_add_registration_status'
down_revision = '049_remove_commission_tax_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # registration_status 컬럼이 없으면 추가, 있으면 데이터 업데이트
    from sqlalchemy import inspect
    import sqlalchemy as sa
    
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    if 'registration_status' not in columns:
        # 컬럼 추가
        op.add_column('users', sa.Column('registration_status', sa.String(20), nullable=False, server_default='DONE'))
        op.create_index(op.f('ix_users_registration_status'), 'users', ['registration_status'], unique=False)
    else:
        # 기존 데이터 업데이트
        op.execute("UPDATE users SET registration_status = 'DONE' WHERE registration_status = '가입 완료'")
        op.execute("UPDATE users SET registration_status = 'NOT_YET' WHERE registration_status = '가입 전'")


def downgrade() -> None:
    # 롤백 시 컬럼 삭제
    op.drop_index(op.f('ix_users_registration_status'), table_name='users')
    op.drop_column('users', 'registration_status')
