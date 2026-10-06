from cydra_web2.invariants import authorization_invariants,InvariantKind
from cydra_web2.experiment_queue import ExperimentQueue
from cydra_web2.cache_diff import CacheObservation,compare_cache
from cydra_web2.integration import CampaignPlanner
from cydra_web2.model import TargetModel,Identity,Resource,Endpoint
from cydra_web2.hypothesis import Hypothesis,HypothesisKind
def m():
    x=TargetModel("https://authorized.example"); x.add_identity(Identity("a","owner",True)); x.add_identity(Identity("b","other",True)); x.add_resource(Resource("r","doc","a","D1")); x.add_endpoint(Endpoint("e","GET","/d/{id}",("r",),"read")); return x
def test_invariant_and_campaign():
    x=m(); assert authorization_invariants(x)[0].kind==InvariantKind.OWNERSHIP; p=CampaignPlanner().plan(x); assert p.hypotheses==1 and p.authorization_cells==1
def test_queue_priority():
    q=ExperimentQueue(); q.push(Hypothesis("h",HypothesisKind.AUTHORIZATION,"x"),3,"high"); assert q.pop().hypothesis.id=="h"
def test_cache_boundary():
    a=CacheObservation("a","HIT","1","same"); b=CacheObservation("b","HIT","1","same"); assert compare_cache(a,b).suspicious