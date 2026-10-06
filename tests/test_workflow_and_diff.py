from cydra_web2.differential import DifferentialAction
from cydra_web2.workflow import StateTransition,WorkflowPlanner
from cydra_web2.request_diff import RequestDifferentialPlanner
def test_workflow_cross_identity_plan():
    t=StateTransition("transfer",DifferentialAction("alice","POST","/transfer"),("owned",),("transferred",))
    p=WorkflowPlanner().plan_cross_identity((t,),"alice","bob")
    assert p[0].attack.action.identity_id=="bob"
    assert p[0].attack.requires==("owned",)
def test_identifier_substitution_is_explicit():
    x=RequestDifferentialPlanner().plan_identifier_substitution("/records/a1","a1","b2")
    assert x.variant.path=="/records/b2"
def test_no_identifier_means_no_mutation():
    assert RequestDifferentialPlanner().plan_identifier_substitution("/records/a1","","b2") is None
