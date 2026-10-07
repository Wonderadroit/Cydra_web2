from cydra_web2.model import TargetModel
from cydra_web2.discovery import _documents,_ids

def test_json_identifier_observation():
    docs=_documents('{"user":{"id":"u1"},"items":[{"uuid":"r1"}]}')
    values={(k,v) for d in docs for k,v,_ in _ids(d)}
    assert ("id","u1") in values
    assert ("uuid","r1") in values

def test_discovery_does_not_assign_ownership():
    docs=_documents('{"id":"r1"}')
    values=list(_ids(docs[0]))
    assert values[0][1]=="r1"

def test_discovery_associates_observed_resource_with_endpoint():
    from types import SimpleNamespace
    from cydra_web2.discovery import discover
    from cydra_web2.model import Identity

    calls = []
    class Adapter:
        def request(self, *, method, path, identity_id=None):
            calls.append(path)
            return SimpleNamespace(
                identity_id=identity_id, status_code=200,
                body='{"id":"r1"}', body_sha256="a"*64,
            )

    m=TargetModel("https://authorized.example")
    m.add_identity(Identity("alice","owner",True))
    result=discover(Adapter(),m,seeds=("/",),identity_id="alice")
    endpoint=m.endpoints["GET /"]
    assert endpoint.resource_ids == (result.resource_ids[0],)
    assert m.observations[0].identity_id=="alice"


def test_api_paths_are_extracted_from_public_javascript():
    from cydra_web2.discovery import _api_paths
    body='const a="/api/users/123"; const b="/graphql"; const c="/v2/inventory";'
    assert _api_paths(body) == {"/api/users/123", "/graphql", "/v2/inventory"}

def test_js_reconstruction_resolves_fetch_axios_and_xhr():
    from cydra_web2.discovery import _analyze_bundle
    a = _analyze_bundle(
        "/app.js",
        'const API_BASE = "/api"; const users = API_BASE + "/users"; fetch(users); axios.post(API_BASE + "/session"); const xhr = new XMLHttpRequest(); xhr.open("GET", API_BASE + "/profile");',
        "https://authorized.example",
    )
    assert ("GET", "/api/users") in a.endpoints
    assert ("POST", "/api/session") in a.endpoints
    assert ("GET", "/api/profile") in a.endpoints

def test_js_reconstruction_records_external_origin_without_executing_it():
    from cydra_web2.discovery import _analyze_bundle
    a = _analyze_bundle("/app.js", 'fetch("https://api.example.net/v1/profile");', "https://authorized.example")
    assert ("https://api.example.net/v1/profile", "https://api.example.net") in a.request_origins
    assert all(path != "https://api.example.net/v1/profile" for _, path in a.endpoints)

def test_discovery_analyzes_js_and_models_static_methods():
    from types import SimpleNamespace
    from cydra_web2.discovery import discover
    class Adapter:
        def request(self, *, method, path, identity_id=None):
            return SimpleNamespace(
                identity_id=identity_id, status_code=200,
                body='fetch("/v1/items"); axios.post("/v1/session");',
                body_sha256="a"*64, headers={"Content-Type":"application/javascript"},
            )
    m=TargetModel("https://authorized.example")
    result=discover(Adapter(),m,seeds=("/app.js",),max_paths=1,max_js_bundles=1)
    assert ("GET","/v1/items") in {(e.method,e.path) for e in m.endpoints.values()}
    assert ("POST","/v1/session") in {(e.method,e.path) for e in m.endpoints.values()}
    assert result.bundle_analyses[0].request_origins[0][1] == "https://authorized.example"

def test_discovery_prioritizes_recovered_api_routes_over_static_assets():
    from types import SimpleNamespace
    from cydra_web2.discovery import discover
    class Adapter:
        def request(self, *, method, path, identity_id=None):
            body = 'fetch("/v1/me");' if path == "/app.js" else '{"id":"user-1"}' if path == "/v1/me" else '<script src="/static.js"></script>'
            ctype = "application/javascript" if path == "/app.js" else "application/json" if path == "/v1/me" else "text/html"
            return SimpleNamespace(identity_id=identity_id, status_code=200, body=body, headers={"Content-Type": ctype})
    m = TargetModel("https://authorized.example")
    result = discover(Adapter(), m, seeds=("/app.js",), max_paths=3, max_js_bundles=1)
    assert calls[:2] == ["/app.js", "/v1/me"]
    assert result.resource_ids
