# ueberdosis/tiptap-7532

Ensure the Markdown parsing in the editor handles code blocks fenced with tildes (~~~) as valid CommonMark/GFM syntax. Tilde-fenced code blocks, with or without language specifiers, should be parsed into the same code block representation as backtick-fenced blocks and must no longer be dropped. Parsing of backtick-fenced and indented code blocks should remain unchanged. This is a parse-only requirement; output serialization may continue to use backtick fences.
