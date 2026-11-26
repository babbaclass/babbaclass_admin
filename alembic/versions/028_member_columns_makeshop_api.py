"""Placeholder for merged migration (content moved to 027)

This migration was merged into 027_align_product_columns_with_makeshop_api
and is kept as a placeholder for backward compatibility with existing DB history.

Revision ID: 028_member_columns_makeshop_api
Revises: 027
Create Date: 2025-01-14
"""

# revision identifiers, used by Alembic.
revision = '028_member_columns_makeshop_api'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade():
    """No-op: Member column changes already applied in migration 027"""
    pass


def downgrade():
    """No-op: Downgrade handled separately if needed"""
    pass
