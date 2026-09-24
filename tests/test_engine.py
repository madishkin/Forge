import unittest
from pathlib import Path
from unittest.mock import MagicMock

from forge.engine import DeploymentEngine
from forge.models import (
    ContainerState,
    DeploymentConfig,
    DeploymentFailedError,
    DockerError,
)


class TestDeploymentEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_adapter = MagicMock()
        self.engine = DeploymentEngine(adapter=self.mock_adapter)
        self.app_dir = Path("test-app")
        self.config = DeploymentConfig(
            app_dir=self.app_dir,
            container_port=8080,
            domain="test-app.localhost",
            health_check_timeout=2.0,
            env_vars={"ENV": "production"},
        )

    def test_missing_dockerfile_raises_error(self) -> None:
        non_existent_config = DeploymentConfig(
            app_dir=Path("non_existent_directory_12345"),
            container_port=8080,
        )
        with self.assertRaises(FileNotFoundError):
            self.engine.deploy(non_existent_config)

    def test_successful_blue_green_deployment(self) -> None:
        self.mock_adapter.list_app_containers.return_value = ["test-app-old"]
        self.mock_adapter.build_image_stream.return_value = ["Step 1/2\n", "Step 2/2\n"]
        self.mock_adapter.inspect_container.return_value = ContainerState(
            status="running",
            running=True,
            exit_code=0,
        )
        self.mock_adapter.check_container_health.return_value = True

        build_logs: list[str] = []
        result = self.engine.deploy(self.config, build_output_callback=build_logs.append)

        self.mock_adapter.ensure_network.assert_called_once()
        self.mock_adapter.ensure_proxy.assert_called_once()
        self.mock_adapter.run_container.assert_called_once()
        self.assertEqual(self.mock_adapter.run_container.call_args[1]["env_vars"], {"ENV": "production"})
        self.mock_adapter.inspect_container.assert_called_once()
        self.mock_adapter.check_container_health.assert_called_once()
        # Old container was gracefully stopped and decommissioned
        self.mock_adapter.stop_container.assert_called_once_with("test-app-old", timeout=10)
        self.mock_adapter.remove_container.assert_called_once_with("test-app-old", force=True)
        self.assertTrue(result.state.running)
        self.assertEqual(result.domain, "test-app.localhost")
        self.assertEqual(result.url, "http://test-app.localhost")

    def test_health_check_failure_aborts_and_preserves_old_container(self) -> None:
        self.mock_adapter.list_app_containers.return_value = ["test-app-old"]
        self.mock_adapter.build_image_stream.return_value = ["Step 1/1\n"]
        self.mock_adapter.inspect_container.return_value = ContainerState(
            status="running",
            running=True,
            exit_code=0,
        )
        self.mock_adapter.check_container_health.return_value = False
        self.mock_adapter.get_container_logs.return_value = "App starting...\nTimeout"

        with self.assertRaises(DeploymentFailedError) as ctx:
            self.engine.deploy(self.config)

        self.assertIn("Health check failed", str(ctx.exception))
        # Ensure only the new container was removed, and old container was preserved
        removed_containers = [
            call[0][0] for call in self.mock_adapter.remove_container.call_args_list
        ]
        self.assertNotIn("test-app-old", removed_containers)
        self.assertEqual(len(removed_containers), 1)

    def test_immediate_crash_aborts_and_preserves_old_container(self) -> None:
        self.mock_adapter.list_app_containers.return_value = ["test-app-old"]
        self.mock_adapter.build_image_stream.return_value = ["Step 1/1\n"]
        self.mock_adapter.inspect_container.return_value = ContainerState(
            status="exited",
            running=False,
            exit_code=42,
        )
        self.mock_adapter.get_container_logs.return_value = "fatal crash"

        with self.assertRaises(DeploymentFailedError) as ctx:
            self.engine.deploy(self.config)

        self.assertEqual(ctx.exception.exit_code, 42)
        # Ensure only new container was removed, and old container was preserved
        removed_containers = [
            call[0][0] for call in self.mock_adapter.remove_container.call_args_list
        ]
        self.assertNotIn("test-app-old", removed_containers)
        self.assertEqual(len(removed_containers), 1)

    def test_blue_green_stop_failure_still_removes_old_container(self) -> None:
        self.mock_adapter.list_app_containers.return_value = ["test-app-old"]
        self.mock_adapter.build_image_stream.return_value = ["Step 1/1\n"]
        self.mock_adapter.inspect_container.return_value = ContainerState(
            status="running",
            running=True,
            exit_code=0,
        )
        self.mock_adapter.check_container_health.return_value = True
        self.mock_adapter.stop_container.side_effect = DockerError("Stop failed")

        result = self.engine.deploy(self.config)

        self.mock_adapter.stop_container.assert_called_once_with("test-app-old", timeout=10)
        self.mock_adapter.remove_container.assert_called_once_with("test-app-old", force=True)
        self.assertTrue(result.state.running)


if __name__ == "__main__":
    unittest.main()
