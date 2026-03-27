# pygments/pygments-3027

Update the TOML lexer to support TOML 1.1.0 syntax. Inline tables should allow newlines and trailing commas. Basic strings should recognize \xHH escapes for codepoints up to 255. Datetime and time literals should allow the seconds component to be omitted. Ensure behavior matches TOML 1.1.0 expectations.
