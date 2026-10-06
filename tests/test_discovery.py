from cydra_web2.model import TargetModel
from cydra_web2.discovery import _documents,_ids

def test_json_identifier_observation():
    docs=_documents('{"user":{"id":"u1"},"items":[{"uuid":"r1"}]}')
    values={(k,v) for d in docs for k,v,_ in _ids(d)}
    assert ("id","u1") in values
    assert ("uuid","r1") in values

def test_discovery_does_not_assign_ownership():
    docs=_documents('{"id":"r1"}')
    values=list(_ids(docs[0]))
    assert values[0][1]=="r1"

def test_discovery_associates_observed_resource_with_endpoint():
    from types import SimpleNamespace
    from cydra_web2.discovery import discover
    from cydra_web2.model import Identity

    class Adapter:
        def request(self, *, method, path, identity_id=None):
            return SimpleNamespace(
                identity_id=identity_id, status_code=200,
                body='{"id":"r1"}', body_sha256="a"*64,
            )

    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("alice","owner",True))
    result=discover(Adapter(),m,seeds=("/",),identity_id="alice")
    endpoint=m.endpoints["GET /"]
    assert endpoint.resource_ids == (result.resource_ids[0],)
    assert m.observations[0].identity_id=="alice"
