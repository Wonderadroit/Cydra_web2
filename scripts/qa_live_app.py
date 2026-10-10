from __future__ import annotations
import ipaddress,json,os,socket
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,urlunparse
from playwright.sync_api import sync_playwright
OUT=Path(os.environ.get('CYDRA_QA_OUT','artifacts/live-app-qa'))
RAW=os.environ.get('CYDRA_QA_TARGET_URL','').strip()
def now(): return datetime.now(timezone.utc).isoformat()
def validate(raw):
 if not raw or len(raw)>2048: raise ValueError('Provide a target URL no longer than 2048 characters.')
 p=urlparse(raw)
 if p.scheme.lower()!='https' or not p.hostname: raise ValueError('Target must be an absolute HTTPS URL.')
 if p.username or p.password: raise ValueError('Credentials embedded in URLs are not allowed.')
 if p.port not in (None,443): raise ValueError('Only standard HTTPS port 443 is allowed.')
 host=p.hostname.rstrip('.').lower()
 if host=='localhost' or host.endswith(('.localhost','.local')): raise ValueError('Local hostnames are not allowed.')
 try: ips=[ipaddress.ip_address(host.strip('[]'))]
 except ValueError:
  ips=[ipaddress.ip_address(x[4][0].split('%')[0]) for x in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)]
 if not ips or any(not x.is_global for x in ips): raise ValueError('Target resolves to a non-public IP address.')
 p=p._replace(scheme='https',netloc=host+(f':{p.port}' if p.port else ''),fragment='')
 return urlunparse(p),host
