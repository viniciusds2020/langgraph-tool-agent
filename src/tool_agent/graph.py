from __future__ import annotations

import operator
import os
from functools import lru_cache
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt

from tool_agent.safe_tools import (
    calculate,
    current_datetime,
    knowledge_search,
    profile_csv,
    sqlite_read_query,
)

SYSTEM_PROMPT = """Você é um agente analítico orientado a ferramentas.
Planeje silenciosamente, use somente as ferramentas disponíveis e responda em português.
Não invente resultados de ferramentas. Cite quais ferramentas sustentam a conclusão.
Consultas SQL exigem aprovação humana. Pare quando houver evidência suficiente.
Máximo de oito ciclos de execução."""


@tool
def calculator(expression: str) -> float:
    """Calcula uma expressão aritmética sem executar código."""
    return calculate(expression)


@tool
def calendar_now(timezone: str = "America/Sao_Paulo") -> str:
    """Retorna data e hora atuais para um timezone IANA."""
    return current_datetime(timezone)


@tool
def csv_profiler(dataset_id: int) -> str:
    """Analisa qualidade, nulos, constantes, IDs e estatísticas de um CSV cadastrado."""
    return profile_csv(dataset_id)


@tool
def read_business_database(query: str) -> str:
    """Executa SELECT somente leitura na tabela business_metrics após aprovação."""
    return sqlite_read_query(query)


@tool
def search_agent_knowledge(query: str) -> str:
    """Busca boas práticas de agentes, governança e qualidade na base local."""
    return knowledge_search(query)


TOOLS = [calculator, calendar_now, csv_profiler, read_business_database, search_agent_knowledge]
TOOL_MAP = {item.name: item for item in TOOLS}
SENSITIVE_TOOLS = {"read_business_database"}


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    iterations: int
    traces: Annotated[list[dict], operator.add]


def create_graph():
    model = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
    ).bind_tools(TOOLS)

    def agent_node(state: AgentState) -> dict:
        response = model.invoke([SystemMessage(content=SYSTEM_PROMPT), *state["messages"]])
        calls = [call["name"] for call in getattr(response, "tool_calls", [])]
        return {
            "messages": [response],
            "iterations": state.get("iterations", 0) + 1,
            "traces": [{"node": "agent", "tools_requested": calls}],
        }

    def tool_node(state: AgentState) -> dict:
        last = state["messages"][-1]
        outputs, traces = [], []
        for call in last.tool_calls:
            name, arguments = call["name"], call["args"]
            if name in SENSITIVE_TOOLS:
                decision = interrupt({
                    "type": "tool_approval",
                    "tool": name,
                    "arguments": arguments,
                    "reason": "Consulta a uma fonte de dados governada.",
                })
                if not decision.get("approved", False):
                    outputs.append(ToolMessage(
                        content="Execução recusada pelo usuário.", tool_call_id=call["id"]
                    ))
                    traces.append({"node": "tool", "tool": name, "status": "denied"})
                    continue
            selected = TOOL_MAP.get(name)
            if selected is None:
                result = "Ferramenta não permitida."
                status = "blocked"
            else:
                try:
                    result = selected.invoke(arguments)
                    status = "completed"
                except Exception as exc:
                    result = f"Falha controlada: {exc}"
                    status = "failed"
            outputs.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
            traces.append({"node": "tool", "tool": name, "status": status})
        return {"messages": outputs, "traces": traces}

    def route(state: AgentState):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls and state["iterations"] < 8:
            return "tools"
        return END

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=InMemorySaver())


@lru_cache
def runtime():
    return create_graph()


def resume_graph(thread_id: str, approved: bool):
    return runtime().invoke(
        Command(resume={"approved": approved}),
        config={"configurable": {"thread_id": thread_id}},
    )
