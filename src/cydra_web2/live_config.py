from dataclasses import dataclass
import json
import os
from .adapter import IdentitySession,TargetConfig

@dataclass(frozen=True)
class LiveDogfoodConfig:
    target:TargetConfig
    identities:tuple[IdentitySession,...]

    @classmethod
    def from_environment(cls):
        base=os.environ.get("CYDRA_TARGET_URL","").strip()
        if not base:
            raise ValueError("CYDRA_TARGET_URL is required")
        extra={x.strip() for x in os.environ.get("CYDRA_EXTRA_HOSTS","").split(",") if x.strip()}
        shared_headers=cls._headers_from_environment()
        identities=[]
        raw=os.environ.get("CYDRA_IDENTITIES","")
        for item in raw.split(";"):
            item=item.strip()
            if not item: continue
            if "=" not in item:
                raise ValueError("CYDRA_IDENTITIES entries must use identity_id=authorization_header")
            identity,token=item.split("=",1)
            if not identity or not token:
                raise ValueError("identity bindings cannot be empty")
            headers=dict(shared_headers)
            headers["Authorization"]=token
            identities.append(IdentitySession(identity,headers))
        if not identities:
            raise ValueError("CYDRA_IDENTITIES must contain at least one explicit identity")
        return cls(TargetConfig.from_url(base,extra_hosts=extra),tuple(identities))

    @staticmethod
    def _headers_from_environment():
        raw=os.environ.get("CYDRA_SHARED_HEADERS","").strip()
        if not raw:
            return {}
        try:
            parsed=json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("CYDRA_SHARED_HEADERS must be a JSON object") from exc
        if not isinstance(parsed,dict):
            raise ValueError("CYDRA_SHARED_HEADERS must be a JSON object")
        headers={}
        for name,value in parsed.items():
            if not isinstance(name,str) or not name.strip() or not isinstance(value,str):
                raise ValueError("CYDRA_SHARED_HEADERS must contain string header names and values")
            headers[name.strip()]=value
        return headers
