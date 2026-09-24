from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ContainerState:
    status: str
    running: bool
    exit_code: int


@dataclass(frozen=True)
class DeploymentConfig:
    app_dir: Path
    container_port: int = 8000
    domain: str = ""
    health_check_path: str = "/"
    health_check_timeout: float = 15.0
    env_vars: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.domain:
            object.__setattr__(self, "domain", f"{self.app_dir.name}.localhost")


@dataclass(frozen=True)
class DeploymentResult:
    image_tag: str
    container_name: str
    domain: str
    url: str
    state: ContainerState


class ForgeError(Exception):
    """Base domain exception for Forge platform."""


class DockerError(ForgeError):
    """Base exception for Docker interactions."""


class BuildError(DockerError):
    """Raised when building a Docker image fails."""


class ContainerRunError(DockerError):
    """Raised when creating or running a container fails."""


class InspectError(DockerError):
    """Raised when inspecting container metadata or state fails."""


class DeploymentFailedError(ForgeError):
    """Raised when container deployment fails after start or container terminates unexpectedly."""

    def __init__(self, message: str, exit_code: int, logs: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.logs = logs
