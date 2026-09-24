import argparse
import sys
from pathlib import Path

from forge.config import load_project_config
from forge.engine import DeploymentEngine
from forge.models import (
    BuildError,
    ContainerRunError,
    DeploymentConfig,
    DeploymentFailedError,
    ForgeError,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Forge application deployment engine")
    parser.add_argument(
        "project_path",
        type=Path,
        help="Path to application directory containing Dockerfile",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default="",
        help="Domain name for routing (default: <app_name>.localhost)",
    )
    parser.add_argument(
        "--container-port",
        type=int,
        default=None,
        help="Container port exposed by application (default: 8000 or from manifest)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_path: Path = args.project_path
    dockerfile = project_path / "Dockerfile"

    print(dockerfile)
    if not dockerfile.is_file():
        print("dockerfile not found")
        sys.exit(1)

    print("dockerfile found")
    print("building docker image")

    def on_build_output(line: str) -> None:
        sys.stdout.write(line)
        sys.stdout.flush()

    manifest, env_vars = load_project_config(project_path)

    container_port = args.container_port
    if container_port is None:
        container_port = int(manifest.get("container_port", 8000))

    domain = args.domain
    if not domain:
        domain = str(manifest.get("app_name", "")) or f"{project_path.name}.localhost"
        if not domain.endswith(".localhost") and "." not in domain:
            domain = f"{domain}.localhost"

    health_check_path = str(manifest.get("health_check_path", "/"))

    config = DeploymentConfig(
        app_dir=project_path,
        container_port=container_port,
        domain=domain,
        health_check_path=health_check_path,
        env_vars=env_vars,
    )
    engine = DeploymentEngine()

    try:
        result = engine.deploy(config, build_output_callback=on_build_output)
        print("docker image built")
        print("running container")
        print(f"Deployment success! App is live at: {result.url}")
    except DeploymentFailedError as exc:
        print("docker image built")
        print("running container")
        print(f"\nDeployment failed with exit code: {exc.exit_code}")
        print("Deployment failed! Active container was not affected (zero-downtime preserved).")
        print("--- Container Logs ---")
        print(exc.logs.strip() if exc.logs.strip() else "<no logs>")
        print("----------------------")
        sys.exit(1)
    except BuildError as exc:
        print(f"error building docker image: {exc}")
        sys.exit(1)
    except ContainerRunError as exc:
        print(f"error running container: {exc}")
        sys.exit(1)
    except ForgeError as exc:
        print(f"deployment error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()