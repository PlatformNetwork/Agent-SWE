"""Tests for Docker image validation logic."""

from unittest.mock import AsyncMock, MagicMock, patch
import subprocess

import pytest

from swe_forge.publish.docker_builder import (
    verify_docker_image,
    VerifyResult,
    _validate_pre_apply_with_retry,
)


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run for Docker operations."""
    with patch("swe_forge.publish.docker_builder.subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture
def workspace_with_tests() -> dict:
    """Create a sample workspace dict with test configuration."""
    return {
        "task_id": "test-owner-repo-123",
        "tests": {
            "fail_to_pass": ["pytest tests/test_feature.py -v"],
            "pass_to_pass": ["pytest tests/test_other.py -v"],
        },
        "repo": {
            "url": "https://github.com/test/repo.git",
            "base_commit": "abc123",
        },
        "language": "python",
    }


class TestValidatePreApplyWithRetry:
    """Tests for _validate_pre_apply_with_retry function (flaky test handling)."""

    def test_all_failures_accepted(self):
        """Test that 3/3 failures is accepted (valid test)."""
        with patch(
            "swe_forge.publish.docker_builder._run_test_in_container"
        ) as mock_run:
            mock_run.return_value = {
                "command": "pytest test.py",
                "exit_code": 1,
                "success": False,
                "output": "FAILED",
                "error": "",
            }

            with patch("swe_forge.publish.docker_builder.time.sleep"):
                result = _validate_pre_apply_with_retry(
                    "container", "pytest test.py", max_runs=3, required_failures=2
                )

        assert result["valid"] is True
        assert result["failures"] >= 2
        assert result["passes"] == 0
        assert result["is_flaky"] is False

    def test_flaky_test_2_failures_1_pass_accepted(self):
        """Test that 2/3 failures is accepted (flaky test allowed)."""
        call_count = {"count": 0}

        def mock_run_side_effect(container, cmd, timeout=120):
            call_count["count"] += 1
            if call_count["count"] == 2:
                return {
                    "command": cmd,
                    "exit_code": 0,
                    "success": True,
                    "output": "PASSED",
                    "error": "",
                }
            return {
                "command": cmd,
                "exit_code": 1,
                "success": False,
                "output": "FAILED",
                "error": "",
            }

        with patch(
            "swe_forge.publish.docker_builder._run_test_in_container",
            side_effect=mock_run_side_effect,
        ):
            with patch("swe_forge.publish.docker_builder.time.sleep"):
                result = _validate_pre_apply_with_retry(
                    "container", "pytest test.py", max_runs=3, required_failures=2
                )

        assert result["valid"] is True
        assert result["failures"] == 2
        assert result["passes"] == 1
        assert result["is_flaky"] is True

    def test_flaky_test_1_failure_2_passes_rejected(self):
        """Test that 1/3 failures is rejected (too flaky)."""
        call_count = {"count": 0}

        def mock_run_side_effect(container, cmd, timeout=120):
            call_count["count"] += 1
            if call_count["count"] == 2:
                return {
                    "command": cmd,
                    "exit_code": 1,
                    "success": False,
                    "output": "FAILED",
                    "error": "",
                }
            return {
                "command": cmd,
                "exit_code": 0,
                "success": True,
                "output": "PASSED",
                "error": "",
            }

        with patch(
            "swe_forge.publish.docker_builder._run_test_in_container",
            side_effect=mock_run_side_effect,
        ):
            with patch("swe_forge.publish.docker_builder.time.sleep"):
                result = _validate_pre_apply_with_retry(
                    "container", "pytest test.py", max_runs=3, required_failures=2
                )

        assert result["valid"] is False
        assert result["failures"] == 1
        assert result["passes"] == 2
        assert result["is_flaky"] is True
        assert "failed only 1/3" in result["error"]

    def test_all_passes_rejected(self):
        """Test that 0/3 failures is rejected (broken test - always passes)."""
        with patch(
            "swe_forge.publish.docker_builder._run_test_in_container"
        ) as mock_run:
            mock_run.return_value = {
                "command": "pytest test.py",
                "exit_code": 0,
                "success": True,
                "output": "PASSED",
                "error": "",
            }

            with patch("swe_forge.publish.docker_builder.time.sleep"):
                result = _validate_pre_apply_with_retry(
                    "container", "pytest test.py", max_runs=3, required_failures=2
                )

        assert result["valid"] is False
        assert result["failures"] == 0
        assert result["passes"] >= 2
        assert "always passes" in result["error"]

    def test_early_exit_on_enough_failures(self):
        """Test that we stop early once we have enough failures."""
        call_count = {"count": 0}

        def mock_run_side_effect(container, cmd, timeout=120):
            call_count["count"] += 1
            return {
                "command": cmd,
                "exit_code": 1,
                "success": False,
                "output": "FAILED",
                "error": "",
            }

        with patch(
            "swe_forge.publish.docker_builder._run_test_in_container",
            side_effect=mock_run_side_effect,
        ):
            with patch("swe_forge.publish.docker_builder.time.sleep"):
                result = _validate_pre_apply_with_retry(
                    "container", "pytest test.py", max_runs=3, required_failures=2
                )

        assert result["valid"] is True
        assert result["failures"] == 2
        assert call_count["count"] == 2


class TestVerifyResultDataclass:
    """Tests for VerifyResult dataclass behavior."""

    def test_default_values(self):
        """Test VerifyResult default values."""
        result = VerifyResult(success=True)
        assert result.success is True
        assert result.before_patch_fail is False
        assert result.after_patch_pass is False
        assert result.pass_to_pass_ok is True
        assert result.error is None
        assert result.details is None

    def test_custom_values(self):
        """Test VerifyResult with custom values."""
        result = VerifyResult(
            success=True,
            before_patch_fail=True,
            after_patch_pass=True,
            pass_to_pass_ok=True,
            details={"before": [], "after": []},
        )
        assert result.success is True
        assert result.before_patch_fail is True
        assert result.after_patch_pass is True
        assert result.pass_to_pass_ok is True
        assert result.details == {"before": [], "after": []}

    def test_failure_result(self):
        """Test VerifyResult failure case."""
        result = VerifyResult(success=False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_equality(self):
        """Test VerifyResult equality."""
        result1 = VerifyResult(success=True, before_patch_fail=True)
        result2 = VerifyResult(success=True, before_patch_fail=True)
        assert result1 == result2


class TestVerifyDockerImage:
    """Tests for verify_docker_image function."""

    @pytest.mark.asyncio
    async def test_verify_passes_when_tests_fail_before_and_pass_after(
        self, workspace_with_tests
    ):
        """Test that verification passes when tests fail before patch and pass after."""
        with patch("swe_forge.publish.docker_builder.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

            with patch("swe_forge.publish.docker_builder.time.sleep"):
                with patch(
                    "swe_forge.publish.docker_builder._validate_pre_apply_with_retry"
                ) as mock_validate:
                    mock_validate.return_value = {
                        "command": "pytest tests/test_feature.py -v",
                        "failures": 2,
                        "passes": 1,
                        "results": [],
                        "is_flaky": False,
                        "valid": True,
                        "error": None,
                    }

                    with patch(
                        "swe_forge.publish.docker_builder._run_test_in_container"
                    ) as mock_run_test:
                        # After patch - tests pass
                        mock_run_test.side_effect = [
                            {
                                "command": "pytest tests/test_feature.py -v",
                                "exit_code": 0,
                                "success": True,
                                "output": "PASSED",
                                "error": "",
                            },
                            {
                                "command": "pytest tests/test_other.py -v",
                                "exit_code": 0,
                                "success": True,
                                "output": "PASSED",
                                "error": "",
                            },
                        ]

                        result = await verify_docker_image(
                            "test-image:latest", workspace_with_tests
                        )

        assert result.success is True
        assert result.before_patch_fail is True
        assert result.after_patch_pass is True
        assert result.pass_to_pass_ok is True

    @pytest.mark.asyncio
    async def test_verify_fails_when_tests_pass_before_patch(
        self, workspace_with_tests
    ):
        """Test that verification fails when tests pass before patch (bug doesn't exist)."""
        with patch("swe_forge.publish.docker_builder.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

            with patch("swe_forge.publish.docker_builder.time.sleep"):
                with patch(
                    "swe_forge.publish.docker_builder._validate_pre_apply_with_retry"
                ) as mock_validate:
                    mock_validate.return_value = {
                        "command": "pytest tests/test_feature.py -v",
                        "failures": 0,
                        "passes": 3,
                        "results": [],
                        "is_flaky": False,
                        "valid": False,
                        "error": "Test passed 3/3 times - test appears broken",
                    }

                    result = await verify_docker_image(
                        "test-image:latest", workspace_with_tests
                    )

        assert result.success is False
        assert result.before_patch_fail is False
        assert "Pre-apply validation failed" in result.error

    @pytest.mark.asyncio
    async def test_verify_fails_when_tests_fail_after_patch(self, workspace_with_tests):
        """Test that verification fails when tests still fail after patch (patch doesn't fix bug)."""
        with patch("swe_forge.publish.docker_builder.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

            with patch("swe_forge.publish.docker_builder.time.sleep"):
                with patch(
                    "swe_forge.publish.docker_builder._validate_pre_apply_with_retry"
                ) as mock_validate:
                    mock_validate.return_value = {
                        "command": "pytest tests/test_feature.py -v",
                        "failures": 2,
                        "passes": 0,
                        "results": [],
                        "is_flaky": False,
                        "valid": True,
                        "error": None,
                    }

                    with patch(
                        "swe_forge.publish.docker_builder._run_test_in_container"
                    ) as mock_run_test:
                        # After patch - test still fails
                        mock_run_test.return_value = {
                            "command": "pytest tests/test_feature.py -v",
                            "exit_code": 1,
                            "success": False,
                            "output": "FAILED",
                            "error": "AssertionError still",
                        }

                        result = await verify_docker_image(
                            "test-image:latest", workspace_with_tests
                        )

        assert result.success is False
        assert result.before_patch_fail is True
        assert result.after_patch_pass is False
        assert "FAIL after patch" in result.error

    @pytest.mark.asyncio
    async def test_verify_fails_with_no_fail_to_pass_tests(self):
        """Test that verification fails when no fail_to_pass tests are defined."""
        workspace = {
            "task_id": "test-owner-repo-123",
            "tests": {
                "fail_to_pass": [],
                "pass_to_pass": ["pytest tests/test_other.py -v"],
            },
        }

        result = await verify_docker_image("test-image:latest", workspace)

        assert result.success is False
        assert "No fail_to_pass tests" in result.error

    @pytest.mark.asyncio
    async def test_verify_handles_patch_failure(self, workspace_with_tests):
        """Test that verification handles patch application failures."""

        def mock_subprocess_run(*args, **kwargs):
            mock_result = MagicMock()
            if "exec" in str(args) and "git apply" in str(args):
                mock_result.returncode = 1
                mock_result.stderr = "error: patch failed"
            else:
                mock_result.returncode = 0
            mock_result.stdout = ""
            return mock_result

        with patch(
            "swe_forge.publish.docker_builder.subprocess.run",
            side_effect=mock_subprocess_run,
        ):
            with patch("swe_forge.publish.docker_builder.time.sleep"):
                with patch(
                    "swe_forge.publish.docker_builder._validate_pre_apply_with_retry"
                ) as mock_validate:
                    mock_validate.return_value = {
                        "command": "pytest tests/test_feature.py -v",
                        "failures": 2,
                        "passes": 0,
                        "results": [],
                        "is_flaky": False,
                        "valid": True,
                        "error": None,
                    }

                    result = await verify_docker_image(
                        "test-image:latest", workspace_with_tests
                    )

        assert result.success is False
        assert "Failed to apply patch" in result.error

    @pytest.mark.asyncio
    async def test_verify_handles_timeout(self, workspace_with_tests):
        """Test that verification handles timeout gracefully."""
        call_count = {"count": 0}

        def mock_run_side_effect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 2:
                raise subprocess.TimeoutExpired(cmd="docker", timeout=300)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch(
            "swe_forge.publish.docker_builder.subprocess.run",
            side_effect=mock_run_side_effect,
        ):
            with patch("swe_forge.publish.docker_builder.time.sleep"):
                result = await verify_docker_image(
                    "test-image:latest", workspace_with_tests, timeout=300
                )

        assert result.success is False
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_verify_handles_regression(self, workspace_with_tests):
        """Test detection of pass_to_pass regression (tests that should stay passing fail)."""
        with patch("swe_forge.publish.docker_builder.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

            with patch("swe_forge.publish.docker_builder.time.sleep"):
                with patch(
                    "swe_forge.publish.docker_builder._validate_pre_apply_with_retry"
                ) as mock_validate:
                    mock_validate.return_value = {
                        "command": "pytest tests/test_feature.py -v",
                        "failures": 2,
                        "passes": 0,
                        "results": [],
                        "is_flaky": False,
                        "valid": True,
                        "error": None,
                    }

                    with patch(
                        "swe_forge.publish.docker_builder._run_test_in_container"
                    ) as mock_run_test:
                        mock_run_test.side_effect = [
                            {
                                "command": "pytest tests/test_feature.py -v",
                                "exit_code": 0,
                                "success": True,
                                "output": "PASSED",
                                "error": "",
                            },
                            {
                                "command": "pytest tests/test_other.py -v",
                                "exit_code": 1,
                                "success": False,
                                "output": "FAILED",
                                "error": "Regression",
                            },
                        ]

                        result = await verify_docker_image(
                            "test-image:latest", workspace_with_tests
                        )

        assert result.success is True
        assert result.before_patch_fail is True
        assert result.after_patch_pass is True
        assert result.pass_to_pass_ok is False


class TestVerifyDockerImageFlakyTests:
    """Tests for flaky test handling."""

    @pytest.mark.asyncio
    async def test_verify_with_flaky_test_accepted(self, workspace_with_tests):
        """Test handling when test is flaky (2/3 failures) - should be accepted."""
        with patch("swe_forge.publish.docker_builder.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

            with patch("swe_forge.publish.docker_builder.time.sleep"):
                with patch(
                    "swe_forge.publish.docker_builder._validate_pre_apply_with_retry"
                ) as mock_validate:
                    mock_validate.return_value = {
                        "command": "pytest tests/test_feature.py -v",
                        "failures": 2,
                        "passes": 1,
                        "results": [],
                        "is_flaky": True,
                        "valid": True,
                        "error": None,
                    }

                    with patch(
                        "swe_forge.publish.docker_builder._run_test_in_container"
                    ) as mock_run_test:
                        mock_run_test.side_effect = [
                            {
                                "command": "pytest tests/test_feature.py -v",
                                "exit_code": 0,
                                "success": True,
                                "output": "PASSED",
                                "error": "",
                            },
                            {
                                "command": "pytest tests/test_other.py -v",
                                "exit_code": 0,
                                "success": True,
                                "output": "PASSED",
                                "error": "",
                            },
                        ]

                        result = await verify_docker_image(
                            "test-image:latest", workspace_with_tests
                        )

        assert result.success is True
        assert result.before_patch_fail is True
        assert result.after_patch_pass is True
        assert "flaky_tests" in result.details

    @pytest.mark.asyncio
    async def test_verify_with_multiple_fail_to_pass_tests(self, workspace_with_tests):
        """Test handling with multiple fail_to_pass tests."""
        workspace_with_tests["tests"]["fail_to_pass"] = [
            "pytest tests/test_a.py -v",
            "pytest tests/test_b.py -v",
        ]

        with patch("swe_forge.publish.docker_builder.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

            with patch("swe_forge.publish.docker_builder.time.sleep"):
                with patch(
                    "swe_forge.publish.docker_builder._validate_pre_apply_with_retry"
                ) as mock_validate:
                    mock_validate.return_value = {
                        "command": "pytest tests/test_a.py -v",
                        "failures": 2,
                        "passes": 0,
                        "results": [],
                        "is_flaky": False,
                        "valid": True,
                        "error": None,
                    }

                    with patch(
                        "swe_forge.publish.docker_builder._run_test_in_container"
                    ) as mock_run_test:
                        mock_run_test.side_effect = [
                            {
                                "command": "pytest tests/test_a.py -v",
                                "exit_code": 0,
                                "success": True,
                                "output": "PASSED",
                                "error": "",
                            },
                            {
                                "command": "pytest tests/test_b.py -v",
                                "exit_code": 0,
                                "success": True,
                                "output": "PASSED",
                                "error": "",
                            },
                            {
                                "command": "pytest tests/test_other.py -v",
                                "exit_code": 0,
                                "success": True,
                                "output": "PASSED",
                                "error": "",
                            },
                        ]

                        result = await verify_docker_image(
                            "test-image:latest", workspace_with_tests
                        )

        assert result.success is True
        assert result.before_patch_fail is True
        assert result.after_patch_pass is True

    @pytest.mark.asyncio
    async def test_verify_rejects_too_flaky_test(self, workspace_with_tests):
        """Test that test with only 1/3 failures is rejected."""
        with patch("swe_forge.publish.docker_builder.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

            with patch("swe_forge.publish.docker_builder.time.sleep"):
                with patch(
                    "swe_forge.publish.docker_builder._validate_pre_apply_with_retry"
                ) as mock_validate:
                    mock_validate.return_value = {
                        "command": "pytest tests/test_feature.py -v",
                        "failures": 1,
                        "passes": 2,
                        "results": [],
                        "is_flaky": True,
                        "valid": False,
                        "error": "Test failed only 1/3 times",
                    }

                    result = await verify_docker_image(
                        "test-image:latest", workspace_with_tests
                    )

        assert result.success is False
        assert "Pre-apply validation failed" in result.error

    @pytest.mark.asyncio
    async def test_verify_detects_flaky_tests_in_details(self, workspace_with_tests):
        """Test that flaky tests are logged in the result details."""
        with patch("swe_forge.publish.docker_builder.subprocess") as mock_subprocess:
            mock_subprocess.run.return_value = MagicMock(
                returncode=0, stdout="", stderr=""
            )
            mock_subprocess.TimeoutExpired = subprocess.TimeoutExpired

            with patch("swe_forge.publish.docker_builder.time.sleep"):
                with patch(
                    "swe_forge.publish.docker_builder._validate_pre_apply_with_retry"
                ) as mock_validate:
                    mock_validate.return_value = {
                        "command": "pytest tests/test_feature.py -v",
                        "failures": 2,
                        "passes": 1,
                        "results": [],
                        "is_flaky": True,
                        "valid": True,
                        "error": None,
                    }

                    with patch(
                        "swe_forge.publish.docker_builder._run_test_in_container"
                    ) as mock_run_test:
                        mock_run_test.side_effect = [
                            {
                                "command": "pytest tests/test_feature.py -v",
                                "exit_code": 0,
                                "success": True,
                                "output": "PASSED",
                                "error": "",
                            },
                            {
                                "command": "pytest tests/test_other.py -v",
                                "exit_code": 0,
                                "success": True,
                                "output": "PASSED",
                                "error": "",
                            },
                        ]

                        result = await verify_docker_image(
                            "test-image:latest", workspace_with_tests
                        )

        assert result.success is True
        assert result.details is not None
        assert "flaky_tests" in result.details
        assert "before_validations" in result.details
        assert len(result.details["flaky_tests"]) > 0
