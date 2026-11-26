"""Merge heads 001 and 003_organization_models

Revision ID: 004_merge_heads
Revises: 001, 003_organization_models
Create Date: 2025-11-06

"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision = '004_merge_heads'
down_revision = ('001', '003_organization_models')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # This is a merge migration; no schema changes.
    pass


def downgrade() -> None:
    # This is a merge migration; no schema changes to undo.
    pass
