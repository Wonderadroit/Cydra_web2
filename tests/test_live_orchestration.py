from cydra_web2.model import TargetModel,Identity,Resource,Endpoint
from cydra_web2.campaign import CampaignBuilder
from cydra_web2.request_matrix import RequestVariantPlanner
from cydra_web2.sequence import SequencePlanner,SequenceAction
from cydra_web2.verification import verify_replay
from types import SimpleNamespace
def model():
 m=TargetModel("https://authorized.example"); m.add_identity(Identity("a","owner",True)); m.add_identity(Identity("b","other",True)); m.add_resource(Resource("r","doc","a","D1")); m.add_endpoint(Endpoint("e","GET","/docs/{id}",("r",),"read")); return m
def test_campaign_is_model_driven():
 c=CampaignBuilder().build(model()); assert c.next() and c.next().hypothesis_id.startswith("auth:")
def test_request_variants_are_bounded():
 p=RequestVariantPlanner().build("GET","/docs/D1","D1"); assert len(p)==3
def test_sequence_cross_identity():
 a=SequenceAction("a","GET","/docs/D1","read"); p=SequencePlanner().cross_identity((a,),"a","b"); assert p[0].actions[0].identity_id=="b"
def test_verification_requires_stable_impact():
 e=SimpleNamespace(finding_candidate=True,data={"resource_marker_found":True})
 resp=SimpleNamespace(status_code=200,method="GET")
 r=SimpleNamespace(evidence=e,comparison_response=resp)
 v=verify_replay((r,r)); assert v.ready
