from scripts.browser_public_origin_discovery import is_api_path, safe_url_parts, summarize_api_origins


def test_safe_url_parts_drops_query_and_fragment():
    assert safe_url_parts("https://api.example.test/v1/items?token=secret#frag") == ("https://api.example.test", "/v1/items")
    assert safe_url_parts("javascript:alert(1)") is None


def test_api_path_match_is_narrow_and_case_insensitive():
    assert is_api_path("/v1/items")
    assert is_api_path("/graphql")
    assert is_api_path("/API/users")
    assert not is_api_path("/images/v1/items.png")
    assert not is_api_path("/version2/about")


def test_origin_summary_only_marks_external_api_origins_as_candidates():
    rows = [
        {"origin": "https://app.example.test", "hostname": "app.example.test", "path": "/v1/items", "method": "GET", "resource_type": "fetch", "first_party": True, "count": 1},
        {"origin": "https://api.example.test", "hostname": "api.example.test", "path": "/v1/items", "method": "GET", "resource_type": "fetch", "first_party": False, "count": 2},
        {"origin": "https://analytics.example", "hostname": "analytics.example", "path": "/event", "method": "POST", "resource_type": "fetch", "first_party": False, "count": 1},
    ]
    result = summarize_api_origins(rows, "app.example.test")
    assert result["candidate_service_origins"] == ["https://api.example.test"]
    assert len(result["same_origin_api_requests"]) == 1
    assert len(result["api_requests"]) == 2