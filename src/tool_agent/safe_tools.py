from __future__ import annotations

import ast
import io
import json
import math
import operator
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from tool_agent.database import connection, get_dataset

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculate(expression: str) -> float:
    if len(expression) > 200:
        raise ValueError("Expression is too long.")
    tree = ast.parse(expression, mode="eval")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("Exponent outside the safe limit.")
            return OPERATORS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](evaluate(node.operand))
        raise ValueError("Unsupported expression.")

    result = float(evaluate(tree))
    if not math.isfinite(result):
        raise ValueError("Result is not finite.")
    return result


def current_datetime(timezone: str = "America/Sao_Paulo") -> str:
    try:
        return datetime.now(ZoneInfo(timezone)).isoformat()
    except Exception as exc:
        raise ValueError("Invalid IANA timezone.") from exc


def profile_csv(dataset_id: int) -> str:
    dataset = get_dataset(dataset_id)
    if not dataset:
        raise ValueError("Dataset not found.")
    frame = pd.read_csv(io.StringIO(dataset["csv_content"]))
    report = {
        "dataset": dataset["name"],
        "rows": len(frame),
        "columns": len(frame.columns),
        "duplicated_rows": int(frame.duplicated().sum()),
        "constant_columns": [
            name for name in frame if frame[name].nunique(dropna=False) <= 1
        ],
        "possible_ids": [
            name for name in frame
            if len(frame) > 20 and frame[name].nunique(dropna=True) / len(frame) >= 0.98
        ],
        "missing_fraction": {
            name: round(float(value), 4)
            for name, value in frame.isna().mean().items()
            if value > 0
        },
        "numeric_summary": frame.describe(include="number").round(3).to_dict(),
    }
    return json.dumps(report, ensure_ascii=False, default=str)


def sqlite_read_query(query: str) -> str:
    normalized = re.sub(r"\s+", " ", query.strip()).lower()
    forbidden = (";", "--", "/*", "pragma", "attach", "insert", "update", "delete",
                 "drop", "alter", "create", "replace")
    if not normalized.startswith("select ") or any(token in normalized for token in forbidden):
        raise ValueError("Only one read-only SELECT is allowed.")
    if "business_metrics" not in normalized:
        raise ValueError("Only the business_metrics table is available.")
    with connection() as db:
        cursor = db.execute(query)
        rows = cursor.fetchmany(100)
        columns = [item[0] for item in cursor.description]
    return json.dumps([dict(zip(columns, row, strict=True)) for row in rows], ensure_ascii=False)


def knowledge_search(query: str) -> str:
    documents = [
        "Quality gates prevent models or agents from being promoted below acceptance criteria.",
        "Human approval is recommended before external writes, payments, deletion or messaging.",
        "LangGraph checkpoints persist state by thread and enable pause and resume workflows.",
        "Tool allowlists, timeouts and structured inputs reduce the attack surface of agents.",
    ]
    terms = set(re.findall(r"[a-zA-ZÀ-ÿ]{4,}", query.lower()))
    ranked = sorted(
        documents,
        key=lambda text: len(terms.intersection(set(text.lower().split()))),
        reverse=True,
    )
    return json.dumps(ranked[:3], ensure_ascii=False)
