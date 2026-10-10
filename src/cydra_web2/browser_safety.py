"""Safe browser observation helpers. Never trust URL string prefixes as origins."""
from urllib.parse import urlsplit, urlunsplit


def same_origin(candidate: str, target: str) -> bool:
    """Return true only for identical normalized scheme/host/port origins."""
    try:
        left, right = urlsplit(candidate), urlsplit(target)
        if left.scheme.lower() not in {"http", "https"} or right.scheme.lower() not in {"http", "https"}:
            return False
        if not left.hostname or not right.hostname:
            return False
        left_port = left.port or (443 if left.scheme.lower() == "https" else 80)
        right_port = right.port or (443 if right.scheme.lower() == "https" else 80)
        return (
            left.scheme.lower() == right.scheme.lower()
            and left.hostname.lower().rstrip(".") == right.hostname.lower().rstrip(".")
            and left_port == right_port
        )
    except (ValueError, TypeError):
        return False


def safe_observed_url(candidate: str, target: str) -> str | None:
    """Return same-origin URL path only; omit userinfo, query strings and fragments."""
    if not same_origin(candidate, target):
        return None
    try:
        parsed = urlsplit(candidate)
        path = parsed.path or "/"
        return urlunsplit((parsed.scheme.lower(), urlsplit(target).netloc, path, "", ""))
    except (ValueError, TypeError):
        return None
