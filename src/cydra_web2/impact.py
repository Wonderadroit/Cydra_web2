from dataclasses import dataclass
from enum import Enum
class ImpactClass(str,Enum):
    NONE="none"; READ="read"; WRITE="write"; ACCOUNT="account"; FINANCIAL="financial"; PRIVILEGE="privilege"
@dataclass(frozen=True)
class ImpactAssessment:
    classification:ImpactClass
    confidence:float
    rationale:str
def assess(*,status_code:int,resource_marker_found:bool,method:str)->ImpactAssessment:
    if not 200 <= status_code < 300 or not resource_marker_found:
        return ImpactAssessment(ImpactClass.NONE,0.2,"no demonstrated unauthorized resource effect")
    if method.upper() in {"POST","PUT","PATCH","DELETE"}:
        return ImpactAssessment(ImpactClass.WRITE,0.8,"successful state-changing request against a protected resource")
    return ImpactAssessment(ImpactClass.READ,0.8,"successful access to a protected resource")
