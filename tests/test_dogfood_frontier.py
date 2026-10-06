from types import SimpleNamespace
from cydra_web2.dogfood import DogfoodConfig, DogfoodRunner
from cydra_web2.adapter import TargetConfig, IdentitySession
from cydra_web2.model import Identity, Resource, Endpoint, TargetModel

def test_dogfood_enters_full_frontier(monkeypatch):
    model=TargetModel("https://authorized.example")
    model.add_identity(Identity("alice","owner",True))
    model.add_resource(Resource("r1","record",None,"r1"))
    model.add_endpoint(Endpoint("GET /records/{id}","GET","/records/{id}",("r1",)))
    config=DogfoodConfig(TargetConfig.from_url("https://authorized.example"),(IdentitySession("alice",{"Authorization":"Bearer test"}),),1)
    runner=DogfoodRunner(model,config)
    class FakeRunner:
        def run_research(self):
            return "frontier"
    runner.runner=FakeRunner()
    assert runner.run()=="frontier"
