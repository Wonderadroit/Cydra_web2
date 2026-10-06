import pytest
from cydra_web2.dogfood import DogfoodConfig,DogfoodRunner
from cydra_web2.adapter import IdentitySession,TargetConfig
from cydra_web2.model import TargetModel,Identity,Resource,Endpoint

def model():
    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("alice","owner",True))
    m.add_identity(Identity("bob","comparison",True))
    m.add_resource(Resource("r","record","alice","record-1"))
    m.add_endpoint(Endpoint("e","GET","/records/{id}",("r",),"read"))
    return m

def test_dogfood_requires_bindings_for_all_authenticated_model_identities():
    with pytest.raises(ValueError,match="missing identity bindings"):
        DogfoodRunner(model(),DogfoodConfig(TargetConfig.from_url("https://authorized.example"),(IdentitySession("alice",{}),)))

def test_dogfood_accepts_complete_identity_set():
    r=DogfoodRunner(model(),DogfoodConfig(TargetConfig.from_url("https://authorized.example"),(IdentitySession("alice",{}),IdentitySession("bob",{}))))
    assert r.config.target.base_url=="https://authorized.example"
