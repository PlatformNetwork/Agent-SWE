"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest

from swe_forge.config import Settings, PipelineConfig, HarnessConfig


class TestSettings:
    """Tests for Settings class."""

    def test_settings_requires_required_fields(self):
        """Settings should raise validation error without required env vars."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception):
                Settings()

    def test_settings_loads_from_env_vars(self):
        """Settings should load values from environment variables."""
        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test-openrouter-key",
                "GITHUB_TOKEN": "test-github-token",
                "OPENAI_API_KEY": "test-openai-key",
                "ANTHROPIC_API_KEY": "test-anthropic-key",
                "LOG_LEVEL": "DEBUG",
                "MODEL_NAME": "openai/gpt-4",
            },
            clear=True,
        ):
            settings = Settings()
            assert settings.openrouter_api_key == "test-openrouter-key"
            assert settings.github_token == "test-github-token"
            assert settings.openai_api_key == "test-openai-key"
            assert settings.anthropic_api_key == "test-anthropic-key"
            assert settings.log_level == "DEBUG"
            assert settings.model_name == "openai/gpt-4"

    def test_settings_uses_defaults(self):
        """Settings should use default values for optional fields."""
        with patch.dict(
            os.environ,
            {
                "OPENROUTER_API_KEY": "test-key",
                "GITHUB_TOKEN": "test-token",
            },
            clear=True,
        ):
            settings = Settings()
            assert settings.openai_api_key == ""
            assert settings.anthropic_api_key == ""
            assert settings.log_level == "INFO"
            assert settings.model_name == "openai/gpt-4o-mini"


class TestPipelineConfig:
    """Tests for PipelineConfig class."""

    def test_pipeline_config_defaults(self):
        """PipelineConfig should have correct default values."""
        config = PipelineConfig()
        assert config.max_concurrent_gharchive == 8
        assert config.max_concurrent_enrichment == 20
        assert config.max_concurrent_llm == 25


class TestHarnessConfig:
    """Tests for HarnessConfig class."""

    def test_harness_config_defaults(self):
        """HarnessConfig should have correct default values."""
        config = HarnessConfig()
        assert config.docker_image == "python:3.12-slim"
        assert config.agent_timeout == 600
        assert config.test_timeout == 120
