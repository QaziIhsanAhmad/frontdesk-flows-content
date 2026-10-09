import json,sys,subprocess
sc=json.load(open(sys.argv[1]))
wid=open(sc.get('workflowIdFile','/home/claude/n8n/prodid')).read().strip()
def curl(*a): return subprocess.run(['curl','-s','-b','/home/claude/n8n/cj',*a],capture_output=True,text=True).stdout
d=json.loads(curl(f'localhost:5678/rest/workflows/{wid}'))['data']
pin={}
if sc.get('pin'): pin.update(sc['pin'])
if sc.get('sheetRow'): pin['Log Lead to Sheet']=[{'json':sc['sheetRow']}]
body={'name':d['name'],'nodes':d['nodes'],'connections':d['connections'],'settings':d['settings'],'versionId':d['versionId'],'pinData':pin}
r=curl('-X','PATCH',f'localhost:5678/rest/workflows/{wid}','-H','content-type: application/json','-d',json.dumps(body))
print('pinned' if '"data"' in r else r[:300])
