# Forge

Forge is an educational deployment platform designed to automate the build, deployment, execution, and lifecycle management of applications running in Docker containers.

The primary objective is to build a simplified, self-hosted alternative to platforms such as Heroku and Coolify while gaining practical understanding of deployment systems, container orchestration concepts, asynchronous job execution, health monitoring, version management, rollback mechanisms, and server infrastructure.

Forge accepts either a local application directory or, in later iterations, a Git repository as its deployment source. It builds a Docker image from the application, creates and starts a container, monitors its execution state, performs health validation, and exposes deployment information to the user.

## Core Deployment Pipeline

```text
Application Source
       │
       ├── Local Directory
       └── Git Repository
              │
              ▼
        Deployment Engine
              │
              ▼
         Docker Build
              │
              ▼
          Docker Image
              │
              ▼
        Container Runtime
              │
              ▼
         Health Check
              │
        ┌─────┴─────┐
        │           │
      HEALTHY      FAILED
        │           │
        ▼           ▼
     Running     Cleanup /
                  Failure State
```

## Initial Scope

The first version of Forge should implement a minimal but functional deployment engine capable of:

* accepting an application path through a CLI;
* validating the deployment context and checking for a `Dockerfile`;
* invoking the Docker CLI to build an application image;
* creating and starting a Docker container from the generated image;
* capturing `stdout`, `stderr`, and process exit codes;
* retrieving container metadata and runtime state;
* reporting deployment status to the user;
* stopping running containers;
* retrieving and displaying container logs;
* handling basic build and runtime failures without leaving the system in an inconsistent state.

The initial implementation should deliberately avoid unnecessary abstractions. The goal is to establish a reliable deployment lifecycle before introducing persistent state, networking, asynchronous execution, or distributed components.

## Deployment Lifecycle

A deployment can be represented as a state machine:

```text
PENDING
   │
   ▼
BUILDING
   │
   ├──────────────► FAILED
   │
   ▼
STARTING
   │
   ├──────────────► FAILED
   │
   ▼
HEALTHY
   │
   ├──────────────► STOPPED
   │
   └──────────────► FAILED
```

As the platform evolves, deployment state should become explicit rather than being inferred directly from Docker processes.

The planned states are:

```text
PENDING
BUILDING
STARTING
HEALTHY
FAILED
STOPPED
```

This state model will eventually allow Forge to distinguish between a deployment that is currently being built, one that failed during startup, one that is running correctly, and one that was intentionally stopped.

## Planned Capabilities

Once the basic deployment engine is stable, Forge should evolve toward a complete deployment platform.

### Git-based Deployments

Applications should be deployable directly from Git repositories. Forge will be responsible for cloning or fetching the requested revision and using that source tree as the deployment context.

Future deployments should be associated with immutable revisions, such as Git commit hashes, rather than only human-readable branch names.

### Persistent State

Deployment metadata should be stored in PostgreSQL.

A deployment record may eventually contain information such as:

```text
Project
Deployment
  ├── ID
  ├── Project ID
  ├── Source revision
  ├── Image reference
  ├── Container ID
  ├── Status
  ├── Created timestamp
  ├── Started timestamp
  └── Finished timestamp
```

This allows Forge to reconstruct deployment history independently of the current Docker runtime state.

### Background Workers

Builds and deployments are potentially long-running operations and should not block API request handlers.

The architecture will therefore evolve toward asynchronous job execution:

```text
API
 │
 ▼
Job / Deployment Record
 │
 ▼
Worker
 │
 ├── Build
 ├── Start
 ├── Health Check
 └── Update State
```

The worker becomes responsible for executing deployment jobs while the API remains responsive and primarily handles control-plane operations.

### Health Checks

A container being in the `running` state does not necessarily mean that the application is operational.

Forge should therefore support application-level health validation through mechanisms such as HTTP health endpoints or Docker health checks.

The deployment should only become `HEALTHY` after the configured health check succeeds.

