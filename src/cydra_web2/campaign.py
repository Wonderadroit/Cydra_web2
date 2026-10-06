from dataclasses import dataclass,field
from .hypothesis import HypothesisPlanner
from .experiment_queue import ExperimentQueue
from .matrix import AuthorizationMatrix
@dataclass(frozen=True)
class CampaignStep:
    hypothesis_id:str
    priority:float
    rationale:str
@dataclass
class Campaign:
    steps:list[CampaignStep]=field(default_factory=list)
    def next(self):
        return self.steps[0] if self.steps else None
    def consume(self):
        return self.steps.pop(0) if self.steps else None
class CampaignBuilder:
    def build(self,model):
        frontier=HypothesisPlanner().build(model); queue=ExperimentQueue()
        matrix=AuthorizationMatrix().build(model)
        for h in frontier.hypotheses:
            cells=sum(1 for c in matrix if c.resource.id in h.resource_ids and c.endpoint.id in h.endpoint_ids)
            queue.push(h,10.0+cells,"modeled authorization boundary")
        return Campaign([CampaignStep(x.hypothesis.id,x.priority,x.rationale) for x in queue.items])