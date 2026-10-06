from types import SimpleNamespace
from cydra_web2.engine import ResearchEngine
from cydra_web2.model import TargetModel,Identity,Resource,Endpoint
from cydra_web2.campaign_runner import CampaignRunner

class ControlledAuthorizedTarget:
    def request(self, *, method, path, identity_id=None, **kwargs):
        if identity_id == "alice":
            body='{"id":"record-1","owner":"alice","secret":"authorized"}'
        else:
            body='{"id":"record-1","owner":"alice","secret":"authorized"}'
        return SimpleNamespace(url=path,final_url=path,method=method,identity_id=identity_id,status_code=200,headers={},body=body,body_sha256="same")

def test_controlled_target_produces_replay_backed_boundary_assessment():
    model=TargetModel("https://controlled.authorized")
    model.add_identity(Identity("alice","owner",True))
    model.add_identity(Identity("bob","comparison",True))
    model.add_resource(Resource("record-1","record","alice","record-1"))
    model.add_endpoint(Endpoint("records","GET","/records/{id}",("record-1",),"read"))
    engine=ResearchEngine(model,ControlledAuthorizedTarget())
    outcome=CampaignRunner(engine).run(engine.plan_authorization_frontier())
    assert outcome.stopped
    assert outcome.assessment is not None
    assert outcome.assessment.reportable
    assert len(outcome.assessment.evidence_ids)==2
