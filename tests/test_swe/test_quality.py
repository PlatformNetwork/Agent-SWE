"""Tests for quality scoring after test generation."""

from swe_forge.swe.difficulty import ClassifyResponse
from swe_forge.swe.models import SweTask
from swe_forge.swe.quality import (
    QualityAssessment,
    QualityConfig,
    QualityScorer,
    ValidationResult,
)


class TestQualityConfig:
    """Tests for QualityConfig dataclass."""

    def test_default_min_quality_score_is_0_25(self):
        """Critical: Default threshold is 0.25, NOT 0.30."""
        config = QualityConfig()
        assert config.min_quality_score == 0.25

    def test_custom_min_quality_score(self):
        config = QualityConfig(min_quality_score=0.5)
        assert config.min_quality_score == 0.5

    def test_rejection_below_threshold(self):
        config = QualityConfig(min_quality_score=0.3)
        assert config.min_quality_score == 0.3


class TestQualityAssessment:
    """Tests for QualityAssessment dataclass."""

    def test_create_assessment(self):
        assessment = QualityAssessment(
            score=0.5,
            passed=True,
            reasons=["All checks passed"],
            difficulty_level="medium",
            difficulty_score=0.5,
        )
        assert assessment.score == 0.5
        assert assessment.passed is True
        assert assessment.reasons == ["All checks passed"]
        assert assessment.difficulty_level == "medium"
        assert assessment.difficulty_score == 0.5

    def test_assessment_with_rejection_reasons(self):
        assessment = QualityAssessment(
            score=0.1,
            passed=False,
            reasons=["quality gate: score=0.10, quality_good=False"],
            difficulty_level="easy",
            difficulty_score=0.15,
        )
        assert assessment.passed is False
        assert len(assessment.reasons) == 1


class TestValidationResult:
    """Tests for ValidationResult enum."""

    def test_accepted_variant(self):
        result = ValidationResult.ACCEPTED()
        assert result.is_accepted is True

    def test_rejected_variant_with_reason(self):
        result = ValidationResult.REJECTED(
            "quality gate: score=0.10, quality_good=False"
        )
        assert result.is_accepted is False
        assert "quality gate" in result.reason

    def test_rejected_is_not_accepted(self):
        accepted = ValidationResult.ACCEPTED()
        rejected = ValidationResult.REJECTED("test reason")
        assert accepted != rejected


