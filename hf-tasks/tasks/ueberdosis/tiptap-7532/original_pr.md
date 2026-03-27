# ueberdosis/tiptap-7532 (original PR)

ueberdosis/tiptap (#7532): Hotfix/markdown codeblock tilde rendering

## Changes Overview

Fix `@tiptap/markdown` silently dropping code blocks that use tilde fences (`~~~`), which are valid CommonMark and GFM syntax.

## Implementation Approach

The `parseMarkdown` handler in the CodeBlock extension had a guard condition that only accepted code tokens whose `raw` property starts with backtick fences (`` ``` ``) or are indented code blocks. Tilde-fenced blocks (`~~~`) were rejected, returning an empty array and silently dropping the content.

The fix adds `token.raw?.startsWith('~~~') === false` to the existing guard condition so tilde fences are accepted alongside backtick fences.

## Testing Done

Added 5 new tests in `packages/markdown/__tests__/conversion.spec.ts`:

- Parse tilde fenced code blocks (no language)
- Parse tilde fenced code blocks with language specifier
- Parse backtick fenced code blocks (no language)
- Parse backtick fenced code blocks with language specifier
- Verify tilde and backtick fences produce identical JSON output

Full unit test suite passes: **63 test files, 647 tests, 0 failures**.

## Verification Steps

1. Parse a tilde-fenced code block via the markdown manager and confirm it produces a `codeBlock` node:
   ```
   ~~~js
   console.log("hello")
   ~~~
   ```
2. Confirm the output is identical to parsing the same content with backtick fences.
3. Run `pnpm test:unit` and verify all tests pass.

## Additional Notes

The serializer (`renderMarkdown`) always outputs backtick fences, which is correct — this is a parse-only fix. The input rules for `~~~` in the editor already worked; only the markdown-to-JSON parsing path was affected.

## Checklist

- [x] I have created a [changeset](https://github.com/changesets/changesets) for this PR if necessary.
- [x] My changes do not break the library.
- [x] I have added tests where applicable.
- [x] I have followed the project guidelines.
- [x] I have fixed any lint issues.

## Related Issues

Fixes #7528
