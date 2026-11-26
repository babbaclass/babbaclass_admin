"""update_registration_status_to_done

Revision ID: 051_update_reg_to_done
Revises: 050_add_registration_status
Create Date: 2025-11-27 01:10:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '051_update_reg_to_done'
down_revision = '050_add_registration_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 모든 기존 데이터를 DONE으로 변환
    op.execute("UPDATE users SET registration_status = 'DONE' WHERE registration_status = '가입 완료' OR registration_status IS NULL")


def downgrade() -> None:
    # 롤백 시 원래 값으로 복원
    op.execute("UPDATE users SET registration_status = '가입 완료' WHERE registration_status = 'DONE'")
