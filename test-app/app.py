import os
from fastapi import FastAPI

app = FastAPI(title="test-app")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "status": "ok",
        "app_env": os.getenv("APP_ENV", "development"),
        "secret_key": os.getenv("SECRET_KEY", "not-set"),
        "database_url": os.getenv("DATABASE_URL", "sqlite:///default.db"),
    }