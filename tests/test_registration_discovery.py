from pathlib import Path
import importlib.util

MODULE = Path(__file__).parents[1] / "scripts" / "registration_discovery.py"
spec = importlib.util.spec_from_file_location("registration_discovery", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_registration_discovery_requires_https(tmp_path):
    try:
        module.discover("http://example.com", tmp_path / "report.json")
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("HTTP targets must be rejected")


def test_registration_discovery_does_not_submit_forms():
    source = MODULE.read_text()
    assert ".click(" not in source
    assert ".fill(" not in source
    assert ".submit(" not in source
    assert "No forms submitted" in source
