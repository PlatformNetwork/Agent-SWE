# pygments/pygments-3027 (original PR)

pygments/pygments (#3027): TOML lexer: Support TOML 1.1.0

The TOML 1.1.0 changes are:

- Allow newlines and trailing commas in inline tables
- Add \xHH notation to basic strings for codepoints ≤255
- Add \e escape for the escape character (not applicable: pygments allows anything after the backslash)
- Seconds in datetime and time values are now optional

Ref. the TOML changelog: https://github.com/toml-lang/toml/blob/main/CHANGELOG.md#110--2025-12-18

Fixes #3026
