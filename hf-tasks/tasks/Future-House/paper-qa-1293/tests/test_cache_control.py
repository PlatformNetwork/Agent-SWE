from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from paperqa.agents import build_index, search_query
from paperqa.settings import Settings, make_default_litellm_model_list_settings


def test_default_index_name_preserved_for_cli_default(
    stub_data_dir: Path,
) -> None:
    settings = Settings(
        agent={"index": {"paper_directory": stub_data_dir, "name": "custom_idx"}}
    )

    with patch(
        "paperqa.agents.get_directory_index", new_callable=AsyncMock
    ) as mock_get_directory_index:
        build_index("default", stub_data_dir, settings)

    assert settings.agent.index.name == "custom_idx"
    mock_get_directory_index.assert_awaited_once_with(settings=settings)
    passed_settings = mock_get_directory_index.call_args.kwargs["settings"]
    assert passed_settings.agent.index.name == "custom_idx"

    with patch("paperqa.agents.index_search", new_callable=AsyncMock) as mock_index_search:
        mock_index_search.return_value = []
        search_query("What is a transformer model?", "default", settings)

    mock_index_search.assert_awaited_once()
    assert mock_index_search.call_args.kwargs["index_name"] == "custom_idx"


def test_default_litellm_model_settings_include_cache_control() -> None:
    config = make_default_litellm_model_list_settings("custom-llm", temperature=0.35)

    assert config["model_list"][0]["model_name"] == "custom-llm"
    litellm_params = config["model_list"][0]["litellm_params"]
    assert litellm_params["temperature"] == 0.35

    injection_points = litellm_params["cache_control_injection_points"]
    assert {"location": "message", "role": "system"} in injection_points
    assert len(injection_points) == 1
