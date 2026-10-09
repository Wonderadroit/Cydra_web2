from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def identity_differentials(observations: Iterable[object]) -> list[dict]:
    """Summarize same-endpoint response differences across identities without asserting a finding."""
    grouped: dict[str, dict[str, list[object]]] = defaultdict(lambda: defaultdict(list))
    for observation in observations:
        endpoint_id = getattr(observation, "endpoint_id", None)
        identity_id = getattr(observation, "identity_id", None)
        if not isinstance(endpoint_id, str) or not endpoint_id or not isinstance(identity_id, str) or not identity_id:
            continue
        grouped[endpoint_id][identity_id].append(observation)

    output = []
    for endpoint_id, by_identity in sorted(grouped.items()):
        if len(by_identity) < 2:
            continue
        identities = {}
        signatures = {}
        for identity_id, records in sorted(by_identity.items()):
            signatures_for_identity = sorted({
                (int(getattr(record, "status_code", 0)), str(getattr(record, "body_sha256", "")), int(getattr(record, "body_length", 0)))
                for record in records
            })
            signatures[identity_id] = signatures_for_identity
            identities[identity_id] = {
                "observation_count": len(records),
                "status_codes": sorted({x[0] for x in signatures_for_identity}),
                "body_lengths": sorted({x[2] for x in signatures_for_identity}),
                "body_fingerprints": sorted({x[1] for x in signatures_for_identity if x[1]}),
            }
        differs = len({tuple(value) for value in signatures.values()}) > 1
        output.append({
            "endpoint_id": endpoint_id,
            "identities": identities,
            "response_differs_between_identities": differs,
            "classification": "differential_candidate" if differs else "no_observed_difference",
            "finding_asserted": False,
            "limitation": "response differences are triage signals only; ownership, authorization boundary, and impact require independent validation",
        })
    return output
