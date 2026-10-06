from cydra_web2.model import Identity, Resource, Endpoint, Observation, TargetModel
from cydra_web2.ownership import OwnershipClaim, resolve_ownership

def test_ownership_requires_observed_identity():
    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("alice","user",True)); m.add_identity(Identity("bob","user",True))
    m.add_resource(Resource("r1","profile",None,"123"))
    m.add_endpoint(Endpoint("GET /profiles/{id}","GET","/profiles/{id}",("r1",)))
    m.add_observation(Observation("o1","GET /profiles/{id}","alice",200,"a"*64,10,"req"))
    resolve_ownership(m,(OwnershipClaim("r1","alice","o1","observed owner session"),))
    assert m.resources["r1"].owner_id=="alice"

def test_unknown_owner_cannot_be_guessed():
    m=TargetModel("https://authorized.example"); m.add_identity(Identity("alice","user",True)); m.add_resource(Resource("r1","profile",None,"123"))
    try: resolve_ownership(m,(OwnershipClaim("r1","alice","missing","guess"),))
    except ValueError as e: assert "observation" in str(e)
    else: raise AssertionError("ownership must fail closed")
