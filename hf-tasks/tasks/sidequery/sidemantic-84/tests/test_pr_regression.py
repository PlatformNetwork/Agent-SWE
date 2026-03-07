import json
import signal
import pytest

from sidemantic import Dimension, Metric, Model
from sidemantic import mcp_server
from sidemantic.mcp_server import initialize_layer, run_query
from sqlglot import parse_one, exp
import sqlglot


@pytest.fixture
def temporal_layer(tmp_path):
    model_yaml = """
models:
  - name: events
    table: events_table
    dimensions:
      - name: event_id
        sql: event_id
        type: categorical
      - name: event_date
        sql: event_date
        type: time
        granularity: day
      - name: event_timestamp
        sql: event_timestamp
        type: time
        granularity: hour
    metrics:
      - name: event_count
        agg: count
"""
    model_file = tmp_path / "events.yml"
    model_file.write_text(model_yaml)

    layer = initialize_layer(str(tmp_path), db_path=":memory:")
    layer.get_model("events").primary_key = "event_id"
    layer.adapter.execute(
        """
        CREATE TABLE events_table (
            event_id INTEGER,
            event_date DATE,
            event_timestamp TIMESTAMP
        )
        """
    )
    layer.adapter.execute(
        """
        INSERT INTO events_table VALUES
            (1, '2024-02-10', '2024-02-10 09:15:30'),
            (2, '2024-02-11', '2024-02-11 10:45:00')
        """
    )

    return layer


def test_run_query_temporal_values_json_serializable(temporal_layer):
    result = run_query(
        dimensions=[
            "events.event_date",
            "events.event_timestamp",
        ],
        metrics=["events.event_count"],
    )

    assert result["row_count"] == 2
    assert len(result["rows"]) == 2

    for row in result["rows"]:
        assert isinstance(row["event_date"], str)
        assert isinstance(row["event_timestamp"], str)
        assert row["event_date"].startswith("2024-02-")
        assert "T" in row["event_timestamp"]

    json.dumps(result)


def _timeout_handler(signum, frame):
    raise TimeoutError("get_hierarchy_path timed out")


def test_hierarchy_path_cycle_with_timeout():
    model = Model(
        name="cycle",
        table="t",
        dimensions=[
            Dimension(name="alpha", type="categorical", parent="beta"),
            Dimension(name="beta", type="categorical", parent="gamma"),
            Dimension(name="gamma", type="categorical", parent="alpha"),
        ],
        metrics=[Metric(name="count", agg="count")],
    )

    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(2)
    try:
        path = model.get_hierarchy_path("beta")
    finally:
        signal.alarm(0)

    assert path[0] in {"alpha", "beta", "gamma"}
    assert "beta" in path
    assert len(path) == 3


def test_validate_filter_rejects_alter_statements():
    parsed = parse_one("SELECT 1 WHERE 1=1")
    parsed.set("where", exp.Where(this=exp.Alter(this=exp.to_identifier("users"))))

    def fake_parse_one(_sql, dialect=None):
        return parsed

    sqlglot.parse_one = fake_parse_one

    with pytest.raises(ValueError, match="disallowed SQL"):
        mcp_server._validate_filter("status = 'active'")
