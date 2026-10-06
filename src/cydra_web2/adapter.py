from dataclasses import dataclass,field
import hashlib,json,urllib.error,urllib.parse,urllib.request
from http.cookiejar import CookieJar
from typing import Any,Mapping
from .scope import check_scope
from .session import IdentityBinding,SessionRegistry

@dataclass(frozen=True)
class TargetConfig:
    base_url:str
    allowed_hosts:frozenset[str]
    timeout_seconds:float=15.0
    @classmethod
    def from_url(cls,base_url:str,*,extra_hosts:set[str]|None=None):
        p=urllib.parse.urlparse(base_url)
        if p.scheme not in {"http","https"} or not p.hostname: raise ValueError("base_url must be an absolute HTTP(S) URL")
        hosts={p.hostname}\n        for host in extra_hosts or set(): hosts.add(host.lower().strip())\n        return cls(base_url.rstrip("/"),frozenset(hosts))

@dataclass(frozen=True)
class HttpResponse:
    url:str
    final_url:str
    method:str
    identity_id:str|None
    status_code:int
    headers:Mapping[str,str]
    body:str
    body_sha256:str

@dataclass(frozen=True)
class IdentitySession:
    identity_id:str
    headers:Mapping[str,str]=field(default_factory=dict)

class HttpAdapter:
    """Scoped HTTP executor. Live execution is HTTPS-only and identity-bound."""
    def __init__(self,target:TargetConfig,identities:tuple[IdentitySession,...]=(),*,session_registry:SessionRegistry|None=None):
        self.target=target
        bindings=tuple(IdentityBinding(x.identity_id,x.headers) for x in identities)
        self.registry=session_registry or SessionRegistry(bindings)
        self._jars={}
    @property
    def identities(self):
        return {identity_id: self.registry.get(identity_id) for identity_id in self.registry.ids()}
    def request(self,*,method:str,path:str,identity_id:str|None=None,headers:Mapping[str,str]|None=None,body:Any=None):
        if identity_id is not None:
            binding=self.registry.get(identity_id)
        elif self.registry.ids():
            raise PermissionError("anonymous execution is disabled when explicit identities are configured")
        url=urllib.parse.urljoin(self.target.base_url+"/",path.lstrip("/"))
        decision=check_scope(url,self.target.allowed_hosts,("https",))
        if not decision.allowed:
            raise PermissionError(decision.reason)
        jar=self._jars.setdefault(identity_id or "__anonymous__",CookieJar())
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        merged={"User-Agent":"CYDRA-Web2/0.1"}
        if identity_id is not None: merged.update(binding.headers)
        merged.update(headers or {})
        payload=None
        if body is not None:
            payload=body if isinstance(body,bytes) else (body.encode() if isinstance(body,str) else json.dumps(body,separators=(",",":")).encode())
            if not isinstance(body,(bytes,str)): merged.setdefault("Content-Type","application/json")
        req=urllib.request.Request(url,data=payload,headers=merged,method=method.upper())
        try:
            r=opener.open(req,timeout=self.target.timeout_seconds); raw=r.read(); status=r.status; rh=dict(r.headers.items()); final=r.geturl()
        except urllib.error.HTTPError as e:
            raw=e.read(); status=e.code; rh=dict(e.headers.items()); final=e.geturl()
        except urllib.error.URLError as e:
            raise OSError(f"HTTP transport failed: {e.reason}") from e
        self._validate_final_host(final)
        return HttpResponse(url,final,method.upper(),identity_id,status,rh,raw.decode("utf-8",errors="replace"),hashlib.sha256(raw).hexdigest())
    def _validate_final_host(self,url):
        decision=check_scope(url,self.target.allowed_hosts,("https",))
        if not decision.allowed: raise PermissionError(f"redirect escaped scope: {decision.reason}")