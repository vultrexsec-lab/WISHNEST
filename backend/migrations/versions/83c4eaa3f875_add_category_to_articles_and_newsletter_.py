"""add_category_to_articles_and_newsletter_subscribers

Revision ID: 83c4eaa3f875
Revises:
Create Date: 2026-07-04

Safe for:
  - Fresh databases (tables absent → created here)
  - Existing databases missing category / newsletter_subscribers
  - Databases that already have everything (all ops guarded by IF NOT EXISTS checks)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "83c4eaa3f875"
down_revision = None
branch_labels = None
depends_on = None


def _index_exists(conn, index_name: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = :name"
        ),
        {"name": index_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # ── 1. articles.category ─────────────────────────────────────────────────
    if "articles" in existing_tables:
        existing_cols = [c["name"] for c in inspector.get_columns("articles")]
        if "category" not in existing_cols:
            op.add_column(
                "articles",
                sa.Column("category", sa.String(), nullable=True),
            )
        if not _index_exists(conn, "ix_articles_category"):
            op.create_index(
                "ix_articles_category", "articles", ["category"], unique=False
            )

    # ── 2. newsletter_subscribers table ──────────────────────────────────────
    if "newsletter_subscribers" not in existing_tables:
        op.create_table(
            "newsletter_subscribers",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
            ),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        if not _index_exists(conn, "ix_newsletter_subscribers_email"):
            op.create_index(
                "ix_newsletter_subscribers_email",
                "newsletter_subscribers",
                ["email"],
                unique=True,
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "newsletter_subscribers" in existing_tables:
        if _index_exists(conn, "ix_newsletter_subscribers_email"):
            op.drop_index(
                "ix_newsletter_subscribers_email",
                table_name="newsletter_subscribers",
            )
        op.drop_table("newsletter_subscribers")

    if "articles" in existing_tables:
        existing_cols = [c["name"] for c in inspector.get_columns("articles")]
        if "category" in existing_cols:
            if _index_exists(conn, "ix_articles_category"):
                op.drop_index("ix_articles_category", table_name="articles")
            op.drop_column("articles", "category")
