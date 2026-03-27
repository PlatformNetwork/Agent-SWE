"""Language detection for any project type."""

from .language import Language, detect_language, detect_language_from_files
from .package_manager import PackageManager, detect_package_manager

__all__ = [
    "Language",
    "PackageManager",
    "detect_language",
    "detect_language_from_files",
    "detect_package_manager",
]
