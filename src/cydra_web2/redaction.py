from collections.abc import Mapping

SENSITIVE_KEYS = frozenset({
    "authorization", "proxy-authorization", "cookie", "set-cookie",
    "x-api-key", "api-key", "apikey", "access-token", "refresh-token",
    "id-token", "token", "password", "secret", "client-secret",
})


def _sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("_", "-")
    return normalized in SENSITIVE_KEYS or normalized.endswith("-token") or normalized.endswith("-secret")


def redact(value):
    """Recursively remove credential material before artifacts/log-facing serialization."""
    if isinstance(value, Mapping):
        return {key: "[REDACTED]" if _sensitive_key(key) else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value
