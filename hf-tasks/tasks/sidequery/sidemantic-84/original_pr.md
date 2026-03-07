# sidequery/sidemantic-84 (original PR)

sidequery/sidemantic (#84): Fix temporal JSON serialization and hierarchy cycle detection

## Summary

- Convert date/datetime/time values to ISO strings in `_convert_to_json_compatible` so temporal queries through `run_query` and `run_sql` don't fail at MCP response serialization
- Add cycle detection to `Model.get_hierarchy_path` using a visited set, preventing infinite loops on malformed parent references (e.g., A->B->A)
- Fix `sqlglot.exp.AlterTable` reference to `sqlglot.exp.Alter` in `_validate_filter` (AlterTable doesn't exist in current sqlglot)
