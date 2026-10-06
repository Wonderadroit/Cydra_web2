from dataclasses import dataclass
from .model import Resource, TargetModel, Observation
from .differential import OwnershipExperiment
from .evidence import response_contains_marker

@dataclass(frozen=True)
class OwnershipClaim:
    resource_id: str
    identity_id: str
    observation_id: str
    rationale: str

def resolve_ownership(model: TargetModel, claims: tuple[OwnershipClaim, ...]) -> TargetModel:
    """Apply explicit, observed ownership claims; never infer ownership from field names."""
    updated = model
    for claim in claims:
        if claim.resource_id not in updated.resources:
            raise ValueError("ownership claim references unknown resource")
        if claim.identity_id not in updated.identities:
            raise ValueError("ownership claim references unknown identity")
        if not any(o.id == claim.observation_id and o.identity_id == claim.identity_id for o in updated.observations):
            raise ValueError("ownership claim requires an observation by the claimed owner")
        current = updated.resources[claim.resource_id]
        if current.owner_id is not None and current.owner_id != claim.identity_id:
            raise ValueError("conflicting ownership claim")
        updated.resources[claim.resource_id] = Resource(current.id, current.label, claim.identity_id, current.identifier, current.source_observation)
    return updated

def claim_from_experiment(model: TargetModel, experiment: OwnershipExperiment, observation: Observation, response_body: str) -> OwnershipClaim:
    """Convert an ownership experiment into a claim only when target evidence proves control."""
    if observation.identity_id != experiment.identity_id:
        raise ValueError("ownership evidence must come from the experiment identity")
    if observation.endpoint_id != experiment.endpoint_id:
        raise ValueError("ownership evidence must come from the experiment endpoint")
    resource = model.resources.get(experiment.resource_id)
    if resource is None:
        raise ValueError("ownership experiment references unknown resource")
    if resource.identifier is None:
        raise ValueError("ownership evidence requires a resource identifier")
    if not 200 <= observation.status_code < 300:
        raise ValueError("ownership evidence requires a successful response")
    if not response_contains_marker(response_body, resource.identifier):
        raise ValueError("ownership evidence requires the exact resource marker")
    return OwnershipClaim(
        resource_id=resource.id,
        identity_id=experiment.identity_id,
        observation_id=observation.id,
        rationale="successful ownership experiment response contained the exact modeled resource identifier",
    )

def resolve_experiment_ownership(model: TargetModel, experiment: OwnershipExperiment, observation: Observation, response_body: str) -> TargetModel:
    claim = claim_from_experiment(model, experiment, observation, response_body)
    return resolve_ownership(model, (claim,))
