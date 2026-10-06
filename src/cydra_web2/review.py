from dataclasses import dataclass
from .boundary import BoundaryAssessment
from .impact import assess
from .report import Finding,build_finding

@dataclass(frozen=True)
class HumanReview:
    accepted:bool
    reviewer_note:str

def finalize_finding(*,assessment:BoundaryAssessment,endpoint:str,identity:str,resource:str,method:str,status_code:int,resource_marker_found:bool,reproduction:tuple[str,...],review:HumanReview)->Finding:
    if not review.accepted:
        raise PermissionError("human review is required before a finding is finalized")
    if not assessment.reportable:
        raise ValueError("boundary assessment is not reportable")
    impact=assess(status_code=status_code,resource_marker_found=resource_marker_found,method=method)
    return build_finding("Verified authorization boundary violation",endpoint,identity,resource,impact,assessment.evidence_ids,reproduction)
