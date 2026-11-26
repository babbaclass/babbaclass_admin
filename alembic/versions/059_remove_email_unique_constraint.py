"""remove unique constraint from email

Revision ID: 059
Revises: 058_make_login_id_nullable
Create Date: 2025-01-15

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '059'
down_revision = '058_make_login_id_nullable'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    import sqlalchemy as sa
    
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # 모든 email 관련 인덱스/제약 확인 및 제거
    indexes = inspector.get_indexes('users')
    for idx in indexes:
        if 'email' in idx['column_names'] and idx['name']:
            try:
                op.drop_index(idx['name'], table_name='users')
                print(f"Dropped index: {idx['name']}")
            except Exception as e:
                print(f"Failed to drop index {idx['name']}: {e}")
    
    # unique 제약 제거 시도
    unique_constraints = inspector.get_unique_constraints('users')
    for constraint in unique_constraints:
        if 'email' in constraint['column_names'] and constraint['name']:
            try:
                op.drop_constraint(constraint['name'], 'users', type_='unique')
                print(f"Dropped constraint: {constraint['name']}")
            except Exception as e:
                print(f"Failed to drop constraint {constraint['name']}: {e}")
    
    # 추가로 이름으로 직접 시도
    for name in ['ux_users_email', 'ix_users_email', 'email']:
        try:
            op.execute(f'ALTER TABLE users DROP INDEX {name}')
            print(f"Dropped index by name: {name}")
        except Exception:
            pass
    
    # email을 nullable로 변경
    op.alter_column('users', 'email',
                    existing_type=sa.String(255),
                    nullable=True,
                    existing_nullable=False)
    
    # 그 다음 non-unique 인덱스 생성
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=False)


def downgrade() -> None:
    import sqlalchemy as sa
    
    # Remove the non-unique index
    op.drop_index('ix_users_email', table_name='users')
    
    # email을 NOT NULL로 복원 (NULL 값이 있으면 실패할 수 있음)
    op.alter_column('users', 'email',
                    existing_type=sa.String(255),
                    nullable=False,
                    existing_nullable=True)
    
    # Restore unique index (이 과정에서 중복 제거된 데이터는 원래대로 돌아오지 않음)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
