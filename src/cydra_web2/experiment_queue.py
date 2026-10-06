from dataclasses import dataclass
from .hypothesis import Hypothesis
@dataclass(frozen=True)
class QueuedExperiment:
    hypothesis:Hypothesis; priority:float; rationale:str
class ExperimentQueue:
    def __init__(self): self.items=[]
    def push(self,h,priority,rationale): self.items.append(QueuedExperiment(h,priority,rationale)); self.items.sort(key=lambda x:(-x.priority,x.hypothesis.id))
    def pop(self): return self.items.pop(0) if self.items else None
    def extend(self,items):
        for x in items: self.push(x.hypothesis,x.priority,x.rationale)
    def __len__(self): return len(self.items)