from __future__ import annotations
import os
from pathlib import Path

from cydra_web2.artifact import campaign_artifact, dumps_artifact
from cydra_web2.discovery import discover
from cydra_web2.differential import OwnershipExperiment
from cydra_web2.hypothesis import HypothesisPlanner
from cydra_web2.live_config import LiveDogfoodConfig
from cydra_web2.model import Identity, TargetModel


def main() -> int:
    config = LiveDogfoodConfig.from_environment()
    if len(config.identities) < 2:
        raise ValueError("live dogfood requires at least two explicit identities for differential testing")

    model = TargetModel(config.target.base_url)
    for session in config.identities:
        model.add_identity(Identity(session.identity_id, session.identity_id, True))

    adapter = __import__("cydra_web2.adapter", fromlist=["HttpAdapter"]).HttpAdapter(
        config.target, config.identities
    )
    seeds = tuple(x.strip() for x in os.environ.get("CYDRA_DISCOVERY_SEEDS", "/").split(",") if x.strip())
    max_paths = int(os.environ.get("CYDRA_MAX_PATHS", "50"))

    observations = []
    for session in config.identities:
        result = discover(adapter, model, seeds=seeds, max_paths=max_paths, identity_id=session.identity_id)
        observations.extend(result.observations)

    frontier = HypothesisPlanner().build(model)
    artifact = campaign_artifact(
        target=config.target.base_url,
        model=model,
        hypotheses=frontier.prioritized(),
        experiments=(),
        evidence=(),
        replays=(),
        assessment=None,
    )
    artifact["live"] = {
        "identities": [x.identity_id for x in config.identities],
        "discovery_observations": len(observations),
        "paths": sorted({x.endpoint_id for x in observations}),
        "status": "ownership unresolved; no authorization claim emitted",
    }

    output = Path(os.environ.get("CYDRA_ARTIFACT", "artifacts/live-dogfood.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_artifact(artifact), encoding="utf-8")

    print(
        f"CYDRA live discovery complete: identities={len(config.identities)} "
        f"observations={len(observations)} endpoints={len(model.endpoints)} "
        f"resources={len(model.resources)} hypotheses={len(frontier.hypotheses)}"
    )
    print("No finding is asserted: ownership/authentication boundaries require target evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
