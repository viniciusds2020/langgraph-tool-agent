from fastapi.testclient import TestClient

from tool_agent.database import initialize
from tool_agent.main import app


def test_agent_simulation_and_dataset_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "api.db"))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    initialize()
    with TestClient(app) as client:
        dataset = client.post(
            "/api/datasets",
            json={"name": "sales.csv", "csv_content": "id,value\n1,10\n2,20\n"},
        )
        assert dataset.status_code == 201
        response = client.post(
            "/api/agent/run",
            json={"question": f"Analise o dataset #{dataset.json()['id']}", "live": False},
        )
        assert response.status_code == 200
        assert response.json()["mode"] == "simulation"
        assert response.json()["input_tokens"] == 0
        assert client.get("/api/runs").json()


def test_health_and_capabilities(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "health.db"))
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        tools = client.get("/api/capabilities").json()["tools"]
        assert any(item["approval"] for item in tools)

