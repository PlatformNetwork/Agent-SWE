# guardian/dotcom-rendering-15398

Enable the football match header to render entirely on the client when match data isn’t available at render time. Accept a single optional initial data input instead of separate match/tab/league values; when it’s missing, show a placeholder and then load and display match data on the client. Preserve current server-rendered behavior when initial data is provided.
