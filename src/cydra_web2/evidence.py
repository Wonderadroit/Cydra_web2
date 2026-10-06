from dataclasses import dataclass
from enum import Enum
import hashlib,json,re
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
def response_contains_marker(body:str,marker:str)->bool:
    if not marker: return False
    if marker in body: return True
    try:
        data=json.loads(body)
    except (TypeError,json.JSONDecodeError): return False
    def walk(v):
        if isinstance(v,dict): return any(walk(x) for x in v.values())
        if isinstance(v,list): return any(walk(x) for x in v)
        return str(v)==marker
    return walk(data)
def classify_differential(experiment,owner_response,comparison_response,resource_marker=None):
    digest=hashlib.sha256(f"{owner_response.status_code}|{comparison_response.status_code}|{owner_response.body_sha256}|{comparison_response.body_sha256}".encode()).hexdigest()[:16]
    if owner_response.status_code>=500 or comparison_response.status_code>=500:
        return Evidence(f"{experiment.id}:server-error:{digest}",EvidenceKind.DIFFERENTIAL,0.2,False,"server errors are anomalies, not authorization proof",{"owner_status":owner_response.status_code,"comparison_status":comparison_response.status_code})
    owner_success=200<=owner_response.status_code<300
    comparison_success=200<=comparison_response.status_code<300
    same_success=owner_success and comparison_success and owner_response.body_sha256==comparison_response.body_sha256
    marker=bool(resource_marker and response_contains_marker(comparison_response.body,resource_marker))
    if same_success or (comparison_success and marker):
        reason="comparison identity received the same successful response fingerprint" if same_success else "comparison identity received a successful response containing the protected resource marker"
        return Evidence(f"{experiment.id}:authorization-boundary:{digest}",EvidenceKind.DIFFERENTIAL,0.9,True,reason,{"owner_status":owner_response.status_code,"comparison_status":comparison_response.status_code,"resource_marker_found":marker})
    return Evidence(f"{experiment.id}:divergent:{digest}",EvidenceKind.DIFFERENTIAL,0.75,False,"identities produced different or non-proving outcomes; causal testing is required",{"owner_status":owner_response.status_code,"comparison_status":comparison_response.status_code,"resource_marker_found":marker})
