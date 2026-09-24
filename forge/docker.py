import json
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

from forge.models import (
    BuildError,
    ContainerRunError,
    ContainerState,
    DockerError,
    InspectError,
)


class DockerAdapter:
    def __init__(self, timeout: float = 120.0) -> None:
        self.timeout = timeout

    def build_image_stream(self, context_path: Path, tag: str) -> Iterator[str]:
        command = ["docker", "build", "-t", tag, str(context_path)]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError as exc:
            raise DockerError("Docker executable not found in system PATH") from exc
        except OSError as exc:
            raise DockerError(f"Failed to start Docker process: {exc}") from exc

        assert process.stdout is not None
        try:
            for line in process.stdout:
                yield line
        finally:
            if process.stdout is not None and hasattr(process.stdout, "close"):
                process.stdout.close()
            return_code = process.wait()
            if return_code != 0:
                raise BuildError(f"Docker build failed with exit code {return_code}")

    def ensure_network(self, network_name: str = "forge-net") -> None:
        inspect_cmd = ["docker", "network", "inspect", network_name]
        try:
            inspect_res = subprocess.run(
                inspect_cmd,
                text=True,
                capture_output=True,
                timeout=self.timeout,
            )
            if inspect_res.returncode == 0:
                return
        except subprocess.TimeoutExpired as exc:
            raise DockerError(
                f"Network inspection timed out for '{network_name}'"
            ) from exc
        except OSError as exc:
            raise DockerError(
                f"Failed to inspect network '{network_name}': {exc}"
            ) from exc

        create_cmd = ["docker", "network", "create", network_name]
        try:
            create_res = subprocess.run(
                create_cmd,
                text=True,
                capture_output=True,
                timeout=self.timeout,
            )
            if create_res.returncode != 0:
                error_msg = create_res.stderr.strip() or "Unknown error"
                if "already exists" not in error_msg.lower():
                    raise DockerError(
                        f"Failed to create network '{network_name}': {error_msg}"
                    )
        except subprocess.TimeoutExpired as exc:
            raise DockerError(
                f"Network creation timed out for '{network_name}'"
            ) from exc
        except OSError as exc:
            raise DockerError(
                f"Failed to create network '{network_name}': {exc}"
            ) from exc
    def ensure_proxy(self) -> None:
        proxy_name = "forge-proxy"
        try:
            state = self.inspect_container(proxy_name)
            if state.running:
                return
            self.remove_container(proxy_name, force=True)
        except InspectError:
            pass

        command = [
            "docker",
            "run",
            "-d",
            "--name",
            proxy_name,
            "--restart",
            "unless-stopped",
            "--network",
            "forge-net",
            "-p",
            "80:80",
            "-v",
            "/var/run/docker.sock:/var/run/docker.sock",
            "-e",
            "DOCKER_API_VERSION=1.44",
            "traefik:latest",
            "--providers.docker=true",
            "--providers.docker.exposedbydefault=false",
            "--providers.docker.network=forge-net",
            "--entrypoints.web.address=:80",
        ]

        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContainerRunError(
                f"Reverse proxy startup timed out after {self.timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise DockerError("Docker executable not found in system PATH") from exc
        except OSError as exc:
            raise DockerError(f"Failed to execute proxy start: {exc}") from exc

        if result.returncode != 0:
            error_detail = (
                result.stderr.strip() or result.stdout.strip() or "Unknown error"
            )
            raise ContainerRunError(
                f"Failed to start reverse proxy '{proxy_name}': {error_detail}"
            )

    def run_container(
        self,
        image_tag: str,
        container_name: str,
        app_name: str,
        domain: str,
        container_port: int,
        version: str = "",
        env_vars: dict[str, str] | None = None,
        network: str = "forge-net",
    ) -> None:
        version_label = version if version else "latest"
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "--network",
            network,
            "--label",
            f"forge.app={app_name}",
            "--label",
            f"forge.version={version_label}",
            "--label",
            "traefik.enable=true",
            "--label",
            f'traefik.http.routers.{app_name}.rule=Host("{domain}")',
            "--label",
            f"traefik.http.services.{app_name}.loadbalancer.server.port={container_port}",
        ]

        if env_vars:
            for key, val in env_vars.items():
                command.extend(["-e", f"{key}={val}"])

        command.append(image_tag)

        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContainerRunError(
                f"Container startup timed out after {self.timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise DockerError("Docker executable not found in system PATH") from exc
        except OSError as exc:
            raise DockerError(f"Failed to execute docker run: {exc}") from exc

        if result.returncode != 0:
            error_detail = (
                result.stderr.strip() or result.stdout.strip() or "Unknown error"
            )
            raise ContainerRunError(
                f"Failed to run container '{container_name}': {error_detail}"
            )

    def inspect_container(self, container_name: str) -> ContainerState:
        command = ["docker", "inspect", container_name]
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise InspectError(
                f"Container inspection timed out after {self.timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise DockerError("Docker executable not found in system PATH") from exc
        except OSError as exc:
            raise DockerError(f"Failed to execute docker inspect: {exc}") from exc

        if result.returncode != 0:
            error_detail = result.stderr.strip() or "Unknown error"
            raise InspectError(
                f"Failed to inspect container '{container_name}': {error_detail}"
            )

        try:
            inspected_data = json.loads(result.stdout)
            if not inspected_data or not isinstance(inspected_data, list):
                raise InspectError(
                    f"Unexpected inspect response format for '{container_name}'"
                )
            state = inspected_data[0]["State"]
            return ContainerState(
                status=str(state["Status"]),
                running=bool(state["Running"]),
                exit_code=int(state["ExitCode"]),
            )
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise InspectError(
                f"Malformed inspect data for container '{container_name}'"
            ) from exc

    def get_container_ip(self, container_name: str, network_name: str = "forge-net") -> str:
        command = ["docker", "inspect", container_name]
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise InspectError(
                f"Inspecting IP for '{container_name}' timed out after {self.timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise DockerError("Docker executable not found in system PATH") from exc
        except OSError as exc:
            raise DockerError(f"Failed to execute docker inspect: {exc}") from exc

        if result.returncode != 0:
            error_detail = result.stderr.strip() or "Unknown error"
            raise InspectError(
                f"Failed to inspect IP for container '{container_name}': {error_detail}"
            )

        try:
            data = json.loads(result.stdout)
            networks = data[0].get("NetworkSettings", {}).get("Networks", {})
            net_info = networks.get(network_name)
            if not net_info:
                raise InspectError(
                    f"Container '{container_name}' is not connected to network '{network_name}'"
                )
            ip_address = str(net_info.get("IPAddress", "")).strip()
            if not ip_address:
                raise InspectError(
                    f"Container '{container_name}' has no IP assigned in network '{network_name}'"
                )
            return ip_address
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise InspectError(
                f"Malformed network inspect data for container '{container_name}'"
            ) from exc

    def check_container_health(
        self,
        container_name: str,
        port: int = 8000,
        path: str = "/",
        timeout: float = 15.0,
        interval: float = 0.5,
    ) -> bool:
        if not path.startswith("/"):
            path = f"/{path}"
        python_script = (
            f"import urllib.request, sys; "
            f"sys.exit(0 if 200 <= urllib.request.urlopen('http://127.0.0.1:{port}{path}', timeout=2).getcode() < 400 else 1)"
        )
        command = [
            "docker",
            "exec",
            container_name,
            "python",
            "-c",
            python_script,
        ]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                result = subprocess.run(
                    command,
                    text=True,
                    capture_output=True,
                    timeout=min(self.timeout, 5.0),
                )
                if result.returncode == 0:
                    return True
            except (subprocess.TimeoutExpired, OSError):
                pass

            time.sleep(interval)

        return False

    def list_app_containers(self, app_name: str) -> list[str]:
        command = [
            "docker",
            "ps",
            "--filter",
            f"label=forge.app={app_name}",
            "--filter",
            "status=running",
            "--format",
            "{{.CreatedAt}}\t{{.Names}}",
        ]
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise DockerError(
                f"Listing containers for '{app_name}' timed out after {self.timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise DockerError("Docker executable not found in system PATH") from exc
        except OSError as exc:
            raise DockerError(f"Failed to list containers: {exc}") from exc

        if result.returncode != 0:
            raise DockerError(
                f"Failed to list containers for '{app_name}': {result.stderr.strip()}"
            )

        lines = [
            line.strip()
            for line in result.stdout.strip().splitlines()
            if line.strip()
        ]
        lines.sort()
        return [line.split("\t")[-1].strip() for line in lines if "\t" in line]

    def get_container_logs(self, container_name: str) -> str:
        command = ["docker", "logs", container_name]
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=self.timeout,
            )
            return (result.stdout + result.stderr).strip()
        except subprocess.TimeoutExpired as exc:
            raise DockerError(
                f"Fetching logs for '{container_name}' timed out after {self.timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise DockerError("Docker executable not found in system PATH") from exc
        except OSError as exc:
            raise DockerError(
                f"Failed to fetch logs for container '{container_name}': {exc}"
            ) from exc

    def stop_container(self, container_name: str, timeout: int = 10) -> None:
        command = ["docker", "stop", "-t", str(timeout), container_name]
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=max(self.timeout, float(timeout) + 5.0),
            )
        except subprocess.TimeoutExpired as exc:
            raise DockerError(
                f"Stopping container '{container_name}' timed out after {timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise DockerError("Docker executable not found in system PATH") from exc
        except OSError as exc:
            raise DockerError(
                f"Failed to execute docker stop for '{container_name}': {exc}"
            ) from exc

        if result.returncode != 0:
            error_detail = result.stderr.strip() or "Unknown error"
            raise DockerError(
                f"Failed to stop container '{container_name}': {error_detail}"
            )

    def remove_container(self, container_name: str, force: bool = True) -> None:
        command = ["docker", "rm"]
        if force:
            command.append("-f")
        command.append(container_name)
        try:
            subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise DockerError(
                f"Removing container '{container_name}' timed out after {self.timeout}s"
            ) from exc
        except FileNotFoundError as exc:
            raise DockerError("Docker executable not found in system PATH") from exc
        except OSError as exc:
            raise DockerError(
                f"Failed to execute docker rm for '{container_name}': {exc}"
            ) from exc

