from dataclasses import dataclass
from urllib.parse import urlparse

@dataclass(frozen=True)
class ScopePolicy:
    allowed_hosts:frozenset[str]
    allowed_schemes:frozenset[str]=frozenset({"https"})
    max_requests:int=1000

class ScopeGuard:
    def __init__(self,policy): self.policy=policy; self.count=0
    def check(self,url):
        u=urlparse(url)
        if u.scheme not in self.policy.allowed_schemes: raise ValueError("scheme outside scope")
        if u.hostname not in self.policy.allowed_hosts: raise ValueError("host outside scope")
        if self.count>=self.policy.max_requests: raise RuntimeError("request budget exhausted")
        self.count+=1; return True
