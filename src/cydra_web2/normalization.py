import hashlib, json, re
from dataclasses import dataclass

_VOLATILE_KEY=re.compile(r"(token|csrf|nonce|timestamp|expires|request[_-]?id|trace[_-]?id|session)",re.I)
@dataclass(frozen=True)
class NormalizedResponse:
    status_code:int
    content_type:str
    semantic_sha256:str
    markers:tuple[str,...]

def _clean(v):
    if isinstance(v,dict):
        return {k:_clean(x) for k,x in sorted(v.items()) if not _VOLATILE_KEY.search(k)}
    if isinstance(v,list): return [_clean(x) for x in v]
    return v

def normalize_body(body:str, content_type="") -> str:
    try:
        return json.dumps(_clean(json.loads(body)),sort_keys=True,separators=(",",":"))
    except (TypeError,json.JSONDecodeError):
        return re.sub(r"\b[0-9a-fA-F]{8,}\b","<volatile>",body.strip())

def semantic_fingerprint(status_code:int,body:str,content_type=""):
    normalized=normalize_body(body,content_type)
    return hashlib.sha256(f"{status_code}|{content_type.lower()}|{normalized}".encode()).hexdigest()

def normalize_response(response):
    ct=response.headers.get("content-type","") if getattr(response,"headers",None) else ""
    return NormalizedResponse(response.status_code,ct,semantic_fingerprint(response.status_code,response.body,ct),())
