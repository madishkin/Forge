import json
from pathlib import Path
from typing import Any


def parse_env_file(file_path: Path) -> dict[str, str]:
    if not file_path.is_file():
        return {}

    env: dict[str, str] = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            if key:
                env[key] = val
    return env


def parse_manifest(file_path: Path) -> dict[str, Any]:
    if not file_path.is_file():
        return {}

    if file_path.suffix == ".json":
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    data: dict[str, Any] = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if (v.startswith('"') and v.endswith('"')) or (
                    v.startswith("'") and v.endswith("'")
                ):
                    v = v[1:-1]
                elif v.isdigit():
                    v = int(v)
                elif v.lower() == "true":
                    v = True
                elif v.lower() == "false":
                    v = False
                if k:
                    data[k] = v
    return data


def load_project_config(app_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
    manifest: dict[str, Any] = {}
    for filename in ("forge.json", "forge.yaml", "forge.yml"):
        manifest_path = app_dir / filename
        if manifest_path.is_file():
            manifest = parse_manifest(manifest_path)
            break

    env_path = app_dir / ".env"
    env_vars = parse_env_file(env_path)

    return manifest, env_vars