def main():
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'screenshots').mkdir(exist_ok=True)
 start=now(); tests=[]
 report={'title':'CYDRA Authorized Live Application QA','target':RAW,'target_type':'Operator-supplied public HTTPS URL; one-page read-only smoke QA','started_at_utc':start,'tests':tests,'limitations':['Only the supplied page is loaded. No crawling, form submission, login, fuzzing, or exploit payloads.','Console errors and failed requests are observations, not proof of a product defect.','A passing smoke check does not establish application-wide quality or security.','DNS checks are best-effort safeguards, not a substitute for authorized network controls.']}
 try:
  target,host=validate(RAW); report['target']=target
  t={'id':'LIVE-QA-001','name':'HTTPS page-load and runtime smoke check','url':target,'status':'INCONCLUSIVE','failure_category':None,'steps':['Validate public HTTPS target','Load one page without submitting forms','Capture status, title, readiness, and readable text','Record runtime diagnostics and screenshot'],'observed':{},'diagnostics':{'console_errors':[],'page_errors':[],'failed_requests':[],'http_errors':[]},'screenshots':[],'notes':[]}; tests.append(t)
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True,args=['--disable-dev-shm-usage'])
   try:
    page=browser.new_page(viewport={'width':1365,'height':900}); page.set_default_timeout(15000); d=t['diagnostics']
    page.on('console',lambda m:d['console_errors'].append(m.text[:500]) if m.type=='error' and len(d['console_errors'])<40 else None)
    page.on('pageerror',lambda e:d['page_errors'].append(str(e)[:500]) if len(d['page_errors'])<40 else None)
    page.on('requestfailed',lambda r:d['failed_requests'].append({'url':r.url.split('?')[0][:400],'error':str(r.failure or 'unknown')[:300]}) if len(d['failed_requests'])<40 else None)
    page.on('response',lambda r:d['http_errors'].append({'url':r.url.split('?')[0][:400],'status':r.status}) if r.status>=400 and len(d['http_errors'])<40 else None)
    def guard(route):
     u=urlparse(route.request.url)
     if u.scheme in ('data','blob','about'): route.continue_(); return
     try:
      if u.scheme not in ('https','http') or not u.hostname: raise ValueError('unsupported URL')
      h=u.hostname.lower().rstrip('.')
      if route.request.is_navigation_request() and route.request.frame == page.main_frame and (u.scheme != 'https' or h != host):
       route.abort(); return
      try: ips=[ipaddress.ip_address(h.strip('[]'))]
      except ValueError: ips=[ipaddress.ip_address(x[4][0].split('%')[0]) for x in socket.getaddrinfo(h,u.port or (443 if u.scheme=='https' else 80),type=socket.SOCK_STREAM)]
      if not ips or any(not x.is_global for x in ips): route.abort(); return
     except (OSError,ValueError): route.abort(); return
     route.continue_()
    page.route('**/*',guard)
    response=page.goto(target,wait_until='domcontentloaded',timeout=15000); t['http_status']=response.status if response else None; t['final_url']=page.url[:1000]
    final=urlparse(page.url)
    if final.scheme!='https' or (final.hostname or '').lower().rstrip('.')!=host:
     t.update(status='FAIL',failure_category='OUT_OF_SCOPE_REDIRECT'); t['notes'].append('Top-level page navigated away from the supplied hostname; no further links were followed.')
    else:
     page.locator('body').wait_for(state='attached',timeout=5000); title=page.title().strip(); body=page.locator('body').inner_text(timeout=5000).strip()
     t['observed']={'title':title[:500],'document_ready_state':page.locator('html').evaluate('(el)=>document.readyState'),'body_text_excerpt':body[:1500],'visible_links_count':page.locator('a:visible').count(),'forms_detected_not_submitted':page.locator('form').count(),'interactive_elements_detected_not_used':page.locator('input,textarea,select,button').count(),'same_origin_links_sample':page.locator('a[href]').evaluate_all('(els)=>els.map(a=>a.href).filter(h=>{try{return new URL(h).origin===location.origin}catch{return false}}).slice(0,20)')}
     if response is None: t.update(status='INCONCLUSIVE',failure_category='NO_MAIN_DOCUMENT_RESPONSE'); t['notes'].append('No main-document HTTP response was available.')
     elif response.status>=400: t.update(status='FAIL',failure_category='HTTP_STATUS'); t['notes'].append(f'The supplied page returned HTTP {response.status}; review expected availability.')
     elif not title or not body: t.update(status='FAIL',failure_category='PAGE_CONTENT_ASSERTION'); t['notes'].append('Page lacked a document title or readable body text.')
     else: t['status']='PASS'; t['notes'].append('The page returned a non-error response and exposed a title and readable body text.')
    try:
     shot=OUT/'screenshots'/'live-page.png'; page.screenshot(path=str(shot),full_page=True,timeout=5000,animations='disabled'); t['screenshots'].append(str(shot.relative_to(OUT)))
    except Exception as e: t['notes'].append(f'Screenshot unavailable: {type(e).__name__}: {str(e)[:300]}')
   except Exception as e: t.update(status='INCONCLUSIVE',failure_category='EXECUTION_OR_ENVIRONMENT'); t['notes'].append(f'{type(e).__name__}: {str(e)[:1000]}')
   finally: browser.close()
 except Exception as e:
  tests.append({'id':'LIVE-QA-000','name':'Target safety validation','url':RAW,'status':'INCONCLUSIVE','failure_category':'TARGET_VALIDATION','steps':['Validate supplied URL before connecting'],'observed':{},'diagnostics':{},'screenshots':[],'notes':[f'{type(e).__name__}: {str(e)[:1000]}']})
 end=now(); report['ended_at_utc']=end; passed=sum(x['status']=='PASS' for x in tests); failed=sum(x['status']=='FAIL' for x in tests); inc=sum(x['status']=='INCONCLUSIVE' for x in tests)
 report['summary']={'total':len(tests),'passed':passed,'failed':failed,'inconclusive':inc}; report['environment']={'browser':'Chromium','viewport':'1365x900','mode':'single-page read-only smoke QA'}; report['interpretation']='This is a bounded smoke check of one supplied page. Runtime diagnostics are not confirmed defects. FAIL requires human review; INCONCLUSIVE is not a pass or a product defect.'
 (OUT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf-8')
 lines=['# CYDRA Authorized Live Application QA','',f'Target: {report["target"]}',f'Started: {start}',f'Ended: {end}','',f'Summary: {passed} passed, {failed} failed, {inc} inconclusive.','','## Scope and safety',*[f'- {x}' for x in report['limitations']],'']
 for t in tests: lines += [f'## {t["id"]}: {t["name"]}',f'Status: {t["status"]}',f'Failure category: {t.get("failure_category") or "none"}',f'URL: {t.get("url","")}','','### Observed','```json',json.dumps(t.get('observed',{}),indent=2),'```','','### Notes',*[f'- {x}' for x in t.get('notes',[])],'','### Runtime diagnostics','```json',json.dumps(t.get('diagnostics',{}),indent=2)[:10000],'```','']
 (OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')
 return 0 if failed==0 and inc==0 else 1
if __name__=='__main__': raise SystemExit(main())