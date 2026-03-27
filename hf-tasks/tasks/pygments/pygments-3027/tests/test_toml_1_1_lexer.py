import re

from pygments.lexers import get_lexer_by_name
from pygments.token import Comment, Error, Literal, Punctuation, String


def _lex_toml(text: str):
    lexer = get_lexer_by_name("toml")
    return list(lexer.get_tokens(text))


def _assert_no_error_tokens(tokens):
    errors = [val for tok, val in tokens if tok is Error]
    assert not errors, f"unexpected Error tokens: {errors}"


def test_inline_table_allows_newlines_comments_and_trailing_commas():
    text = (
        "tbl = {\n"
        "  a = 1,\n"
        "  # inline comment\n"
        "  b = \"hi\",\n"
        "}\n"
    )
    tokens = _lex_toml(text)

    _assert_no_error_tokens(tokens)
    assert any(tok is Comment.Single and val == "# inline comment" for tok, val in tokens)
    assert sum(1 for tok, val in tokens if tok is Punctuation and val == ",") == 2


def test_basic_string_hex_escape_sequences():
    text = "msg = \"hex: \\x7F and nul \\x00\"\n"
    tokens = _lex_toml(text)

    escape_tokens = [val for tok, val in tokens if tok is String.Escape]
    assert escape_tokens == ["\\x7F", "\\x00"]
    assert any(tok is String.Double and "hex:" in val for tok, val in tokens)


def test_time_literals_without_seconds():
    time_text = "t = 09:30\n"
    datetime_text = "dt = 2024-06-01 10:11\n"

    time_tokens = _lex_toml(time_text)
    datetime_tokens = _lex_toml(datetime_text)

    _assert_no_error_tokens(time_tokens)
    _assert_no_error_tokens(datetime_tokens)

    assert any(tok is Literal.Date and val == "09:30" for tok, val in time_tokens)
    assert any(tok is Literal.Date and val == "2024-06-01 10:11" for tok, val in datetime_tokens)
