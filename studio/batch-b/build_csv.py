import json, uuid, copy
d = json.load(open('/home/claude/n8n/prod.json'))
keep = ['Website Form','Settings','Clean & Check','Reply to Form','Is Valid?','AI Triage & Draft','Read AI Answer','Not Spam?','Email Reply to Lead']
nodes = [copy.deepcopy(n) for n in d['nodes'] if n['name'] in keep]
for n in nodes:
    n['id'] = str(uuid.uuid4())
    if n['type'].endswith('webhook'):
        n['webhookId'] = str(uuid.uuid4()); n['parameters']['path'] = 'clinic-enquiry-csv'
code = r"""// One tidy row per enquiry. No Google Sheet, no paid CRM.
const a = $json; const lead = $('Is Valid?').first().json;
return [{ json: {
  received: lead.receivedAt,
  name: lead.name,
  email: lead.email,
  phone: lead.phone,
  category: a.category,
  urgent: a.urgent ? 'YES' : '',
  summary: a.summary,
  status: 'New'
} }];"""
nodes += [
 {"id": str(uuid.uuid4()), "name": "Build CRM Row", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [0,0], "parameters": {"jsCode": code}},
 {"id": str(uuid.uuid4()), "name": "Convert to CSV", "type": "n8n-nodes-base.convertToFile", "typeVersion": 1.1, "position": [0,0],
  "parameters": {"operation": "csv", "options": {"headerRow": False, "fileName": "leads.csv"}}},
 {"id": str(uuid.uuid4()), "name": "Append to leads.csv", "type": "n8n-nodes-base.readWriteFile", "typeVersion": 1, "position": [0,0],
  "parameters": {"operation": "write", "fileName": "/home/claude/n8n/data/.n8n-files/leads.csv", "options": {"append": True}}},
]
pos = {'Website Form':[0,300],'Settings':[220,300],'Clean & Check':[440,300],'Reply to Form':[660,300],'Is Valid?':[880,300],
       'AI Triage & Draft':[1100,300],'Read AI Answer':[1320,300],'Not Spam?':[1540,160],'Email Reply to Lead':[1760,160],
       'Build CRM Row':[1540,440],'Convert to CSV':[1760,440],'Append to leads.csv':[1980,440]}
for n in nodes: n['position'] = pos[n['name']]
conns = {}
def C(a,b,i=0):
    conns.setdefault(a, {"main": [[]]})["main"][0].append({"node": b, "type": "main", "index": 0})
for a,b in [('Website Form','Settings'),('Settings','Clean & Check'),('Clean & Check','Reply to Form'),('Reply to Form','Is Valid?'),
            ('Is Valid?','AI Triage & Draft'),('AI Triage & Draft','Read AI Answer'),('Read AI Answer','Not Spam?'),('Read AI Answer','Build CRM Row'),
            ('Not Spam?','Email Reply to Lead'),('Build CRM Row','Convert to CSV'),('Convert to CSV','Append to leads.csv')]:
    C(a,b)
wf = {"name": "FrontDesk Flows – Free CSV lead log", "active": False, "nodes": nodes, "connections": conns, "settings": {"executionOrder": "v1"}}
json.dump(wf, open('csv.json','w'), indent=1)
