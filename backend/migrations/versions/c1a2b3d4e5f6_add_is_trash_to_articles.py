"""add_is_trash_to_articles

Adds the is_trash boolean column (default false) powering the admin
Recycle Bin / Trash feature. Guarded by IF NOT EXISTS-equivalent checks so
this is safe to run on fresh databases, existing databases, and everything
in between.

Revision ID: c1a2b3d4e5f6
Revises: b9e1f2a3c4d5
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = "c1a2b3d4e5f6"
down_revision = "b9e1f2a3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "articles" not in existing_tables:
        return  # create_tables.py / prior migration handles fresh DB creation

    existing_cols = {c["name"] for c in inspector.get_columns("articles")}
    if "is_trash" not in existing_cols:
        op.add_column(
            "articles",
            sa.Column("is_trash", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "articles" not in existing_tables:
        return

    existing_cols = {c["name"] for c in inspector.get_columns("articles")}
    if "is_trash" in existing_cols:
        op.drop_column("articles", "is_trash")
