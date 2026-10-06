from dataclasses import dataclass, field
@dataclass(frozen=True)
class Identity:
    id:str
    label:str
    authenticated:bool=False
@dataclass(frozen=True)
class Resource:
    id:str
    label:str
    owner_id:str|None
    identifier:str|None
    source_observation:str|None=None
@dataclass(frozen=True)
class Endpoint:
    id:str
    method:str
    path:str
    resource_ids:tuple[str,...]=()
    action:str|None=None
@dataclass(frozen=True)
class Observation:
    id:str
    endpoint_id:str
    identity_id:str|None
    status_code:int
    body_sha256:str
    body_length:int
    request_fingerprint:str
@dataclass
class TargetModel:
    target:str
    identities:dict[str,Identity]=field(default_factory=dict)
    resources:dict[str,Resource]=field(default_factory=dict)
    endpoints:dict[str,Endpoint]=field(default_factory=dict)
    observations:list[Observation]=field(default_factory=list)
    def add_identity(self,x): self._unique(self.identities,x.id,x)
    def add_resource(self,x):
        if x.owner_id is not None and x.owner_id not in self.identities: raise ValueError("resource owner must be a modeled identity")
        self._unique(self.resources,x.id,x)
    def add_endpoint(self,x):
        missing=[r for r in x.resource_ids if r not in self.resources]
        if missing: raise ValueError(f"endpoint references unknown resources: {missing}")
        self._unique(self.endpoints,x.id,x)
    def add_observation(self,x):
        if x.endpoint_id not in self.endpoints: raise ValueError("observation references an unknown endpoint")
        if x.identity_id is not None and x.identity_id not in self.identities: raise ValueError("observation references an unknown identity")
        if any(o.id==x.id for o in self.observations): raise ValueError(f"duplicate observation: {x.id}")
        self.observations.append(x)
    def authorization_candidates(self):
        out=[]
        for r in sorted(self.resources.values(),key=lambda x:x.id):
            if r.owner_id is None: continue
            owner=self.identities[r.owner_id]
            for other in sorted(self.identities.values(),key=lambda x:x.id):
                if other.id==owner.id: continue
                for e in sorted(self.endpoints.values(),key=lambda x:x.id):
                    if r.id in e.resource_ids: out.append((owner,other,r,e))
        return tuple(out)
    @staticmethod
    def _unique(store,key,value):
        if not key.strip(): raise ValueError("model identifiers must not be empty")
        if key in store and store[key]!=value: raise ValueError(f"conflicting model object: {key}")
        store[key]=value
