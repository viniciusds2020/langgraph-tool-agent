from __future__ import annotations

import os
import re
import time
import uuid

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from tool_agent.database import save_run
from tool_agent.graph import resume_graph, runtime
from tool_agent.safe_tools import calculate, current_datetime, knowledge_search, profile_csv


def simulate(question: str, thread_id: str) -> dict:
    started = time.perf_counter()
    traces = [{"node": "planner", "status": "completed", "detail": "Intenção identificada."}]
    evidence = []
    lowered = question.lower()
    dataset_match = re.search(r"dataset\s*#?\s*(\d+)", lowered)
    expression_match = re.search(r"(-?\d+(?:\.\d+)?\s*[+*/%-]\s*-?\d+(?:\.\d+)?)", question)
    if dataset_match:
        result = profile_csv(int(dataset_match.group(1)))
        traces.append({"node": "tool", "tool": "csv_profiler", "status": "completed"})
        evidence.append(result)
    elif expression_match:
        result = calculate(expression_match.group(1))
        traces.append({"node": "tool", "tool": "calculator", "status": "completed"})
        evidence.append(f"Resultado do cálculo: {result}")
    elif any(word in lowered for word in ("data", "hora", "hoje")):
        result = current_datetime()
        traces.append({"node": "tool", "tool": "calendar_now", "status": "completed"})
        evidence.append(f"Data e hora: {result}")
    else:
        result = knowledge_search(question)
        traces.append({"node": "tool", "tool": "search_agent_knowledge", "status": "completed"})
        evidence.append(result)
    traces.append({"node": "reviewer", "status": "completed", "detail": "Evidência validada."})
    answer = "Análise em modo simulado baseada nas ferramentas locais:\n" + "\n".join(evidence)
    payload = {
        "thread_id": thread_id, "question": question, "mode": "simulation",
        "status": "completed", "answer": answer, "traces": traces,
        "input_tokens": 0, "output_tokens": 0,
        "duration_ms": round((time.perf_counter() - started) * 1000),
    }
    payload["run_id"] = save_run(payload)
    return payload


def execute(question: str, live: bool, thread_id: str | None = None) -> dict:
    thread_id = thread_id or str(uuid.uuid4())
    if not live or not os.getenv("GROQ_API_KEY"):
        return simulate(question, thread_id)
    started = time.perf_counter()
    result = runtime().invoke(
        {"messages": [HumanMessage(content=question)], "iterations": 0, "traces": []},
        config={"configurable": {"thread_id": thread_id}},
    )
    return _serialize_live(result, question, thread_id, started)


def resume(thread_id: str, question: str, approved: bool) -> dict:
    started = time.perf_counter()
    result = resume_graph(thread_id, approved)
    return _serialize_live(result, question, thread_id, started)


def _serialize_live(result: dict, question: str, thread_id: str, started: float) -> dict:
    interrupts = result.get("__interrupt__", [])
    messages = result.get("messages", [])
    answer = next(
        (message.content for message in reversed(messages)
         if isinstance(message, AIMessage) and not message.tool_calls),
        None,
    )
    input_tokens = output_tokens = 0
    for message in messages:
        usage = getattr(message, "usage_metadata", None) or {}
        input_tokens += int(usage.get("input_tokens", 0))
        output_tokens += int(usage.get("output_tokens", 0))
    traces = list(result.get("traces", []))
    traces.extend(
        {"node": "observation", "tool_call_id": message.tool_call_id}
        for message in messages if isinstance(message, ToolMessage)
    )
    status = "approval_required" if interrupts else "completed"
    payload = {
        "thread_id": thread_id, "question": question, "mode": "live", "status": status,
        "answer": answer, "traces": traces, "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "pending_approval": [
            getattr(item, "value", item) for item in interrupts
        ],
    }
    payload["run_id"] = save_run(payload)
    return payload

