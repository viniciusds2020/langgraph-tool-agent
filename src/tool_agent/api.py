from __future__ import annotations

import csv
import io
import os

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from tool_agent.database import create_dataset, list_datasets, list_runs
from tool_agent.service import execute, resume

router = APIRouter(prefix="/api")


class AgentRequest(BaseModel):
    question: str = Field(min_length=3, max_length=5000)
    live: bool = False
    thread_id: str | None = Field(default=None, max_length=100)


class ResumeRequest(BaseModel):
    question: str = Field(min_length=3, max_length=5000)
    approved: bool


class DatasetCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    csv_content: str = Field(min_length=3, max_length=2_000_000)


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "live_available": bool(os.getenv("GROQ_API_KEY")),
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "max_iterations": 8,
        "tools": [
            {"name": "calculator", "approval": False},
            {"name": "calendar_now", "approval": False},
            {"name": "csv_profiler", "approval": False},
            {"name": "read_business_database", "approval": True},
            {"name": "search_agent_knowledge", "approval": False},
        ],
    }


@router.post("/agent/run")
def run_agent(request: AgentRequest) -> dict:
    try:
        return execute(request.question, request.live, request.thread_id)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/agent/{thread_id}/resume")
def resume_agent(thread_id: str, request: ResumeRequest) -> dict:
    try:
        return resume(thread_id, request.question, request.approved)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/datasets", status_code=status.HTTP_201_CREATED)
def add_dataset(request: DatasetCreate) -> dict:
    try:
        reader = csv.reader(io.StringIO(request.csv_content))
        header = next(reader)
        if not header or len(header) > 500:
            raise ValueError("CSV header is invalid.")
    except Exception as exc:
        raise HTTPException(422, "Invalid CSV content.") from exc
    dataset_id = create_dataset(request.name, request.csv_content)
    return {"id": dataset_id, "name": request.name, "columns": header}


@router.get("/datasets")
def datasets() -> list[dict]:
    return list_datasets()


@router.get("/runs")
def runs(limit: int = 30) -> list[dict]:
    return list_runs(limit)

