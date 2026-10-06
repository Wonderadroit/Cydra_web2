import pytest
from cydra_web2.model import Identity,Resource,Endpoint,Observation,TargetModel
from cydra_web2.workflow_graph import Transition
from cydra_web2.control import establish_control

def base():
    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("alice","owner",True))
    m.add_resource(Resource("r1","record",None,"r1"))
    m.add_endpoint(Endpoint("POST /records","POST","/records",("r1",)))
    o=Observation("o1","POST /records","alice",201,"hash",4,"request")
    m.add_observation(o)
    t=Transition("create-r1","create record",produces=("r1",),identity_id="alice",method="POST",path="/records")
    return m,t,o

def test_write_control_requires_causal_transition_and_marker():
    m,t,o=base()
    p=establish_control(m,t,o,"r1",'{"id":"r1"}')
    assert p.identity_id=="alice"
    assert p.resource_id=="r1"
    assert p.control_kind=="creation"

def test_read_transition_cannot_establish_control():
    m,t,o=base()
    read=Transition("read-r1","read record",produces=("r1",),identity_id="alice",method="GET",path="/records/r1")
    with pytest.raises(ValueError,match="write-capable"):
        establish_control(m,read,o,"r1",'{"id":"r1"}')

def test_wrong_producer_cannot_establish_control():
    m,t,o=base()
    other=Transition("other","other",produces=("different",),identity_id="alice",method="POST",path="/other")
    with pytest.raises(ValueError,match="causally"):
        establish_control(m,other,o,"r1",'{"id":"r1"}')
