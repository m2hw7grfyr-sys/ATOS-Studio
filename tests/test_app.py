import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app, get_db
from config.settings import Settings
from database import Base
from models.schemas import AtosContentItem


client = TestClient(app)


class StudioAppTests(unittest.TestCase):
    def test_health(self):
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"service": "atos-studio", "status": "ok", "version": "0.1.0"},
        )

    def test_homepage_loads_without_optional_workers(self):
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ATOS Studio", response.text)
        self.assertIn("Not configured", response.text)
        self.assertIn("GPU Worker", response.text)
        self.assertIn("ComfyUI", response.text)

    def test_placeholder_pages(self):
        paths = [
            "/inspiration",
            "/video-projects",
            "/generation-queue",
            "/assets",
            "/renders",
            "/settings",
        ]
        for path in paths:
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("该模块将在后续Sprint实现", response.text)

    def test_content_pool_page_loads(self):
        response = client.get("/content-pool")
        self.assertEqual(response.status_code, 200)
        self.assertIn("从ATOS导入", response.text)
        self.assertIn("内容池列表", response.text)

    def test_config_defaults(self):
        settings = Settings(_env_file=None)
        self.assertEqual(settings.studio_port, 8502)
        self.assertEqual(settings.comfyui_status, "Not configured")
        self.assertEqual(settings.gpu_worker_status, "Not configured")
        self.assertTrue(settings.studio_database_url.startswith("sqlite:///"))

    def test_env_is_ignored(self):
        with open(".gitignore", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(".env", content)
        self.assertFalse(os.path.exists(".env"))


class ContentPoolTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)

    def atos_item(self):
        return AtosContentItem(
            atos_post_id="1",
            atos_post_uuid="post-uuid",
            source_platform="reddit",
            source_post_id="abc123",
            source_url="https://example.com/abc123",
            title="Studio candidate",
            body="Useful source text",
            author="author-a",
            published_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            score=42,
            comment_count=7,
            risk_level=None,
            tags=["studio"],
            metadata={"community": "demo"},
        )

    def test_import_is_idempotent_and_status_updates(self):
        with patch("app.main.AtosClient.get_content_item", return_value=self.atos_item()):
            created = self.client.post(
                "/api/content-items/import",
                json={"source_platform": "reddit", "source_post_id": "abc123"},
            )
            duplicate = self.client.post(
                "/api/content-items/import",
                json={"source_platform": "reddit", "source_post_id": "abc123"},
            )

        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.json()["created"])
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])
        item_id = created.json()["item"]["id"]

        listed = self.client.get("/api/content-items")
        self.assertEqual(listed.json()["total"], 1)

        updated = self.client.patch(f"/api/content-items/{item_id}/status", json={"status": "approved"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["status"], "approved")

        invalid = self.client.patch(f"/api/content-items/{item_id}/status", json={"status": "drafting"})
        self.assertEqual(invalid.status_code, 422)

    def test_content_pool_detail_page_contains_snapshot(self):
        with patch("app.main.AtosClient.get_content_item", return_value=self.atos_item()):
            created = self.client.post(
                "/api/content-items/import",
                json={"source_platform": "reddit", "source_post_id": "abc123"},
            )
        item_id = created.json()["item"]["id"]
        page = self.client.get(f"/content-pool/{item_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("原始source snapshot", page.text)
        self.assertIn("Studio candidate", page.text)


if __name__ == "__main__":
    unittest.main()
