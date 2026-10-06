from dataclasses import dataclass
from typing import Any,Mapping
@dataclass(frozen=True)
class RequestVariant:
    name:str
    method:str
    path:str
    headers:Mapping[str,str]=None
    body:Any=None
@dataclass(frozen=True)
class RequestExperiment:
    id:str
    hypothesis:str
    baseline:RequestVariant
    variant:RequestVariant
class RequestDifferentialPlanner:
    def plan_method_variants(self, method:str,path:str)->tuple[RequestVariant,...]:
        variants=[]
        for candidate in ("GET","POST","PUT","PATCH","DELETE"):
            if candidate != method.upper():
                variants.append(RequestVariant(candidate.lower(),candidate,path))
        return tuple(variants)
    def plan_identifier_substitution(self,path:str,source_id:str,target_id:str):
        if not source_id or not target_id or source_id==target_id: return None
        if source_id not in path: return None
        variant=path.replace(source_id,target_id,1)
        return RequestExperiment("request:id-substitution",f"changing only the resource identifier must not cross an authorization boundary",RequestVariant("baseline","GET",path),RequestVariant("substitute","GET",variant))