```text
Container Started
       │
       ▼
Health Check
   │         │
Success    Failure
   │         │
   ▼         ▼
HEALTHY    FAILED
```

### Version Management

Each deployment should produce a uniquely identifiable application version.

For example:

```text
my-app:v1
my-app:v2
my-app:v3
```

or, preferably, immutable image references based on deployment IDs or source revisions.

Forge should maintain the relationship between application versions, Docker images, containers, and deployment status.

### Rollback

Once multiple versions are supported, Forge should be capable of reverting an application to the last known-good deployment.

A rollback should not rebuild the application unnecessarily. Instead, it should reuse the previously built immutable image when possible.

```text
v1 ──► v2 ──► v3
       │       │
       │       └── FAILED
       │
       └────────── Rollback
                    │
                    ▼
                   v2
```

### Zero-Downtime Deployment

Later iterations should support deploying a new version without immediately terminating the currently healthy version.

The conceptual workflow is:

```text
v1 RUNNING
    │
    ▼
Deploy v2
    │
    ▼
v2 STARTING
    │
    ▼
v2 HEALTHY
    │
    ▼
Traffic → v2
    │
    ▼
Stop v1
```

This requires separating application lifecycle management from traffic routing and will naturally lead to the introduction of a reverse proxy.

### Reverse Proxy

Caddy or Nginx can eventually act as the external entry point for deployed applications.

The proxy layer will be responsible for routing incoming requests to the currently active container.

```text
Internet
   │
   ▼
Reverse Proxy
   │
   ├── app-v1
   └── app-v2
```

This layer becomes essential for zero-downtime deployments, version switching, domain management, and TLS termination.

### CI/CD

Forge should eventually be capable of automatically creating deployments in response to repository changes.

A possible pipeline:

```text
Git Push
   │
   ▼
CI Trigger
   │
   ▼
Forge Deployment
   │
   ▼
Build Image
   │
   ▼
Start Candidate
   │
   ▼
Health Check
   │
   ▼
Promote Version
```

GitHub Actions can initially provide the external CI trigger while Forge remains responsible for deployment orchestration.

### Resource Limits and Isolation

Docker containers should eventually support configurable resource constraints, including CPU and memory limits.

Basic isolation should also be considered when executing untrusted or user-provided applications.

The platform should treat container execution as a privileged infrastructure operation rather than simply executing arbitrary Docker commands without restrictions.

## Technology Stack

The initial technology stack is intentionally small:

```text
Python
FastAPI
PostgreSQL
SQLAlchemy
Alembic
Docker
Linux
Caddy / Nginx
GitHub Actions
pytest
```

Additional technologies should only be introduced when a concrete architectural problem requires them.

For example, a message broker or dedicated task queue should not be introduced merely because production deployment platforms commonly use one. Forge should first establish the underlying worker model and introduce additional infrastructure only when its limitations become apparent.

## Development Philosophy

Forge should not begin as a fully designed production architecture.

The system should evolve incrementally, with each architectural component introduced as a response to a concrete limitation in the previous implementation.

The intended progression is:

```text
Python Script
      │
      ▼
Docker Integration
      │
      ▼
CLI
      │
      ▼
Deployment Engine
      │
      ▼
HTTP API
      │
      ▼
Persistent State
      │
      ▼
Background Workers
      │
      ▼
Health Checks
      │
      ▼
Version Management
      │
      ▼
Rollback
      │
      ▼
Reverse Proxy
      │
      ▼
CI/CD
      │
      ▼
Production-like Deployment Platform
```

This approach is deliberate. Forge is not primarily a feature-development project. It is an infrastructure engineering exercise.

The purpose is to understand how the control plane communicates with the container runtime, how deployment state is represented and persisted, how long-running operations are executed safely, how failures propagate through the system, and how individual infrastructure components eventually form a coherent deployment platform.

The final system should therefore be judged not only by the number of features it supports, but by how well its implementation demonstrates the underlying mechanisms of modern deployment infrastructure.
