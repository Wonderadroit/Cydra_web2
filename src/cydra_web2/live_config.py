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
        shared_headers=cls._headers_from_environment("CYDRA_SHARED_HEADERS")
        identity_headers=cls._identity_headers_from_environment()
        identities=[]
        if identity_headers is not None:
            for identity,headers in identity_headers.items():
                merged=dict(shared_headers)
                merged.update(headers)
                identities.append(IdentitySession(identity,merged))
        else:
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
            for identity in cls._browser_identity_ids_from_environment():
                identities.append(IdentitySession(identity,dict(shared_headers)))
        if not identities:
            raise ValueError("CYDRA_IDENTITIES, CYDRA_IDENTITY_HEADERS, or CYDRA_BROWSER_STORAGE_STATES must contain at least one explicit identity")
        return cls(TargetConfig.from_url(base,extra_hosts=extra),tuple(identities))

    @staticmethod
    def _headers_from_environment(name):
        raw=os.environ.get(name,"").strip()
        if not raw:
            return {}
        try:
            parsed=json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{name} must be a JSON object") from exc
        if not isinstance(parsed,dict):
            raise ValueError(f"{name} must be a JSON object")
        return LiveDogfoodConfig._validate_headers(parsed,name)

    @classmethod
    def _identity_headers_from_environment(cls):
        raw=os.environ.get("CYDRA_IDENTITY_HEADERS","").strip()
        if not raw:
            return None
        try:
            parsed=json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("CYDRA_IDENTITY_HEADERS must be a JSON object") from exc
        if not isinstance(parsed,dict):
            raise ValueError("CYDRA_IDENTITY_HEADERS must be a JSON object")
        out={}
        for identity,headers in parsed.items():
            if not isinstance(identity,str) or not identity.strip() or not isinstance(headers,dict):
                raise ValueError("CYDRA_IDENTITY_HEADERS must map identity IDs to header objects")
            out[identity.strip()]=cls._validate_headers(headers,"CYDRA_IDENTITY_HEADERS")
        return out

    @staticmethod
    def _browser_identity_ids_from_environment():
        raw=os.environ.get("CYDRA_BROWSER_STORAGE_STATES","").strip()
        if not raw:
            return ()
        try:
            parsed=json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("CYDRA_BROWSER_STORAGE_STATES must be a JSON object") from exc
        if not isinstance(parsed,dict):
            raise ValueError("CYDRA_BROWSER_STORAGE_STATES must be a JSON object")
        identities=[]
        for identity in parsed:
            if not isinstance(identity,str) or not identity.strip():
                raise ValueError("CYDRA_BROWSER_STORAGE_STATES must map non-empty identity IDs to storage states")
            identities.append(identity.strip())
        return tuple(identities)

    @staticmethod
    def _validate_headers(headers,name):
        out={}
        for key,value in headers.items():
            if not isinstance(key,str) or not key.strip() or not isinstance(value,str):
                raise ValueError(f"{name} must contain string header names and values")
            out[key.strip()]=value
        return out
