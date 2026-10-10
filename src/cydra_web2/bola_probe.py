"""Bounded, read-only BOLA differential probe for operator-authorized test objects."""
from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import urlsplit

from .evidence import classify_differential
from .verification import verify_replay


def run_read_only_bola_probe(
    adapter,
    *,
    path: str,
    resource_marker: str,
    owner_identity: str,
    comparison_identity: str,
    owner_control_confirmed: bool,
    runs: int = 2,
) -> dict:
    """Compare GET access to one operator-attested owner-controlled object.

    The caller must attest that the resource belongs exclusively to the owner
    test identity and that cross-identity testing is authorized. The probe never
    sends a state-changing method and never places response bodies in its report.
    """
    if not owner_control_confirmed:
        raise PermissionError("operator must confirm owner control of the test resource")
    if not owner_identity or not comparison_identity or owner_identity == comparison_identity:
        raise ValueError("two distinct explicit identity IDs are required")
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("resource path must be an absolute path on the configured target")
    if "\r" in path or "\n" in path:
        raise ValueError("resource path must not contain line breaks")
    parsed_path = urlsplit(path)
    if parsed_path.scheme or parsed_path.netloc or path.startswith("//"):
        raise ValueError("resource path must not specify another origin")
    if not resource_marker or not resource_marker.strip():
        raise ValueError("resource marker is required")
    if runs < 2:
        raise ValueError("at least two runs are required for replay verification")

    results = []
    observations = []
    for index in range(runs):
        owner = adapter.request(method="GET", path=path, identity_id=owner_identity)
        comparison = adapter.request(method="GET", path=path, identity_id=comparison_identity)
        experiment = SimpleNamespace(id=f"bola-read-only:{index + 1}")
        evidence = classify_differential(experiment, owner, comparison, resource_marker)
        result = SimpleNamespace(
            experiment=experiment,
            owner_response=owner,
            comparison_response=comparison,
            evidence=evidence,
        )
        results.append(result)
        observations.append({
            "run": index + 1,
            "method": "GET",
            "owner_status": owner.status_code,
            "comparison_status": comparison.status_code,
            "owner_resource_marker_found": bool(evidence.data.get("owner_resource_marker_found")),
            "comparison_resource_marker_found": bool(evidence.data.get("comparison_resource_marker_found")),
            "response_fingerprints_equal": bool(evidence.data.get("response_fingerprints_equal")),
            "candidate": bool(evidence.finding_candidate),
        })

    owner_baseline_valid = all(
        item["owner_resource_marker_found"] and 200 <= item["owner_status"] < 300
        for item in observations
    )
    if all(item["candidate"] for item in observations):
        verification = verify_replay(tuple(results))
        if verification.ready:
            status = "candidate"
            rationale = (
                "The comparison identity received the known resource marker in repeated successful GET responses. "
                "Human review must validate the operator's exclusive-ownership assertion and target policy."
            )
        else:
            status = "inconclusive"
            rationale = "The cross-identity observation did not pass replay impact verification."
    elif not owner_baseline_valid:
        status = "inconclusive"
        rationale = "The owner identity did not consistently demonstrate the known resource marker; comparison is not interpretable."
    elif all(
        not item["comparison_resource_marker_found"]
        and (item["comparison_status"] in {401, 403, 404})
        for item in observations
    ):
        status = "no_cross_identity_disclosure_observed"
        rationale = (
            "The comparison identity received an authorization-style denial or not-found response and did not receive "
            "the known resource marker in these read-only trials. This does not prove the application is secure or "
            "exclude other authorization flaws."
        )
    else:
        status = "inconclusive"
        rationale = "Results differed across replay runs; investigate state, caching, or session instability."

    return {
        "title": "CYDRA read-only BOLA differential probe",
        "status": status,
        "method": "GET",
        "path": parsed_path.path,
        "query_parameters_present": bool(parsed_path.query),
        "owner_identity": owner_identity,
        "comparison_identity": comparison_identity,
        "owner_control_attested_by_operator": True,
        "replay_runs": runs,
        "observations": observations,
        "rationale": rationale,
        "limitations": [
            "This probe tests one operator-supplied path and one known resource marker only.",
            "Ownership is attested by the operator; the probe cannot independently prove exclusive ownership.",
            "A candidate requires human validation of object ownership, expected policy, and actual impact.",
            "A negative result is limited to this request, these identities, and these observations.",
            "Response bodies, request headers, cookies, and resource marker values are not written to the report.",
        ],
    }
