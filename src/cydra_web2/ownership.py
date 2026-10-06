from dataclasses import dataclass
from .model import Resource, TargetModel

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
