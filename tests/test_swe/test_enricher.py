"""Tests for PR enrichment logic."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from swe_forge.swe.enricher import (
    EnrichedPullRequest,
    count_additions,
    count_deletions,
    detect_language,
    enrich_pr,
    enrich_prs_batch,
    extract_linked_issues,
    filter_bots,
    is_bot,
    parse_files_from_diff,
)
from swe_forge.swe.gharchive import GhArchiveEvent


def make_event(
    repo: str = "owner/repo",
    number: int = 123,
    title: str = "Test PR",
    body: str = "Test body",
    user: str = "testuser",
) -> GhArchiveEvent:
    return GhArchiveEvent(
        id="evt-test-123",
        event_type="PullRequestEvent",
        repository=repo,
        actor=user,
        action="merged",
        pull_number=number,
        title=title,
        body=body,
        user=user,
        base_sha="abc123",
        merge_sha="merge456",
        stars=100,
        created_at=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        merged_at=datetime(2023, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
    )


def make_diff(
    files: list[str] | None = None,
    additions: int = 10,
    deletions: int = 5,
) -> str:
    """Create a mock unified diff for testing."""
    if files is None:
        files = ["src/file1.py", "src/file2.py", "tests/test_file.py"]

    diff_lines = []
    for filepath in files:
        diff_lines.append(f"diff --git a/{filepath} b/{filepath}")
        diff_lines.append(f"--- a/{filepath}")
        diff_lines.append(f"+++ b/{filepath}")
        diff_lines.append("@@ -1,5 +1,10 @@")
        for _ in range(additions):
            diff_lines.append("+added line")
        for _ in range(deletions):
            diff_lines.append("-removed line")

    return "\n".join(diff_lines)


class TestIsBot:
    def test_detects_bot_with_bot_suffix(self):
        assert is_bot("dependabot[bot]") is True
        assert is_bot("renovate[bot]") is True
        assert is_bot("github-actions[bot]") is True

    def test_detects_dependabot(self):
        assert is_bot("dependabot") is True
        assert is_bot("dependabot-preview") is True

    def test_detects_renovate(self):
        assert is_bot("renovate") is True
        assert is_bot("renovatebot") is True

    def test_detects_github_actions(self):
        assert is_bot("github-actions") is True

    def test_detects_pyup(self):
        assert is_bot("pyup-bot") is True

    def test_not_bot_regular_user(self):
        assert is_bot("normaluser") is False
        assert is_bot("john-doe") is False
        assert is_bot("developer123") is False

    def test_case_insensitive(self):
        assert is_bot("DEPENDABOT[BOT]") is True
        assert is_bot("RenovateBot") is True


class TestDetectLanguage:
    def test_python_files(self):
        assert detect_language(["main.py", "utils.py"]) == "python"

    def test_javascript_files(self):
        assert detect_language(["index.js", "app.js"]) == "javascript"

    def test_typescript_files(self):
        assert detect_language(["index.ts", "utils.ts"]) == "typescript"

    def test_tsx_files(self):
        assert detect_language(["Component.tsx"]) == "typescript"

    def test_go_files(self):
        assert detect_language(["main.go"]) == "go"

    def test_rust_files(self):
        assert detect_language(["lib.rs", "main.rs"]) == "rust"

    def test_java_files(self):
        assert detect_language(["Main.java"]) == "java"

    def test_mixed_files_returns_most_common(self):
        files = ["a.py", "b.py", "c.py", "d.js", "e.js"]
        assert detect_language(files) == "python"

    def test_mixed_equal_count_returns_first(self):
        files = ["a.py", "b.js"]
        result = detect_language(files)
        assert result in ("python", "javascript")

    def test_empty_list_returns_unknown(self):
        assert detect_language([]) == "unknown"

    def test_no_recognized_extensions_returns_unknown(self):
        assert detect_language(["README", "Makefile", "Dockerfile"]) == "unknown"

    def test_handles_path_with_directories(self):
        assert detect_language(["src/lib/main.py"]) == "python"
        assert detect_language(["frontend/src/App.tsx"]) == "typescript"

    def test_multiple_extensions(self):
        files = ["test.spec.ts", "main.ts", "utils.ts"]
        assert detect_language(files) == "typescript"


class TestExtractLinkedIssues:
    def test_fixes_pattern(self):
        assert extract_linked_issues("fixes #123") == [123]
        assert extract_linked_issues("Fixes #456") == [456]
        assert extract_linked_issues("FIXES #789") == [789]

    def test_close_pattern(self):
        assert extract_linked_issues("close #100") == [100]
        assert extract_linked_issues("Closes #200") == [200]
        assert extract_linked_issues("closed #300") == [300]

    def test_resolve_pattern(self):
        assert extract_linked_issues("resolve #111") == [111]
        assert extract_linked_issues("Resolves #222") == [222]
        assert extract_linked_issues("resolved #333") == [333]

    def test_multiple_issues(self):
        result = extract_linked_issues("fixes #123 and closes #456")
        assert 123 in result
        assert 456 in result

    def test_duplicate_issues(self):
        result = extract_linked_issues("fixes #123 and fixes #123")
        assert result == [123]

    def test_empty_body(self):
        assert extract_linked_issues("") == []

    def test_no_issues(self):
        assert extract_linked_issues("Just some text") == []

    def test_sorted_output(self):
        result = extract_linked_issues("fixes #300 and fixes #100 and fixes #200")
        assert result == [100, 200, 300]


class TestEnrichedPullRequest:
    def test_create_minimal(self):
        pr = EnrichedPullRequest(
            id="evt-123",
            repo="owner/repo",
            number=123,
        )
        assert pr.id == "evt-123"
        assert pr.repo == "owner/repo"
        assert pr.number == 123
        assert pr.title == ""
        assert pr.is_bot is False

    def test_create_full(self):
        pr = EnrichedPullRequest(
            id="evt-456",
            repo="owner/repo",
            number=456,
            title="Add feature",
            body="Description",
            user="developer",
            state="closed",
            files_changed=5,
            additions=100,
            deletions=50,
            changed_files=["a.py", "b.py"],
            language="python",
            stars=1000,
            is_bot=False,
            linked_issues=[10, 20],
        )
        assert pr.id == "evt-456"
        assert pr.language == "python"
        assert pr.linked_issues == [10, 20]

    def test_defaults(self):
        pr = EnrichedPullRequest(id="x", repo="y", number=1)
        assert pr.files_changed == 0
        assert pr.additions == 0
        assert pr.deletions == 0
        assert pr.changed_files == []
        assert pr.language == "unknown"
        assert pr.linked_issues == []
        assert pr.metadata == {}

    def test_validates_non_negative(self):
        with pytest.raises(ValueError):
            EnrichedPullRequest(id="x", repo="y", number=1, additions=-1)

    def test_json_serialization(self):
        pr = EnrichedPullRequest(
            id="evt-123",
            repo="owner/repo",
            number=123,
            title="Test",
        )
        data = pr.model_dump()
        assert data["id"] == "evt-123"
        assert data["number"] == 123


class TestParseFilesFromDiff:
    def test_parses_single_file(self):
        diff = "diff --git a/src/main.py b/src/main.py\n--- a/src/main.py\n+++ b/src/main.py\n@@ -1,3 +1,4 @@\n+new line"
        assert parse_files_from_diff(diff) == ["src/main.py"]

    def test_parses_multiple_files(self):
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
diff --git a/tests/test_main.py b/tests/test_main.py
--- a/tests/test_main.py
+++ b/tests/test_main.py"""
        assert parse_files_from_diff(diff) == ["src/main.py", "tests/test_main.py"]

    def test_empty_diff_returns_empty_list(self):
        assert parse_files_from_diff("") == []

    def test_no_file_headers_returns_empty_list(self):
        assert parse_files_from_diff("some random content\nno diff headers") == []


