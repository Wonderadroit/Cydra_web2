from dataclasses import dataclass
from .adapter import HttpAdapter,HttpResponse
from .differential import DifferentialExperiment,DifferentialPlanner
from .evidence import Evidence,EvidenceKind,classify_differential
from .model import TargetModel
@dataclass(frozen=True)
class ExperimentResult:
    experiment:DifferentialExperiment
    owner_response:HttpResponse
    comparison_response:HttpResponse
    evidence:Evidence
class ResearchEngine:
    def __init__(self,model:TargetModel,adapter:HttpAdapter):
        self.model=model; self.adapter=adapter; self.planner=DifferentialPlanner()
    def plan_authorization_frontier(self): return self.planner.plan_authorization(self.model)
    def execute(self,experiment):
        owner=self.adapter.request(method=experiment.owner.method,path=experiment.owner.path,identity_id=experiment.owner.identity_id)
        comparison=self.adapter.request(method=experiment.comparison.method,path=experiment.comparison.path,identity_id=experiment.comparison.identity_id)
        resource=self.model.resources.get(experiment.resource_id)
        marker=resource.identifier if resource else None
        return ExperimentResult(experiment,owner,comparison,classify_differential(experiment,owner,comparison,marker))
    def replay(self,experiment,runs=2):
        if runs<2: raise ValueError("causal replay requires at least two runs")
        return tuple(self.execute(experiment) for _ in range(runs))
    @staticmethod
    def causal_gate(results):
        return len(results)>=2 and all(x.evidence.finding_candidate and x.evidence.kind==EvidenceKind.DIFFERENTIAL for x in results)
