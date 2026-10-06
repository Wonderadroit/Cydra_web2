from types import SimpleNamespace
from cydra_web2.model import TargetModel,Identity,Resource,Endpoint,Observation
from cydra_web2.workflow_graph import Transition
from cydra_web2.control import establish_control,apply_control_ownership
from cydra_web2.engine import ResearchEngine
from cydra_web2.campaign_runner import CampaignRunner

class Target:
    def request(self,*,method,path,identity_id=None,**kwargs):
        return SimpleNamespace(url=path,final_url=path,method=method,identity_id=identity_id,status_code=200,headers={},body='{"id":"record-1","owner":"alice","secret":"authorized"}',body_sha256="same")

def test_control_then_differential_then_replay_is_reportable():
    m=TargetModel("https://controlled.authorized")
    m.add_identity(Identity("alice","owner",True)); m.add_identity(Identity("bob","comparison",True))
    m.add_resource(Resource("record-1","record",None,"record-1"))
    m.add_endpoint(Endpoint("create","POST","/records",("record-1",),"create"))
    m.add_endpoint(Endpoint("read","GET","/records/{id}",("record-1",),"read"))
    obs=Observation("create-observation","create","alice",201,"created",30,"create-request")
    m.add_observation(obs)
    transition=Transition("create-record","create record",produces=("record-1",),identity_id="alice",method="POST",path="/records")
    provenance=establish_control(m,transition,obs,"record-1",'{"id":"record-1"}')
    apply_control_ownership(m,provenance)
    engine=ResearchEngine(m,Target())
    outcome=CampaignRunner(engine).run(engine.plan_authorization_frontier())
    assert outcome.stopped and outcome.assessment is not None
    assert outcome.assessment.reportable
    assert len(outcome.assessment.evidence_ids)==2
