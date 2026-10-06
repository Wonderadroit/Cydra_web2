from dataclasses import dataclass,field
import hashlib,json,urllib.error,urllib.parse,urllib.request
from http.cookiejar import CookieJar
from typing import Any,Mapping
@dataclass(frozen=True)
class TargetConfig:
    base_url:str
    allowed_hosts:frozenset[str]
    timeout_seconds:float=15.0
    @classmethod
    def from_url(cls,base_url:str,*,extra_hosts:set[str]|None=None):
        p=urllib.parse.urlparse(base_url)
        if p.scheme not in {"http","https"} or not p.hostname: raise ValueError("base_url must be an absolute HTTP(S) URL")
        return cls(base_url.rstrip("/"),frozenset({p.hostname}|(extra_hosts or set())))
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
    def __init__(self,target:TargetConfig,identities:tuple[IdentitySession,...]=()):
        self.target=target; self.identities={x.identity_id:x for x in identities}; self._jars={}
    def request(self,*,method:str,path:str,identity_id:str|None=None,headers:Mapping[str,str]|None=None,body:Any=None):
        url=urllib.parse.urljoin(self.target.base_url+"/",path.lstrip("/"))
        if urllib.parse.urlparse(url).hostname not in self.target.allowed_hosts: raise PermissionError("request host is outside the target allowlist")
        session=self.identities.get(identity_id) if identity_id else None
        jar=self._jars.setdefault(identity_id or "__anonymous__",CookieJar())
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        merged={"User-Agent":"CYDRA-Web2/0.1"}
        if session: merged.update(session.headers)
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
        if urllib.parse.urlparse(url).hostname not in self.target.allowed_hosts: raise PermissionError("redirect escaped the target allowlist")
