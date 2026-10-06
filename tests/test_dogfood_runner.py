import pytest
from types import SimpleNamespace
from cydra_web2.dogfood import DogfoodConfig,DogfoodRunner
from cydra_web2.adapter import IdentitySession,TargetConfig
from cydra_web2.model import TargetModel,Identity,Resource,Endpoint

class ControlledAdapter:
    pass

def model():
    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("alice","owner",True))
    m.add_identity(Identity("bob","comparison",True))
    m.add_resource(Resource("r","record","alice","record-1"))
    m.add_endpoint(Endpoint("e","GET","/records/{id}",("r",),"read"))
    return m

def test_dogfood_requires_target_match():
    with pytest.raises(ValueError,match="model target"):
        DogfoodRunner(model(),DogfoodConfig(TargetConfig.from_url("https://other.example"),(IdentitySession("alice",{}),)))

def test_dogfood_requires_explicit_identities():
    with pytest.raises(ValueError,match="at least one"):
        DogfoodRunner(model(),DogfoodConfig(TargetConfig.from_url("https://authorized.example"),()))

def test_dogfood_rejects_duplicate_identity_bindings():
    with pytest.raises(ValueError,match="unique"):
        DogfoodRunner(model(),DogfoodConfig(TargetConfig.from_url("https://authorized.example"),(IdentitySession("alice",{}),IdentitySession("alice",{}))))
