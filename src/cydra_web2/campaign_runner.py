from dataclasses import dataclass
from .boundary import BoundaryAssessment,assess_boundary
from .engine import ResearchEngine
from .experiment_state import ExperimentState,ExperimentStage,advance

@dataclass(frozen=True)
class CampaignOutcome:
    executed:int
    candidates:int
    assessment:BoundaryAssessment|None
    stopped:bool
    states:tuple[ExperimentState,...]=()

class CampaignRunner:
    """Run bounded authorization experiments and replay the first real candidate."""
    def __init__(self,engine:ResearchEngine,max_experiments:int=25):
        if max_experiments<1: raise ValueError("max_experiments must be positive")
        self.engine=engine; self.max_experiments=max_experiments
    def run(self,experiments):
        executed=0; candidates=0; states=[]
        for experiment in experiments:
            if executed>=self.max_experiments: break
            executed+=1
            state=ExperimentState(experiment.id,ExperimentStage.PLANNED,"selected from bounded campaign")
            state=advance(state,ExperimentStage.VALIDATED,"execution scope and model planning already passed")
            first=self.engine.execute(experiment)
            state=advance(state,ExperimentStage.EXECUTED,"owner/comparison requests completed")
            state=advance(state,ExperimentStage.OBSERVED,"differential evidence classified")
            states.append(state)
            if not first.evidence.finding_candidate: continue
            candidates+=1
            replay=self.engine.replay(experiment,2)
            verification=self.engine.causal_gate(replay)
            from .verification import verify_replay
            assessment=assess_boundary(tuple(r.evidence for r in replay),verify_replay(replay))
            if assessment.reportable:
                states[-1]=advance(states[-1],ExperimentStage.CAUSAL,"replay established stable non-NONE impact")
                return CampaignOutcome(executed,candidates,assessment,True,tuple(states))
        return CampaignOutcome(executed,candidates,None,False,tuple(states))
