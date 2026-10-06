import pytest
from cydra_web2.session import SessionRegistry,IdentityBinding
from cydra_web2.experiment_state import ExperimentState,ExperimentStage,advance
from cydra_web2.scope import check_scope

def test_identity_bindings_are_explicit():
 r=SessionRegistry((IdentityBinding("alice",{"Authorization":"secret"}),))
 assert r.get("alice").headers["Authorization"]=="secret"
 with pytest.raises(KeyError): r.get("bob")

def test_experiment_lifecycle_is_monotonic():
 s=ExperimentState("x",ExperimentStage.PLANNED,"created")
 s=advance(s,ExperimentStage.VALIDATED,"scope checked")
 with pytest.raises(ValueError): advance(s,ExperimentStage.PLANNED,"backward")

def test_scope_fails_closed():
 assert check_scope("https://target.example/a",{"target.example"}).allowed
 assert not check_scope("https://other.example/a",{"target.example"}).allowed
 assert not check_scope("http://target.example/a",{"target.example"}).allowed
