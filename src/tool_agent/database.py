from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def database_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", "data/tool_agent.db"))


@contextmanager
def connection():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def initialize() -> None:
    with connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS datasets(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                csv_content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS business_metrics(
                month TEXT PRIMARY KEY,
                revenue REAL NOT NULL,
                customers INTEGER NOT NULL,
                tickets INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                question TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                answer TEXT,
                traces_json TEXT NOT NULL DEFAULT '[]',
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        if db.execute("SELECT COUNT(*) FROM business_metrics").fetchone()[0] == 0:
            db.executemany(
                "INSERT INTO business_metrics(month,revenue,customers,tickets) VALUES(?,?,?,?)",
                [
                    ("2026-01", 125000.0, 820, 190),
                    ("2026-02", 119500.0, 805, 215),
                    ("2026-03", 132400.0, 861, 177),
                    ("2026-04", 141200.0, 902, 165),
                ],
            )


def create_dataset(name: str, content: str) -> int:
    with connection() as db:
        return db.execute(
            "INSERT INTO datasets(name,csv_content) VALUES(?,?)", (name, content)
        ).lastrowid


def get_dataset(dataset_id: int) -> dict | None:
    with connection() as db:
        row = db.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        return dict(row) if row else None


def list_datasets() -> list[dict]:
    with connection() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT id,name,created_at,LENGTH(csv_content) bytes FROM datasets ORDER BY id DESC"
            ).fetchall()
        ]


def save_run(payload: dict) -> int:
    with connection() as db:
        return db.execute(
            """INSERT INTO runs(thread_id,question,mode,status,answer,traces_json,
            input_tokens,output_tokens,duration_ms) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                payload["thread_id"], payload["question"], payload["mode"], payload["status"],
                payload.get("answer"), json.dumps(payload.get("traces", []), ensure_ascii=False),
                payload.get("input_tokens", 0), payload.get("output_tokens", 0),
                payload.get("duration_ms", 0),
            ),
        ).lastrowid


def list_runs(limit: int = 30) -> list[dict]:
    with connection() as db:
        return [
            dict(row)
            for row in db.execute(
                """SELECT id,thread_id,question,mode,status,input_tokens,output_tokens,
                duration_ms,created_at FROM runs ORDER BY id DESC LIMIT ?""",
                (min(max(limit, 1), 100),),
            ).fetchall()
        ]

