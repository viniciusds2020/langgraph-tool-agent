import json

import pytest

from tool_agent.database import create_dataset, initialize
from tool_agent.safe_tools import calculate, profile_csv, sqlite_read_query


def test_calculator_blocks_code_execution():
    assert calculate("10 + 2 * 3") == 16
    with pytest.raises(ValueError):
        calculate("__import__('os').system('echo unsafe')")


def test_csv_profiler_and_read_only_sql(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "tools.db"))
    initialize()
    dataset_id = create_dataset(
        "quality.csv",
        "id,value,constant\n1,10,A\n2,,A\n3,30,A\n",
    )
    profile = json.loads(profile_csv(dataset_id))
    assert profile["rows"] == 3
    assert "constant" in profile["constant_columns"]
    rows = json.loads(sqlite_read_query(
        "SELECT month, revenue FROM business_metrics ORDER BY month"
    ))
    assert len(rows) == 4
    with pytest.raises(ValueError):
        sqlite_read_query("DELETE FROM business_metrics")

