from dataclasses import dataclass
from enum import Enum
import hashlib
class EvidenceKind(str,Enum):
    OBSERVATION="observation"; DIFFERENTIAL="differential"; CAUSAL_REPLAY="causal_replay"; CAPABILITY_FAILURE="capability_failure"
@dataclass(frozen=True)
class Evidence:
    id:str
    kind:EvidenceKind
    confidence:float
    finding_candidate:bool
    rationale:str
    data:dict
def classify_differential(experiment,owner_response,comparison_response):
    digest=hashlib.sha256(f"{owner_response.status_code}|{comparison_response.status_code}|{owner_response.body_sha256}|{comparison_response.body_sha256}".encode()).hexdigest()[:16]
    if owner_response.status_code>=500 or comparison_response.status_code>=500:
        return Evidence(f"{experiment.id}:server-error:{digest}",EvidenceKind.DIFFERENTIAL,0.2,False,"server errors are anomalies, not authorization proof",{"owner_status":owner_response.status_code,"comparison_status":comparison_response.status_code})
    same_success=200<=owner_response.status_code<300 and 200<=comparison_response.status_code<300 and owner_response.body_sha256==comparison_response.body_sha256
    if same_success:
        return Evidence(f"{experiment.id}:same-success:{digest}",EvidenceKind.DIFFERENTIAL,0.85,True,"owner and comparison identities received the same successful response fingerprint for the same modeled resource",{"owner_status":owner_response.status_code,"comparison_status":comparison_response.status_code})
    return Evidence(f"{experiment.id}:divergent:{digest}",EvidenceKind.DIFFERENTIAL,0.75,False,"identities produced different outcomes; causal testing is required",{"owner_status":owner_response.status_code,"comparison_status":comparison_response.status_code})
