from dataclasses import dataclass
from .hypothesis import HypothesisPlanner
from .matrix import AuthorizationMatrix
from .experiment_queue import ExperimentQueue
@dataclass(frozen=True)
class ResearchPlan:
    hypotheses:int; authorization_cells:int; next_hypothesis_id:str|None
class CampaignPlanner:
    def plan(self,model):
        frontier=HypothesisPlanner().build(model); queue=ExperimentQueue()
        for h in frontier.hypotheses: queue.push(h,1.0+len(h.resource_ids)+len(h.endpoint_ids),"explicit security-boundary hypothesis")
        matrix=AuthorizationMatrix().build(model)
        return ResearchPlan(len(frontier.hypotheses),len(matrix),queue.items[0].hypothesis.id if queue.items else None)