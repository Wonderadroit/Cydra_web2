from dataclasses import dataclass
import re
from .model import TargetModel
@dataclass(frozen=True)
class DifferentialAction:
    identity_id:str
    method:str
    path:str
@dataclass(frozen=True)
class DifferentialExperiment:
    id:str
    hypothesis:str
    owner:DifferentialAction
    comparison:DifferentialAction
    resource_id:str
    endpoint_id:str
class DifferentialPlanner:
    _PARAM=re.compile(r"{([A-Za-z_][A-Za-z0-9_-]*)}|:([A-Za-z_][A-Za-z0-9_-]*)")
    def plan_authorization(self,model:TargetModel):
        out=[]
        for owner,other,resource,endpoint in model.authorization_candidates():
            path=self._materialize(endpoint,resource)
            if path is None: continue
            out.append(DifferentialExperiment(f"auth:{resource.id}:{endpoint.id}:{other.id}",f"{other.id} must not receive the owner's authorized resource outcome from {endpoint.method} {endpoint.path}",DifferentialAction(owner.id,endpoint.method,path),DifferentialAction(other.id,endpoint.method,path),resource.id,endpoint.id))
        return tuple(out)
    def _materialize(self,endpoint,resource):
        if not self._PARAM.search(endpoint.path): return endpoint.path
        if resource.identifier is None: return None
        path=endpoint.path
        for m in list(self._PARAM.finditer(path))[::-1]:
            path=path[:m.start()]+resource.identifier+path[m.end():]
        return path
