from types import SimpleNamespace
from cydra_web2.engine import ResearchEngine
from cydra_web2.model import TargetModel,Identity,Resource,Endpoint
from cydra_web2.campaign_runner import CampaignRunner

class FakeAdapter:
    def __init__(self): self.calls=[]
    def request(self,*,method,path,identity_id=None,**kwargs):
        self.calls.append((method,path,identity_id))
        owner=identity_id=="alice"
        body='{"id":"record-1","secret":"owned"}' if owner else '{"id":"record-1","secret":"owned"}'
        return SimpleNamespace(url=path,final_url=path,method=method,identity_id=identity_id,status_code=200,headers={},body=body,body_sha256="same")

def test_authorization_candidate_replay_becomes_reportable():
    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("alice","owner",True)); m.add_identity(Identity("bob","other",True))
    m.add_resource(Resource("r","record","alice","record-1"))
    m.add_endpoint(Endpoint("e","GET","/records/{id}",( "r",),"read"))
    engine=ResearchEngine(m,FakeAdapter())
    plan=engine.plan_authorization_frontier()
    outcome=CampaignRunner(engine).run(plan)
    assert outcome.stopped and outcome.assessment and outcome.assessment.reportable
    assert outcome.executed==1 and outcome.candidates==1
