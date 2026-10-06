from dataclasses import dataclass
from urllib.parse import urlparse

@dataclass(frozen=True)
class ScopeDecision:
    allowed:bool
    reason:str

def check_scope(url,allowed_hosts,allowed_schemes=("https",)):
    p=urlparse(url)
    if p.scheme not in allowed_schemes: return ScopeDecision(False,"scheme outside allowlist")
    if p.hostname not in set(allowed_hosts): return ScopeDecision(False,"host outside allowlist")
    return ScopeDecision(True,"target is within explicit scope")
