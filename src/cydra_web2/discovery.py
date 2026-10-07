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
    def __init__(self): super().__init__(); self.links = set()
    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if v and k.lower() in {'href','src','action'}: self.links.add(v)

_ID = re.compile(r'^(?:id|uuid|[A-Za-z][A-Za-z0-9]*(?:_id|_uuid|Id|UUID))$', re.I)
_PATH = re.compile(r'/(?:api|graphql|rpc|v[0-9]+)(?:/[A-Za-z0-9_.$:@%~+\-{}]+)*')
_REQUEST = re.compile(r'''\\b(?:(fetch)|(axios|api|client|http|request)\\.(get|post|put|patch|delete|head|options))\\s*\\(\\s*([^,\\)]+)''', re.I)
_OPEN = re.compile(r'''\.open\s*\(\s*['\"](GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)['\"]\s*,\s*([^,\)]+)''', re.I)
_ASSIGN = re.compile(r'''\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(['\"])([^'\"]+)\2''')
_COMBINED = re.compile(r'''\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*([A-Za-z_$][\w$]*)\s*\+\s*(['\"])([^'\"]+)\3''')
_ORIGIN = re.compile(r'''(?:baseURL|baseUrl|apiBase|apiBaseUrl|API_BASE_URL|API_BASE|apiUrl|apiURL|API_URL|backendUrl|backendURL|BACKEND_URL|serviceUrl|serviceURL|SERVICE_URL|graphqlUrl|graphqlURL|GRAPHQL_URL|endpointUrl|ENDPOINT_URL|apiEndpoint|apiEndpointUrl|apiHost|apiDomain|baseApiUrl|BASE_API_URL|PUBLIC_API_URL|NEXT_PUBLIC_API_URL|VITE_API_URL)\s*[:=]\s*['\"](https?://[^'\"\s]+)''', re.I)

def _api_paths(body: str):
    out = set()
    for token in re.findall(r'''['\"]([^'\"]+)['\"]''', body):
        if re.match(r'^/(?:api|graphql|rpc|v[0-9]+)(?:/|$)', token, re.I): out.add(token.split('?',1)[0])
    for m in _PATH.finditer(body): out.add(m.group(0).split('?',1)[0])
    return out

def _documents(body: str):
    docs=[]
    try: docs.append(json.loads(body))
    except (TypeError,json.JSONDecodeError): pass
    for attrs, source in re.findall(r'<script\b([^>]*)>(.*?)</script\s*>', body, re.I|re.S):
        if re.search(r'type\s*=\s*["\']application/json["\']', attrs, re.I):
            try: docs.append(json.loads(source))
            except (TypeError,json.JSONDecodeError): pass
    return docs

def _ids(value, path=''):
    if isinstance(value,dict):
        for k,v in value.items():
            p=f'{path}.{k}' if path else str(k)
            if _ID.fullmatch(str(k)) and isinstance(v,(str,int)) and str(v).strip(): yield str(k),str(v),p
            yield from _ids(v,p)
    elif isinstance(value,list):
        for i,v in enumerate(value): yield from _ids(v,f'{path}[{i}]')

def _resolve(expr, constants):
    expr=expr.strip().strip('()')
    if len(expr)>=2 and expr[0] in "'\"" and expr[-1]==expr[0]: return expr[1:-1]
    parts=re.split(r'\s*\+\s*',expr)
    out=[]
    for part in parts:
        part=part.strip()
        if len(part)>=2 and part[0] in "'\"" and part[-1]==part[0]: out.append(part[1:-1])
        elif part in constants: out.append(constants[part])
        else: return None
    return ''.join(out)

def _analyze_bundle(path, body, target):
    constants={m.group(1):m.group(3) for m in _ASSIGN.finditer(body)}
    for m in _COMBINED.finditer(body):
        if m.group(2) in constants: constants[m.group(1)]=constants[m.group(2)]+m.group(4)
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
    for value in _api_paths(body): endpoints.add(('GET',value)); request_origins.add((value,f'{urlparse(target).scheme}://{urlparse(target).netloc}'))
    return BundleAnalysis(path,tuple(sorted(methods)),tuple(sorted(endpoints)),tuple(sorted(request_origins)),tuple(sorted(origins)),tuple(sorted(unresolved)))

def discover(adapter: HttpAdapter, model: TargetModel, seeds: Iterable[str]=('/',), max_paths: int=50, identity_id: str|None=None, max_js_bundles: int=50)->DiscoveryResult:
    queue=list(dict.fromkeys(seeds)); seen=set(); observations=[]; resource_ids=[]; analyses=[]; analyzed=set()
    while queue and len(seen)<max_paths:
        path=queue.pop(0)
        if path in seen: continue
        seen.add(path); endpoint_id=f'GET {path}'
        if endpoint_id not in model.endpoints: model.add_endpoint(Endpoint(endpoint_id,'GET',path))
        response=adapter.request(method='GET',path=path,identity_id=identity_id)
        fp=hashlib.sha256(response.body.encode()).hexdigest()
        obs=Observation(f'obs:{len(observations)}',endpoint_id,response.identity_id,response.status_code,fp,len(response.body),f'GET:{path}')
        model.add_observation(obs); observations.append(obs)
        ctype=str(getattr(response,'headers',{}).get('Content-Type','')).lower(); is_js='javascript' in ctype or path.lower().endswith(('.js','.mjs'))
        if is_js and path not in analyzed and len(analyzed)<max_js_bundles: analyses.append(_analyze_bundle(path,response.body,model.target)); analyzed.add(path)
        candidates=set(_api_paths(response.body))
        parser=_Links(); parser.feed(response.body); candidates.update(x for x in parser.links if x.startswith('/'))
        if is_js: candidates.update(x for _,x in analyses[-1].endpoints if x.startswith('/'))
        for candidate in sorted(candidates):
            if candidate not in seen and candidate not in queue: queue.append(candidate)
        for key,identifier,field_path in _ids(_documents(response.body)):
            rid='resource:'+hashlib.sha256((key+'|'+identifier).encode()).hexdigest()[:16]
            if rid not in model.resources: model.add_resource(Resource(rid,key,None,identifier,obs.id)); resource_ids.append(rid)
            endpoint=model.endpoints[endpoint_id]
            if rid not in endpoint.resource_ids: model.endpoints[endpoint_id]=Endpoint(endpoint.id,endpoint.method,endpoint.path,tuple(sorted(set(endpoint.resource_ids)|{rid})),endpoint.action)
    for analysis in analyses:
        for method,path in analysis.endpoints:
            endpoint_id=f'{method} {path}'
            if endpoint_id not in model.endpoints: model.add_endpoint(Endpoint(endpoint_id,method,path))
    return DiscoveryResult(model,tuple(seen),tuple(observations),tuple(resource_ids),tuple(analyses))