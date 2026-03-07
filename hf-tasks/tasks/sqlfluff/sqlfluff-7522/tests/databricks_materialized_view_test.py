from sqlfluff.core import FluffConfig, Linter


def _parse_databricks(sql: str):
    config = FluffConfig(overrides={"dialect": "databricks"})
    linter = Linter(config=config)
    parsed = linter.parse_string(sql)
    assert parsed.tree
    assert not parsed.violations
    assert "unparsable" not in parsed.tree.type_set()
    return parsed.tree


def test_databricks_materialized_view_allows_table_constraints():
    sql = """
    CREATE OR REPLACE MATERIALIZED VIEW mv_constraints (
        col1 BIGINT,
        col2 STRING,
        col3 BOOLEAN,
        CONSTRAINT pk_mv PRIMARY KEY (col1),
        CONSTRAINT fk_mv FOREIGN KEY (col2) REFERENCES dim_table (col2)
    ) AS SELECT col1, col2, col3 FROM source_table;
    """
    tree = _parse_databricks(sql)
    table_constraints = list(tree.recursive_crawl("table_constraint"))
    assert len(table_constraints) == 2
    column_defs = list(tree.recursive_crawl("column_definition"))
    assert len(column_defs) >= 3


def test_databricks_row_filter_allows_literal_and_qualified_function():
    sql = """
    CREATE MATERIALIZED VIEW mv_filtered
    WITH ROW FILTER security.filter_func ON (region, 'APAC')
    AS SELECT * FROM customers;
    """
    tree = _parse_databricks(sql)
    object_refs = [seg.raw.lower() for seg in tree.recursive_crawl("object_reference")]
    assert "security.filter_func" in object_refs
    column_refs = [seg.raw.lower() for seg in tree.recursive_crawl("column_reference")]
    assert "region" in column_refs


def test_databricks_row_filter_allows_empty_argument_list():
    sql = """
    CREATE MATERIALIZED VIEW mv_zero_arg
    WITH ROW FILTER sec.zero_arg_filter ON ()
    AS SELECT 1;
    """
    tree = _parse_databricks(sql)
    bracketed = [seg.raw for seg in tree.recursive_crawl("bracketed")]
    assert "()" in bracketed
    assert "sec.zero_arg_filter" in [
        seg.raw.lower() for seg in tree.recursive_crawl("object_reference")
    ]
