"""
Function call schemas for LLM orchestrator.

These schemas follow OpenAI function calling format and define
all callable functions in the pipeline orchestration.
"""

from typing import Any


# =============================================================================
# Function Schemas (OpenAI Function Calling Format)
# =============================================================================

GENERATE_TESTS_SCHEMA: dict[str, Any] = {
    "name": "generate_tests",
    "description": "Generate test files for the task via LLM agent. "
    "Agent clones the repo, analyzes the patch context, and creates "
    "test files that verify the bug fix.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Unique identifier for the task (e.g., 'owner-repo-123').",
            },
            "patch": {
                "type": "string",
                "description": "Unified diff patch content to generate tests for.",
            },
            "repo_url": {
                "type": "string",
                "description": "Git repository URL to clone.",
            },
            "base_commit": {
                "type": "string",
                "description": "Git commit SHA to checkout before applying patch.",
            },
            "language": {
                "type": "string",
                "description": "Programming language of the repository (e.g., 'python', 'rust').",
            },
        },
        "required": ["task_id", "patch", "repo_url", "base_commit", "language"],
    },
}

VALIDATE_TESTS_SCHEMA: dict[str, Any] = {
    "name": "validate_tests",
    "description": "Validate test structure and quality BEFORE Docker build. "
    "Checks: file syntax, assertion presence, patch relevance.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Unique identifier for the task.",
            },
            "tests": {
                "type": "array",
                "description": "List of test files to validate.",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative file path for the test file.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Complete content of the test file.",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
            "patch": {
                "type": "string",
                "description": "Unified diff patch to check test relevance against.",
            },
        },
        "required": ["task_id", "tests", "patch"],
    },
}

BUILD_DOCKER_SCHEMA: dict[str, Any] = {
    "name": "build_docker",
    "description": "Build Docker image with repository cloned at base_commit "
    "and test files copied in. Returns image name for verification.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Unique identifier for the task.",
            },
            "tests": {
                "type": "array",
                "description": "List of test files to include in the image.",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative file path for the test file.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Complete content of the test file.",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
            "repo_url": {
                "type": "string",
                "description": "Git repository URL to clone in the image.",
            },
            "base_commit": {
                "type": "string",
                "description": "Git commit SHA to checkout.",
            },
            "language": {
                "type": "string",
                "description": "Programming language (determines base image and tooling).",
            },
        },
        "required": ["task_id", "tests", "repo_url", "base_commit", "language"],
    },
}

VERIFY_FAIL_TO_PASS_SCHEMA: dict[str, Any] = {
    "name": "verify_fail_to_pass",
    "description": "Verify tests FAIL before patch and PASS after patch. "
    "Runs tests in Docker container before and after applying the fix.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Unique identifier for the task.",
            },
            "image_name": {
                "type": "string",
                "description": "Docker image name to run tests in.",
            },
            "tests": {
                "type": "array",
                "description": "Test commands to execute.",
                "items": {"type": "string"},
            },
            "patch": {
                "type": "string",
                "description": "Patch to apply between test runs.",
            },
            "max_retries": {
                "type": "integer",
                "description": "Maximum retry attempts for flaky tests (default: 3).",
                "default": 3,
            },
        },
        "required": ["task_id", "image_name", "tests", "patch"],
    },
}

REPAIR_TEST_SCHEMA: dict[str, Any] = {
    "name": "repair_test",
    "description": "Fix failing tests via LLM agent. "
    "Agent diagnoses the error and generates fixes.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Unique identifier for the task.",
            },
            "error_output": {
                "type": "string",
                "description": "Error output from failed test run.",
            },
            "max_attempts": {
                "type": "integer",
                "description": "Maximum repair attempts (default: 5).",
                "default": 5,
            },
        },
        "required": ["task_id", "error_output"],
    },
}

