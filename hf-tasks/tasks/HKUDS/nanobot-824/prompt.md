# HKUDS/nanobot-824

Allow the Telegram /help command to work for all users regardless of access control restrictions. Ensure it returns the help text directly without requiring users to be in the allowlist, while keeping existing access control behavior for other commands unchanged (e.g., /new still requires authorization and /start continues to work as before).
