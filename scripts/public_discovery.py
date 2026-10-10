from __future__ import annotations

import os
from pathlib import Path

from cydra_web2.adapter import HttpAdapter, TargetConfig
from cydra_web2.artifact import campaign_artifact, dumps_artifact, ownership_next_experiments, resource_provenance
from cydra_web2.discovery import discover
from cydra_web2.hypothesis import HypothesisPlanner
from cydra_web2.model import TargetModel


def main() -> int:
    target_url = os.environ.get("CYDRA_TARGET_URL", "").strip()
    if not target_url:
        raise ValueError("CYDRA_TARGET_URL is required")

    extra_hosts = {
        x.strip()
        for x in os.environ.get("CYDRA_EXTRA_HOSTS", "").split(",")
        if x.strip()
    }
    target = TargetConfig.from_url(target_url, extra_hosts=extra_hosts)

    # Public/anonymous development mode deliberately has no identity binding.
    # It may discover and model exposed behavior, but it must never infer
    # ownership or emit an authorization finding from anonymous observations.
    model = TargetModel(target.base_url)
    adapter = HttpAdapter(target, ())

    seeds = tuple(
        x.strip()
        for x in os.environ.get("CYDRA_DISCOVERY_SEEDS", "/").split(",")
        if x.strip()
    )
    max_paths = int(os.environ.get("CYDRA_MAX_PATHS", "50"))

    result = discover(
        adapter,
        model,
        seeds=seeds,
        max_paths=max_paths,
        identity_id=None,
    )
    frontier = HypothesisPlanner().build(model)

    artifact = campaign_artifact(
        target=target.base_url,
        model=model,
        hypotheses=frontier.prioritized(),
        experiments=(),
        evidence=(),
        replays=(),
        assessment=None,
    )
    api_frontier = sorted(
        endpoint.path
        for endpoint in model.endpoints.values()
        if endpoint.path.startswith("/api/") or endpoint.path.startswith("/graphql") or endpoint.path.startswith("/v1/") or endpoint.path.startswith("/v2/") or endpoint.path.startswith("/v3/")
    )
    artifact["live"] = {
        "mode": "public-anonymous-discovery",
        "discovery_observations": len(result.observations),
        "paths": list(result.paths),
        "status": "anonymous observation only; ownership/authentication boundaries remain unresolved",
        "api_frontier": api_frontier,
        "observations": [
            {"id": o.id, "endpoint": o.endpoint_id, "status_code": o.status_code, "identity_id": o.identity_id, "body_size": o.body_length, "fingerprint": o.body_sha256}
            for o in result.observations
        ],
        "resources": resource_provenance(model),
        "next_experiments": ownership_next_experiments(model),
        "bundle_frontier": [
            {"path": a.path, "methods": list(a.methods), "endpoints": [{"method": m, "path": p} for m, p in a.endpoints], "service_origins": list(a.service_origins), "request_origins": [{"value": v, "origin": o} for v, o in a.request_origins], "unresolved": list(a.unresolved)}
            for a in result.bundle_analyses
        ],
        "hypothesis_frontier": [
            {"id": h.id, "kind": h.kind.value, "claim": h.claim}
            for h in frontier.prioritized()
        ],
    }

    output = Path(os.environ.get("CYDRA_ARTIFACT", "artifacts/public-discovery.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_artifact(artifact), encoding="utf-8")

    print(
        "CYDRA public discovery complete: "
        f"observations={len(result.observations)} "
        f"endpoints={len(model.endpoints)} "
        f"resources={len(model.resources)} "
        f"hypotheses={len(frontier.hypotheses)}"
    )
    print("No authorization or ownership finding is asserted in anonymous mode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
