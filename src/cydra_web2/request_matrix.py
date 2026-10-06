from dataclasses import dataclass
@dataclass(frozen=True)
class RequestVariant:
    label:str
    method:str
    path:str
    headers:tuple[tuple[str,str],...]=()
    body:str|None=None
@dataclass(frozen=True)
class VariantPair:
    baseline:RequestVariant
    variant:RequestVariant
class RequestVariantPlanner:
    def build(self,method,path,identifier=None):
        out=[RequestVariant("baseline",method,path)]
        if identifier:
            out.append(RequestVariant("identifier-substitution",method,path.replace(identifier,"{SUBSTITUTED}")))
        if method.upper()=="GET":
            out.extend([RequestVariant("head","HEAD",path),RequestVariant("options","OPTIONS",path)])
        return tuple(VariantPair(out[0],x) for x in out[1:])