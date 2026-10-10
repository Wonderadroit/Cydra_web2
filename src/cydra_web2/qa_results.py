"""Conservative result classification for QA execution outcomes."""


def classify_exception(exc: BaseException) -> tuple[str, str]:
    """Return (status, category) without overstating uncertain runtime failures.

    Only an explicit behavioral assertion failure is classified as FAIL.
    Browser, renderer, timeout, and other exceptions are INCONCLUSIVE because
    they may indicate either an application issue or an execution problem.
    """
    if isinstance(exc, AssertionError):
        return "FAIL", "BEHAVIOR_ASSERTION"
    return "INCONCLUSIVE", "EXECUTION_OR_ENVIRONMENT"
