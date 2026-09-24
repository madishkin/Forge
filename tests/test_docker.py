import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from forge.docker import DockerAdapter
from forge.models import (
    BuildError,
    ContainerRunError,
    ContainerState,
    DockerError,
    InspectError,
)


class TestDockerAdapter(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = DockerAdapter(timeout=5.0)

    @patch("subprocess.Popen")
    def test_build_image_stream_success(self, mock_popen: MagicMock) -> None:
        process_mock = MagicMock()
        process_mock.stdout = iter(["Step 1\n", "Successfully tagged app:latest\n"])
        process_mock.wait.return_value = 0
        mock_popen.return_value = process_mock

        lines = list(self.adapter.build_image_stream(Path("test-app"), "test-tag:latest"))
        self.assertEqual(len(lines), 2)
        mock_popen.assert_called_once()

    @patch("subprocess.Popen")
    def test_build_image_stream_failure_raises_build_error(self, mock_popen: MagicMock) -> None:
        process_mock = MagicMock()
        process_mock.stdout = iter(["Error in Dockerfile\n"])
        process_mock.wait.return_value = 1
        mock_popen.return_value = process_mock

        with self.assertRaises(BuildError):
            list(self.adapter.build_image_stream(Path("test-app"), "test-tag:latest"))

    @patch("subprocess.run")
    def test_ensure_network_already_exists(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        self.adapter.ensure_network("forge-net")
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args[0][0], ["docker", "network", "inspect", "forge-net"])

    @patch("subprocess.run")
    def test_ensure_network_creates_when_missing(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="network not found"),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]
        self.adapter.ensure_network("forge-net")
        self.assertEqual(mock_run.call_count, 2)
        self.assertEqual(mock_run.call_args_list[1][0][0], ["docker", "network", "create", "forge-net"])

    @patch.object(DockerAdapter, "inspect_container")
    @patch("subprocess.run")
    def test_ensure_proxy_already_running(self, mock_run: MagicMock, mock_inspect: MagicMock) -> None:
        mock_inspect.return_value = ContainerState(status="running", running=True, exit_code=0)
        self.adapter.ensure_proxy()
        mock_run.assert_not_called()

    @patch.object(DockerAdapter, "inspect_container")
    @patch.object(DockerAdapter, "remove_container")
    @patch("subprocess.run")
    def test_ensure_proxy_starts_when_missing(
        self, mock_run: MagicMock, mock_remove: MagicMock, mock_inspect: MagicMock
    ) -> None:
        mock_inspect.side_effect = InspectError("No such container")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="proxy-id\n", stderr=""
        )
        self.adapter.ensure_proxy()
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("forge-proxy", cmd)
        self.assertIn("traefik:latest", cmd)
        self.assertIn("forge-net", cmd)
        self.assertIn("-v", cmd)
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock", cmd)

    @patch("subprocess.run")
    def test_run_container_with_system_and_traefik_labels_and_env(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="container-id-123\n", stderr=""
        )
        self.adapter.run_container(
            image_tag="app:tag",
            container_name="app-container",
            app_name="my-app",
            domain="my-app.localhost",
            container_port=8080,
            version="v123",
            env_vars={"NODE_ENV": "production", "PORT": "8080"},
        )
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertNotIn("-p", cmd)
        self.assertIn("--network", cmd)
        self.assertIn("forge-net", cmd)
        self.assertIn("forge.app=my-app", cmd)
        self.assertIn("forge.version=v123", cmd)
        self.assertIn("traefik.enable=true", cmd)
        self.assertIn('traefik.http.routers.my-app.rule=Host("my-app.localhost")', cmd)
        self.assertIn("traefik.http.services.my-app.loadbalancer.server.port=8080", cmd)
        self.assertIn("-e", cmd)
        self.assertIn("NODE_ENV=production", cmd)
        self.assertIn("PORT=8080", cmd)

    @patch("subprocess.run")
    def test_check_container_health_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        healthy = self.adapter.check_container_health("my-app-cont", port=8080, path="/health", timeout=1.0)
        self.assertTrue(healthy)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("exec", cmd)
        self.assertIn("my-app-cont", cmd)

    @patch("subprocess.run")
    def test_check_container_health_failure_timeout(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="connection refused"
        )
        healthy = self.adapter.check_container_health(
            "my-app-cont", port=8080, path="/health", timeout=0.2, interval=0.1
        )
        self.assertFalse(healthy)
        self.assertGreaterEqual(mock_run.call_count, 1)

    @patch("subprocess.run")
    def test_get_container_ip_success(self, mock_run: MagicMock) -> None:
        raw_inspect = [
            {
                "NetworkSettings": {
                    "Networks": {
                        "forge-net": {
                            "IPAddress": "172.18.0.7",
                        }
                    }
                }
            }
        ]
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(raw_inspect), stderr=""
        )
        ip = self.adapter.get_container_ip("test-container", "forge-net")
        self.assertEqual(ip, "172.18.0.7")

    @patch("subprocess.run")
    def test_list_app_containers(self, mock_run: MagicMock) -> None:
        stdout_output = "2026-09-24 10:00:00\tapp-old\n2026-09-24 10:05:00\tapp-new\n"
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=stdout_output, stderr=""
        )
        containers = self.adapter.list_app_containers("my-app")
        self.assertEqual(containers, ["app-old", "app-new"])

    @patch("subprocess.run")
    def test_remove_container_idempotent(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="No such container"
        )
        self.adapter.remove_container("non-existent-container", force=True)
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_stop_container_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="my-container\n", stderr=""
        )
        self.adapter.stop_container("my-container", timeout=10)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd, ["docker", "stop", "-t", "10", "my-container"])

    @patch("subprocess.run")
    def test_stop_container_timeout_raises_docker_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["docker", "stop"], timeout=15.0)
        with self.assertRaises(DockerError):
            self.adapter.stop_container("my-container", timeout=10)

    @patch("subprocess.run")
    def test_stop_container_failure_raises_docker_error(self, mock_run: MagicMock) -> None:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Error response from daemon"
        )
        with self.assertRaises(DockerError):
            self.adapter.stop_container("my-container", timeout=10)


if __name__ == "__main__":
    unittest.main()
