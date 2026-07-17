from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tool_agent.api import router
from tool_agent.database import initialize

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize()
    yield


app = FastAPI(
    title="LangGraph Tool Agent",
    version="0.1.0",
    description="Stateful problem-solving agent with safe tools and human approval.",
    lifespan=lifespan,
)
app.include_router(router)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "graph": "agent -> tools -> agent"}


def run() -> None:
    import uvicorn
    uvicorn.run("tool_agent.main:app", host="0.0.0.0", port=8000)

