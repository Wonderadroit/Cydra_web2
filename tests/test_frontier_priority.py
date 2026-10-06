from cydra_web2.hypothesis import Hypothesis,HypothesisKind,ResearchFrontier

def test_frontier_priority():
    f=ResearchFrontier()
    f.add(Hypothesis("ownership:r",HypothesisKind.OWNERSHIP,"x",resource_ids=("r",)))
    f.add(Hypothesis("auth:r:e:a:b",HypothesisKind.AUTHORIZATION,"x",identity_ids=("a","b"),resource_ids=("r",),endpoint_ids=("e",)))
    assert [x.id for x in f.prioritized()]==["auth:r:e:a:b","ownership:r"]
