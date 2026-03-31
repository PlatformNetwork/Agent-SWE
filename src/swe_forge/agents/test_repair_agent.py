"""LLM-powered test repair agent for diagnosing and fixing failing tests."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from swe_forge.llm import LLMClient, Message

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "openai/gpt-4o-mini"


@dataclass
class Diagnosis:
    """Result of diagnosing a test failure."""

    fixable: bool
    reason: str
    suggested_fix: str | None = None
    error_type: str | None = None
    confidence: float = 0.0


@dataclass
class Fix:
    """A proposed fix for a failing test."""

    description: str
    modified_test: str | None = None
    skip_task: bool = False
    patch_modification: str | None = None
    install_commands: list[str] = field(default_factory=list)


@dataclass
class RepairAttempt:
    """Record of a single repair attempt."""

    attempt_number: int
    diagnosis: Diagnosis
    fix_applied: Fix | None = None
    success: bool = False
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error: str | None = None


class TestRepairAgent:
    """LLM-powered agent that diagnoses and fixes failing tests.

    This agent analyzes test failures from Docker verification and attempts
    to generate fixes using an LLM. It supports multiple retry attempts
    and logs all repair attempts.

    Attributes:
        llm_client: The LLM client to use for diagnosis and fix generation.
        model: The model identifier to use for completions.

    Example:
        >>> from swe_forge.llm import OpenRouterClient
        >>> client = OpenRouterClient(api_key="sk-or-...")
        >>> agent = TestRepairAgent(client)
        >>> diagnosis = await agent.diagnose_failure(test_output, patch, repo_url, error)
    """

    def __init__(
        self,
        llm_client: LLMClient,
        model: str = DEFAULT_MODEL,
    ):
        self.llm_client = llm_client
        self.model = model

    def _build_diagnosis_prompt(
        self,
        test_output: dict[str, Any],
        patch: str,
        repo_url: str,
        error: str,
    ) -> list[Message]:
        """Build the prompt for diagnosing test failure."""
        from swe_forge.llm import Message

        test_output_str = json.dumps(test_output, indent=2, default=str)[:3000]
        patch_preview = patch[:2000] if patch else "No patch provided"

        system_prompt = """You are a test repair expert. Analyze failing test output and determine:
1. Whether the issue is fixable (missing dependency, wrong assertion, environment issue)
2. The root cause of the failure
3. A suggested fix if applicable

Output valid JSON with these fields:
{
  "fixable": boolean,
  "reason": "string explaining the diagnosis",
  "suggested_fix": "string with concrete fix suggestion or null",
  "error_type": "one of: dependency|assertion|environment|patch|timeout|other",
  "confidence": float between 0 and 1
}"""

        user_prompt = f"""Analyze this test verification failure:

REPOSITORY: {repo_url}
ERROR: {error}

PATCH (preview):
```
{patch_preview}
```

TEST OUTPUT:
```json
{test_output_str}
```

Provide your diagnosis as JSON."""

        return [
            Message.system(system_prompt),
            Message.user(user_prompt),
        ]

    def _build_fix_prompt(self, diagnosis: Diagnosis) -> list[Message]:
        """Build the prompt for generating a fix."""
        from swe_forge.llm import Message

        system_prompt = """You are a test repair expert. Generate a concrete fix for the diagnosed issue.

Output valid JSON with these fields:
{
  "description": "string describing the fix",
  "modified_test": "full content of modified test file or null",
  "skip_task": boolean - true if task should be skipped entirely,
  "patch_modification": "suggested patch modification or null",
  "install_commands": ["list", "of", "install", "commands"]
}"""

        user_prompt = f"""Generate a fix for this diagnosis:

Fixable: {diagnosis.fixable}
Reason: {diagnosis.reason}
Error Type: {diagnosis.error_type}
Suggested Fix: {diagnosis.suggested_fix}

Provide your fix as JSON."""

        return [
            Message.system(system_prompt),
            Message.user(user_prompt),
        ]

    def _parse_json_response(self, content: str | None) -> dict[str, Any]:
        """Extract and parse JSON from LLM response content."""
        if not content:
            return {}

        content = content.strip()

        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines)

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    pass
            return {}

    async def diagnose_failure(
        self,
        test_output: dict[str, Any],
        patch: str,
        repo_url: str,
        error: str,
    ) -> Diagnosis:
        """Analyze test failure and determine if fixable.

        Args:
            test_output: Dictionary containing test execution details.
            patch: The patch that was applied.
            repo_url: URL of the repository being tested.
            error: Error message from verification.

        Returns:
            A Diagnosis object with analysis results.
        """
        from swe_forge.llm import GenerationRequest

        messages = self._build_diagnosis_prompt(test_output, patch, repo_url, error)
        request = GenerationRequest(
            model=self.model,
            messages=messages,
            temperature=0.1,
            max_tokens=1000,
        )

        try:
            response = await self.llm_client.complete(request)
            content = response.first_content()

            if not content:
                return Diagnosis(
                    fixable=False,
                    reason="No response from LLM",
                    error_type="other",
                )

            data = self._parse_json_response(content)

            return Diagnosis(
                fixable=data.get("fixable", False),
                reason=data.get("reason", "Unknown reason"),
                suggested_fix=data.get("suggested_fix"),
                error_type=data.get("error_type", "other"),
                confidence=data.get("confidence", 0.0),
            )

        except Exception as e:
            logger.error(f"Diagnosis failed: {e}")
            return Diagnosis(
                fixable=False,
                reason=f"Diagnosis error: {e}",
                error_type="other",
            )

    async def generate_fix(self, diagnosis: Diagnosis) -> Fix:
        """Generate a fix based on the diagnosis.

        Args:
            diagnosis: The diagnosis from analyze_failure.

        Returns:
            A Fix object with the proposed solution.
        """
        if not diagnosis.fixable or not diagnosis.suggested_fix:
            return Fix(
                description="Task marked as unfixable",
                skip_task=True,
            )

        from swe_forge.llm import GenerationRequest

        messages = self._build_fix_prompt(diagnosis)
        request = GenerationRequest(
            model=self.model,
            messages=messages,
            temperature=0.1,
            max_tokens=2000,
        )

        try:
            response = await self.llm_client.complete(request)
            content = response.first_content()

            if not content:
                return Fix(
                    description="No fix generated",
                    skip_task=True,
                )

            data = self._parse_json_response(content)

            return Fix(
                description=data.get("description", "No description"),
                modified_test=data.get("modified_test"),
                skip_task=data.get("skip_task", False),
                patch_modification=data.get("patch_modification"),
                install_commands=data.get("install_commands", []),
            )

        except Exception as e:
            logger.error(f"Fix generation failed: {e}")
            return Fix(
                description=f"Fix generation error: {e}",
                skip_task=True,
            )
