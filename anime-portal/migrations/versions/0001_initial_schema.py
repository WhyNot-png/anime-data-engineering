"""Начальная схема: студии, жанры, аниме, пользователи, списки, отзывы.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

ANIME_STATUS = "('upcoming', 'airing', 'finished')"
WATCH_STATUS = "('planned', 'watching', 'completed', 'dropped')"


def upgrade() -> None:
    op.create_table(
        "studios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("founded_year", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "founded_year IS NULL OR founded_year BETWEEN 1900 AND 2100",
            name="ck_studios_founded_year",
        ),
    )
    op.create_index("ix_studios_name", "studios", ["name"], unique=True)

    op.create_table(
        "genres",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.UniqueConstraint("slug", name="uq_genres_slug"),
    )
    op.create_index("ix_genres_name", "genres", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "anime",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mal_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("title_english", sa.String(300), nullable=True),
        sa.Column("synopsis", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("episodes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="finished"),
        sa.Column("studio_id", sa.Integer(), sa.ForeignKey("studios.id", ondelete="RESTRICT")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(f"status IN {ANIME_STATUS}", name="ck_anime_status"),
        sa.CheckConstraint("episodes IS NULL OR episodes >= 0", name="ck_anime_episodes"),
        sa.CheckConstraint("year IS NULL OR year BETWEEN 1900 AND 2100", name="ck_anime_year"),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 300", name="ck_anime_title_length"),
    )
    op.create_index("ix_anime_mal_id", "anime", ["mal_id"], unique=True)
    op.create_index("ix_anime_title", "anime", ["title"])
    op.create_index("ix_anime_year", "anime", ["year"])
    op.create_index("ix_anime_status", "anime", ["status"])
    op.create_index("ix_anime_studio_id", "anime", ["studio_id"])

    op.create_table(
        "anime_genres",
        sa.Column(
            "anime_id",
            sa.Integer(),
            sa.ForeignKey("anime.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "genre_id",
            sa.Integer(),
            sa.ForeignKey("genres.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index("ix_anime_genres_genre_id", "anime_genres", ["genre_id"])

    op.create_table(
        "watch_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "anime_id", sa.Integer(), sa.ForeignKey("anime.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="planned"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "anime_id", name="uq_watch_entries_user_anime"),
        sa.CheckConstraint(f"status IN {WATCH_STATUS}", name="ck_watch_entries_status"),
        sa.CheckConstraint("progress >= 0", name="ck_watch_entries_progress"),
    )
    op.create_index("ix_watch_entries_user_id", "watch_entries", ["user_id"])
    op.create_index("ix_watch_entries_anime_id", "watch_entries", ["anime_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "anime_id", sa.Integer(), sa.ForeignKey("anime.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "anime_id", name="uq_reviews_user_anime"),
        sa.CheckConstraint("rating BETWEEN 1 AND 10", name="ck_reviews_rating"),
        sa.CheckConstraint("length(body) <= 2000", name="ck_reviews_body_length"),
    )
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"])
    op.create_index("ix_reviews_anime_id", "reviews", ["anime_id"])


def downgrade() -> None:
    op.drop_index("ix_reviews_anime_id", table_name="reviews")
    op.drop_index("ix_reviews_user_id", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("ix_watch_entries_anime_id", table_name="watch_entries")
    op.drop_index("ix_watch_entries_user_id", table_name="watch_entries")
    op.drop_table("watch_entries")
    op.drop_index("ix_anime_genres_genre_id", table_name="anime_genres")
    op.drop_table("anime_genres")
    op.drop_index("ix_anime_studio_id", table_name="anime")
    op.drop_index("ix_anime_status", table_name="anime")
    op.drop_index("ix_anime_year", table_name="anime")
    op.drop_index("ix_anime_title", table_name="anime")
    op.drop_index("ix_anime_mal_id", table_name="anime")
    op.drop_table("anime")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_genres_name", table_name="genres")
    op.drop_table("genres")
    op.drop_index("ix_studios_name", table_name="studios")
    op.drop_table("studios")
