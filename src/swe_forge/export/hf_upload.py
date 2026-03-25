"""HuggingFace Hub upload functionality for datasets and files."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from huggingface_hub import HfApi

if TYPE_CHECKING:
    pass


class HfUploadError(Exception):
    """Raised when HuggingFace upload fails."""

    pass


def _get_token(token: str | None) -> str:
    """Get token from parameter or environment."""
    if token is not None:
        return token
    env_token = os.environ.get("HF_TOKEN")
    if env_token:
        return env_token
    raise HfUploadError("Token required: pass token parameter or set HF_TOKEN env var")


def upload_to_hf(
    path: str | Path,
    repo_id: str,
    token: str | None = None,
    private: bool = False,
    repo_type: str = "dataset",
) -> bool:
    """Upload a file to HuggingFace Hub.

    Args:
        path: Local file path to upload.
        repo_id: Repository ID (e.g., "org/dataset-name").
        token: HuggingFace API token. If None, uses HF_TOKEN env var.
        private: Whether to create a private repository.
        repo_type: Type of repository ("dataset" or "model").

    Returns:
        True if upload successful.

    Raises:
        HfUploadError: If upload fails or token is missing.
    """
    resolved_token = _get_token(token)
    api = HfApi(token=resolved_token)

    p = Path(path)
    if not p.exists():
        raise HfUploadError(f"Path does not exist: {path}")

    api.create_repo(
        repo_id=repo_id, repo_type=repo_type, private=private, exist_ok=True
    )

    if p.is_file():
        api.upload_file(
            path_or_fileobj=str(p),
            path_in_repo=p.name,
            repo_id=repo_id,
            repo_type=repo_type,
        )
    else:
        api.upload_folder(
            folder_path=str(p),
            repo_id=repo_id,
            repo_type=repo_type,
        )

    return True


def upload_dataset_folder(
    folder: str | Path,
    repo_id: str,
    token: str | None = None,
    private: bool = False,
    generate_card: bool = True,
    task_type: str | None = None,
    license: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> bool:
    """Upload an entire folder as a HuggingFace dataset.

    Args:
        folder: Local folder path to upload.
        repo_id: Repository ID (e.g., "org/dataset-name").
        token: HuggingFace API token. If None, uses HF_TOKEN env var.
        private: Whether to create a private repository.
        generate_card: Whether to generate a README.md dataset card.
        task_type: Task type for dataset card (e.g., "text-generation").
        license: License for dataset card.
        description: Description for dataset card.
        tags: Tags for dataset card.

    Returns:
        True if upload successful.

    Raises:
        HfUploadError: If upload fails or folder doesn't exist.
    """
    folder_path = Path(folder)
    if not folder_path.exists():
        raise HfUploadError(f"Folder does not exist: {folder}")
    if not folder_path.is_dir():
        raise HfUploadError(f"Path is not a directory: {folder}")

    resolved_token = _get_token(token)
    api = HfApi(token=resolved_token)

    api.create_repo(
        repo_id=repo_id,
        repo_type="dataset",
        private=private,
        exist_ok=True,
    )

    api.upload_folder(
        folder_path=str(folder_path),
        repo_id=repo_id,
        repo_type="dataset",
    )

    if generate_card:
        card = DatasetCard.from_template(
            repo_id=repo_id,
            task_type=task_type or "other",
            license=license,
            description=description,
            tags=tags,
        )
        api.upload_file(
            path_or_fileobj=card.to_markdown().encode("utf-8"),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="dataset",
        )

    return True


@dataclass
class DatasetCard:
    """Dataset card (README.md) for HuggingFace datasets.

    Generates a valid HuggingFace dataset card with YAML frontmatter
    and markdown content.
    """

    repo_id: str
    task_type: str = "other"
    license: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def repo_url(self) -> str:
        """Get the HuggingFace URL for this dataset."""
        return f"https://huggingface.co/datasets/{self.repo_id}"

    def to_markdown(self) -> str:
        """Generate the markdown content for the dataset card.

        Returns:
            Markdown string with YAML frontmatter and content.
        """
        lines: list[str] = []
        lines.append("---")
        lines.append(f'task_categories: ["{self.task_type}"]')

        if self.license:
            lines.append(f"license: {self.license}")

        all_tags = list(self.tags)
        if self.task_type and self.task_type not in all_tags:
            all_tags.insert(0, self.task_type)
        lines.append(f"tags: {all_tags}")

        lines.append("---")
        lines.append("")
        lines.append(f"# {self.repo_id}")
        lines.append("")

        if self.description:
            lines.append(self.description)
        else:
            lines.append(f"Dataset hosted at {self.repo_url}")

        return "\n".join(lines)

    @classmethod
    def from_template(
        cls,
        repo_id: str,
        task_type: str = "other",
        license: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> "DatasetCard":
        """Create a DatasetCard from template parameters.

        Args:
            repo_id: Repository ID (e.g., "org/dataset-name").
            task_type: Task type (e.g., "text-generation").
            license: License identifier.
            description: Dataset description.
            tags: Optional tags.

        Returns:
            DatasetCard instance.
        """
        return cls(
            repo_id=repo_id,
            task_type=task_type,
            license=license,
            description=description,
            tags=tags or [],
        )
