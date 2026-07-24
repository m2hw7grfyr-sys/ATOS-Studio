"""add creator workspace scene fields

Revision ID: 0012_add_creator_workspace_scene_fields
Revises: 0011_add_workflow_studio_model_registry
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_add_creator_workspace_scene_fields"
down_revision: Union[str, None] = "0011_add_workflow_studio_model_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("studio_video_scenes") as batch:
        batch.add_column(sa.Column("title", sa.String(length=300), nullable=False, server_default=""))
        batch.add_column(sa.Column("purpose", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("visual_description", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("image_prompt", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("video_prompt", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("negative_prompt", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("on_screen_text", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("studio_video_scenes") as batch:
        batch.drop_column("on_screen_text")
        batch.drop_column("negative_prompt")
        batch.drop_column("video_prompt")
        batch.drop_column("image_prompt")
        batch.drop_column("visual_description")
        batch.drop_column("purpose")
        batch.drop_column("title")
