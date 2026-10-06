import pytest
from cydra_web2.impact import ImpactClass,assess
from cydra_web2.report import build_finding
def test_read_impact_requires_marker():
    x=assess(status_code=200,resource_marker_found=True,method="GET")
    assert x.classification is ImpactClass.READ
def test_finding_requires_impact_and_evidence():
    with pytest.raises(ValueError): build_finding("x","/x","bob","r",assess(status_code=403,resource_marker_found=False,method="GET"),(),())
