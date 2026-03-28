"""Custom exceptions for swe-forge."""


class DiscoveryError(Exception):
    """Raised when command discovery fails and no LLM is available.

    This exception is raised when:
    - No install commands were discovered via LLM
    - No test commands were discovered via LLM
    - LLM client is not configured for command discovery

    The pipeline should fail gracefully rather than falling back to
    hardcoded commands.
    """

    pass
