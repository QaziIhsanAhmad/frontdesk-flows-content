import json, uuid, copy
d = json.load(open('/home/claude/n8n/prod.json'))
keep = ['Website Form','Settings','Clean & Check','Reply to Form','Is Valid?','AI Triage & Draft','Read AI Answer','Not Spam?','Email Reply to Lead']
nodes = [copy.deepcopy(n) for n in d['nodes'] if n['name'] in keep]
for n in nodes:
    n['id'] = str(uuid.uuid4())
    if n['type'].endswith('webhook'):
        n['webhookId'] = str(uuid.uuid4()); n['parameters']['path'] = 'clinic-enquiry-private'
pos = {'Website Form':[0,300],'Settings':[220,300],'Clean & Check':[440,300],'Reply to Form':[660,300],'Is Valid?':[880,300],
       'Redact Health Data':[1100,300],'AI Triage & Draft':[1320,300],'Read AI Answer':[1540,300],'Not Spam?':[1760,300],'Email Reply to Lead':[1980,300]}
code = r"""// Strip identifiers before anything leaves for the AI provider.
// The full details stay inside n8n for the email reply.
const rules = [
  [/\b(?:DOB|date of birth)\s*:?\s*\d{1,2}[\/.-]\d{1,2}[\/.-]\d{2,4}/gi, '[DOB removed]'],
  [/\b\d{3}\s?\d{3}\s?\d{4}\b/g, '[NHS no. removed]'],
  [/\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b/gi, '[postcode removed]'],
  [/\b(?:\+44\s?|0)7\d{3}\s?\d{6}\b/g, '[phone removed]'],
  [/[\w.+-]+@[\w-]+\.[\w.]+/g, '[email removed]'],
];
return $input.all().map(item => {
  let msg = item.json.message || '';
  let removed = 0;
  const full = String(item.json.name || '').trim();
  if (full.includes(' ')) msg = msg.split(full).join(full.split(' ')[0]);
  for (const [re, tag] of rules) msg = msg.replace(re, () => { removed++; return tag; });
  const first = String(item.json.name || '').split(' ')[0];
  return { json: { name: first, email: '[not sent to AI]', phone: '[not sent to AI]', message: msg, removed } };
});"""
nodes.append({"id": str(uuid.uuid4()), "name": "Redact Health Data", "type": "n8n-nodes-base.code", "typeVersion": 2,
              "position": pos['Redact Health Data'], "parameters": {"jsCode": code}})
for n in nodes: n['position'] = pos[n['name']]
C = lambda a,b: {a: {"main": [[{"node": b, "type": "main", "index": 0}]]}}
conns = {}
for a,b in [('Website Form','Settings'),('Settings','Clean & Check'),('Clean & Check','Reply to Form'),('Reply to Form','Is Valid?'),
            ('Is Valid?','Redact Health Data'),('Redact Health Data','AI Triage & Draft'),('AI Triage & Draft','Read AI Answer'),
            ('Read AI Answer','Not Spam?'),('Not Spam?','Email Reply to Lead')]:
    conns.update(C(a,b))
wf = {"name": "FrontDesk Flows – Private AI Triage (redacted)", "nodes": nodes, "connections": conns, "settings": {"executionOrder": "v1"}}
json.dump(wf, open('redact.json','w'), indent=1)
print('ok', len(nodes))
