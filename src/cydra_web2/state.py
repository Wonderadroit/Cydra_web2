from dataclasses import dataclass
import hashlib,json
from typing import Any

@dataclass(frozen=True)
class StateFingerprint:
    digest:str
    changed:bool
    rationale:str

def fingerprint(value:Any)->str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()
    return hashlib.sha256(raw).hexdigest()

def compare_state(before:Any,after:Any)->StateFingerprint:
    a,b=fingerprint(before),fingerprint(after)
    return StateFingerprint(b,a!=b,"state fingerprint changed" if a!=b else "state fingerprint unchanged")
