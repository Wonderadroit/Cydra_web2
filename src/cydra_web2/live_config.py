from dataclasses import dataclass
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
            identities.append(IdentitySession(identity,{"Authorization":token}))
        if not identities:
            raise ValueError("CYDRA_IDENTITIES must contain at least one explicit identity")
        return cls(TargetConfig.from_url(base,extra_hosts=extra),tuple(identities))
