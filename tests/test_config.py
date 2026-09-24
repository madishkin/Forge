import tempfile
import unittest
from pathlib import Path

from forge.config import load_project_config, parse_env_file, parse_manifest


class TestConfig(unittest.TestCase):
    def test_parse_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text(
                "# Comment\n"
                "PORT=8080\n"
                "DATABASE_URL='postgres://user:pass@localhost:5432/db'\n"
                'SECRET_KEY="my-secret-key"\n'
                "\n"
                "EMPTY_VAL=\n",
                encoding="utf-8",
            )
            parsed = parse_env_file(env_file)
            self.assertEqual(parsed["PORT"], "8080")
            self.assertEqual(parsed["DATABASE_URL"], "postgres://user:pass@localhost:5432/db")
            self.assertEqual(parsed["SECRET_KEY"], "my-secret-key")
            self.assertEqual(parsed["EMPTY_VAL"], "")

    def test_parse_manifest_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_file = Path(tmp_dir) / "forge.json"
            manifest_file.write_text(
                '{"app_name": "custom-app", "container_port": 9000, "health_check_path": "/healthz"}',
                encoding="utf-8",
            )
            parsed = parse_manifest(manifest_file)
            self.assertEqual(parsed["app_name"], "custom-app")
            self.assertEqual(parsed["container_port"], 9000)
            self.assertEqual(parsed["health_check_path"], "/healthz")

    def test_parse_manifest_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            manifest_file = Path(tmp_dir) / "forge.yaml"
            manifest_file.write_text(
                "# Simple YAML\n"
                "app_name: yaml-app\n"
                "container_port: 7000\n"
                "health_check_path: /ready\n",
                encoding="utf-8",
            )
            parsed = parse_manifest(manifest_file)
            self.assertEqual(parsed["app_name"], "yaml-app")
            self.assertEqual(parsed["container_port"], 7000)
            self.assertEqual(parsed["health_check_path"], "/ready")

    def test_load_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "forge.json").write_text('{"container_port": 5000}', encoding="utf-8")
            (tmp_path / ".env").write_text("API_KEY=12345\n", encoding="utf-8")

            manifest, env_vars = load_project_config(tmp_path)
            self.assertEqual(manifest["container_port"], 5000)
            self.assertEqual(env_vars["API_KEY"], "12345")


if __name__ == "__main__":
    unittest.main()
