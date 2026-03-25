"""Quality scoring for SWE tasks after test generation.

Implements dual-commit validation and quality gating.

Threshold: 0.25 (25%), NOT 0.30 - this is from the Rust implementation.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from swe_forge.swe.difficulty import ClassifyResponse, DifficultyClassifier, TaskInfo
from swe_forge.swe.models import SweTask

if TYPE_CHECKING:
    from swe_forge.llm import LLMClient


@dataclass
class QualityConfig:
    """Configuration for quality scoring.

    Attributes:
        min_quality_score: Minimum quality score threshold (default: 0.25)
    """

    min_quality_score: float = 0.25


@dataclass
class QualityAssessment:
    """Result of quality assessment for a task.

    Attributes:
        score: Quality score (0.0-1.0)
        passed: Whether the task passed quality gate
        reasons: List of reasons for pass/fail
        difficulty_level: Difficulty classification ("easy", "medium", "hard")
        difficulty_score: Raw difficulty score (0.0-1.0)
    """

    score: float
    passed: bool
    reasons: list[str]
    difficulty_level: str
    difficulty_score: float


class ValidationResult:
    """Result of dual-commit validation."""

    def __init__(self, accepted: bool, reason: str | None = None):
        self._accepted = accepted
        self._reason = reason

    @classmethod
    def ACCEPTED(cls) -> "ValidationResult":
        return cls(accepted=True)

    @classmethod
    def REJECTED(cls, reason: str) -> "ValidationResult":
        return cls(accepted=False, reason=reason)

    @property
    def is_accepted(self) -> bool:
        return self._accepted

    @property
    def reason(self) -> str | None:
        return self._reason

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ValidationResult):
            return False
        return self._accepted == other._accepted and self._reason == other._reason

    def __repr__(self) -> str:
        if self._accepted:
            return "ValidationResult.ACCEPTED"
        return f"ValidationResult.REJECTED({self._reason!r})"


def validate_dual_commit(
    task: SweTask,
    apply_patch: callable,
    run_tests: callable,
    revert: callable,
) -> ValidationResult:
    """Validate task using dual-commit strategy.

    1. Apply patch -> run fail_to_pass (must PASS)
    2. Apply patch -> run pass_to_pass (must still PASS)
    3. Revert to base

    Args:
        task: The SWE task to validate
        apply_patch: Function to apply the patch
        run_tests: Function to run tests (returns bool)
        revert: Function to revert to base state

    Returns:
        ValidationResult indicating acceptance or rejection with reason
    """
    try:
        apply_patch(task.patch)

        fail_to_pass_passed = run_tests(task.fail_to_pass)
        if not fail_to_pass_passed:
            return ValidationResult.rejected(
                f"fail_to_pass tests failed: {task.fail_to_pass}"
            )

        pass_to_pass_passed = run_tests(task.pass_to_pass)
        if not pass_to_pass_passed:
            return ValidationResult.rejected(
                f"pass_to_pass tests failed: {task.pass_to_pass}"
            )

        return ValidationResult.accepted()
    finally:
        revert()


class QualityScorer:
    """Scorer for assessing task quality after generation.

    Uses DifficultyClassifier internally for classification.
    Both conditions required for pass:
    - score >= min_quality_score
    - quality_good == True
    """

    def __init__(
        self,
        config: QualityConfig | None = None,
        client: "LLMClient | None" = None,
        model: str = "openai/gpt-4o-mini",
    ):
        self._config = config or QualityConfig()
        self._client = client
        self._model = model
        self._classifier: DifficultyClassifier | None = None
        self._mock_response: ClassifyResponse | None = None

    def _mock_classify_response(self, response: ClassifyResponse) -> None:
        """Set a mock response for testing."""
        self._mock_response = response

    def _get_classifier(self) -> DifficultyClassifier:
        """Get or create the difficulty classifier."""
        if self._classifier is None:
            if self._client is None:
                raise RuntimeError("LLMClient required for classification")
            self._classifier = DifficultyClassifier(self._client, self._model)
        return self._classifier

    def assess(self, task: SweTask) -> QualityAssessment:
        """Assess the quality of a SWE task.

        Args:
            task: The SWE task to assess

        Returns:
            QualityAssessment with score, passed status, and reasons
        """
        if self._mock_response:
            classify_response = self._mock_response
        else:
            task_info = self._extract_task_info(task)
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run, self._get_classifier().classify_full(task_info)
                        )
                        classify_response = future.result()
                else:
                    classify_response = asyncio.run(
                        self._get_classifier().classify_full(task_info)
                    )
            except RuntimeError:
                import asyncio

                classify_response = asyncio.run(
                    self._get_classifier().classify_full(task_info)
                )

        score = classify_response.score
        quality_good = classify_response.quality_good
        passed = score >= self._config.min_quality_score and quality_good

        reasons: list[str] = []
        if not passed:
            reasons.append(
                f"quality gate: score={score:.2f}, quality_good={quality_good}"
            )
        else:
            reasons.append(f"Quality assessment passed: score={score:.2f}")

        return QualityAssessment(
            score=score,
            passed=passed,
            reasons=reasons,
            difficulty_level=classify_response.difficulty,
            difficulty_score=score,
        )

    def _extract_task_info(self, task: SweTask) -> TaskInfo:
        """Extract TaskInfo from SweTask for classification."""
        from swe_forge.swe.difficulty import PRInfo

        pr_info = PRInfo(
            title=task.prompt[:100] if task.prompt else f"Task {task.id}",
            body=task.original_pr_body or "",
        )

        files_changed = len(task.patch.split("diff --git")) - 1 if task.patch else 0
        files_changed = max(0, files_changed)

        lines_added = (
            task.patch.count("\n+") - task.patch.count("+++") if task.patch else 0
        )
        lines_removed = (
            task.patch.count("\n-") - task.patch.count("---") if task.patch else 0
        )
        lines_added = max(0, lines_added)
        lines_removed = max(0, lines_removed)

        file_paths: list[str] = []
        import re

        if task.patch:
            file_pattern = re.compile(r"diff --git a/(.*?) b/")
            file_paths = file_pattern.findall(task.patch)

        return TaskInfo(
            pr_info=pr_info,
            files_changed=files_changed,
            lines_added=lines_added,
            lines_removed=lines_removed,
            file_paths=file_paths,
            diff_preview=task.patch[:500] if task.patch else "",
        )
