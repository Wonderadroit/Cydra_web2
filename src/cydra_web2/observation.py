import hashlib
from .model import Observation


def observation_from_response(*, observation_id: str, endpoint_id: str, identity_id: str | None, response, request_fingerprint: str) -> Observation:
    """Create a model observation from an executed HTTP response without guessing semantics."""
    body = response.body if isinstance(response.body, str) else str(response.body)
    body_hash = getattr(response, "body_sha256", None) or hashlib.sha256(body.encode()).hexdigest()
    return Observation(
        observation_id,
        endpoint_id,
        identity_id,
        response.status_code,
        body_hash,
        len(body.encode()),
        request_fingerprint,
    )
