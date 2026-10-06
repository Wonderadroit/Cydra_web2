from dataclasses import dataclass
import hashlib,json
from typing import Mapping

@dataclass(frozen=True)
class SemanticResponse:
    status:int
    content_type:str|None
    body_hash:str
    json_shape:tuple[str,...]
    location:str|None
    set_cookie_names:tuple[str,...]

def _shape(value,prefix=""):
    out=[]
    if isinstance(value,dict):
        for k,v in sorted(value.items()): out.append(prefix+k); out.extend(_shape(v,prefix+k+"."))
    elif isinstance(value,list):
        for v in value[:3]: out.extend(_shape(v,prefix+"[]"))
    return out

def summarize(status:int,headers:Mapping[str,str],body:str)->SemanticResponse:
    try: data=json.loads(body); shape=tuple(_shape(data))
    except (TypeError,json.JSONDecodeError): shape=()
    cookies=tuple(sorted(k.split("=",1)[0].strip() for k,v in headers.items() if k.lower()=="set-cookie"))
    location=next((v for k,v in headers.items() if k.lower()=="location"),None)
    ctype=next((v for k,v in headers.items() if k.lower()=="content-type"),None)
    return SemanticResponse(status,ctype,hashlib.sha256(body.encode()).hexdigest(),shape,location,cookies)
