from cydra_web2.model import Identity, Resource, Endpoint, Observation, TargetModel
from cydra_web2.ownership import OwnershipClaim, resolve_ownership, claim_from_experiment, resolve_experiment_ownership

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

from cydra_web2.differential import DifferentialPlanner

def _base_model():
    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("alice","user",True))
    m.add_identity(Identity("bob","user",True))
    m.add_resource(Resource("r1","profile",None,"123"))
    m.add_endpoint(Endpoint("GET /profiles/{id}","GET","/profiles/{id}",("r1",)))
    return m

def _experiment(m):
    e=DifferentialPlanner().plan_ownership(m)[0]
    from cydra_web2.differential import OwnershipExperiment
    return OwnershipExperiment(e.id,e.hypothesis,e.identity_id,e.endpoint_id,e.path,e.resource_id,"POST")

def _observation(m, identity="alice", status=200, oid="evidence-1"):
    o=Observation(oid,"GET /profiles/{id}",identity,status,"a"*64,20,"req")
    m.add_observation(o)
    return o

def test_experiment_evidence_can_establish_ownership():
    m=_base_model(); e=_experiment(m); o=_observation(m)
    claim=claim_from_experiment(m,e,o,'{"id":"123"}', control_kind='creation')
    assert claim.resource_id=="r1" and claim.identity_id=="alice"

def test_two_hundred_alone_does_not_establish_ownership():
    m=_base_model(); e=_experiment(m); o=_observation(m)
    try:
        claim_from_experiment(m,e,o,'{"id":"999"}')
    except ValueError as exc:
        assert "resource marker" in str(exc)
    else:
        raise AssertionError("2xx alone must not establish ownership")

def test_experiment_resolution_updates_model():
    m=_base_model(); e=_experiment(m); o=_observation(m)
    resolve_experiment_ownership(m,e,o,'{"id":"123"}', control_kind='creation')
    assert m.resources["r1"].owner_id=="alice"

def test_wrong_identity_cannot_establish_ownership():
    m=_base_model(); e=_experiment(m); o=_observation(m,identity="bob")
    try:
        claim_from_experiment(m,e,o,'{"id":"123"}')
    except ValueError as exc:
        assert "experiment identity" in str(exc)
    else:
        raise AssertionError("ownership evidence must be attributable")

def test_conflicting_owner_fails_closed():
    m=_base_model(); e=_experiment(m); o=_observation(m)
    resolve_experiment_ownership(m,e,o,'{"id":"123"}')
    try:
        resolve_ownership(m,(OwnershipClaim("r1","bob","evidence-1","conflict"),))
    except ValueError as exc:
        assert "conflicting" in str(exc)
    else:
        raise AssertionError("conflicting ownership must fail closed")


def test_read_evidence_is_not_control_provenance():
    m=_base_model(); e=_experiment(m); o=_observation(m)
    try:
        claim_from_experiment(m,e,o,'{"id":"123"}')
    except ValueError as exc:
        assert "exclusive ownership" in str(exc)
    else:
        raise AssertionError("read evidence must not establish exclusive ownership")


def test_ownership_experiment_preserves_endpoint_method():
    m=_base_model()
    e=DifferentialPlanner().plan_ownership(m)[0]
    assert e.method=="GET"
