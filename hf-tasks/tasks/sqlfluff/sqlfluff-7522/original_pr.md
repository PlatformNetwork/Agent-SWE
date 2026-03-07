# sqlfluff/sqlfluff-7522 (original PR)

sqlfluff/sqlfluff (#7522): Databricks: Fixes for Create MV Statement

<!--Thanks for adding this feature!-->

<!--Please give the Pull Request a meaningful title for the release notes-->

### Brief summary of the change made
Fixes #7521 bug where table constraint segments were missing in the table definition.
Also fixes a small Row Filter bug that I introduced when creating this new CreateMaterializedViewStatementSegment by mistakenly not using a reference to the already existing RowFilterClauseGrammar.  Added tests to show these nuances to the syntax.

### Are there any other side effects of this change that we should be aware of?
No

### Pull Request checklist
- [x] Please confirm you have completed any of the necessary steps below.

- Included test cases to demonstrate any code changes, which may be one or more of the following:
  - `.yml` rule test cases in `test/fixtures/rules/std_rule_cases`.
  - `.sql`/`.yml` parser test cases in `test/fixtures/dialects` (note YML files can be auto generated with `tox -e generate-fixture-yml`).
  - Full autofix test cases in `test/fixtures/linter/autofix`.
  - Other.
- Added appropriate documentation for the change.
- Created GitHub issues for any relevant followup/future enhancements if appropriate.

