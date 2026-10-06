from cydra_web2.evidence import response_contains_marker
def test_json_resource_marker_is_detected():
    assert response_contains_marker('{"record":{"id":"r123"}}',"r123")
def test_missing_marker_is_not_evidence():
    assert not response_contains_marker('{"record":{"id":"other"}}',"r123")
