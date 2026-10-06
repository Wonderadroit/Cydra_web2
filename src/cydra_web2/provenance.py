from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib, json

@dataclass(frozen=True)
class EvidenceRecord:
    id:str
    experiment_id:str
    phase:str
    parent_ids:tuple[str,...]
    input_fingerprint:str
    output_fingerprint:str
    timestamp:str
    reproducible:bool

class EvidenceLedger:
    def __init__(self): self.records=[]
    def record(self, experiment_id, phase, parent_ids, inputs, outputs, reproducible=True):
        def fp(x): return hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()
        rid=hashlib.sha256(f"{experiment_id}|{phase}|{fp(inputs)}|{fp(outputs)}".encode()).hexdigest()[:20]
        rec=EvidenceRecord(rid,experiment_id,phase,tuple(parent_ids),fp(inputs),fp(outputs),datetime.now(timezone.utc).isoformat(),reproducible)
        self.records.append(rec); return rec
    def lineage(self, record_id):
        by={r.id:r for r in self.records}; out=[]
        def visit(r):
            out.append(r)
            for p in r.parent_ids:
                if p in by: visit(by[p])
        if record_id in by: visit(by[record_id])
        return tuple(out)
