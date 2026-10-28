import pytest

from tool_agent.database import initialize
from tool_agent.safe_tools import sqlite_read_query


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tools.db"))
    initialize()

def test_rejects_unapproved_table_even_when_allowed_name_in_literal(db):
    with pytest.raises(ValueError):
        sqlite_read_query("SELECT name FROM sqlite_master WHERE name = 'business_metrics'")

def test_rejects_join_to_unapproved_table(db):
    with pytest.raises(ValueError):
        sqlite_read_query("SELECT b.month FROM business_metrics b JOIN datasets d ON 1=1")

def test_allows_parameter_free_safe_projection(db):
    result = sqlite_read_query("SELECT month, revenue FROM business_metrics ORDER BY month")
    assert "2026-01" in result
