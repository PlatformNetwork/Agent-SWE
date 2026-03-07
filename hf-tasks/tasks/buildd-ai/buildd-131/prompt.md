# buildd-ai/buildd-131

Add an integration test that validates session resume behavior. The test should run a session where the agent creates a file and commit, then completes, and a follow-up message should ask for a secret from the first session. Ensure the resumed session preserves context so the secret marker is returned. When failures occur, include diagnostics such as the session identifier, which resume mechanism was used, milestones/commits, session logs, and output.
