import os
import unittest

from fastapi.testclient import TestClient

from app.main import app
from config.settings import Settings


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
            "/content-pool",
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


if __name__ == "__main__":
    unittest.main()

