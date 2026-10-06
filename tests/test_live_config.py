import pytest
from cydra_web2.live_config import LiveDogfoodConfig

def test_live_config_requires_target(monkeypatch):
    monkeypatch.delenv("CYDRA_TARGET_URL",raising=False)
    monkeypatch.setenv("CYDRA_IDENTITIES","alice=secret")
    with pytest.raises(ValueError,match="CYDRA_TARGET_URL"):
        LiveDogfoodConfig.from_environment()

def test_live_config_parses_identities_without_logging_credentials(monkeypatch):
    monkeypatch.setenv("CYDRA_TARGET_URL","https://authorized.example")
    monkeypatch.setenv("CYDRA_IDENTITIES","alice=secret-token;bob=other-token")
    cfg=LiveDogfoodConfig.from_environment()
    assert [x.identity_id for x in cfg.identities]==["alice","bob"]
    assert cfg.target.base_url=="https://authorized.example"


def test_live_config_parses_generic_shared_headers(monkeypatch):
    monkeypatch.setenv("CYDRA_TARGET_URL","https://authorized.example")
    monkeypatch.setenv("CYDRA_SHARED_HEADERS",'{"X-Bug-Bounty":"Bugcrowd-cyberwonder","Accept":"application/json"}')
    monkeypatch.setenv("CYDRA_IDENTITIES","alice=secret-token")
    cfg=LiveDogfoodConfig.from_environment()
    assert dict(cfg.identities[0].headers)=={
        "X-Bug-Bounty":"Bugcrowd-cyberwonder",
        "Accept":"application/json",
        "Authorization":"secret-token",
    }

def test_live_config_rejects_non_object_shared_headers(monkeypatch):
    monkeypatch.setenv("CYDRA_TARGET_URL","https://authorized.example")
    monkeypatch.setenv("CYDRA_SHARED_HEADERS",'["not-an-object"]')
    monkeypatch.setenv("CYDRA_IDENTITIES","alice=secret-token")
    with pytest.raises(ValueError,match="JSON object"):
        LiveDogfoodConfig.from_environment()