class TestCountAdditions:
    def test_counts_added_lines(self):
        diff = "+line1\n+line2\n+line3\n+++\n+line4"
        assert count_additions(diff) == 4

    def test_ignores_file_headers(self):
        diff = "+++ b/file.py\n+line1\n+line2"
        assert count_additions(diff) == 2

    def test_empty_diff_returns_zero(self):
        assert count_additions("") == 0

    def test_no_additions_returns_zero(self):
        diff = "--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@"
        assert count_additions(diff) == 0


class TestCountDeletions:
    def test_counts_deleted_lines(self):
        diff = "-line1\n-line2\n-line3\n---\n-line4"
        assert count_deletions(diff) == 4

    def test_ignores_file_headers(self):
        diff = "--- a/file.py\n-line1\n-line2"
        assert count_deletions(diff) == 2

    def test_empty_diff_returns_zero(self):
        assert count_deletions("") == 0

    def test_no_deletions_returns_zero(self):
        diff = "--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@"
        assert count_deletions(diff) == 0


class TestEnrichPr:
    @pytest.mark.asyncio
    async def test_enrich_success(self):
        event = make_event(title="Test PR")
        client = MagicMock(spec=["get_pr_diff"])
        client.get_pr_diff = AsyncMock(
            return_value=make_diff(
                files=["a.py", "b.py", "c.py"], additions=50, deletions=25
            )
        )

        result = await enrich_pr(event, client)

        assert result.repo == "owner/repo"
        assert result.number == 123
        assert result.title == "Test PR"
        assert result.files_changed == 3
        assert result.additions == 150
        assert result.deletions == 75

    @pytest.mark.asyncio
    async def test_enrich_uses_single_diff_call(self):
        event = make_event()
        client = MagicMock(spec=["get_pr_diff"])
        client.get_pr_diff = AsyncMock(return_value=make_diff())

        await enrich_pr(event, client)

        client.get_pr_diff.assert_called_once_with("owner", "repo", 123)

    @pytest.mark.asyncio
    async def test_enrich_detects_language(self):
        event = make_event()
        client = MagicMock(spec=["get_pr_diff"])
        client.get_pr_diff = AsyncMock(
            return_value=make_diff(
                files=["main.py", "utils.py"], additions=10, deletions=5
            )
        )

        result = await enrich_pr(event, client)
        assert result.language == "python"

    @pytest.mark.asyncio
    async def test_enrich_uses_language_hint(self):
        event = make_event()
        event.language_hint = "go"
        client = MagicMock(spec=["get_pr_diff"])
        client.get_pr_diff = AsyncMock(return_value="")

        result = await enrich_pr(event, client)
        assert result.language == "go"

    @pytest.mark.asyncio
    async def test_enrich_detects_bot(self):
        event = make_event(user="dependabot[bot]")
        client = MagicMock(spec=["get_pr_diff"])
        client.get_pr_diff = AsyncMock(return_value=make_diff())

        result = await enrich_pr(event, client)
        assert result.is_bot is True

    @pytest.mark.asyncio
    async def test_enrich_extracts_linked_issues(self):
        event = make_event(body="This PR fixes #100 and closes #200")
        client = MagicMock(spec=["get_pr_diff"])
        client.get_pr_diff = AsyncMock(return_value=make_diff())

        result = await enrich_pr(event, client)
        assert 100 in result.linked_issues
        assert 200 in result.linked_issues

    @pytest.mark.asyncio
    async def test_enrich_fallback_on_api_error(self):
        event = make_event(title="Event Title", body="Event Body")
        client = MagicMock(spec=["get_pr_diff"])
        client.get_pr_diff = AsyncMock(side_effect=Exception("API Error"))

        result = await enrich_pr(event, client)

        assert result.title == "Event Title"
        assert result.body == "Event Body"
        assert result.metadata.get("has_api_data") == "false"

    @pytest.mark.asyncio
    async def test_enrich_uses_event_data(self):
        event = make_event(
            title="PR Title from Event",
            body="PR Body from Event",
            user="developer",
        )
        client = MagicMock(spec=["get_pr_diff"])
        client.get_pr_diff = AsyncMock(return_value=make_diff())

        result = await enrich_pr(event, client)

        assert result.title == "PR Title from Event"
        assert result.body == "PR Body from Event"
        assert result.user == "developer"


