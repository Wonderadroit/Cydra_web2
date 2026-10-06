from __future__ import annotations
from dataclasses import dataclass
import hashlib,json,re
from html.parser import HTMLParser
from typing import Iterable
from .adapter import HttpAdapter
from .model import Endpoint,Identity,Observation,Resource,TargetModel

@dataclass(frozen=True)
class DiscoveryResult:
    model:TargetModel
    paths:tuple[str,...]
    observations:tuple[Observation,...]
    resource_ids:tuple[str,...]

class _Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=set()
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if v and k.lower() in {"href","src","action"}: self.links.add(v)

_ID=re.compile(r"^(?:id|uuid|[A-Za-z][A-Za-z0-9]*(?:_id|_uuid|Id|UUID))$",re.I)

def _documents(body:str):
    docs=[]
    try: docs.append(json.loads(body))
    except (TypeError,json.JSONDecodeError): pass
    for attrs,source in re.findall(r"<script\\b([^>]*)>(.*?)</script\\s*>",body,re.I|re.S):
        if re.search(r'type\\s*=\\s*["\\\']application/json["\\\']',attrs,re.I):
            try: docs.append(json.loads(source))
            except (TypeError,json.JSONDecodeError): pass
    return docs

def _ids(value,path=""):
    if isinstance(value,dict):
        for k,v in value.items():
            p=f"{path}.{k}" if path else str(k)
            if _ID.fullmatch(str(k)) and isinstance(v,(str,int)) and str(v).strip():
                yield str(k),str(v),p
            yield from _ids(v,p)
    elif isinstance(value,list):
        for i,v in enumerate(value): yield from _ids(v,f"{path}[{i}]")

def discover(adapter:HttpAdapter,model:TargetModel,seeds:Iterable[str]=("/",),max_paths:int=50)->DiscoveryResult:
    queue=list(dict.fromkeys(seeds)); seen=set(); observations=[]; resource_ids=[]
    while queue and len(seen)<max_paths:
        path=queue.pop(0)
        if path in seen: continue
        seen.add(path)
        endpoint_id=f"GET {path}"
        if endpoint_id not in model.endpoints:
            model.add_endpoint(Endpoint(endpoint_id,"GET",path))
        response=adapter.request(method="GET",path=path)
        fp=hashlib.sha256(response.body.encode()).hexdigest()
        obs=Observation(f"obs:{len(observations)}",endpoint_id,response.identity_id,response.status_code,fp,len(response.body),f"GET:{path}")
        model.add_observation(obs); observations.append(obs)
        for key,identifier,field_path in _ids(_documents(response.body)):
            rid="resource:"+hashlib.sha256((key+"|"+identifier).encode()).hexdigest()[:16]
            if rid not in model.resources:
                model.add_resource(Resource(rid,key,None,identifier,obs.id)); resource_ids.append(rid)
        parser=_Links(); parser.feed(response.body)
        for link in sorted(parser.links):
            if link.startswith("/") and link not in seen and link not in queue: queue.append(link)
    return DiscoveryResult(model,tuple(seen),tuple(observations),tuple(resource_ids))
