# HKUDS/nanobot-824 (original PR)

HKUDS/nanobot (#824): fix: /help command bypasses ACL on Telegram

## Summary

- Add dedicated `_on_help` handler for the `/help` command in Telegram channel
- `/help` now responds directly without routing through the message bus ACL check
- Consistent with how `/start` already works (has its own handler)

## Problem

The `/help` slash command always failed on Telegram with:

```
Access denied for sender xxxxxxxx on channel telegram. Add them to allowFrom list in config to grant access.
```

This happened because `/help` was routed through `_forward_command` → `_handle_message` → `is_allowed()`, which rejects users not in the `allowFrom` list.

## Root Cause

In `telegram.py`, both `/new` and `/help` used `_forward_command`, which calls `BaseChannel._handle_message()`. That method checks `is_allowed()` before forwarding to the bus. Since `/help` is purely informational, it should not require authorization.

Meanwhile, `/start` already had its own handler (`_on_start`) that replied directly, bypassing the ACL — so `/start` always worked while `/help` did not.

## Fix

Added a `_on_help` handler that replies directly to the user (like `/start`), bypassing the message bus and ACL check entirely.

## Test plan

- [ ] Send `/help` on Telegram as an unauthorized user → should receive help text
- [ ] Send `/help` on Telegram as an authorized user → should receive help text
- [ ] Send `/new` on Telegram as an authorized user → should still work via bus
- [ ] Send `/start` → should still work as before

Closes #687



