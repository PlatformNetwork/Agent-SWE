# sqlfluff/sqlfluff-7522

Fix the Databricks CREATE MATERIALIZED VIEW parsing so that table constraints are included in the table definition and row filter clauses are correctly recognized using the existing grammar. Ensure the syntax supports these clauses as expected.
