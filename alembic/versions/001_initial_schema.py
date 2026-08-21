"""Initial schema for urls and clicks tables

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-08-21 14:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create urls table
    op.create_table(
        "urls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("short_code", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("short_code"),
    )
    op.create_index(op.f("ix_urls_short_code"), "urls", ["short_code"], unique=True)

    # Create clicks table
    op.create_table(
        "clicks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("url_id", sa.Integer(), nullable=False),
        sa.Column(
            "clicked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["url_id"], ["urls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_clicks_clicked_at"), "clicks", ["clicked_at"], unique=False
    )
    op.create_index(op.f("ix_clicks_url_id"), "clicks", ["url_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_clicks_url_id"), table_name="clicks")
    op.drop_index(op.f("ix_clicks_clicked_at"), table_name="clicks")
    op.drop_table("clicks")
    op.drop_index(op.f("ix_urls_short_code"), table_name="urls")
    op.drop_table("urls")
