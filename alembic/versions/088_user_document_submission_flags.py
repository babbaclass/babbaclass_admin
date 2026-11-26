"""Add document submission flags to users

Revision ID: 088
Revises: 087
Create Date: 2026-05-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "088"
down_revision = "087"
branch_labels = None
depends_on = None

_DOC_COLUMNS = (
    ("doc_contract", "FALSE"),
    ("doc_bankbook", "FALSE"),
    ("doc_personal_info", "FALSE"),
    ("doc_business_registration", "FALSE"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    for name, default in _DOC_COLUMNS:
        if name not in columns:
            op.add_column(
                "users",
                sa.Column(
                    name,
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text(default),
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    for name, _ in reversed(_DOC_COLUMNS):
        if name in columns:
            op.drop_column("users", name)
