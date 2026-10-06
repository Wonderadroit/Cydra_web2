from dataclasses import dataclass, field
from enum import Enum
from .model import TargetModel, Identity, Resource, Endpoint

class HypothesisKind(str, Enum):
    AUTHORIZATION="authorization"
    OBJECT_SUBSTITUTION="object_substitution"
    REQUEST_VARIANT="request_variant"
    WORKFLOW="workflow"
    STATE_BOUNDARY="state_boundary"
    OWNERSHIP="ownership"

@dataclass(frozen=True)
class Hypothesis:
    id: str
    kind: HypothesisKind
    claim: str
    identity_ids: tuple[str,...]=()
    resource_ids: tuple[str,...]=()
    endpoint_ids: tuple[str,...]=()
    expected_boundary: str=""

@dataclass
class ResearchFrontier:
    hypotheses: list[Hypothesis]=field(default_factory=list)
    explored: set[str]=field(default_factory=set)
    def add(self,h):
        if h.id not in {x.id for x in self.hypotheses}: self.hypotheses.append(h)
    def next(self):
        for h in self.hypotheses:
            if h.id not in self.explored: return h
        return None
    def mark_explored(self,hypothesis_id):
        self.explored.add(hypothesis_id)

class HypothesisPlanner:
    def build(self, model: TargetModel) -> ResearchFrontier:
        f=ResearchFrontier()
        for r in sorted(model.resources.values(), key=lambda x: x.id):
            if r.owner_id is None:
                f.add(Hypothesis(
                    id=f"ownership:{r.id}",
                    kind=HypothesisKind.OWNERSHIP,
                    claim=f"ownership of {r.id} is unresolved and must be established from target evidence before authorization testing",
                    resource_ids=(r.id,), expected_boundary="resource ownership"))
        for owner,other,r,e in model.authorization_candidates():
            f.add(Hypothesis(
                id=f"auth:{r.id}:{e.id}:{owner.id}:{other.id}",
                kind=HypothesisKind.AUTHORIZATION,
                claim=f"{other.id} may cross the authorization boundary for {r.id} through {e.id}",
                identity_ids=(owner.id,other.id), resource_ids=(r.id,), endpoint_ids=(e.id,),
                expected_boundary="resource authorization"))
        return f
