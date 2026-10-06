from cydra_web2.checkpoint import CampaignCheckpoint
import pytest

def test_checkpoint_round_trip_and_remaining():
    c=CampaignCheckpoint("https://authorized.example",("a","b","c"),("a",),("a",))
    assert CampaignCheckpoint.loads(c.dumps()).remaining()==("b","c")

def test_checkpoint_rejects_out_of_plan_completion():
    with pytest.raises(ValueError):
        CampaignCheckpoint("https://authorized.example",("a",),("b",))

def test_checkpoint_rejects_candidate_not_completed():
    with pytest.raises(ValueError):
        CampaignCheckpoint("https://authorized.example",("a",),(),("a",))
