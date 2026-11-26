"""Drop categories table - Category model is no longer used

Revision ID: 063
Revises: 062
Create Date: 2025-11-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '063'
down_revision = '062'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop the categories table as it is no longer used in the codebase"""
    # Drop the categories table
    op.drop_table('categories')
    print("✓ Dropped categories table")


def downgrade() -> None:
    """Recreate the categories table if needed"""
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('makeshop_category_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('makeshop_category_id'),
        sa.UniqueConstraint('name')
    )
    print("✓ Recreated categories table")
