import pytest

from swe_forge.swe.test_generator import is_valid_test_content, validate_test_path


def test_validate_test_path_accepts_tests_directory():
    is_valid, _ = validate_test_path(
        "tests/test_feature.py", "pydantic/pydantic", "python"
    )
    assert is_valid


def test_validate_test_path_rejects_external_repo():
    is_valid, error = validate_test_path(
        "tests/glassflow-api/test.py", "pydantic/pydantic", "python"
    )
    assert not is_valid
    assert "cross-contamination" in error.lower()


def test_validate_test_path_rejects_non_test_directory():
    is_valid, error = validate_test_path("src/main.py", "pydantic/pydantic", "python")
    assert not is_valid
    assert "tests/" in error


def test_validate_test_path_enforces_py_extension():
    is_valid, error = validate_test_path(
        "tests/test_file.js", "pydantic/pydantic", "python"
    )
    assert not is_valid
    assert ".py" in error


def test_is_valid_test_content_python():
    is_valid, _ = is_valid_test_content("import pytest\ndef test_x(): pass", "python")
    assert is_valid


def test_is_valid_test_content_rejects_go_in_python():
    is_valid, error = is_valid_test_content(
        "package models\nfunc TestX(t *testing.T) { t.Error() }", "python"
    )
    assert not is_valid
    assert "Go" in error


def test_validate_test_path_rejects_traversal():
    is_valid, error = validate_test_path(
        "tests/../src/test.py", "pydantic/pydantic", "python"
    )
    assert not is_valid
    assert ".." in error


def test_validate_test_path_rejects_absolute():
    is_valid, error = validate_test_path(
        "/tests/test.py", "pydantic/pydantic", "python"
    )
    assert not is_valid
    assert "absolute" in error.lower()


def test_is_valid_test_content_empty():
    is_valid, error = is_valid_test_content("", "python")
    assert not is_valid
    assert "empty" in error.lower()


def test_validate_test_path_accepts_test_prefix():
    is_valid, _ = validate_test_path("test_feature.py", "pydantic/pydantic", "python")
    assert is_valid


def test_validate_test_path_accepts_nested_tests():
    is_valid, _ = validate_test_path(
        "myapp/tests/test_x.py", "pydantic/pydantic", "python"
    )
    assert is_valid
