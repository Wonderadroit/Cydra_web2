import json
from cydra_web2.hypothesis import HypothesisPlanner
from cydra_web2.normalization import normalize_body,semantic_fingerprint
from cydra_web2.matrix import AuthorizationMatrix
from cydra_web2.workflow_graph import WorkflowGraph,Transition
from cydra_web2.provenance import EvidenceLedger
from cydra_web2.schema import parse_openapi,extract_frontend_routes
from cydra_web2.safety import ScopeGuard,ScopePolicy
from cydra_web2.model import TargetModel,Identity,Resource,Endpoint

def model():
    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("owner","owner",True)); m.add_identity(Identity("staff","staff",True)); m.add_identity(Identity("other","other",True))
    m.add_resource(Resource("r1","invoice","owner","INV-7")); m.add_endpoint(Endpoint("read","GET","/invoices/{id}",("r1",),"read")); return m

def test_hypothesis_frontier_and_matrix():
    m=model(); f=HypothesisPlanner().build(m); assert f.next() and len(AuthorizationMatrix().build(m))==2
def test_normalization_removes_volatile_fields():
    a=normalize_body('{"data":{"id":7},"timestamp":1}')
    b=normalize_body('{"data":{"id":7},"timestamp":999}')
    assert a==b and semantic_fingerprint(200,a)==semantic_fingerprint(200,b)
def test_workflow_paths_and_identity_mismatch():
    g=WorkflowGraph({"verified"}); g.add_transition(Transition("a","read",("verified",),("seen",),"owner")); g.add_transition(Transition("b","read",("verified",),("seen",),"other"))
    assert g.reachable() and g.find_identity_mismatches()
def test_provenance_lineage():
    l=EvidenceLedger(); a=l.record("e","observation",(),{"x":1},{"status":200}); b=l.record("e","finding",(a.id,),{"x":2},{"impact":"read"})
    assert l.lineage(b.id)[-1].id==a.id
def test_schema_and_frontend():
    doc=json.dumps({"paths":{"/users/{id}":{"get":{"operationId":"getUser","parameters":[{"name":"id"}]}}}})
    assert parse_openapi(doc)[0].operation_id=="getUser"
    assert "/api/users" in extract_frontend_routes('fetch("/api/users")')
def test_scope_guard():
    g=ScopeGuard(ScopePolicy(frozenset({"authorized.example"}),max_requests=1)); assert g.check("https://authorized.example/a")
    try: g.check("https://evil.example")
    except ValueError: pass
    else: raise AssertionError