SCORE_TASK_SCHEMA: dict[str, Any] = {
    "name": "score_task",
    "description": "Calculate quality score for a completed task. "
    "Considers: complexity, test quality, verification success.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Unique identifier for the task.",
            },
            "validation_result": {
                "type": "object",
                "description": "Result from validate_tests step.",
            },
            "verify_result": {
                "type": "object",
                "description": "Result from verify_fail_to_pass step.",
            },
        },
        "required": ["task_id", "validation_result", "verify_result"],
    },
}

PUBLISH_TASK_SCHEMA: dict[str, Any] = {
    "name": "publish_task",
    "description": "Publish task to HuggingFace dataset. "
    "Requires minimum quality score.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Unique identifier for the task.",
            },
            "score": {"type": "number", "description": "Quality score (0.0 to 1.0)."},
            "dataset_name": {
                "type": "string",
                "description": "HuggingFace dataset name (e.g., 'CortexLM/swe-forge').",
            },
        },
        "required": ["task_id", "score", "dataset_name"],
    },
}

REJECT_TASK_SCHEMA: dict[str, Any] = {
    "name": "reject_task",
    "description": "Reject task with reason. "
    "Used when task fails validation or verification.",
    "parameters": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Unique identifier for the task.",
            },
            "reason": {
                "type": "string",
                "description": "Short rejection reason (e.g., 'complexity_too_low', 'tests_dont_fail').",
            },
            "details": {
                "type": "string",
                "description": "Detailed explanation of why task was rejected.",
            },
        },
        "required": ["task_id", "reason"],
    },
}


# =============================================================================
# Helper Function
# =============================================================================


def get_all_function_schemas() -> list[dict[str, Any]]:
    """
    Return all function schemas for LLM function calling.

    Use this to configure the LLM client with available tools:

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[...],
            tools=get_all_function_schemas()
        )

    Returns:
        List of function schema dictionaries in OpenAI format.
    """
    return [
        GENERATE_TESTS_SCHEMA,
        VALIDATE_TESTS_SCHEMA,
        BUILD_DOCKER_SCHEMA,
        VERIFY_FAIL_TO_PASS_SCHEMA,
        REPAIR_TEST_SCHEMA,
        SCORE_TASK_SCHEMA,
        PUBLISH_TASK_SCHEMA,
        REJECT_TASK_SCHEMA,
    ]


def get_function_schema(name: str) -> dict[str, Any] | None:
    """
    Get a specific function schema by name.

    Args:
        name: Function name (e.g., 'generate_tests').

    Returns:
        Function schema dict or None if not found.
    """
    schemas = {
        "generate_tests": GENERATE_TESTS_SCHEMA,
        "validate_tests": VALIDATE_TESTS_SCHEMA,
        "build_docker": BUILD_DOCKER_SCHEMA,
        "verify_fail_to_pass": VERIFY_FAIL_TO_PASS_SCHEMA,
        "repair_test": REPAIR_TEST_SCHEMA,
        "score_task": SCORE_TASK_SCHEMA,
        "publish_task": PUBLISH_TASK_SCHEMA,
        "reject_task": REJECT_TASK_SCHEMA,
    }
    return schemas.get(name)


# =============================================================================
# Schema Registry (for introspection)
# =============================================================================

# All schema names in order of pipeline execution
PIPELINE_ORDER = [
    "generate_tests",
    "validate_tests",
    "build_docker",
    "verify_fail_to_pass",
    "repair_test",
    "score_task",
    "publish_task",
]

SCHEMA_REGISTRY: dict[str, dict[str, Any]] = {
    "generate_tests": GENERATE_TESTS_SCHEMA,
    "validate_tests": VALIDATE_TESTS_SCHEMA,
    "build_docker": BUILD_DOCKER_SCHEMA,
    "verify_fail_to_pass": VERIFY_FAIL_TO_PASS_SCHEMA,
    "repair_test": REPAIR_TEST_SCHEMA,
    "score_task": SCORE_TASK_SCHEMA,
    "publish_task": PUBLISH_TASK_SCHEMA,
    "reject_task": REJECT_TASK_SCHEMA,
}
