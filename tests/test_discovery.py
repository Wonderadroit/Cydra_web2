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
    calls = []
    class Adapter:
        def request(self, *, method, path, identity_id=None):
            calls.append(path)
            body = 'fetch("/v1/me");' if path == "/app.js" else '{"id":"user-1"}' if path == "/v1/me" else '<script src="/static.js"></script>'
            ctype = "application/javascript" if path == "/app.js" else "application/json" if path == "/v1/me" else "text/html"
            return SimpleNamespace(identity_id=identity_id, status_code=200, body=body, headers={"Content-Type": ctype})
    m = TargetModel("https://authorized.example")
    result = discover(Adapter(), m, seeds=("/app.js",), max_paths=3, max_js_bundles=1)
    assert calls[:2] == ["/app.js", "/v1/me"]
    assert result.resource_ids


def test_bundle_origin_provenance_excludes_arbitrary_absolute_links():
    from cydra_web2.discovery import _analyze_bundle
    body = (
        'const docs = "https://example.com/guide"; '
        'const social = "https://discord.gg/aurory"; '
        'const API_BASE_URL = "https://api.authorized.example";'
    )
    result = _analyze_bundle("/app.js", body, "https://app.authorized.example")
    assert result.service_origins == ("https://api.authorized.example",)
    assert result.request_origins == ()
    assert ("GET", "/api") not in result.endpoints


def test_nextjs_rsc_hydration_extracts_candidates_with_field_path_provenance():
    from cydra_web2.discovery import _documents, _ids

    body = r'''<html><script>self.__next_f.push([1,"1:{\"props\":{\"pageProps\":{\"items\":[{\"id\":\"item-42\"}]}}}"]);</script></html>'''
    docs = _documents(body)
    values = list(item for doc in docs for item in _ids(doc))
    assert ("id", "item-42", "props.pageProps.items[0].id") in values


def test_discovery_retains_source_field_path_without_claiming_ownership():
    from types import SimpleNamespace
    from cydra_web2.discovery import discover
    from cydra_web2.model import TargetModel

    class Adapter:
        def request(self, *, method, path, identity_id=None):
            return SimpleNamespace(
                identity_id=identity_id, status_code=200,
                body=r'''<script>self.__next_f.push([1,"1:{\"props\":{\"items\":[{\"uuid\":\"public-item-9\"}]}}"]);</script>''',
                headers={"Content-Type": "text/html"},
            )

    model = TargetModel("https://authorized.example")
    result = discover(Adapter(), model, seeds=("/",), max_paths=1)
    resource = model.resources[result.resource_ids[0]]
    assert resource.identifier == "public-item-9"
    assert resource.source_field_path == "[0].props.items[0].uuid"
    assert resource.source_observation == model.observations[0].id
    assert resource.owner_id is None


def test_nextjs_flight_chunk_extracts_multiple_records_and_keeps_provenance():
    from cydra_web2.discovery import _documents, _ids

    body = r'''<script>self.__next_f.push([1,"1:{\"items\":[{\"uuid\":\"flight-item-9\"}]}\n2:{\"profile\":{\"user_id\":\"user-7\"}}"]);</script>'''
    docs = _documents(body)
    values = {(key, value, path) for doc in docs for key, value, path in _ids(doc)}
    assert ("uuid", "flight-item-9", "items[0].uuid") in values
    assert ("user_id", "user-7", "profile.user_id") in values


def test_nextjs_flight_deduplicates_repeated_hydration_payloads():
    from cydra_web2.discovery import _documents

    payload = r'''<script>self.__next_f.push([1,"1:{\"item\":{\"id\":\"same-item\"}}"]);self.__next_f.push([1,"1:{\"item\":{\"id\":\"same-item\"}}"]);</script>'''
    docs = _documents(payload)
    assert sum(1 for doc in docs if isinstance(doc, dict) and doc.get("item", {}).get("id") == "same-item") == 1


def test_resource_candidate_extraction_excludes_ui_telemetry_and_public_media_ids():
    from cydra_web2.discovery import _documents, _ids

    docs = _documents('{"topNews":[{"id":"article-1","thumbnail":{"id":"image-1"},"banner":{"id":"banner-1"}}],"navigation":{"id":"menu-1"},"gaId":"G-123","items":[{"uuid":"item-9"}]}')
    values = {(key, value, path) for doc in docs for key, value, path in _ids(doc)}
    assert ("uuid", "item-9", "items[0].uuid") in values
    assert not any(value in {"article-1", "image-1", "banner-1", "menu-1", "G-123"} for _, value, _ in values)
