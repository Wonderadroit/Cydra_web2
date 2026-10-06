from dataclasses import dataclass
from .evidence import Evidence
from .verification import VerificationResult

@dataclass(frozen=True)
class BoundaryAssessment:
    candidate:bool
    replay_verified:bool
    reportable:bool
    evidence_ids:tuple[str,...]
    rationale:str

def assess_boundary(evidence:tuple[Evidence,...],verification:VerificationResult)->BoundaryAssessment:
    ids=tuple(e.id for e in evidence)
    candidate=bool(evidence) and all(e.finding_candidate for e in evidence)
    verified=candidate and verification.ready
    return BoundaryAssessment(candidate,verified,verified and bool(verification.impact.value!="none"),ids,
        "reportable boundary violation" if verified and verification.impact.value!="none" else "boundary candidate is not yet reportable")
