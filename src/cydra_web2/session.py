from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class IdentityBinding:
    identity_id:str
    headers:Mapping[str,str]=()
    enabled:bool=True

class SessionRegistry:
    def __init__(self,bindings=()):
        self._bindings={b.identity_id:b for b in bindings}
    def get(self,identity_id):
        b=self._bindings.get(identity_id)
        if b is None or not b.enabled: raise KeyError(identity_id)
        return b
    def ids(self): return tuple(sorted(self._bindings))
