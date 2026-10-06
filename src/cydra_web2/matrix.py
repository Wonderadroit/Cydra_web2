from dataclasses import dataclass
from itertools import combinations
from .model import TargetModel, Identity, Resource, Endpoint

@dataclass(frozen=True)
class BoundaryCell:
    owner: Identity
    subject: Identity
    resource: Resource
    endpoint: Endpoint
    relation: str

class AuthorizationMatrix:
    def build(self, model: TargetModel):
        cells=[]
        for r in sorted(model.resources.values(),key=lambda x:x.id):
            if not r.owner_id: continue
            owner=model.identities[r.owner_id]
            for subject in sorted(model.identities.values(),key=lambda x:x.id):
                if subject.id==owner.id: continue
                for e in sorted(model.endpoints.values(),key=lambda x:x.id):
                    if r.id in e.resource_ids:
                        relation="same-role" if subject.label==owner.label else "cross-role"
                        cells.append(BoundaryCell(owner,subject,r,e,relation))
        return tuple(cells)

    def role_pairs(self, model: TargetModel):
        identities=sorted(model.identities.values(),key=lambda x:x.id)
        return tuple((a,b) for a,b in combinations(identities,2) if a.authenticated==b.authenticated and a.label!=b.label)
