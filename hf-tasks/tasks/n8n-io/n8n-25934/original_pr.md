# n8n-io/n8n-25934 (original PR)

n8n-io/n8n (#25934): refactor(core): Remove unused serializeExpression() from workflow SDK

## Summary
- Removes the unused proxy-based `serializeExpression()` function and its helpers (`createExpressionProxy`, `buildPath`, `EXPRESSION_ROOT_MAPPINGS`)
- Removes types exclusive to it: `Expression<T>`, `ExpressionContext`, `BinaryContext`, `BinaryField`, `InputContext`
- The string-based `expr()` is the sole expression utility used in practice; `serializeExpression()` had zero consumers outside its own test suite

## Test plan
- [x] All 4,259 workflow-sdk tests pass (86 suites)
- [x] `pnpm typecheck` passes
- [x] Full `pnpm build` succeeds (46/46 tasks)

https://linear.app/n8n/issue/AI-2059

🤖 Generated with [Claude Code](https://claude.com/claude-code)
