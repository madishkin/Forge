import uuid
from collections.abc import Callable
from forge.docker import DockerAdapter
from forge.models import (
    DeploymentConfig,
    DeploymentFailedError,
    DeploymentResult,
    DockerError,
)


class DeploymentEngine:
    def __init__(
        self,
        adapter: DockerAdapter | None = None,
        health_checker: Callable[..., bool] | None = None,
    ) -> None:
        self.adapter = adapter or DockerAdapter()
        self.health_checker = health_checker

    def deploy(
        self,
        config: DeploymentConfig,
        build_output_callback: Callable[[str], None] | None = None,
    ) -> DeploymentResult:
        dockerfile = config.app_dir / "Dockerfile"
        if not dockerfile.is_file():
            raise FileNotFoundError(f"Dockerfile not found in '{config.app_dir}'")

        self.adapter.ensure_network()
        self.adapter.ensure_proxy()

        app_name = config.app_dir.name
        active_containers = self.adapter.list_app_containers(app_name)

        tag = uuid.uuid4().hex[:7]
        image_tag = f"{app_name}:{tag}"
        new_container = f"{app_name}-{tag}"

        for line in self.adapter.build_image_stream(config.app_dir, image_tag):
            if build_output_callback is not None:
                build_output_callback(line)

        try:
            self.adapter.run_container(
                image_tag=image_tag,
                container_name=new_container,
                app_name=app_name,
                domain=config.domain,
                container_port=config.container_port,
                version=tag,
                env_vars=config.env_vars,
            )
            state = self.adapter.inspect_container(new_container)
        except Exception:
            self.adapter.remove_container(new_container, force=True)
            raise

        if not state.running:
            logs = self.adapter.get_container_logs(new_container)
            self.adapter.remove_container(new_container, force=True)
            raise DeploymentFailedError(
                f"Container '{new_container}' failed to start or terminated unexpectedly",
                exit_code=state.exit_code,
                logs=logs,
            )

        if self.health_checker is not None:
            is_healthy = self.health_checker(
                container_name=new_container,
                port=config.container_port,
                path=config.health_check_path,
                timeout=config.health_check_timeout,
            )
        else:
            is_healthy = self.adapter.check_container_health(
                container_name=new_container,
                port=config.container_port,
                path=config.health_check_path,
                timeout=config.health_check_timeout,
            )

        if not is_healthy:
            logs = self.adapter.get_container_logs(new_container)
            self.adapter.remove_container(new_container, force=True)
            raise DeploymentFailedError(
                f"Health check failed for container '{new_container}' on port {config.container_port}{config.health_check_path}",
                exit_code=1,
                logs=logs,
            )

        for old_container in active_containers:
            if old_container != new_container:
                try:
                    self.adapter.stop_container(old_container, timeout=10)
                except DockerError:
                    pass
                self.adapter.remove_container(old_container, force=True)

        url = f"http://{config.domain}"
        return DeploymentResult(
            image_tag=image_tag,
            container_name=new_container,
            domain=config.domain,
            url=url,
            state=state,
        )
