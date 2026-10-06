from cydra_web2.model import Endpoint,Identity,Resource,TargetModel
from cydra_web2.differential import DifferentialPlanner
def build_model(identifier="123"):
    m=TargetModel("https://authorized.example"); m.add_identity(Identity("alice","owner",True)); m.add_identity(Identity("bob","comparison",True)); m.add_resource(Resource("record:1","record","alice",identifier)); m.add_endpoint(Endpoint("get-record","GET","/records/{id}",("record:1",),"read")); return m
def test_explicit_cross_identity_plan():
    p=DifferentialPlanner().plan_authorization(build_model()); assert len(p)==1 and p[0].owner.identity_id=="alice" and p[0].comparison.identity_id=="bob" and p[0].owner.path=="/records/123"
def test_missing_identifier_is_not_fabricated():
    assert DifferentialPlanner().plan_authorization(build_model(None))==()
def test_unknown_owner_rejected():
    m=TargetModel("https://authorized.example"); m.add_identity(Identity("bob","comparison"))
    try: m.add_resource(Resource("r","record","alice","1"))
    except ValueError: pass
    else: raise AssertionError("unknown owner should be rejected")
