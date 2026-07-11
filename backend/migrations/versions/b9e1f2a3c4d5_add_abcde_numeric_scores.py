"""add_abcde_numeric_scores

Adds five Float score columns (1.0–10.0) and an overall grade string to the
articles table, enabling the new ABCDE™ Score Breakdown card on the public
article page. All ops are guarded by IF NOT EXISTS so the migration is safe
to run on fresh databases, existing databases that already have everything,
and everything in between.

Revision ID: b9e1f2a3c4d5
Revises: 83c4eaa3f875
Create Date: 2026-07-11
"""
from alembic import op
import sqlalchemy as sa

revision = "b9e1f2a3c4d5"
down_revision = "83c4eaa3f875"
branch_labels = None
depends_on = None

_NEW_COLS = [
    ("architecture_score", sa.Float()),
    ("landscape_score",    sa.Float()),
    ("connectivity_score", sa.Float()),
    ("delight_score",      sa.Float()),
    ("eat_explore_score",  sa.Float()),
    ("abcde_overall",      sa.String()),
]


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "articles" not in existing_tables:
        return  # create_tables.py / prior migration handles fresh DB creation

    existing_cols = {c["name"] for c in inspector.get_columns("articles")}
    for col_name, col_type in _NEW_COLS:
        if col_name not in existing_cols:
            op.add_column("articles", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "articles" not in existing_tables:
        return

    existing_cols = {c["name"] for c in inspector.get_columns("articles")}
    for col_name, _ in _NEW_COLS:
        if col_name in existing_cols:
            op.drop_column("articles", col_name)
