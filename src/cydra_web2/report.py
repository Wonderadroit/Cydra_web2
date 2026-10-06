from dataclasses import dataclass
from .impact import ImpactAssessment
@dataclass(frozen=True)
class Finding:
    title:str
    endpoint:str
    identity:str
    resource:str
    impact:ImpactAssessment
    evidence_ids:tuple[str,...]
    reproduction:tuple[str,...]
def build_finding(title,endpoint,identity,resource,impact,evidence_ids,reproduction):
    if not evidence_ids: raise ValueError("finding requires evidence")
    if impact.classification.value=="none": raise ValueError("finding requires demonstrated impact")
    return Finding(title,endpoint,identity,resource,impact,tuple(evidence_ids),tuple(reproduction))
