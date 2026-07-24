import os
import json
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
from models.production import StudioGenerationWorkflow
from repositories.content_items import stable_json
from services.ai.providers.llm_provider import LLMGeneration, LLMHealth
from services.generation.providers.comfyui.provider import ComfyUIProvider
from services.topic_intelligence_service import (
    TOPIC_INTELLIGENCE_JOB_TYPE,
    build_topic_intelligence_context,
)
from schemas.editorial_brief import validate_editorial_brief_json


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

    def test_brainy_default_account_migration_exists(self):
        with open("migrations/versions/0008_seed_brainy_default_account.py", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Brainy（小脑瓜）", content)
        self.assertIn("TiredBrainClub", content)
        self.assertIn("medical claims", content)

    def test_default_creator_migration_exists(self):
        with open("migrations/versions/0009_generation_queue_framework.py", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Default Creator", content)
        self.assertIn("general content creator", content)
        self.assertIn("studio_generation_pipelines", content)

    def test_comfyui_migration_and_env_example_exist(self):
        with open("migrations/versions/0010_add_comfyui_image_generation.py", "r", encoding="utf-8") as f:
            content = f.read()
        with open(".env.example", "r", encoding="utf-8") as f:
            env_content = f.read()
        self.assertIn("studio_generation_workflows", content)
        self.assertIn("studio_assets", content)
        self.assertIn("basic_image_generation", content)
        self.assertIn("COMFYUI_URL=http://127.0.0.1:8188", env_content)
        self.assertNotIn("COMFYUI_ENABLED=false", env_content)


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

    def push_payload(
        self,
        source_post_id="abc123",
        title="Studio push candidate",
        score=88,
        comments=42,
        risk="low",
        metadata=None,
    ):
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
            "metadata": metadata or {"community": "demo"},
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

    def create_pushed_item(
        self,
        suffix: str,
        title: str,
        score: int = 50,
        comments: int = 5,
        risk: str = "low",
        metadata=None,
    ):
        headers = {"Authorization": "Bearer studio-push-test-token"}
        response = self.client.post(
            "/api/content-items/push",
            headers=headers,
            json=self.push_payload(
                source_post_id=suffix,
                title=title,
                score=score,
                comments=comments,
                risk=risk,
                metadata=metadata,
            ),
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
        self.assertIn("Editorial Studio", director.text)

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

    def test_topic_intelligence_context_includes_comments_and_optional_metrics(self):
        first_id = self.create_pushed_item(
            "topic-intel-1",
            "People feel stuck when ADHD routines break",
            120,
            14,
            "low",
            metadata={
                "community": "adhd",
                "upvotes": 99,
                "views": 1200,
                "comments": [
                    {"text": "I lose momentum after lunch", "score": 18, "reply_count": 2, "author": "user-a"},
                    "Medication shortage makes planning harder",
                ],
            },
        )
        second_id = self.create_pushed_item(
            "topic-intel-2",
            "Routine advice feels too generic",
            None,
            None,
            "medium",
            metadata={"community": "adhd"},
        )
        package = self.client.post(
            "/api/topic-packages/from-content-items",
            json={"title": "ADHD routine breakdown", "content_item_ids": [first_id, second_id]},
        ).json()

        with self.Session() as db:
            context = build_topic_intelligence_context(db, package["id"])

        self.assertEqual(len(context["contents"]), 2)
        self.assertEqual(context["contents"][0]["metrics"]["upvotes"], 99)
        self.assertEqual(context["contents"][0]["metrics"]["views"], 1200)
        self.assertEqual(context["contents"][0]["comments"][0]["text"], "I lose momentum after lunch")
        self.assertIsNone(context["contents"][1]["metrics"]["upvotes"])
        self.assertEqual(context["contents"][1]["comments"], [])

    def test_topic_intelligence_job_success_failure_and_history_versions(self):
        item_id = self.create_pushed_item(
            "topic-intel-ai",
            "ADHD planning apps all feel overwhelming",
            85,
            22,
            "low",
            metadata={
                "comments": [
                    {"text": "I need fewer steps, not more dashboards", "likes": 12, "author": "user-b"}
                ]
            },
        )
        package = self.client.post(
            "/api/topic-packages/from-content-items",
            json={"title": "ADHD planning apps are overwhelming", "content_item_ids": [item_id]},
        ).json()
        self.create_prompt("topic_intelligence")

        class TopicProvider:
            provider_name = "fake-topic"

            def get_model_info(self):
                return {"model": "topic-model"}

            def generate(self, prompt: str):
                self.prompt = prompt
                return LLMGeneration(
                    text=(
                        '{"core_summary":"Users want simpler planning tools.",'
                        '"audience":{"persona":"ADHD adults","needs":["low friction","less setup"]},'
                        '"pain_points":[{"problem":"planning tools feel heavy","frequency":"high","emotion":"frustrated"}],'
                        '"emotional_triggers":["overwhelm"],'
                        '"controversies":["apps versus paper"],'
                        '"user_quotes":[{"quote":"I need fewer steps, not more dashboards","source":"https://example.com/topic-intel-ai","engagement":12}],'
                        '"content_opportunities":[{"angle":"show a two-step planning method","reason":"matches repeated friction","recommended_format":"short explainer"}],'
                        '"video_direction":{"recommended_hook":"Your planner may be the problem","recommended_style":"supportive","target_platforms":["tiktok"]},'
                        '"opportunity_score":{"total":82,"engagement":25,"comment_quality":22,"emotion":20,"commercial":15}}'
                    ),
                    provider="fake-topic",
                    model="topic-model",
                )

        created = self.client.post(
            f"/api/topic-packages/{package['id']}/ai-jobs",
            params={"job_type": TOPIC_INTELLIGENCE_JOB_TYPE},
        )
        self.assertEqual(created.status_code, 200)
        job_id = created.json()["items"][0]["id"]
        with patch("services.ai_service.get_ai_provider", return_value=TopicProvider()):
            run = self.client.post(f"/api/ai/jobs/{job_id}/run")

        self.assertEqual(run.status_code, 200)
        self.assertEqual(run.json()["status"], "completed")
        analyses = self.client.get(f"/api/topic-packages/{package['id']}/ai-analyses").json()["items"]
        self.assertEqual(analyses[0]["analysis_type"], "topic_intelligence")
        self.assertEqual(analyses[0]["result"]["opportunity_score"]["total"], 82)

        second_job = self.client.post(
            f"/api/topic-packages/{package['id']}/ai-jobs",
            params={"job_type": TOPIC_INTELLIGENCE_JOB_TYPE},
        ).json()["items"][0]["id"]
        with patch("services.ai_service.get_ai_provider", return_value=TopicProvider()):
            self.client.post(f"/api/ai/jobs/{second_job}/run")

        page = self.client.get(f"/topic-packages/{package['id']}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("生成主题智能分析", page.text)
        self.assertIn("重新分析", page.text)
        self.assertIn("Analysis Version 1", page.text)
        self.assertIn("Analysis Version 2", page.text)
        self.assertIn("Users want simpler planning tools.", page.text)
        self.assertIn("I need fewer steps", page.text)

        bad_job = self.client.post(
            f"/api/topic-packages/{package['id']}/ai-jobs",
            params={"job_type": TOPIC_INTELLIGENCE_JOB_TYPE},
        ).json()["items"][0]["id"]

        class BadProvider(TopicProvider):
            def generate(self, prompt: str):
                return LLMGeneration(text="not json", provider="fake-topic", model="topic-model")

        with patch("services.ai_service.get_ai_provider", return_value=BadProvider()):
            failed = self.client.post(f"/api/ai/jobs/{bad_job}/run")
        self.assertEqual(failed.status_code, 200)
        self.assertEqual(failed.json()["status"], "failed")
        self.assertIn("Expecting value", failed.json()["error_message"])

    def create_topic_intelligence_analysis(self, package_id: str):
        self.create_prompt("topic_intelligence")

        class TopicProvider:
            provider_name = "fake-topic"

            def get_model_info(self):
                return {"model": "topic-model"}

            def generate(self, prompt: str):
                return LLMGeneration(
                    text=(
                        '{"core_summary":"Users want practical short advice.",'
                        '"audience":{"persona":"ADHD adults","needs":["clarity"]},'
                        '"pain_points":[{"problem":"too many steps","frequency":"high","emotion":"overwhelmed"}],'
                        '"emotional_triggers":["friction"],'
                        '"controversies":[],'
                        '"user_quotes":[{"quote":"I need fewer steps","source":"https://example.com","engagement":9}],'
                        '"content_opportunities":[{"angle":"two-step method","reason":"clear pain","recommended_format":"short video"}],'
                        '"video_direction":{"recommended_hook":"Stop overbuilding your planner","recommended_style":"supportive","target_platforms":["tiktok"]},'
                        '"opportunity_score":{"total":80,"engagement":20,"comment_quality":20,"emotion":20,"commercial":20}}'
                    ),
                    provider="fake-topic",
                    model="topic-model",
                )

        job = self.client.post(
            f"/api/topic-packages/{package_id}/ai-jobs",
            params={"job_type": TOPIC_INTELLIGENCE_JOB_TYPE},
        ).json()["items"][0]["id"]
        with patch("services.ai_service.get_ai_provider", return_value=TopicProvider()):
            response = self.client.post(f"/api/ai/jobs/{job}/run")
        self.assertEqual(response.json()["status"], "completed")

    def valid_editorial_output(self, title="Planner Reset"):
        return {
            "title": title,
            "hook": "Stop overbuilding your planner",
            "target_audience": "ADHD adults",
            "script": "A short script about reducing planning friction.",
            "scenes": [
                {
                    "scene_number": 1,
                    "duration": 5,
                    "visual_prompt": "A cluttered planner on a desk",
                    "voiceover": "Your planner may be creating more friction.",
                    "subtitle": "Your planner may be the problem",
                    "camera_direction": "close-up",
                }
            ],
            "caption": "A simpler planning reset.",
            "hashtags": ["ADHD", "planning"],
        }

    def test_editorial_prompt_builder_json_validation_versioning_and_page(self):
        item_id = self.create_pushed_item("editorial-1", "ADHD planners can become another chore", 90, 12, "low")
        package = self.client.post(
            "/api/topic-packages/from-content-items",
            json={"title": "ADHD planner friction", "content_item_ids": [item_id]},
        ).json()

        missing = self.client.get(f"/api/topic-packages/{package['id']}/editorial-prompt")
        self.assertEqual(missing.status_code, 422)
        self.assertIn("缺少主题智能分析结果", missing.text)

        self.create_topic_intelligence_analysis(package["id"])
        missing_template = self.client.get(f"/api/topic-packages/{package['id']}/editorial-prompt")
        self.assertEqual(missing_template.status_code, 422)
        self.assertIn("editorial", missing_template.text)
        template = self.create_prompt("editorial")
        prompt = self.client.get(f"/api/topic-packages/{package['id']}/editorial-prompt")
        self.assertEqual(prompt.status_code, 200)
        self.assertIn("素材上下文 JSON", prompt.json()["prompt"])
        self.assertEqual(prompt.json()["prompt_template_id"], template["id"])

        valid_output = self.valid_editorial_output()
        parsed = validate_editorial_brief_json(json.dumps(valid_output))
        self.assertEqual(parsed["scenes"][0]["camera_direction"], "close-up")
        with self.assertRaises(ValueError):
            validate_editorial_brief_json("not json")
        with self.assertRaises(ValueError):
            validate_editorial_brief_json('{"title":"x","hook":"x","script":"x","caption":"x"}')
        with self.assertRaises(ValueError):
            validate_editorial_brief_json('{"title":"x","hook":"x","script":"x","scenes":[],"caption":"x"}')

        first = self.client.post(
            "/api/editorial-briefs",
            json={
                "topic_package_id": package["id"],
                "prompt_snapshot": prompt.json()["prompt"],
                "prompt_template_id": prompt.json()["prompt_template_id"],
                "output_json": valid_output,
            },
        )
        second_output = self.valid_editorial_output("Planner Reset V2")
        second = self.client.post(
            "/api/editorial-briefs",
            json={
                "topic_package_id": package["id"],
                "prompt_snapshot": prompt.json()["prompt"],
                "prompt_template_id": prompt.json()["prompt_template_id"],
                "output_json": json.dumps(second_output),
            },
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["version"], "1")
        self.assertEqual(second.json()["version"], "2")
        self.assertEqual(second.json()["output"]["title"], "Planner Reset V2")

        updated = self.client.patch(f"/api/editorial-briefs/{second.json()['id']}/status", json={"status": "approved"})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["status"], "approved")

        page = self.client.get("/gpt-director", params={"topic_package_id": package["id"], "generate": 1})
        self.assertEqual(page.status_code, 200)
        self.assertIn("素材上下文", page.text)
        self.assertIn("生成GPT Prompt", page.text)
        self.assertIn("GPT Output JSON", page.text)
        self.assertIn("Version 1", page.text)
        self.assertIn("Version 2", page.text)
        self.assertIn("Planner Reset V2", page.text)

    def test_persona_social_account_video_project_and_persona_prompt(self):
        persona = self.client.post(
            "/api/personas",
            json={
                "name": "Sarah ADHD Student",
                "description": "College student persona",
                "target_audience": "ADHD college students",
                "persona_profile": {
                    "identity": "college student",
                    "age_range": "18-25",
                    "tone": "casual",
                    "language": "american english",
                    "style": "personal storytelling",
                    "avoid": ["medical claims"],
                },
                "tone_style": "casual",
                "language_style": "american english",
                "visual_style": "personal storytelling",
                "voice_style": "warm peer voice",
                "content_rules": {"avoid": ["medical claims"]},
            },
        )
        self.assertEqual(persona.status_code, 200)
        persona_id = persona.json()["id"]

        updated_persona = self.client.put(
            f"/api/personas/{persona_id}",
            json={"description": "Updated college student persona"},
        )
        self.assertEqual(updated_persona.status_code, 200)
        self.assertEqual(updated_persona.json()["description"], "Updated college student persona")

        disabled = self.client.post(
            "/api/personas",
            json={"name": "Disabled Persona", "enabled": True},
        ).json()
        disabled_update = self.client.put(f"/api/personas/{disabled['id']}", json={"enabled": False})
        self.assertEqual(disabled_update.status_code, 200)
        self.assertFalse(disabled_update.json()["enabled"])
        coach = self.client.post(
            "/api/personas",
            json={
                "name": "Productivity Coach",
                "target_audience": "busy professionals",
                "persona_profile": {"identity": "productivity coach", "tone": "direct", "avoid": ["diagnosis"]},
                "tone_style": "direct",
            },
        ).json()

        account = self.client.post(
            "/api/social-accounts",
            json={
                "platform": "tiktok",
                "username": "sarahfocus",
                "display_name": "Sarah ADHD",
                "persona_id": persona_id,
                "status": "active",
            },
        )
        self.assertEqual(account.status_code, 200)
        account_id = account.json()["id"]

        filtered_accounts = self.client.get("/api/social-accounts", params={"persona_id": persona_id})
        self.assertEqual(filtered_accounts.status_code, 200)
        self.assertEqual(len(filtered_accounts.json()["items"]), 1)
        self.assertEqual(filtered_accounts.json()["items"][0]["id"], account_id)

        item_id = self.create_pushed_item("video-project-1", "ADHD students need simpler study routines", 90, 18, "low")
        package = self.client.post(
            "/api/topic-packages/from-content-items",
            json={"title": "ADHD student study routine", "content_item_ids": [item_id]},
        ).json()
        self.create_topic_intelligence_analysis(package["id"])
        self.create_prompt("editorial")

        prompt = self.client.get(
            f"/api/topic-packages/{package['id']}/editorial-prompt",
            params={"persona_id": persona_id},
        )
        self.assertEqual(prompt.status_code, 200)
        self.assertIn("Create content for this persona", prompt.json()["prompt"])
        self.assertIn("college student", prompt.json()["prompt"])
        self.assertIn("medical claims", prompt.json()["prompt"])
        coach_prompt = self.client.get(
            f"/api/topic-packages/{package['id']}/editorial-prompt",
            params={"persona_id": coach["id"]},
        )
        self.assertEqual(coach_prompt.status_code, 200)
        self.assertIn("productivity coach", coach_prompt.json()["prompt"])
        self.assertNotEqual(prompt.json()["prompt"], coach_prompt.json()["prompt"])

        output = self.valid_editorial_output("Study Routine Reset")
        brief = self.client.post(
            "/api/editorial-briefs",
            json={
                "topic_package_id": package["id"],
                "prompt_snapshot": prompt.json()["prompt"],
                "prompt_template_id": prompt.json()["prompt_template_id"],
                "output_json": output,
            },
        )
        self.assertEqual(brief.status_code, 200)

        project = self.client.post(
            "/api/video-projects/from-brief",
            json={
                "editorial_brief_id": brief.json()["id"],
                "persona_id": persona_id,
                "social_account_id": account_id,
            },
        )
        self.assertEqual(project.status_code, 200)
        payload = project.json()
        self.assertEqual(payload["persona_id"], persona_id)
        self.assertEqual(payload["social_account_id"], account_id)
        self.assertEqual(payload["target_platforms"], ["tiktok"])
        self.assertEqual(len(payload["scenes"]), 1)
        self.assertEqual(payload["scenes"][0]["visual_prompt"], "A cluttered planner on a desk")

        list_page = self.client.get("/video-projects")
        detail_page = self.client.get(f"/video-projects/{payload['id']}")
        accounts_page = self.client.get("/accounts")
        self.assertEqual(list_page.status_code, 200)
        self.assertIn("Study Routine Reset", list_page.text)
        self.assertEqual(detail_page.status_code, 200)
        self.assertIn("Generation状态", detail_page.text)
        self.assertEqual(accounts_page.status_code, 200)
        self.assertIn("Sarah ADHD Student", accounts_page.text)

    def test_general_video_project_generation_plan_and_provider_registry(self):
        item_id = self.create_pushed_item("generation-1", "ADHD students need visual study resets", 91, 22, "low")
        package = self.client.post(
            "/api/topic-packages/from-content-items",
            json={"title": "Visual study reset", "content_item_ids": [item_id]},
        ).json()
        self.create_topic_intelligence_analysis(package["id"])
        self.create_prompt("editorial")
        prompt = self.client.get(f"/api/topic-packages/{package['id']}/editorial-prompt")
        self.assertEqual(prompt.status_code, 200)
        brief = self.client.post(
            "/api/editorial-briefs",
            json={
                "topic_package_id": package["id"],
                "prompt_snapshot": prompt.json()["prompt"],
                "prompt_template_id": prompt.json()["prompt_template_id"],
                "output_json": self.valid_editorial_output("Visual Study Reset"),
            },
        )
        self.assertEqual(brief.status_code, 200)

        project = self.client.post(
            "/api/video-projects/from-brief",
            json={
                "editorial_brief_id": brief.json()["id"],
                "creation_mode": "general",
            },
        )
        self.assertEqual(project.status_code, 200)
        payload = project.json()
        self.assertEqual(payload["creation_mode"], "general")
        self.assertIsNone(payload["persona_id"])
        self.assertIsNone(payload["social_account_id"])

        plan = self.client.post(f"/api/video-projects/{payload['id']}/generation-plan")
        self.assertEqual(plan.status_code, 200)
        plan_payload = plan.json()
        self.assertEqual(plan_payload["pipeline"]["status"], "queued")
        self.assertEqual(plan_payload["pipeline"]["total_tasks"], 5)
        task_types = [task["task_type"] for task in plan_payload["tasks"]]
        self.assertEqual(
            task_types,
            ["image_generation", "video_generation", "voice_generation", "subtitle_generation", "composition"],
        )
        self.assertEqual(plan_payload["tasks"][0]["context"]["video_project_id"], payload["id"])
        self.assertIsNone(plan_payload["tasks"][0]["context"]["persona_id"])
        self.assertIsNotNone(plan_payload["tasks"][1]["depends_on_task_id"])

        queue_api = self.client.get("/api/generation-tasks", params={"status": "queued"})
        self.assertEqual(queue_api.status_code, 200)
        self.assertEqual(len(queue_api.json()["items"]), 5)
        queue_page = self.client.get("/generation-queue")
        detail_page = self.client.get(f"/video-projects/{payload['id']}")
        self.assertEqual(queue_page.status_code, 200)
        self.assertIn("Generation Queue", queue_page.text)
        self.assertIn("image_generation", queue_page.text)
        self.assertEqual(detail_page.status_code, 200)
        self.assertIn("Video Generation Pipeline", detail_page.text)
        self.assertIn("composition", detail_page.text)

        providers = self.client.get("/api/generation/providers")
        self.assertEqual(providers.status_code, 200)
        provider_names = [row["provider"] for row in providers.json()["items"]]
        self.assertIn("comfyui", provider_names)
        self.assertIn("veo", provider_names)
        health = self.client.get("/api/generation/providers/wan/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "not_configured")
        missing = self.client.get("/api/generation/providers/unknown/health")
        self.assertEqual(missing.status_code, 404)

    def test_comfyui_image_generation_task_asset_and_page(self):
        item_id = self.create_pushed_item("comfyui-1", "A quiet desk scene for ADHD planning", 88, 14, "low")
        package = self.client.post(
            "/api/topic-packages/from-content-items",
            json={"title": "Quiet planning scene", "content_item_ids": [item_id]},
        ).json()
        self.create_topic_intelligence_analysis(package["id"])
        self.create_prompt("editorial")
        prompt = self.client.get(f"/api/topic-packages/{package['id']}/editorial-prompt")
        brief = self.client.post(
            "/api/editorial-briefs",
            json={
                "topic_package_id": package["id"],
                "prompt_snapshot": prompt.json()["prompt"],
                "prompt_template_id": prompt.json()["prompt_template_id"],
                "output_json": self.valid_editorial_output("Quiet Planning Scene"),
            },
        ).json()
        project = self.client.post(
            "/api/video-projects/from-brief",
            json={"editorial_brief_id": brief["id"], "creation_mode": "general"},
        ).json()
        scene_id = project["scenes"][0]["id"]
        with self.Session() as db:
            db.add(
                StudioGenerationWorkflow(
                    id="workflow-test-comfyui",
                    name="basic_image_generation",
                    description="test workflow",
                    provider="comfyui",
                    workflow_type="image_generation",
                    status="available",
                    workflow_json=stable_json({"prompt": {"1": {"inputs": {"text": "{{visual_prompt}}"}}}}),
                    tags_json="[]",
                    required_models_json="[]",
                    test_result_json="{}",
                    version="test",
                    enabled=True,
                    created_by="test",
                )
            )
            db.commit()

        class FakeComfyUI:
            def health_check(self):
                return {"available": True, "status": "available"}

            def submit_job(self, workflow, context):
                assert "visual_prompt" in context
                return {"provider_task_id": "prompt-123", "raw_response": {"prompt_id": "prompt-123"}}

            def get_status(self, provider_task_id):
                return {"provider_task_id": provider_task_id, "status": "completed"}

            def get_result(self, provider_task_id):
                return {
                    "provider_task_id": provider_task_id,
                    "status": "completed",
                    "assets": [
                        {
                            "asset_type": "image",
                            "file_path": "",
                            "url": "http://127.0.0.1:8188/view?filename=test.png",
                            "metadata": {"filename": "test.png"},
                        }
                    ],
                }

        with patch("services.generation_executor.get_generation_provider", return_value=FakeComfyUI()):
            response = self.client.post(f"/api/scenes/{scene_id}/generate-image")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["task"]["status"], "completed")
        self.assertEqual(payload["task"]["provider_task_id"], "prompt-123")
        self.assertEqual(payload["assets"][0]["asset_type"], "image")

        assets = self.client.get(f"/api/generation-tasks/{payload['task']['id']}/assets")
        self.assertEqual(assets.status_code, 200)
        self.assertEqual(len(assets.json()["items"]), 1)
        queue_page = self.client.get("/generation-queue", params={"task_type": "image_generation"})
        detail_page = self.client.get(f"/video-projects/{project['id']}")
        self.assertIn("prompt-123", queue_page.text)
        self.assertIn("1 asset", queue_page.text)
        self.assertIn("生成图片", detail_page.text)
        self.assertNotIn('name="workflow_id"', detail_page.text)
        self.assertIn("图片路径", detail_page.text)
        self.assertIn("test.png", detail_page.text)

    def test_comfyui_health_disabled_and_unavailable(self):
        disabled = ComfyUIProvider(base_url="http://127.0.0.1:8188", enabled=False).health_check()
        self.assertEqual(disabled["status"], "disabled")
        unavailable = ComfyUIProvider(base_url="http://127.0.0.1:1", timeout_seconds=0.01, enabled=True).health_check()
        self.assertEqual(unavailable["status"], "unavailable")

    def test_workflow_import_model_registry_and_preflight(self):
        invalid = self.client.post(
            "/api/generation-workflows",
            json={
                "name": "bad workflow",
                "provider": "comfyui",
                "workflow_type": "image_generation",
                "workflow_json": "not json",
            },
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertIn("Invalid workflow JSON", invalid.text)

        model = self.client.post(
            "/api/model-capabilities",
            json={"name": "FLUX.1 Schnell", "provider": "comfyui", "model_type": "image", "status": "available"},
        )
        self.assertEqual(model.status_code, 200)
        self.assertEqual(model.json()["status"], "available")

        workflow = self.client.post(
            "/api/generation-workflows",
            json={
                "name": "FLUX image workflow",
                "description": "portrait workflow",
                "provider": "comfyui",
                "workflow_type": "image_generation",
                "workflow_json": {"prompt": {"1": {"inputs": {"text": "{{visual_prompt}}"}}}},
                "tags": ["portrait", "ugc"],
                "required_models": [{"name": "FLUX.1 Schnell", "type": "image"}],
            },
        )
        self.assertEqual(workflow.status_code, 200)
        workflow_id = workflow.json()["id"]
        self.assertEqual(workflow.json()["status"], "draft")

        class FakeComfyUI:
            def health_check(self):
                return {"available": True, "status": "available"}

            def submit_job(self, workflow, context):
                return {"provider_task_id": "workflow-prompt", "raw_response": {"prompt_id": "workflow-prompt"}}

            def get_result(self, provider_task_id):
                return {
                    "status": "completed",
                    "assets": [{"asset_type": "image", "url": "http://127.0.0.1:8188/view?filename=workflow.png", "metadata": {}}],
                }

        with patch("services.generation_executor.get_generation_provider", return_value=FakeComfyUI()):
            tested = self.client.post(f"/api/generation-workflows/{workflow_id}/test", json={"visual_prompt": "test"})
        self.assertEqual(tested.status_code, 200)
        self.assertEqual(tested.json()["status"], "available")
        self.assertTrue(tested.json()["test_result"]["success"])

        page = self.client.get("/workflows")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Workflow管理", page.text)
        self.assertIn("FLUX image workflow", page.text)
        self.assertIn("FLUX.1 Schnell", page.text)

        missing_model_workflow = self.client.post(
            "/api/generation-workflows",
            json={
                "name": "Missing model workflow",
                "provider": "comfyui",
                "workflow_type": "image_generation",
                "status": "available",
                "workflow_json": {"prompt": {"1": {"inputs": {"text": "{{visual_prompt}}"}}}},
                "required_models": [{"name": "Missing Model", "type": "image"}],
            },
        ).json()
        item_id = self.create_pushed_item("preflight-1", "Preflight image scene", 80, 10, "low")
        package = self.client.post(
            "/api/topic-packages/from-content-items",
            json={"title": "Preflight scene", "content_item_ids": [item_id]},
        ).json()
        self.create_topic_intelligence_analysis(package["id"])
        self.create_prompt("editorial")
        prompt = self.client.get(f"/api/topic-packages/{package['id']}/editorial-prompt")
        brief = self.client.post(
            "/api/editorial-briefs",
            json={
                "topic_package_id": package["id"],
                "prompt_snapshot": prompt.json()["prompt"],
                "prompt_template_id": prompt.json()["prompt_template_id"],
                "output_json": self.valid_editorial_output("Preflight Scene"),
            },
        ).json()
        project = self.client.post(
            "/api/video-projects/from-brief",
            json={"editorial_brief_id": brief["id"], "creation_mode": "general"},
        ).json()
        scene_id = project["scenes"][0]["id"]

        with patch("services.generation_executor.get_generation_provider", return_value=FakeComfyUI()):
            failed = self.client.post(
                f"/api/scenes/{scene_id}/generate-image",
                params={"workflow_id": missing_model_workflow["id"]},
            )
        self.assertEqual(failed.status_code, 200)
        self.assertEqual(failed.json()["task"]["status"], "failed")
        self.assertEqual(failed.json()["task"]["error_message"], "missing_model")


if __name__ == "__main__":
    unittest.main()
