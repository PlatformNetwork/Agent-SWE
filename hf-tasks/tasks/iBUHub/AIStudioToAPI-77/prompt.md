# iBUHub/AIStudioToAPI-77

Update the login flow to work with the latest AI Studio changes. Stop using the blank app proxy method and instead require a developer-provided pre-created app for authentication. Remove support for configuring the WebSocket port via an environment variable; the service must always use port 9998. Reflect this behavior as a user-facing change.
