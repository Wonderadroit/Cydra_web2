from dataclasses import dataclass
from .boundary import BoundaryAssessment,assess_boundary
from .engine import ResearchEngine

@dataclass(frozen=True)
class CampaignOutcome:
    executed:int
    candidates:int
    assessment:BoundaryAssessment|None
    stopped:bool

class CampaignRunner:
    """Run bounded authorization experiments and replay the first real candidate."""
    def __init__(self,engine:ResearchEngine,max_experiments:int=25):
        if max_experiments<1: raise ValueError("max_experiments must be positive")
        self.engine=engine; self.max_experiments=max_experiments
    def run(self,experiments):
        executed=0; candidates=0
        for experiment in experiments:
            if executed>=self.max_experiments: break
            executed+=1
            first=self.engine.execute(experiment)
            if not first.evidence.finding_candidate: continue
            candidates+=1
            replay=self.engine.replay(experiment,2)
            verification=self.engine.causal_gate(replay)
            from .verification import verify_replay
            assessment=assess_boundary(tuple(r.evidence for r in replay),verify_replay(replay))
            if assessment.reportable:
                return CampaignOutcome(executed,candidates,assessment,True)
        return CampaignOutcome(executed,candidates,None,False)
