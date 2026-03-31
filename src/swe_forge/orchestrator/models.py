"""Data models for the orchestrator system.

This module defines the core data structures for tracking the full lifecycle
of test generation and validation tasks through the orchestrator pipeline.

Pipeline order: Generate Tests -> Validate Tests -> Build Docker -> Verify -> Repair -> Score -> Publish
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TaskState(str, Enum):
    """State machine states for orchestrator tasks.

    Tasks flow through these states in order:
    PENDING -> GENERATING_TESTS -> VALIDATING_TESTS -> BUILDING_DOCKER -> VERIFYING -> REPAIRING -> SCORING -> PUBLISHING -> COMPLETED

    Tasks can also end in REJECTED or FAILED from any state.
    """

    PENDING = "pending"
    GENERATING_TESTS = "generating_tests"
    VALIDATING_TESTS = "validating_tests"
    BUILDING_DOCKER = "building_docker"
    VERIFYING = "verifying"
    REPAIRING = "repairing"
    SCORING = "scoring"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class TestFile:
    """Represents a generated test file.

    Attributes:
        path: Relative path for the test file (e.g., "tests/test_feature.py")
        content: Full content of the test file
    """

    path: str
    content: str


@dataclass
class GenerateTestsResult:
    """Result of the test generation stage.

    Attributes:
        success: Whether test generation succeeded
        tests: Raw test specifications (fail_to_pass, pass_to_pass)
        test_files: List of generated test files
        install_commands: Commands needed to install the project
        error: Error message if generation failed
        turn_count: Number of LLM turns used during generation
    """

    success: bool
    tests: dict[str, list[str]] = field(default_factory=dict)
    test_files: list[TestFile] = field(default_factory=list)
    install_commands: list[str] = field(default_factory=list)
    error: str | None = None
    turn_count: int = 0


@dataclass
class ValidateTestsResult:
    """Result of the test validation stage.

    Attributes:
        success: Whether validation passed
        has_assertions: Whether tests contain meaningful assertions
        has_valid_syntax: Whether tests have valid syntax
        relevant_to_patch: Whether tests are relevant to the patch
        issues: List of validation issues found
        error: Error message if validation failed
    """

    success: bool
    has_assertions: bool = False
    has_valid_syntax: bool = False
    relevant_to_patch: bool = False
    issues: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class BuildDockerResult:
    """Result of the Docker build stage.

    Attributes:
        success: Whether Docker build succeeded
        image_name: Name of the built Docker image
        build_time_seconds: Time taken to build the image
        error: Error message if build failed
    """

    success: bool
    image_name: str | None = None
    build_time_seconds: float = 0.0
    error: str | None = None


@dataclass
class VerifyResult:
    """Result of the verification stage.

    Tests should FAIL before applying the patch (bug exists) and
    PASS after applying the patch (fix works).

    Attributes:
        success: Whether verification passed
        before_patch_failed: Whether tests failed before applying patch
        after_patch_passed: Whether tests passed after applying patch
        needs_repair: Whether task needs repair
        error: Error message if verification failed
    """

    success: bool
    before_patch_failed: bool = False
    after_patch_passed: bool = False
    needs_repair: bool = False
    error: str | None = None


@dataclass
class RepairResult:
    """Result of the repair stage.

    Attributes:
        success: Whether repair succeeded
        attempts: Number of repair attempts made
        fix_applied: Description of the fix applied
        error: Error message if repair failed
    """

    success: bool
    attempts: int = 0
    fix_applied: str | None = None
    error: str | None = None


@dataclass
class ScoreResult:
    """Result of the scoring stage.

    Attributes:
        score: Overall quality score (0.0 to 1.0)
        complexity_score: Score based on code complexity
        test_quality_score: Score based on test quality
        verification_score: Score based on verification results
    """

    score: float = 0.0
    complexity_score: float = 0.0
    test_quality_score: float = 0.0
    verification_score: float = 0.0


@dataclass
class PublishResult:
    """Result of the publish stage.

    Attributes:
        success: Whether publishing succeeded
        dataset_name: Name of the published dataset
        task_id: ID of the published task
        error: Error message if publishing failed
    """

    success: bool
    dataset_name: str | None = None
    task_id: str | None = None
    error: str | None = None


@dataclass
class OrchestratorTask:
    """Tracks the full lifecycle of a task through the orchestrator pipeline.

    This is the central data structure that maintains state and results
    for each task as it flows through the pipeline stages.

    Attributes:
        task_id: Unique identifier for the task
        state: Current state in the pipeline
        repo_url: URL of the repository
        base_commit: Git commit to start from
        merge_commit: Git merge commit SHA
        patch: The patch to apply
        language: Programming language detected
        tests: Test specifications
        docker_image: Docker image name for the task
        test_files: Generated test files
        install_commands: Commands to install dependencies
        difficulty_score: Difficulty score (0.0-1.0)
        prompt: Task description prompt
        generate_result: Result from test generation stage
        validate_result: Result from test validation stage
        build_result: Result from Docker build stage
        verify_result: Result from verification stage
        repair_result: Result from repair stage
        score_result: Result from scoring stage
        publish_result: Result from publish stage
        created_at: When the task was created
        updated_at: When the task was last updated
        metadata: Additional task metadata
    """

    task_id: str
    state: TaskState = TaskState.PENDING
    repo_url: str = ""
    base_commit: str = ""
    merge_commit: str = ""
    patch: str = ""
    language: str = "unknown"
    tests: dict[str, list[str]] = field(default_factory=dict)
    test_files: list[TestFile] = field(default_factory=list)
    install_commands: list[str] = field(default_factory=list)
    docker_image: str = ""
    difficulty_score: float = 0.0
    prompt: str = ""

    # Stage results
    generate_result: GenerateTestsResult | None = None
    validate_result: ValidateTestsResult | None = None
    build_result: BuildDockerResult | None = None
    verify_result: VerifyResult | None = None
    repair_result: RepairResult | None = None
    score_result: ScoreResult | None = None
    publish_result: PublishResult | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def transition_to(self, new_state: TaskState) -> None:
        """Transition to a new state and update timestamp."""
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc)

    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.state in (TaskState.COMPLETED, TaskState.REJECTED, TaskState.FAILED)


@dataclass
class OrchestratorStats:
    """Statistics for the orchestrator pipeline.

    Tracks counts per state and provides useful methods for
    calculating pass rates and summary statistics.

    Attributes:
        total_tasks: Total number of tasks processed
        state_counts: Count of tasks in each state
        timing: Timing information for each stage
    """

    total_tasks: int = 0
    state_counts: dict[TaskState, int] = field(default_factory=dict)
    timing: dict[str, float] = field(default_factory=dict)

    def pass_rate(self) -> float:
        """Calculate the overall pass rate.

        Returns:
            Percentage of tasks that completed successfully (0.0 to 1.0)
        """
        if self.total_tasks == 0:
            return 0.0

        completed = self.state_counts.get(TaskState.COMPLETED, 0)
        return completed / self.total_tasks

    def failure_rate(self) -> float:
        """Calculate the overall failure rate.

        Returns:
            Percentage of tasks that failed or were rejected (0.0 to 1.0)
        """
        if self.total_tasks == 0:
            return 0.0

        failed = self.state_counts.get(TaskState.FAILED, 0)
        rejected = self.state_counts.get(TaskState.REJECTED, 0)
        return (failed + rejected) / self.total_tasks

    def average_time_per_task(self) -> float:
        """Calculate average processing time per task.

        Returns:
            Average time in seconds, or 0 if no tasks processed
        """
        if self.total_tasks == 0:
            return 0.0

        total_time = sum(self.timing.values())
        return total_time / self.total_tasks
