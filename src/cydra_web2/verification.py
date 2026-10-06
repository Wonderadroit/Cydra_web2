from dataclasses import dataclass
from .impact import assess,ImpactClass
@dataclass(frozen=True)
class VerificationResult:
    replay_count:int
    stable:bool
    impact:ImpactClass
    ready:bool
    rationale:str
def verify_replay(results):
    if len(results)<2: return VerificationResult(len(results),False,ImpactClass.NONE,False,"at least two independent executions are required")
    candidates=[r.evidence.finding_candidate for r in results]
    impacts=[]
    for r in results:
        marker=bool(r.evidence.data.get("resource_marker_found"))
        impacts.append(assess(status_code=r.comparison_response.status_code,resource_marker_found=marker,method=r.comparison_response.method).classification)
    stable=all(candidates) and len(set(impacts))==1
    impact=impacts[0] if impacts else ImpactClass.NONE
    return VerificationResult(len(results),stable,impact,stable and impact!=ImpactClass.NONE,"replay is stable and demonstrates non-NONE impact" if stable and impact!=ImpactClass.NONE else "replay did not establish stable impact")