from cydra_web2.state import compare_state,fingerprint

def test_state_fingerprint_is_deterministic():
    assert fingerprint({"b":2,"a":1})==fingerprint({"a":1,"b":2})

def test_state_change_is_detected():
    x=compare_state({"balance":1},{"balance":2})
    assert x.changed and x.rationale=="state fingerprint changed"
