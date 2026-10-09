import json, uuid, copy, os, sys
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'clinic-enquiry-ai-triage.json')
d = json.load(open(SRC))
keep = ['Website Form','Settings','Clean & Check','Reply to Form','Is Valid?','AI Triage & Draft','Read AI Answer','Not Spam?','Email Reply to Lead']
nodes = [copy.deepcopy(n) for n in d['nodes'] if n['name'] in keep]
for n in nodes:
    n['id'] = str(uuid.uuid4())
    if n['type'].endswith('webhook'):
        n['webhookId'] = str(uuid.uuid4()); n['parameters']['path'] = 'clinic-enquiry-csv'
# Where the log lives. Default is n8n's own file folder (/home/node/.n8n-files in the official Docker image).
for n in nodes:
    if n['name'] == 'Settings':
        n['parameters']['assignments']['assignments'].append({"id": str(uuid.uuid4()), "name": "leadsCsvPath", "value": "/home/node/.n8n-files/leads.csv", "type": "string"})
code = r"""// One tidy CSV row per enquiry. No Google Sheet, no paid CRM.
// Cells are quoted, and anything a spreadsheet could run as a formula (= + - @) is prefixed with '.
const a = $('Read AI Answer').first().json; const lead = $('Is Valid?').first().json;
const cell = v => {
  let s = String(v ?? '').replace(/\r?\n/g, ' ');
  if (/^[=+\-@\t]/.test(s)) s = "'" + s;
  return '"' + s.replace(/"/g, '""') + '"';
};
const cols = ['received','name','email','phone','category','urgent','summary','status'];
const row = [lead.receivedAt, lead.name, lead.email, lead.phone, a.category, a.urgent ? 'YES' : '', a.summary, 'New'].map(cell).join(',');
const fileExists = !!$('Read leads.csv').first().binary;
const csv = (fileExists ? '' : cols.join(',') + '\n') + row + '\n';
return [{ json: { csv } }];"""
nodes += [
 {"id": str(uuid.uuid4()), "name": "Read leads.csv", "type": "n8n-nodes-base.readWriteFile", "typeVersion": 1, "position": [0,0],
  "parameters": {"fileSelector": "={{ $('Settings').first().json.leadsCsvPath }}", "options": {}}, "onError": "continueRegularOutput", "alwaysOutputData": True},
 {"id": str(uuid.uuid4()), "name": "Build CRM Row", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [0,0], "parameters": {"jsCode": code}},
 {"id": str(uuid.uuid4()), "name": "Convert to CSV", "type": "n8n-nodes-base.convertToFile", "typeVersion": 1.1, "position": [0,0],
  "parameters": {"operation": "toText", "sourceProperty": "csv", "options": {"fileName": "leads.csv"}}},
 {"id": str(uuid.uuid4()), "name": "Append to leads.csv", "type": "n8n-nodes-base.readWriteFile", "typeVersion": 1, "position": [0,0],
  "parameters": {"operation": "write", "fileName": "={{ $('Settings').first().json.leadsCsvPath }}", "options": {"append": True}}},
]
pos = {'Website Form':[0,300],'Settings':[220,300],'Clean & Check':[440,300],'Reply to Form':[660,300],'Is Valid?':[880,300],
       'AI Triage & Draft':[1100,300],'Read AI Answer':[1320,300],'Not Spam?':[1540,520],'Email Reply to Lead':[1760,520],
       'Read leads.csv':[1540,300],'Build CRM Row':[1760,300],'Convert to CSV':[1980,300],'Append to leads.csv':[2200,300]}
for n in nodes: n['position'] = pos[n['name']]
conns = {}
def C(a,b,i=0):
    conns.setdefault(a, {"main": [[]]})["main"][0].append({"node": b, "type": "main", "index": 0})
for a,b in [('Website Form','Settings'),('Settings','Clean & Check'),('Clean & Check','Reply to Form'),('Reply to Form','Is Valid?'),
            ('Is Valid?','AI Triage & Draft'),('AI Triage & Draft','Read AI Answer'),('Read AI Answer','Not Spam?'),('Read AI Answer','Read leads.csv'),('Read leads.csv','Build CRM Row'),
            ('Not Spam?','Email Reply to Lead'),('Build CRM Row','Convert to CSV'),('Convert to CSV','Append to leads.csv')]:
    C(a,b)
wf = {"name": "FrontDesk Flows – Free CSV lead log", "active": False, "nodes": nodes, "connections": conns, "settings": {"executionOrder": "v1"}}
json.dump(wf, open(os.path.join(sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__)), 'csv.json'),'w'), indent=1)
