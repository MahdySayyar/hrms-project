"""Docker startup secret boundaries with temporary synthetic files, never real credentials."""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("docker_entrypoint", ROOT / "deployments/app/entrypoint.py")
entrypoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entrypoint)


class DockerEntrypoint(TestCase):
    def test_tc_01_16_secondary_worker_skips_seed_and_removes_password(self):
        from app import seed
        with patch.dict(os.environ, {"ADMIN_PASSWORD": "Synthetic-only-password"}, clear=True), \
             patch.object(sys, "argv", ["entrypoint.py", "--web-only"]), \
             patch.object(entrypoint, "configure"), patch.object(seed, "seed") as seed_call, \
             patch.object(entrypoint.os, "execv") as exec_call:
            entrypoint.main()
            seed_call.assert_not_called()
            exec_call.assert_called_once()
            self.assertNotIn("ADMIN_PASSWORD", os.environ)

    def test_tc_01_08_runtime_secrets_are_required_and_url_encoded(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            secret = Path(folder) / "synthetic-secret"
            password = "Synthetic:@/%#?Password"
            secret.write_text(password + "\n", encoding="utf-8")
            os.environ.update({"DB_PASSWORD_FILE": str(secret), "ADMIN_PASSWORD_FILE": str(secret)})
            entrypoint.configure()
            url = make_url(os.environ["DATABASE_URL"])
            self.assertEqual(url.password, password)
            self.assertEqual(url.host, "db")
            self.assertEqual(url.database, "hrms_docker")
            self.assertEqual(os.environ["ADMIN_PASSWORD"], password)
            os.environ.pop("DB_PASSWORD_FILE")
            with self.assertRaisesRegex(RuntimeError, "DB_PASSWORD_FILE"):
                entrypoint.configure()
            os.environ["DB_PASSWORD_FILE"] = str(secret)
            secret.write_text("short", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "too short"):
                entrypoint.configure()

    def test_tc_01_09_seed_precedes_exec_and_admin_password_is_removed(self):
        from app import seed
        calls = []
        def configure():
            calls.append("configure")
            os.environ["ADMIN_PASSWORD"] = "Synthetic-only-password"
        def seed_once():
            calls.append("seed")
            self.assertIn("ADMIN_PASSWORD", os.environ)
        def exec_server(executable, arguments):
            calls.append("exec")
            self.assertNotIn("ADMIN_PASSWORD", os.environ)
            self.assertEqual(executable, sys.executable)
            self.assertEqual(arguments, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
        with patch.dict(os.environ, {}, clear=True), patch.object(entrypoint, "configure", configure), \
             patch.object(seed, "seed", seed_once), patch.object(entrypoint.os, "execv", exec_server):
            entrypoint.main()
        self.assertEqual(calls, ["configure", "seed", "exec"])
