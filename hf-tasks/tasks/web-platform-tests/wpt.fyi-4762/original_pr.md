# web-platform-tests/wpt.fyi-4762 (original PR)

web-platform-tests/wpt.fyi (#4762): Verify that triage URLs are actually URLs.

It's easy as a tirager to type a malformed URL into the URL field, i.e. crbug.com/123, when triaging failures. This adds logic to check that the provided URL string at least looks like a valid URL, to avoid YAML errors etc once the triage results makes it into the metadata.

