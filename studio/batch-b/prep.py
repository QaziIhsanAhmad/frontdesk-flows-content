import json,sys,subprocess,os
N=os.path.join(os.environ.get('STUDIO_DIR','/home/claude/studio'),'n8n')
sc=json.load(open(sys.argv[1]))
f=sc.get('workflowIdFile','prodid')
wid=open(f if os.path.isabs(f) else os.path.join(N,f)).read().strip()
def curl(*a): return subprocess.run(['curl','-s','-b',os.path.join(N,'cj'),*a],capture_output=True,text=True).stdout
d=json.loads(curl(f'localhost:5678/rest/workflows/{wid}'))['data']
pin={}
if sc.get('pin'): pin.update(sc['pin'])
if sc.get('sheetRow'): pin['Log Lead to Sheet']=[{'json':sc['sheetRow']}]
body={'name':d['name'],'nodes':d['nodes'],'connections':d['connections'],'settings':d['settings'],'versionId':d['versionId'],'pinData':pin}
r=curl('-X','PATCH',f'localhost:5678/rest/workflows/{wid}','-H','content-type: application/json','-d',json.dumps(body))
print('pinned' if '"data"' in r else r[:300])
