from dataclasses import dataclass
from enum import Enum
from typing import Any,Mapping

class ParameterLocation(str,Enum):
    PATH="path"; QUERY="query"; HEADER="header"; COOKIE="cookie"; JSON="json"; FORM="form"

@dataclass(frozen=True)
class Parameter:
    name:str
    location:ParameterLocation
    value:Any

@dataclass(frozen=True)
class RequestTemplate:
    method:str
    path:str
    parameters:tuple[Parameter,...]=()

    def mutate(self,name:str,value:Any)->"RequestTemplate":
        found=False; out=[]
        for p in self.parameters:
            if p.name==name:
                out.append(Parameter(p.name,p.location,value)); found=True
            else: out.append(p)
        if not found: raise KeyError(name)
        return RequestTemplate(self.method,self.path,tuple(out))
