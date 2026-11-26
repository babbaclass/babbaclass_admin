"""Rename contract_endings to contract_end, rename note to memo, remove status column

Revision ID: 083
Revises: 082
Create Date: 2026-02-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "083"
down_revision = "082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Rename table from contract_endings to contract_end
    # This assumes contract_endings exists (created by migration 081)
    try:
        op.rename_table("contract_endings", "contract_end")
    except Exception:
        # If rename fails, assume table is already named contract_end or doesn't exist
        pass
    
    # Step 2: Drop status column if it exists
    try:
        op.drop_column("contract_end", "status")
    except Exception:
        pass
    
    # Step 3: Rename note to memo if note exists
    try:
        op.alter_column("contract_end", "note", new_column_name="memo", existing_type=sa.Text())
    except Exception:
        pass
    
    # Step 4: Rename indices
    try:
        op.drop_index("ix_contract_endings_user_id", table_name="contract_end")
    except Exception:
        pass
    try:
        op.drop_index("ix_contract_endings_company_id", table_name="contract_end")
    except Exception:
        pass
    try:
        op.drop_index("ix_contract_endings_contract_end_date", table_name="contract_end")
    except Exception:
        pass
    try:
        op.drop_index("ix_contract_endings_status", table_name="contract_end")
    except Exception:
        pass
    
    # Create new indices
    try:
        op.create_index("ix_contract_end_user_id", "contract_end", ["user_id"])
    except Exception:
        pass
    try:
        op.create_index("ix_contract_end_company_id", "contract_end", ["company_id"])
    except Exception:
        pass
    try:
        op.create_index("ix_contract_end_contract_end_date", "contract_end", ["contract_end_date"])
    except Exception:
        pass


def downgrade() -> None:
    # Reverse the migration
    op.drop_index("ix_contract_end_contract_end_date", table_name="contract_end")
    op.drop_index("ix_contract_end_company_id", table_name="contract_end")
    op.drop_index("ix_contract_end_user_id", table_name="contract_end")
    
    op.create_index("ix_contract_endings_contract_end_date", "contract_end", ["contract_end_date"])
    op.create_index("ix_contract_endings_company_id", "contract_end", ["company_id"])
    op.create_index("ix_contract_endings_user_id", "contract_end", ["user_id"])
    
    # Add status column back
    op.add_column("contract_end", sa.Column("status", sa.String(length=50), nullable=True))
    op.create_index("ix_contract_endings_status", "contract_end", ["status"])
    
    # Rename column memo back to note
    op.alter_column("contract_end", "memo", new_column_name="note")
    
    # Rename table back
    op.rename_table("contract_end", "contract_endings")
