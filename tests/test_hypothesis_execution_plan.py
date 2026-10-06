from cydra_web2.engine import ResearchEngine
from cydra_web2.model import TargetModel,Identity,Resource,Endpoint
from cydra_web2.adapter import IdentitySession,TargetConfig
from cydra_web2.dogfood import DogfoodConfig,DogfoodRunner

def test_hypotheses_are_explicitly_connected_to_experiments():
    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("alice","owner",True)); m.add_identity(Identity("bob","other",True))
    m.add_resource(Resource("r","record","alice","record-1"))
    m.add_endpoint(Endpoint("e","GET","/records/{id}",("r",),"read"))
    e=ResearchEngine(m,object())
    planned=e.plan_research()
    assert len(planned)==1
    assert planned[0].hypothesis.resource_ids==("r",)
    assert planned[0].experiment.resource_id=="r"
