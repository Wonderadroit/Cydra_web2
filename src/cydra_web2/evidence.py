from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re


class EvidenceKind(str, Enum):
    OBSERVATION = "observation"
    DIFFERENTIAL = "differential"
    CAUSAL_REPLAY = "causal_replay"
    CAPABILITY_FAILURE = "capability_failure"


@dataclass(frozen=True)
class Evidence:
    id: str
    kind: EvidenceKind
    confidence: float
    finding_candidate: bool
    rationale: str
    data: dict


def response_contains_marker(body: str, marker: str) -> bool:
    if not marker:
        return False
    try:
        data = json.loads(body)
    except (TypeError, json.JSONDecodeError):
        # For non-JSON bodies, require token boundaries so a marker such as
        # "record-12" does not match an unrelated "record-123".
        return re.search(
            rf"(?<![A-Za-z0-9_-]){re.escape(marker)}(?![A-Za-z0-9_-])",
            body,
        ) is not None

    def walk(value):
        if isinstance(value, dict):
            return any(walk(item) for item in value.values())
        if isinstance(value, list):
            return any(walk(item) for item in value)
        return str(value) == marker

    return walk(data)


def classify_differential(experiment, owner_response, comparison_response, resource_marker=None):
    """Flag only a demonstrated cross-identity disclosure of the modeled object.

    Equal successful response fingerprints are not sufficient: public endpoints,
    generic envelopes, and cached boilerplate can legitimately return identical
    bodies to different identities. Require a known object marker in both the
    owner's successful baseline and the comparison identity's successful response.
    """
    digest = hashlib.sha256(
        f"{owner_response.status_code}|{comparison_response.status_code}|"
        f"{owner_response.body_sha256}|{comparison_response.body_sha256}".encode()
    ).hexdigest()[:16]
    common_data = {
        "owner_status": owner_response.status_code,
        "comparison_status": comparison_response.status_code,
        "resource_marker_supplied": bool(resource_marker),
    }
    if owner_response.status_code >= 500 or comparison_response.status_code >= 500:
        return Evidence(
            f"{experiment.id}:server-error:{digest}", EvidenceKind.DIFFERENTIAL,
            0.2, False, "server errors are anomalies, not authorization proof", common_data,
        )

    owner_success = 200 <= owner_response.status_code < 300
    comparison_success = 200 <= comparison_response.status_code < 300
    owner_marker = bool(resource_marker and response_contains_marker(owner_response.body, resource_marker))
    comparison_marker = bool(resource_marker and response_contains_marker(comparison_response.body, resource_marker))
    data = {
        **common_data,
        "owner_resource_marker_found": owner_marker,
        "comparison_resource_marker_found": comparison_marker,
        "resource_marker_found": comparison_marker,  # Backward-compatible input for replay impact assessment.
        "response_fingerprints_equal": owner_response.body_sha256 == comparison_response.body_sha256,
    }
    if owner_success and comparison_success and owner_marker and comparison_marker:
        return Evidence(
            f"{experiment.id}:authorization-boundary:{digest}", EvidenceKind.DIFFERENTIAL,
            0.9, True,
            "the modeled owner's successful baseline and the other identity's successful response both contain the protected resource marker",
            data,
        )

    return Evidence(
        f"{experiment.id}:inconclusive-differential:{digest}", EvidenceKind.DIFFERENTIAL,
        0.75, False,
        "cross-identity disclosure was not demonstrated: require a known resource marker in both successful responses; status or matching fingerprints alone are insufficient",
        data,
    )
