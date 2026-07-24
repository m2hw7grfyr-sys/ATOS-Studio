"""add generation task retry fields

Revision ID: 0013_add_generation_task_retry_fields
Revises: 0012_add_creator_workspace_scene_fields
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_add_generation_task_retry_fields"
down_revision: Union[str, None] = "0012_add_creator_workspace_scene_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("studio_generation_tasks") as batch:
        batch.add_column(sa.Column("current_step", sa.String(length=80), nullable=False, server_default=""))
        batch.add_column(sa.Column("failed_step", sa.String(length=80), nullable=False, server_default=""))
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_studio_generation_tasks_current_step", "studio_generation_tasks", ["current_step"])
    op.create_index("ix_studio_generation_tasks_failed_step", "studio_generation_tasks", ["failed_step"])


def downgrade() -> None:
    op.drop_index("ix_studio_generation_tasks_failed_step", table_name="studio_generation_tasks")
    op.drop_index("ix_studio_generation_tasks_current_step", table_name="studio_generation_tasks")
    with op.batch_alter_table("studio_generation_tasks") as batch:
        batch.drop_column("completed_at")
        batch.drop_column("failed_step")
        batch.drop_column("current_step")