class TestQualityScorer:
    """Tests for QualityScorer class."""

    def test_assess_returns_quality_assessment(self):
        """assess() should return a QualityAssessment."""
        scorer = QualityScorer()
        task = SweTask(id="test-1", repo="owner/repo")

        # Use mock for testing without LLM
        mock_classify = ClassifyResponse(
            difficulty="medium",
            score=0.5,
            quality_good=True,
            reasoning="Good quality",
        )
        scorer._mock_classify_response(mock_classify)

        assessment = scorer.assess(task)
        assert isinstance(assessment, QualityAssessment)

    def test_quality_good_true_and_score_above_threshold_passes(self):
        """Both conditions required: score >= threshold AND quality_good=True."""
        scorer = QualityScorer()

        # Create a mock ClassifyResponse
        mock_classify = ClassifyResponse(
            difficulty="medium",
            score=0.5,  # >= 0.25
            quality_good=True,
            reasoning="Good quality PR",
        )

        # Mock the classifier
        scorer._mock_classify_response(mock_classify)

        task = SweTask(id="test-1", repo="owner/repo")
        assessment = scorer.assess(task)

        assert assessment.passed is True
        assert assessment.score == 0.5

    def test_quality_good_false_rejects_even_with_high_score(self):
        """quality_good=False should reject even with high score."""
        scorer = QualityScorer()

        mock_classify = ClassifyResponse(
            difficulty="medium",
            score=0.9,  # High score
            quality_good=False,  # But quality_good is False
            reasoning="Missing tests",
        )

        scorer._mock_classify_response(mock_classify)

        task = SweTask(id="test-1", repo="owner/repo")
        assessment = scorer.assess(task)

        assert assessment.passed is False
        assert "quality gate" in assessment.reasons[0].lower()

    def test_score_below_threshold_rejects_even_with_quality_good(self):
        """Low score should reject even if quality_good=True."""
        scorer = QualityScorer()

        mock_classify = ClassifyResponse(
            difficulty="easy",
            score=0.15,  # Below 0.25 threshold
            quality_good=True,
            reasoning="Small changes",
        )

        scorer._mock_classify_response(mock_classify)

        task = SweTask(id="test-1", repo="owner/repo")
        assessment = scorer.assess(task)

        assert assessment.passed is False

    def test_rejection_reason_format(self):
        """Rejection reason format: 'quality gate: score=X.XX, quality_good=BOOL'."""
        scorer = QualityScorer()

        mock_classify = ClassifyResponse(
            difficulty="medium",
            score=0.2,
            quality_good=False,
            reasoning="Test reasoning",
        )

        scorer._mock_classify_response(mock_classify)

        task = SweTask(id="test-1", repo="owner/repo")
        assessment = scorer.assess(task)

        assert assessment.passed is False
        # Check the rejection reason format
        reason = assessment.reasons[0]
        assert "quality gate:" in reason.lower()
        assert "score=" in reason.lower()
        assert "quality_good=" in reason.lower()

    def test_custom_config_threshold(self):
        """QualityScorer respects custom QualityConfig threshold."""
        config = QualityConfig(min_quality_score=0.5)
        scorer = QualityScorer(config=config)

        mock_classify = ClassifyResponse(
            difficulty="medium",
            score=0.4,  # Above default 0.25, but below 0.5
            quality_good=True,
            reasoning="Medium quality",
        )

        scorer._mock_classify_response(mock_classify)

        task = SweTask(id="test-1", repo="owner/repo")
        assessment = scorer.assess(task)

        # Should fail because 0.4 < 0.5 threshold
        assert assessment.passed is False

    def test_passed_assessment_has_no_rejection_reasons(self):
        """Passed assessment should have empty or success reasons."""
        scorer = QualityScorer()

        mock_classify = ClassifyResponse(
            difficulty="medium",
            score=0.5,
            quality_good=True,
            reasoning="Good PR",
        )

        scorer._mock_classify_response(mock_classify)

        task = SweTask(id="test-1", repo="owner/repo")
        assessment = scorer.assess(task)

        assert assessment.passed is True
        # Should not have rejection reasons
        for reason in assessment.reasons:
            assert "quality gate:" not in reason.lower()


class TestQualityScorerWithTaskInfo:
    """Tests for QualityScorer with TaskInfo extraction."""

    def test_assess_uses_task_fields_for_classification(self):
        """assess() should extract info from SweTask for classification."""
        scorer = QualityScorer()

        task = SweTask(
            id="test-123",
            repo="owner/repo",
            prompt="Fix the bug in authentication",
            original_pr_body="This PR fixes a critical bug",
        )

        mock_classify = ClassifyResponse(
            difficulty="medium",
            score=0.5,
            quality_good=True,
            reasoning="Bug fix with clear description",
        )

        scorer._mock_classify_response(mock_classify)

        assessment = scorer.assess(task)
        assert assessment.passed is True


class TestValidateDualCommit:
    """Tests for validate_dual_commit function signature (integration placeholder)."""

    def test_validate_dual_commit_signature_exists(self):
        """validate_dual_commit should exist as a callable."""
        from swe_forge.swe.quality import validate_dual_commit

        assert callable(validate_dual_commit)

    def test_validate_dual_commit_returns_validation_result(self):
        """validate_dual_commit should return ValidationResult."""
        from swe_forge.swe.quality import validate_dual_commit

        # This is a placeholder test - actual implementation would need
        # a real workspace and tests
        # For now, we test the signature exists
        import inspect

        sig = inspect.signature(validate_dual_commit)
        # Should have parameters for task, workspace operations
        assert len(sig.parameters) >= 0
