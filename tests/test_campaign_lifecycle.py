from types import SimpleNamespace
from cydra_web2.campaign_runner import CampaignRunner
from cydra_web2.engine import ResearchEngine
from cydra_web2.model import TargetModel,Identity,Resource,Endpoint
class A:
 def request(self,*,method,path,identity_id=None,**kwargs):
  return SimpleNamespace(url=path,final_url=path,method=method,identity_id=identity_id,status_code=200,headers={},body='{"id":"record-1","secret":"owned"}',body_sha256="same")
def test_campaign_records_causal_lifecycle():
 m=TargetModel("https://authorized.example"); m.add_identity(Identity("alice","owner",True)); m.add_identity(Identity("bob","other",True)); m.add_resource(Resource("r","record","alice","record-1")); m.add_endpoint(Endpoint("e","GET","/records/{id}",("r",),"read"))
 o=CampaignRunner(ResearchEngine(m,A())).run(ResearchEngine(m,A()).plan_authorization_frontier())
 assert o.stopped
 assert o.states[-1].stage.value=="causal"
