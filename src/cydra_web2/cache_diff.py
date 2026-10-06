from dataclasses import dataclass
@dataclass(frozen=True)
class CacheObservation:
    identity_id:str; cache_status:str|None; age:str|None; body_sha256:str
@dataclass(frozen=True)
class CacheDifferential:
    suspicious:bool; rationale:str
def compare_cache(owner,other):
    same_body=owner.body_sha256==other.body_sha256
    shared_cache=bool(owner.cache_status and other.cache_status and owner.cache_status.upper()==other.cache_status.upper()=="HIT")
    if same_body and shared_cache and owner.identity_id!=other.identity_id:
        return CacheDifferential(True,"distinct identities received identical cache-hit content; authorization-aware cache behavior requires causal validation")
    return CacheDifferential(False,"no cache-boundary contradiction established")