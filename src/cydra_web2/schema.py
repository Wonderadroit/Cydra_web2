import json,re
from dataclasses import dataclass

@dataclass(frozen=True)
class SchemaEndpoint:
    method:str
    path:str
    operation_id:str|None=None
    parameters:tuple[str,...]=()

def parse_openapi(text:str):
    try: doc=json.loads(text)
    except json.JSONDecodeError: raise ValueError("schema parser currently requires JSON OpenAPI")
    out=[]
    for path,item in doc.get("paths",{}).items():
        for method,op in item.items():
            if method.lower() in {"get","post","put","patch","delete","options","head"}:
                params=tuple(p.get("name","") for p in op.get("parameters",[]) if p.get("name"))
                out.append(SchemaEndpoint(method.upper(),path,op.get("operationId"),params))
    return tuple(out)

def extract_frontend_routes(script:str):
    routes=set()
    patterns=[r"""["'](/(?:api|graphql|v[0-9]+)[^"'\s]*)["']""",r"""fetch\(\s*["']([^"']+)["']"""]
    for p in patterns: routes.update(re.findall(p,script))
    return tuple(sorted(routes))
