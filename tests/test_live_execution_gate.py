import pytest
from cydra_web2.adapter import HttpAdapter,TargetConfig,IdentitySession

def test_live_adapter_requires_https():
    adapter=HttpAdapter(TargetConfig.from_url("http://target.example"),(IdentitySession("alice",{"Authorization":"token"}),))
    with pytest.raises(PermissionError,match="scheme outside allowlist"):
        adapter.request(method="GET",path="/records",identity_id="alice")

def test_live_adapter_rejects_unknown_identity():
    adapter=HttpAdapter(TargetConfig.from_url("https://target.example"),(IdentitySession("alice",{}),))
    with pytest.raises(KeyError):
        adapter.request(method="GET",path="/records",identity_id="bob")

def test_live_adapter_rejects_anonymous_when_identities_exist():
    adapter=HttpAdapter(TargetConfig.from_url("https://target.example"),(IdentitySession("alice",{}),))
    with pytest.raises(PermissionError,match="anonymous"):
        adapter.request(method="GET",path="/records")

def test_target_config_allowlist_is_explicit():
    adapter=HttpAdapter(TargetConfig.from_url("https://target.example"),(IdentitySession("alice",{}),))
    with pytest.raises(PermissionError,match="host outside allowlist"):
        adapter.request(method="GET",path="https://other.example/records",identity_id="alice")
