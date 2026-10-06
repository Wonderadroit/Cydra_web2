from dataclasses import dataclass
from .adapter import HttpAdapter,HttpResponse
from .differential import DifferentialExperiment,DifferentialPlanner
from .evidence import Evidence,EvidenceKind,classify_differential
from .model import TargetModel
from .normalization import semantic_fingerprint
from .provenance import EvidenceLedger
from .verification import verify_replay
@dataclass(frozen=True)
class ExperimentResult:
    experiment:DifferentialExperiment
    owner_response:HttpResponse
    comparison_response:HttpResponse
    evidence:Evidence
class ResearchEngine:
    def __init__(self,model:TargetModel,adapter:HttpAdapter):
        self.model=model; self.adapter=adapter; self.planner=DifferentialPlanner()\n        self.ledger=EvidenceLedger()
    def plan_authorization_frontier(self): return self.planner.plan_authorization(self.model)
    def execute(self,experiment):
        owner=self.adapter.request(method=experiment.owner.method,path=experiment.owner.path,identity_id=experiment.owner.identity_id)
        comparison=self.adapter.request(method=experiment.comparison.method,path=experiment.comparison.path,identity_id=experiment.comparison.identity_id)
        resource=self.model.resources.get(experiment.resource_id)
        marker=resource.identifier if resource else None
        result=ExperimentResult(experiment,owner,comparison,classify_differential(experiment,owner,comparison,marker))
        self.ledger.record(experiment.id,"execution",(),{"owner":experiment.owner.__dict__,"comparison":experiment.comparison.__dict__},{"owner":owner.body_sha256,"comparison":comparison.body_sha256})
        return result
    def replay(self,experiment,runs=2):
        if runs<2: raise ValueError("causal replay requires at least two runs")
        results=tuple(self.execute(experiment) for _ in range(runs))
        self.ledger.record(experiment.id,"replay",(),{"runs":runs},{"stable":verify_replay(results).stable})
        return results
    @staticmethod
    def causal_gate(results):
        return verify_replay(results).ready and all(x.evidence.kind==EvidenceKind.DIFFERENTIAL for x in results)
