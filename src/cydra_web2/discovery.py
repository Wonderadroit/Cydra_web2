from __future__ import annotations
from dataclasses import dataclass
import hashlib, json, re
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse
from .adapter import HttpAdapter
from .model import Endpoint, Observation, Resource, TargetModel

@dataclass(frozen=True)
class BundleAnalysis:
    path: str
    methods: tuple[str, ...] = ()
    endpoints: tuple[tuple[str, str], ...] = ()
    request_origins: tuple[tuple[str, str], ...] = ()
    service_origins: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()

@dataclass(frozen=True)
class DiscoveryResult:
    model: TargetModel
    paths: tuple[str, ...]
    observations: tuple[Observation, ...]
    resource_ids: tuple[str, ...]
    bundle_analyses: tuple[BundleAnalysis, ...] = ()

class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()
        self.script_sources = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for k, v in attrs:
            if v and k.lower() in {'href', 'src', 'action'}:
                self.links.add(v)
        if tag.lower() == "script" and values.get("src"):
            self.script_sources.add(values["src"])

_ID = re.compile(r'^(?:id|uuid|[A-Za-z][A-Za-z0-9]*(?:_id|_uuid|Id|UUID))$', re.I)
_PATH = re.compile(r'/(?:api|graphql|rpc|v[0-9]+)(?:/[A-Za-z0-9_.$:@%~+\-{}]+)*')
_REQUEST = re.compile(r'''\b(?:(fetch)|(axios|api|client|http|request)\.(get|post|put|patch|delete|head|options))\s*\(\s*([^,\)]+)''', re.I)
_OPEN = re.compile(r'''\.open\s*\(\s*['\"](GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)['\"]\s*,\s*([^,\)]+)''', re.I)
_ASSIGN = re.compile(r'''\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(['\"`])([^'\"`]+)\2''')
_COMBINED = re.compile(r'''\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\s*\+\s*(['\"])([^'\"]+)\3''')
_ORIGIN = re.compile(r'''(?:baseURL|baseUrl|apiBase|apiBaseUrl|API_BASE_URL|API_BASE|apiUrl|apiURL|API_URL|backendUrl|backendURL|BACKEND_URL|serviceUrl|serviceURL|SERVICE_URL|graphqlUrl|graphqlURL|GRAPHQL_URL|endpointUrl|ENDPOINT_URL|apiEndpoint|apiEndpointUrl|apiHost|apiDomain|baseApiUrl|BASE_API_URL|PUBLIC_API_URL|NEXT_PUBLIC_API_URL|VITE_API_URL)\s*[:=]\s*['\"](https?://[^'\"\s]+)''', re.I)
_CSP = re.compile(r'''(?:connect-src|default-src)\s+([^;]+)''', re.I)

def _api_paths(body: str):
    out = set()
    # Do not parse the scheme/hostname portion of absolute URLs as route paths
    # (e.g. the //api in https://api.example.com is not an /api endpoint).
    scan_body = re.sub(r'''https?://[^'\"]+''', '', body, flags=re.I)
    for token in re.findall(r'''['\"]([^'\"]+)['\"]''', scan_body):
        if re.match(r'^/(?:api|graphql|rpc|v[0-9]+)(?:/|$)', token, re.I): out.add(token.split('?',1)[0])
    for m in _PATH.finditer(scan_body): out.add(m.group(0).split('?',1)[0])
    return out

