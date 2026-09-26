from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="Streaming Live RAG")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
