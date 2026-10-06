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
