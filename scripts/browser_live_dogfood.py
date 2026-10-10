from __future__ import annotations
import base64, json, os
from pathlib import Path

from playwright.sync_api import sync_playwright

from cydra_web2.adapter import HttpAdapter, IdentitySession
from cydra_web2.discovery import discover
from cydra_web2.live_config import LiveDogfoodConfig
from cydra_web2.browser_safety import safe_observed_url


def _states():
    raw=os.environ.get("CYDRA_BROWSER_STORAGE_STATES","").strip()
    if not raw:
        raise ValueError("CYDRA_BROWSER_STORAGE_STATES is required for browser-backed live dogfood")
    try:
        parsed=json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("CYDRA_BROWSER_STORAGE_STATES must be a JSON object") from exc
    if not isinstance(parsed,dict) or len(parsed)<2:
        raise ValueError("CYDRA_BROWSER_STORAGE_STATES must contain at least two identities")
    out={}
    for identity,value in parsed.items():
        if not isinstance(identity,str) or not identity.strip() or not isinstance(value,str) or not value.strip():
            raise ValueError("browser storage states must map identity IDs to base64 strings")
        try:
            out[identity.strip()]=json.loads(base64.b64decode(value).decode("utf-8"))
        except Exception as exc:
            raise ValueError(f"invalid browser storage state for identity {identity}") from exc
    return out


def _cookie_applies(domain, allowed_hosts):
    domain=domain.lstrip(".").lower()
    return any(host == domain or host.endswith("." + domain) for host in allowed_hosts)


def main():
    config=LiveDogfoodConfig.from_environment()
    states=_states()
    missing=set(x.identity_id for x in config.identities)-set(states)
    if missing:
        raise ValueError(f"browser storage states missing configured identities: {sorted(missing)}")
    identities=[]
    browser_observations=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for identity in config.identities:
            context=browser.new_context(storage_state=states[identity.identity_id])
            page=context.new_page()
            network=[]
            auth_headers={}
            def on_request(request):
                # Exact origin comparison prevents lookalike hosts from contaminating
                # target observations. Query strings and URL userinfo are never persisted.
                safe_url = safe_observed_url(request.url, config.target.base_url)
                if safe_url is None:
                    return
                network.append({
                    "url": safe_url,
                    "method": request.method,
                })
                for name, value in request.headers.items():
                    lname = name.lower()
                    if lname == "authorization" or lname.startswith("x-"):
                        auth_headers.setdefault(name, value)
            page.on("request", on_request)
            page.goto(config.target.base_url, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            observed_paths={"/"}
            target_host=__import__("urllib.parse",fromlist=["urlparse"]).urlparse(config.target.base_url).hostname
            for item in network:
                parsed=__import__("urllib.parse",fromlist=["urlparse"]).urlparse(item["url"])
                if parsed.hostname==target_host:
                    observed_paths.add(parsed.path or "/")
            browser_observations.append({
                "identity":identity.identity_id,
                "final_url": safe_observed_url(page.url, config.target.base_url) or "external_or_cross_origin",
                "title":page.title(),
                "network_requests":[x for x in network if x["method"] in {"GET","POST","PUT","PATCH","DELETE"}][:200],
                "observed_paths":sorted(observed_paths)[:250],
                "cookie_count":len(context.cookies()),
                "browser_auth_header_names":sorted(auth_headers),
            })
            cookies=context.cookies()
            cookie_header="; ".join(
                f"{c['name']}={c['value']}"
                for c in cookies
                if _cookie_applies(c["domain"], config.target.allowed_hosts)
            )
            headers=dict(auth_headers)
            headers.update(identity.headers)
            if cookie_header:
                headers["Cookie"]=cookie_header
            identities.append(IdentitySession(identity.identity_id,headers))
            context.close()
        browser.close()

    adapter=HttpAdapter(config.target,tuple(identities))
    from cydra_web2.model import Identity,TargetModel
    model=TargetModel(config.target.base_url)
    for x in identities:
        model.add_identity(Identity(x.identity_id,x.identity_id,True))
    configured_seeds=tuple(x.strip() for x in os.environ.get("CYDRA_DISCOVERY_SEEDS","/").split(",") if x.strip())
    observed_seed_paths=tuple(sorted({path for item in browser_observations for path in item.get("observed_paths",[]) if isinstance(path,str) and path.startswith("/")}))
    seeds=tuple(dict.fromkeys(configured_seeds + observed_seed_paths))
    observations=[]
    for x in identities:
        result=discover(adapter,model,seeds=seeds,max_paths=int(os.environ.get("CYDRA_MAX_PATHS","250")),identity_id=x.identity_id)
        observations.extend(result.observations)
    artifact={
        "target":config.target.base_url,
        "browser":browser_observations,
        "identities":[x.identity_id for x in identities],
        "http_observations":len(observations),
        "endpoints":sorted(model.endpoints),
        "resources":sorted(model.resources),
        "note":"Browser session material is never written to the artifact; authorization findings require causal evidence.",
    }
    out=Path(os.environ.get("CYDRA_ARTIFACT","artifacts/live-browser-dogfood.json"))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(artifact,indent=2,sort_keys=True),encoding="utf-8")
    print(f"Browser-backed live dogfood complete: identities={len(identities)} http_observations={len(observations)} endpoints={len(model.endpoints)} resources={len(model.resources)}")


if __name__=="__main__":
    main()
