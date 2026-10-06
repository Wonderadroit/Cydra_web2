from dataclasses import dataclass, field

@dataclass(frozen=True)
class StateFact:
    name:str
    value:object=True

@dataclass(frozen=True)
class Transition:
    id:str
    action:str
    requires:tuple[str,...]=()
    produces:tuple[str,...]=()
    identity_id:str|None=None

@dataclass
class WorkflowGraph:
    facts:set[str]=field(default_factory=set)
    transitions:list[Transition]=field(default_factory=list)
    def add_transition(self,t): self.transitions.append(t)
    def reachable(self, max_steps=8):
        paths=[]
        def walk(facts,path,remaining):
            if len(path)>=max_steps: return
            for t in self.transitions:
                if t in remaining and set(t.requires)<=facts:
                    nf=facts|set(t.produces)
                    paths.append(path+(t,))
                    walk(nf,path+(t,),[x for x in remaining if x!=t])
        walk(set(self.facts),(),list(self.transitions))
        return tuple(paths)

    def find_identity_mismatches(self):
        groups={}
        for t in self.transitions:
            groups.setdefault(t.action,[]).append(t)
        return tuple((action,tuple(ts)) for action,ts in groups.items() if len({t.identity_id for t in ts})>1)
