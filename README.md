# Forge

> Lightweight zero-dependency deployment engine with zero-downtime Blue-Green rollouts and Traefik ingress.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)]()

Forge is a minimalist PaaS and deployment engine built entirely on the Python standard library. It provisions an automated Traefik reverse proxy, orchestrates container builds, performs in-container health checks, and guarantees zero-downtime deployments with graceful shutdown.

---

## Architecture

```text
 Client Request (http://<app>.localhost)
                   │
                   ▼
       ┌────────────────────────┐
       │   Traefik Proxy (80)   │  (Docker Provider on forge-net)
       └───────────┬────────────┘
                   │
         ┌─────────┴─────────┐
         │ Dynamic Routing   │
         ▼                   ▼
┌──────────────────┐   ┌──────────────────┐
│  Candidate (v2)  │   │   Active (v1)    │
│  (HEALTH CHECK)  │   │  (SERVING TRAFFIC│
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         ├─► [docker exec]      │
         │   (urlopen /health)  │
         │                      │
   [200 OK passed]              │
         │                      │
         ▼                      ▼
  Traefik switches ────► Graceful Stop
  traffic to v2          (SIGTERM -t 10)
                                │
                                ▼
                         docker rm (v1)
```

---

## Core Features

- **Pure Python Standard Library**: Zero external pip dependencies required to run the Forge engine. Built strictly on Python 3.10+ native modules (`subprocess`, `urllib`, `json`, `dataclasses`).
- **In-Container Health Verification**: Performs isolated application health validation via `docker exec` using an internal Python one-liner without requiring exposed host ports.
- **Zero-Downtime Blue-Green Lifecycle**: New container versions are built and verified before traffic cuts over. The previous container is decommissioned only after the candidate passes health checks.
- **Graceful Shutdown**: Sends `SIGTERM` with configurable timeout (`docker stop -t 10`) giving Traefik and existing requests time to finish before final container removal.
- **Automatic Reverse Proxy & Domain Routing**: Sets up an isolated bridge network (`forge-net`) and manages a Traefik reverse proxy that dynamically binds `<app>.localhost` domains via container labels.
- **Environment & Manifest Configuration**: Automatically parses and injects `.env` files and optional `forge.json` or `forge.yaml` manifests.
- **Cross-Platform Support**: Fully compatible with Linux and Windows (Docker Desktop / WSL2).

---

## Quickstart

### Prerequisites

- Python 3.10+
- Docker Engine / Docker Desktop (running)

### Installation

Clone the repository and install the CLI locally:

```bash
git clone https://github.com/madishkin/Forge.git
cd Forge
pip install -e .
```

### Deploying an Application

To deploy any project containing a `Dockerfile`:

```bash
forge path/to/your-app
```

Or run via module directly:

```bash
python main.py path/to/your-app
```

Once the build and health checks complete, your app is live at:
```text
http://<app-name>.localhost
```

---

## Configuration

Forge works out of the box with zero configuration by discovering your `Dockerfile` and exposing default port `8000`.

To customize routing, ports, or health checks, place a `forge.json` (or `forge.yaml`) in your application root:

```json
{
  "app_name": "my-service",
  "domain": "my-service.localhost",
  "container_port": 8000,
  "health_check_path": "/health"
}
```

### Environment Variables

Any `.env` file present in the target application directory is automatically parsed and injected into the container during `docker run`:

```env
APP_ENV=production
SECRET_KEY=forge-secret-token
DATABASE_URL=postgres://user:pass@db:5432/app
```

---

## Testing

Forge includes a comprehensive unit test suite covering Docker adapter operations, CLI arguments, configuration parsers, health checkers, and deployment lifecycle edge cases:

```bash
python -m unittest discover tests
```

---

## License

This project is licensed under the [MIT License](LICENSE).
