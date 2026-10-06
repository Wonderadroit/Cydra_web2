from dataclasses import dataclass
@dataclass(frozen=True)
class SequenceAction:
    identity_id:str
    method:str
    path:str
    label:str
@dataclass(frozen=True)
class SequencePlan:
    actions:tuple[SequenceAction,...]
    rationale:str
class SequencePlanner:
    def cross_identity(self,actions,owner_id,other_id):
        if not actions: return ()
        return (SequencePlan(tuple(SequenceAction(other_id,a.method,a.path,a.label) for a in actions),"replay the same workflow under a different identity"),)
    def prefix(self,actions):
        return tuple(SequencePlan(tuple(actions[:i]),f"workflow prefix length {i}") for i in range(1,len(actions)+1))