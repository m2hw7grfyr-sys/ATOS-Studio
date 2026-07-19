import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app, get_db
from config.settings import get_settings
from config.settings import Settings
from database import Base
from models.schemas import AtosContentItem
from services.ai.providers.llm_provider import LLMGeneration, LLMHealth


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
        os.environ["STUDIO_PUSH_AUTH_ENABLED"] = "true"
        os.environ["STUDIO_PUSH_API_TOKEN"] = "studio-push-test-token"
        get_settings.cache_clear()
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
        get_settings.cache_clear()

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

    def push_payload(self, source_post_id="abc123", title="Studio push candidate", score=88, comments=42, risk="low"):
        return {
            "source_platform": "reddit",
            "atos_post_id": source_post_id,
            "source_post_id": source_post_id,
            "source_url": f"https://example.com/{source_post_id}",
            "title": title,
            "body": "Useful pushed text",
            "author": "author-a",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "source_score": score,
            "comment_count": comments,
            "risk_level": risk,
            "tags": ["studio"],
            "metadata": {"community": "demo"},
            "push_context": {
                "requested_content_type": "video",
                "target_platforms": ["tiktok"],
                "operator_note": "operator note",
            },
        }

    def test_push_requires_valid_token(self):
        missing = self.client.post("/api/content-items/push", json=self.push_payload())
        wrong = self.client.post(
            "/api/content-items/push",
            headers={"Authorization": "Bearer wrong"},
            json=self.push_payload(),
        )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)

    def test_push_is_idempotent_and_does_not_reset_approved_status(self):
        headers = {"Authorization": "Bearer studio-push-test-token"}
        created = self.client.post("/api/content-items/push", headers=headers, json=self.push_payload())
        duplicate = self.client.post("/api/content-items/push", headers=headers, json=self.push_payload())

        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.json()["created"])
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])
        item_id = created.json()["studio_item_id"]

        approved = self.client.patch(f"/api/content-items/{item_id}/status", json={"status": "approved"})
        self.assertEqual(approved.status_code, 200)
        pushed_again = self.client.post("/api/content-items/push", headers=headers, json=self.push_payload())
        self.assertEqual(pushed_again.status_code, 200)
        item = self.client.get(f"/api/content-items/{item_id}").json()
        self.assertEqual(item["status"], "approved")
        self.assertEqual(item["push_count"], 3)

    def test_source_status_and_batch_status(self):
        headers = {"Authorization": "Bearer studio-push-test-token"}
        self.client.post("/api/content-items/push", headers=headers, json=self.push_payload())

        status_response = self.client.get(
            "/api/content-items/source-status",
            headers=headers,
            params={"source_platform": "reddit", "source_post_id": "abc123"},
        )
        batch_response = self.client.post(
            "/api/content-items/source-status/batch",
            headers=headers,
            json={
                "items": [
                    {"source_platform": "reddit", "source_post_id": "abc123"},
                    {"source_platform": "reddit", "source_post_id": "missing"},
                ]
            },
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.json()["exists"])
        self.assertEqual(batch_response.status_code, 200)
        self.assertTrue(batch_response.json()["items"][0]["exists"])
        self.assertFalse(batch_response.json()["items"][1]["exists"])

    def test_invalid_push_payload_returns_422(self):
        headers = {"Authorization": "Bearer studio-push-test-token"}
        response = self.client.post(
            "/api/content-items/push",
            headers=headers,
            json={"source_platform": "reddit", "title": ""},
        )
        self.assertEqual(response.status_code, 422)

    def create_pushed_item(self, suffix: str, title: str, score: int = 50, comments: int = 5, risk: str = "low"):
        headers = {"Authorization": "Bearer studio-push-test-token"}
        response = self.client.post(
            "/api/content-items/push",
            headers=headers,
            json=self.push_payload(source_post_id=suffix, title=title, score=score, comments=comments, risk=risk),
        )
        self.assertIn(response.status_code, {200, 201})
        return response.json()["studio_item_id"]

    def test_content_status_batch_partial_failure_and_review_timestamps(self):
        first_id = self.create_pushed_item("batch-1", "Batch item one")
        second_id = self.create_pushed_item("batch-2", "Batch item two")
        response = self.client.post(
            "/api/content-items/status-batch",
            json={
                "content_item_ids": [first_id, second_id, "missing-id", first_id],
                "status": "approved",
                "review_note": "适合后续做短视频",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["updated"], 2)
        self.assertEqual(payload["failed"], 1)

        item = self.client.get(f"/api/content-items/{first_id}").json()
        self.assertEqual(item["status"], "approved")
        self.assertEqual(item["review_note"], "适合后续做短视频")
        self.assertIsNotNone(item["approved_at"])

        invalid = self.client.post(
            "/api/content-items/status-batch",
            json={"content_item_ids": [first_id], "status": "drafting"},
        )
        self.assertEqual(invalid.status_code, 422)

    def test_topic_package_full_manual_workflow(self):
        first_id = self.create_pushed_item("topic-1", "ADHD medication wears off too early", 90, 40, "low")
        second_id = self.create_pushed_item("topic-2", "Medication wears off early at work", 70, 20, "medium")
        third_id = self.create_pushed_item("topic-3", "How to handle ADHD medication crash", 50, 10, "high")

        self.client.post(
            "/api/content-items/status-batch",
            json={"content_item_ids": [first_id, second_id, third_id], "status": "approved"},
        )
        created = self.client.post(
            "/api/topic-packages/from-content-items",
            json={
                "title": "ADHD medication wears off too early",
                "content_item_ids": [first_id, second_id, second_id, third_id],
                "content_angle": "解释型",
                "target_content_type": "video",
                "target_platforms": ["tiktok", "youtube_shorts"],
                "primary_content_item_id": first_id,
            },
        )
        self.assertEqual(created.status_code, 200)
        package = created.json()
        package_id = package["id"]
        self.assertEqual(package["source_count"], 3)
        self.assertEqual(package["total_comment_count"], 70)
        self.assertEqual(package["max_source_score"], 90)
        self.assertEqual(package["risk_level"], "high")
        self.assertEqual(sum(1 for item in package["items"] if item["is_primary"]), 1)

        duplicate = self.client.post(
            f"/api/topic-packages/{package_id}/items",
            json={"content_item_ids": [second_id]},
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["results"][0]["status"], "duplicate")

        removed = self.client.delete(f"/api/topic-packages/{package_id}/items/{second_id}")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json()["source_count"], 2)
        restored = self.client.post(
            f"/api/topic-packages/{package_id}/items",
            json={"content_item_ids": [second_id]},
        )
        self.assertEqual(restored.json()["results"][0]["status"], "restored")

        primary = self.client.patch(
            f"/api/topic-packages/{package_id}/primary-item",
            json={"content_item_id": third_id},
        )
        self.assertEqual(primary.status_code, 200)
        self.assertEqual(sum(1 for item in primary.json()["items"] if item["is_primary"]), 1)

        ordered_ids = [third_id, first_id, second_id]
        reordered = self.client.patch(
            f"/api/topic-packages/{package_id}/items/order",
            json={"ordered_content_item_ids": ordered_ids},
        )
        self.assertEqual(reordered.status_code, 200)
        self.assertEqual([item["content_item_id"] for item in reordered.json()["items"]], ordered_ids)

        approved = self.client.patch(f"/api/topic-packages/{package_id}/status", json={"status": "approved"})
        self.assertEqual(approved.json()["status"], "approved")

        fourth_id = self.create_pushed_item("topic-4", "ADHD medication wears off too early again", 66, 8, "low")
        similar_package = self.client.post(
            "/api/topic-packages/from-content-items",
            json={
                "title": "ADHD medication wears off too early",
                "content_item_ids": [fourth_id],
                "target_platforms": ["tiktok"],
            },
        ).json()
        similar = self.client.get("/api/topic-packages/similar", params={"title": "ADHD medication wears off too early"})
        self.assertGreaterEqual(len(similar.json()["items"]), 1)

        merged = self.client.post(
            "/api/topic-packages/merge",
            json={
                "target_topic_package_id": package_id,
                "source_topic_package_ids": [similar_package["id"]],
                "archive_sources": True,
            },
        )
        self.assertEqual(merged.status_code, 200)
        source_after = self.client.get(f"/api/topic-packages/{similar_package['id']}").json()
        target_after = self.client.get(f"/api/topic-packages/{package_id}").json()
        self.assertEqual(source_after["status"], "archived")
        self.assertEqual(target_after["source_count"], 4)

        audit = self.client.get(f"/api/topic-packages/{package_id}/audit")
        self.assertEqual(audit.status_code, 200)
        self.assertTrue(any(item["action"] == "topic_package_merged" for item in audit.json()["items"]))

    def test_topic_package_pages_load(self):
        item_id = self.create_pushed_item("page-topic", "Page topic candidate")
        created = self.client.post(
            "/api/topic-packages/from-content-items",
            json={"title": "Page topic candidate", "content_item_ids": [item_id]},
        ).json()
        list_page = self.client.get("/topic-packages")
        detail_page = self.client.get(f"/topic-packages/{created['id']}")
        self.assertEqual(list_page.status_code, 200)
        self.assertIn("主题包列表", list_page.text)
        self.assertEqual(detail_page.status_code, 200)
        self.assertIn("来源内容列表", detail_page.text)

    def create_prompt(self, category="analysis"):
        response = self.client.post(
            "/api/prompt-templates",
            json={
                "name": f"{category} prompt",
                "category": category,
                "description": "test prompt",
                "template": "Return JSON",
                "variables": ["topic_title"],
                "version": "test",
                "enabled": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_ai_health_and_prompt_templates(self):
        health = self.client.get("/api/ai/health")
        self.assertEqual(health.status_code, 200)
        self.assertIn(health.json()["status"], {"available", "unavailable", "not_configured", "error"})

        created = self.create_prompt("analysis")
        listed = self.client.get("/api/prompt-templates", params={"category": "analysis"})
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(any(item["id"] == created["id"] for item in listed.json()["items"]))

    def test_ai_job_success_and_editorial_brief(self):
        item_id = self.create_pushed_item("ai-topic", "AI topic candidate", 80, 30, "low")
        package = self.client.post(
            "/api/topic-packages/from-content-items",
            json={"title": "AI topic candidate", "content_item_ids": [item_id]},
        ).json()
        self.create_prompt("analysis")

        class FakeProvider:
            provider_name = "fake-local"

            def health_check(self):
                return LLMHealth("fake-local", "available", "fake-model")

            def get_model_info(self):
                return {"provider": "fake-local", "model": "fake-model"}

            def generate(self, prompt: str):
                return LLMGeneration(
                    text='{"core_issue":"focus drop","main_points":["afternoon crash"],"source_summary":"summary"}',
                    provider="fake-local",
                    model="fake-model",
                )

        created_job = self.client.post(
            f"/api/topic-packages/{package['id']}/ai-jobs",
            params={"job_type": "topic_summary"},
        )
        self.assertEqual(created_job.status_code, 200)
        job_id = created_job.json()["items"][0]["id"]
        with patch("services.ai_service.get_ai_provider", return_value=FakeProvider()):
            run = self.client.post(f"/api/ai/jobs/{job_id}/run")
        self.assertEqual(run.status_code, 200)
        self.assertEqual(run.json()["status"], "completed")

        analyses = self.client.get(f"/api/topic-packages/{package['id']}/ai-analyses")
        self.assertEqual(analyses.status_code, 200)
        self.assertEqual(analyses.json()["items"][0]["analysis_type"], "summary")

        page = self.client.get(f"/topic-packages/{package['id']}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("AI Insights", page.text)

        director = self.client.get("/gpt-director", params={"topic_package_id": package["id"]})
        self.assertEqual(director.status_code, 200)
        self.assertIn("生成GPT Prompt", director.text)

        brief = self.client.post(
            "/api/editorial-briefs",
            json={
                "topic_package_id": package["id"],
                "prompt_snapshot": "prompt",
                "input_json": '{"hook":"test"}',
            },
        )
        self.assertEqual(brief.status_code, 200)
        self.assertEqual(brief.json()["status"], "draft")

    def test_ai_job_failure_is_stored_without_crashing(self):
        item_id = self.create_pushed_item("ai-fail-topic", "AI fail topic candidate")
        package = self.client.post(
            "/api/topic-packages/from-content-items",
            json={"title": "AI fail topic candidate", "content_item_ids": [item_id]},
        ).json()
        self.create_prompt("analysis")
        job_id = self.client.post(
            f"/api/topic-packages/{package['id']}/ai-jobs",
            params={"job_type": "topic_summary"},
        ).json()["items"][0]["id"]

        class BrokenProvider:
            provider_name = "broken-local"

            def get_model_info(self):
                return {"model": "broken-model"}

            def generate(self, prompt: str):
                raise RuntimeError("provider unavailable")

        with patch("services.ai_service.get_ai_provider", return_value=BrokenProvider()):
            run = self.client.post(f"/api/ai/jobs/{job_id}/run")
        self.assertEqual(run.status_code, 200)
        self.assertEqual(run.json()["status"], "failed")
        self.assertIn("provider unavailable", run.json()["error_message"])


if __name__ == "__main__":
    unittest.main()
