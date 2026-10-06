import pytest
from cydra_web2.review import HumanReview,finalize_finding
from cydra_web2.boundary import BoundaryAssessment

def assessment():
    return BoundaryAssessment(True,True,True,("evidence-1","evidence-2"),"reportable boundary violation")

def test_finalization_requires_human_acceptance():
    with pytest.raises(PermissionError):
        finalize_finding(assessment=assessment(),endpoint="GET /records/{id}",identity="bob",resource="record-1",method="GET",status_code=200,resource_marker_found=True,reproduction=("authorized test only",),review=HumanReview(False,"not reviewed"))

def test_accepted_review_finalizes_reportable_finding():
    f=finalize_finding(assessment=assessment(),endpoint="GET /records/{id}",identity="bob",resource="record-1",method="GET",status_code=200,resource_marker_found=True,reproduction=("authorized test only",),review=HumanReview(True,"validated"))
    assert f.impact.classification.value=="read"
    assert f.evidence_ids==("evidence-1","evidence-2")
