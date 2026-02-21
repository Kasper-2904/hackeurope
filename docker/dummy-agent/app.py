from fastapi import FastAPI
import os

app = FastAPI(title="Dummy Agent")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/info")
def info() -> dict:
    return {
        "agent_name": os.getenv("AGENT_NAME", "dummy-agent"),
        "agent_role": os.getenv("AGENT_ROLE", "specialist"),
        "agent_version": os.getenv("AGENT_VERSION", "0.1.0"),
    }
