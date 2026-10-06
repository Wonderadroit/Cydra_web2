from dataclasses import dataclass
from .differential import DifferentialAction
@dataclass(frozen=True)
class StateTransition:
    id:str
    action:DifferentialAction
    requires:tuple[str,...]=()
    produces:tuple[str,...]=()
@dataclass(frozen=True)
class WorkflowExperiment:
    id:str
    hypothesis:str
    setup:tuple[StateTransition,...]
    attack:StateTransition
class WorkflowPlanner:
    def plan_cross_identity(self, transitions:tuple[StateTransition,...], owner_id:str, other_id:str):
        out=[]
        for t in transitions:
            if t.action.identity_id != owner_id: continue
            attack=StateTransition(t.id+":other",DifferentialAction(other_id,t.action.method,t.action.path),t.requires,t.produces)
            out.append(WorkflowExperiment("workflow:"+t.id+":"+other_id,
                f"identity {other_id} must not perform {t.action.method} {t.action.path} after the owner's workflow state is established",
                (t,),attack))
        return tuple(out)
