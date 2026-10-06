from cydra_web2.hypothesis import HypothesisKind, HypothesisPlanner
from cydra_web2.matrix import AuthorizationMatrix
from cydra_web2.model import Resource, TargetModel


def test_unowned_resource_creates_non_executable_ownership_hypothesis():
    model = TargetModel("https://authorized.example")
    model.add_resource(Resource("r1", "user", None, "123"))
    frontier = HypothesisPlanner().build(model)
    h = frontier.hypotheses[0]
    assert h.kind is HypothesisKind.OWNERSHIP
    assert h.resource_ids == ("r1",)
    assert model.authorization_candidates() == ()


def test_matrix_exposes_unresolved_ownership_without_guessing():
    model = TargetModel("https://authorized.example")
    model.add_resource(Resource("r1", "user", None, "123"))
    assert [r.id for r in AuthorizationMatrix().unresolved_resources(model)] == ["r1"]
