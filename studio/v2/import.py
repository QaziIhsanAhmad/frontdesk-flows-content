"""After setup.sh: create the local n8n owner, sandbox credentials and import the demo workflows.
Writes <name>id files (prodid, noshowid, reviewsid, remid) next to the n8n folder for rec2.js scenarios."""
import json, os, subprocess, sys
W = os.environ.get('STUDIO_DIR', '/home/claude/studio'); N = f'{W}/n8n'; V2 = os.path.dirname(os.path.abspath(__file__))
def curl(*a): return subprocess.run(['curl', '-s', '-b', f'{N}/cj', '-c', f'{N}/cj', *a], capture_output=True, text=True).stdout
curl('-X', 'POST', 'localhost:5678/rest/owner/setup', '-H', 'content-type: application/json', '-d',
     json.dumps({"email": "demo@frontdeskflows.test", "firstName": "FrontDesk", "lastName": "Flows", "password": "DemoPass123!"}))
curl('-X', 'POST', 'localhost:5678/rest/login', '-H', 'content-type: application/json', '-d',
     json.dumps({"emailOrLdapLoginId": "demo@frontdeskflows.test", "password": "DemoPass123!"}))
def cred(name, type_, data):
    r = json.loads(curl('-X', 'POST', 'localhost:5678/rest/credentials', '-H', 'content-type: application/json', '-d', json.dumps({"name": name, "type": type_, "data": data})))
    return {'id': r['data']['id'], 'name': name}
C = {'httpHeaderAuth': cred('Demo AI key (sandbox)', 'httpHeaderAuth', {"name": "Authorization", "value": "Bearer demo"}),
     'smtp': cred('Demo SMTP (sandbox inbox)', 'smtp', {"user": "", "password": "", "host": "127.0.0.1", "port": 1025, "secure": False, "disableStartTls": True}),
     'googleSheetsOAuth2Api': cred('Google Sheets (demo)', 'googleSheetsOAuth2Api', {"clientId": "demo", "clientSecret": "demo"})}
for f, idf in (('product.json', 'prodid'), ('noshow.json', 'noshowid'), ('reviews.json', 'reviewsid'), ('reminders.json', 'remid')):
    w = json.load(open(f'{V2}/workflows/{f}'))
    for n in w['nodes']:
        for k in list((n.get('credentials') or {}).keys()):
            n['credentials'][k] = C[k]
    w['active'] = False; w.setdefault('pinData', {})
    r = json.loads(curl('-X', 'POST', 'localhost:5678/rest/workflows', '-H', 'content-type: application/json', '-d', json.dumps(w)))
    open(f'{N}/{idf}', 'w').write(r['data']['id']); print(f, r['data']['id'])
# storage state for Playwright
subprocess.run(['node', '-e', """const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const c=await b.newContext();const p=await c.newPage();
await p.goto('http://localhost:5678/signin');await p.fill('input[type=email]','demo@frontdeskflows.test');await p.fill('input[type=password]','DemoPass123!');
await p.keyboard.press('Enter');await p.waitForTimeout(4000);await c.storageState({path:'state.json'});await b.close();})()"""], cwd=W)