def _documents(body: str):
    """Extract structured documents from JSON responses and known hydration containers.

    Framework stream text is candidate data, never proof of resource ownership.
    """
    docs=[]
    try:
        docs.append(json.loads(body))
    except (TypeError,json.JSONDecodeError):
        pass

    scripts = re.findall(r'<script\b([^>]*)>(.*?)</script\s*>', body, re.I|re.S)
    for attrs, source in scripts:
        if re.search(r'type\s*=\s*["\']application/json["\']', attrs, re.I):
            try:
                docs.append(json.loads(source))
            except (TypeError,json.JSONDecodeError):
                pass
        # Next.js App Router streams serialized RSC chunks in calls such as
        # self.__next_f.push([1,"1:{\"props\":{...}}"]). Decode only the JSON
        # argument, then parse chunks that are themselves JSON documents.
        if "self.__next_f.push" not in source:
            continue
        for match in re.finditer(r'self\.__next_f\.push\(\s*(\[[\s\S]*?\])\s*\)', source, re.S):
            try:
                payload = json.loads(match.group(1))
            except (TypeError,json.JSONDecodeError):
                continue
            if not isinstance(payload, list):
                continue
            for chunk in payload:
                if not isinstance(chunk, str):
                    continue
                # Flight payloads can contain multiple newline-delimited records.
                for record in chunk.splitlines() or [chunk]:
                    _, sep, candidate = record.partition(":")
                    if not sep:
                        continue
                    try:
                        value = json.loads(candidate)
                    except (TypeError,json.JSONDecodeError):
                        # Recover only complete JSON fragments embedded in a larger
                        # Flight record; arbitrary text is never treated as an ID.
                        decoder = json.JSONDecoder()
                        for index, char in enumerate(candidate):
                            if char not in "[{":
                                continue
                            try:
                                fragment, _ = decoder.raw_decode(candidate[index:])
                            except json.JSONDecodeError:
                                continue
                            if isinstance(fragment, (dict, list)):
                                docs.append(fragment)
                    else:
                        if isinstance(value, (dict, list)):
                            docs.append(value)
    # Deduplicate identical hydration documents while preserving first-seen order.
    unique = []
    fingerprints = set()
    for doc in docs:
        try:
            fingerprint = json.dumps(doc, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            unique.append(doc)
            continue
        if fingerprint not in fingerprints:
            fingerprints.add(fingerprint)
            unique.append(doc)
    return unique
def _ids(value, path=''):
    """Extract identifier candidates while excluding obvious UI/static-content IDs.

    The path is retained as provenance. IDs under presentation, telemetry, and
    public editorial-media contexts are not useful ownership candidates, so they
    are excluded before resource modeling rather than generating noisy hypotheses.
    """
    non_resource_contexts = {
        "children", "loading", "thumbnail", "thumbnails", "banner", "banners",
        "navigation", "navigationmenu", "consent", "consentdefault",
        "pageloader", "loader", "gaid", "analytics", "tracking",
        "topnews", "news", "articles", "blogposts", "announcements",
        "pressreleases",
    }
    if isinstance(value, dict):
        for k, v in value.items():
            p = f'{path}.{k}' if path else str(k)
            segments = re.findall(r'[A-Za-z][A-Za-z0-9_-]*', p.lower())
            excluded_context = any(
                segment.replace('-', '') in non_resource_contexts
                for segment in segments
            )
            excluded_key = str(k).lower().replace('_', '').replace('-', '') in {
                "gaid", "analyticsid", "trackingid",
            }
            excluded_ui_value = isinstance(v, str) and v.casefold() in {
                "page-loader", "loader-1", "navigation-menu", "consent-default",
            }
            framework_envelope_hash = (
                str(k).lower() == "id"
                and re.fullmatch(r"\[\d+\]\.id", p) is not None
                and isinstance(v, str)
                and re.fullmatch(r"[0-9a-fA-F]{40,64}", v) is not None
            )
            if (not excluded_context and not excluded_key and not excluded_ui_value
                    and not framework_envelope_hash
                    and _ID.fullmatch(str(k)) and isinstance(v, (str, int))
                    and str(v).strip()):
                yield str(k), str(v), p
            yield from _ids(v, p)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _ids(v, f'{path}[{i}]')

def _resolve(expr, constants):
    expr=expr.strip().strip('()')

    def static_template(value):
        # Resolve only simple identifier interpolations whose values are known
        # static constants. Expressions, unknown names, and nested templates
        # remain unresolved: never guess runtime values.
        def replace(match):
            name = match.group(1)
            return constants.get(name, match.group(0))
        resolved = re.sub(r'\$\{([A-Za-z_$][\\w$]*)\}', replace, value)
        return None if "${" in resolved else resolved

    if len(expr)>=2 and expr[0] in "'\"\x60" and expr[-1]==expr[0]:
        value=expr[1:-1]
        return static_template(value) if expr[0]=="\x60" else value
    parts=re.split(r'\s*\+\s*',expr)
    out=[]
    for part in parts:
        part=part.strip()
        if len(part)>=2 and part[0] in "'\"\x60" and part[-1]==part[0]:
            value=part[1:-1]
            if part[0]=="\x60":
                value=static_template(value)
                if value is None: return None
            out.append(value)
        elif part in constants and "${" not in constants[part]:
            out.append(constants[part])
        else: return None
    return ''.join(out)

def _analyze_bundle(path, body, target):
    constants={m.group(1):m.group(3) for m in _ASSIGN.finditer(body)}
    for m in _COMBINED.finditer(body):
        if m.group(2) in constants: constants[m.group(1)]=constants[m.group(2)]+m.group(4)
    # Service origins require service-specific configuration or CSP evidence.
    # Arbitrary absolute URLs in bundles may be docs, social links, examples, or test fixtures.
    endpoints=set(); origins=set(_ORIGIN.findall(body)); request_origins=set(); methods=set(); unresolved=set()
    for m in _REQUEST.finditer(body):
        method = 'GET' if m.group(1) else m.group(3).upper()
        expr = m.group(4); value = _resolve(expr, constants); methods.add(method)
        if value is None: unresolved.add(expr.strip()); continue
        parsed=urlparse(urljoin(target,value)); origin=f'{parsed.scheme}://{parsed.netloc}'
        request_origins.add((value,origin))
        if parsed.hostname==urlparse(target).hostname and parsed.path.startswith('/') and re.match(r'^/(?:api|graphql|rpc|v[0-9]+)(?:/|$)',parsed.path,re.I): endpoints.add((method,parsed.path.split('?',1)[0]))
    for m in _OPEN.finditer(body):
        method=m.group(1).upper(); value=_resolve(m.group(2),constants); methods.add(method)
        if value is None: unresolved.add(m.group(2).strip()); continue
        parsed=urlparse(urljoin(target,value)); request_origins.add((value,f'{parsed.scheme}://{parsed.netloc}'))
        if parsed.hostname==urlparse(target).hostname and re.match(r'^/(?:api|graphql|rpc|v[0-9]+)(?:/|$)',parsed.path,re.I): endpoints.add((method,parsed.path.split('?',1)[0]))
    # Bare route-shaped strings are candidates, not proof of an HTTP call, method,
    # or service origin. Keep them in _api_paths() for frontier scheduling, but
    # only model endpoints here when a request call or XHR open() establishes them.
    for csp_match in _CSP.finditer(body):
        for token in csp_match.group(1).split():
            parsed=urlparse(token)
            if parsed.scheme in {'http','https'} and parsed.hostname:
                origins.add(f'{parsed.scheme}://{parsed.netloc}')
    return BundleAnalysis(path,tuple(sorted(methods)),tuple(sorted(endpoints)),tuple(sorted(request_origins)),tuple(sorted(origins)),tuple(sorted(unresolved)))

def _resource_documents(response):
    """Parse resource-bearing documents only from successful, data-shaped responses.

    A route returning HTTP 200 is not sufficient: SPA fallback HTML and error
    bodies frequently return 200/404 for arbitrary API-shaped paths. JSON is
    accepted when the media type says JSON or the body is visibly a JSON
    object/array (for simple adapters that omit headers). HTML is accepted only
    when it contains a known Next.js Flight hydration container.
    """
    status = int(getattr(response, "status_code", 0) or 0)
    if not 200 <= status < 300:
        return []
    body = str(getattr(response, "body", "") or "")
    headers = getattr(response, "headers", {}) or {}
    content_type = ""
    for key, value in headers.items():
        if str(key).lower() == "content-type":
            content_type = str(value).split(";", 1)[0].strip().lower()
            break
    stripped = body.lstrip()
    is_json_type = content_type == "application/json" or content_type.endswith("+json")
    is_json_shape = stripped.startswith("{") or stripped.startswith("[")
    if is_json_type or (not content_type and is_json_shape):
        return _documents(body)
    if content_type in {"text/html", "application/xhtml+xml"} and "self.__next_f.push" in body:
        return _documents(body)
    return []


def discover(adapter: HttpAdapter, model: TargetModel, seeds: Iterable[str]=('/',), max_paths: int=50, identity_id: str|None=None, max_js_bundles: int=50)->DiscoveryResult:
    queue=list(dict.fromkeys(seeds)); seen=set(); observations=[]; resource_ids=[]; analyses=[]; analyzed=set()
    while queue and len(seen)<max_paths:
        path=queue.pop(0)
        if path in seen: continue
        seen.add(path); endpoint_id=f'GET {path}'
        if endpoint_id not in model.endpoints: model.add_endpoint(Endpoint(endpoint_id,'GET',path))
        response=adapter.request(method='GET',path=path,identity_id=identity_id)
        fp=hashlib.sha256(response.body.encode()).hexdigest()
        observation_key = hashlib.sha256(f"{response.identity_id or ''}|{endpoint_id}|{fp}".encode()).hexdigest()[:20]
        obs=Observation(f'obs:{observation_key}',endpoint_id,response.identity_id,response.status_code,fp,len(response.body),f'GET:{path}')
        model.add_observation(obs); observations.append(obs)
        ctype=str(getattr(response,'headers',{}).get('Content-Type','')).lower(); is_js='javascript' in ctype or path.lower().endswith(('.js','.mjs'))
        if is_js and path not in analyzed and len(analyzed)<max_js_bundles: analyses.append(_analyze_bundle(path,response.body,model.target)); analyzed.add(path)
        api_candidates = set(_api_paths(response.body))
        parser = _Links()
        parser.feed(response.body)
        static_candidates = {x for x in parser.links if x.startswith('/')}
        script_candidates = {x for x in parser.script_sources if x.startswith('/')}
        if is_js:
            api_candidates.update(
                x for _, x in analyses[-1].endpoints
                if x.startswith('/') and '{' not in x
            )
        # Bootstrap application JavaScript before recursively expanding route-shaped
        # strings. Otherwise a noisy API frontier can consume the path budget before
        # the bundles that reveal real request methods and service configuration run.
        # Script paths are still same-origin relative candidates; HttpAdapter enforces
        # the configured target scope for every request.
        api_candidates = {
            x for x in api_candidates if x.startswith('/') and '{' not in x
        }
        for candidate in sorted(script_candidates, reverse=True):
            if candidate not in seen and candidate not in queue:
                queue.insert(0, candidate)
        for candidate in sorted(api_candidates, reverse=True):
            if candidate not in seen and candidate not in queue:
                queue.append(candidate)
        for candidate in sorted(static_candidates):
            if candidate not in seen and candidate not in queue:
                queue.append(candidate)
        for key,identifier,field_path in _ids(_resource_documents(response)):
            rid='resource:'+hashlib.sha256((key+'|'+identifier).encode()).hexdigest()[:16]
            if rid not in model.resources: model.add_resource(Resource(rid,key,None,identifier,obs.id,field_path)); resource_ids.append(rid)
            endpoint=model.endpoints[endpoint_id]
            if rid not in endpoint.resource_ids: model.endpoints[endpoint_id]=Endpoint(endpoint.id,endpoint.method,endpoint.path,tuple(sorted(set(endpoint.resource_ids)|{rid})),endpoint.action)
    for analysis in analyses:
        for method,path in analysis.endpoints:
            endpoint_id=f'{method} {path}'
            if endpoint_id not in model.endpoints: model.add_endpoint(Endpoint(endpoint_id,method,path))
    return DiscoveryResult(model,tuple(seen),tuple(observations),tuple(resource_ids),tuple(analyses))