from cydra_web2.adapter import TargetConfig,HttpAdapter
def test_target_config_requires_absolute_url():
    try: TargetConfig.from_url("/relative")
    except ValueError: pass
    else: raise AssertionError("relative target must be rejected")
def test_adapter_starts_without_credentials():
    assert HttpAdapter(TargetConfig.from_url("https://authorized.example")).identities=={}