class TestEnrichPrsBatch:
    @pytest.mark.asyncio
    async def test_batch_enriches_all(self):
        events = [make_event(number=i) for i in range(1, 4)]
        client = MagicMock(spec=["get_pr_diff"])
        client.get_pr_diff = AsyncMock(return_value=make_diff())

        results = await enrich_prs_batch(events, client, concurrency=5)

        assert len(results) == 3
        assert results[0].number == 1
        assert results[1].number == 2
        assert results[2].number == 3

    @pytest.mark.asyncio
    async def test_batch_respects_concurrency(self):
        events = [make_event(number=i) for i in range(10)]
        client = MagicMock(spec=["get_pr_diff"])
        client.get_pr_diff = AsyncMock(return_value=make_diff())

        results = await enrich_prs_batch(events, client, concurrency=2)

        assert len(results) == 10


class TestFilterBots:
    def test_filters_bot_prs(self):
        prs = [
            EnrichedPullRequest(id="1", repo="a/b", number=1, is_bot=False),
            EnrichedPullRequest(id="2", repo="a/b", number=2, is_bot=True),
            EnrichedPullRequest(id="3", repo="a/b", number=3, is_bot=False),
        ]

        filtered = filter_bots(prs)

        assert len(filtered) == 2
        assert all(not pr.is_bot for pr in filtered)

    def test_returns_all_if_no_bots(self):
        prs = [
            EnrichedPullRequest(id="1", repo="a/b", number=1, is_bot=False),
            EnrichedPullRequest(id="2", repo="a/b", number=2, is_bot=False),
        ]

        filtered = filter_bots(prs)
        assert len(filtered) == 2

    def test_returns_empty_if_all_bots(self):
        prs = [
            EnrichedPullRequest(id="1", repo="a/b", number=1, is_bot=True),
            EnrichedPullRequest(id="2", repo="a/b", number=2, is_bot=True),
        ]

        filtered = filter_bots(prs)
        assert len(filtered) == 0

    def test_empty_input(self):
        assert filter_bots([]) == []
