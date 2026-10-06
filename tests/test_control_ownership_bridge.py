from cydra_web2.model import Identity,Resource,Endpoint,Observation,TargetModel
from cydra_web2.workflow_graph import Transition
from cydra_web2.control import establish_control,apply_control_ownership

def test_control_provenance_updates_model_owner():
    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("alice","owner",True))
    m.add_resource(Resource("r1","record",None,"r1"))
    m.add_endpoint(Endpoint("POST /records","POST","/records",("r1",)))
    o=Observation("o1","POST /records","alice",201,"hash",4,"request")
    m.add_observation(o)
    t=Transition("create-r1","create",produces=("r1",),identity_id="alice",method="POST",path="/records")
    p=establish_control(m,t,o,"r1",'{"id":"r1"}')
    apply_control_ownership(m,p)
    assert m.resources["r1"].owner_id=="alice"
    assert m.resources["r1"].source_observation=="o1"
