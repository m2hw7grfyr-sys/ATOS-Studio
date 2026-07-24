"""add studio job review fields

Revision ID: 0014_add_studio_job_review_fields
Revises: 0013_add_generation_task_retry_fields
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_add_studio_job_review_fields"
down_revision: Union[str, None] = "0013_add_generation_task_retry_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("studio_video_projects") as batch:
        batch.add_column(sa.Column("review_status", sa.String(length=40), nullable=False, server_default="draft"))
        batch.add_column(sa.Column("review_note", sa.String(length=2000), nullable=False, server_default=""))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("editorial_json_snapshot", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("editorial_parse_error", sa.String(length=1000), nullable=False, server_default=""))
    op.create_index("ix_studio_video_projects_review_status", "studio_video_projects", ["review_status"])


def downgrade() -> None:
    op.drop_index("ix_studio_video_projects_review_status", table_name="studio_video_projects")
    with op.batch_alter_table("studio_video_projects") as batch:
        batch.drop_column("editorial_parse_error")
        batch.drop_column("editorial_json_snapshot")
        batch.drop_column("reviewed_at")
        batch.drop_column("review_note")
        batch.drop_column("review_status")
