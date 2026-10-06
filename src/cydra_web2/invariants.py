from dataclasses import dataclass
from enum import Enum
class InvariantKind(str,Enum):
    CONFIDENTIALITY="confidentiality"; INTEGRITY="integrity"; AUTHORIZATION="authorization"; WORKFLOW="workflow"; OWNERSHIP="ownership"
@dataclass(frozen=True)
class Invariant:
    id:str; kind:InvariantKind; statement:str; protected_resource_id:str|None=None; required_identity_ids:tuple[str,...]=()
@dataclass(frozen=True)
class InvariantViolation:
    invariant:Invariant; evidence_id:str; observed:str; impact:str
def authorization_invariants(model):
    return tuple(Invariant(f"owner:{r.id}",InvariantKind.OWNERSHIP,f"only authorized identities may access {r.id}",r.id,(r.owner_id,))
                 for r in model.resources.values() if r.owner_id)