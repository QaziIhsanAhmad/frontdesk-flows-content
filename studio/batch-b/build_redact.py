import json, uuid, copy, os, sys
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'clinic-enquiry-ai-triage.json')
d = json.load(open(SRC))
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
  // DOB: 14/03/1986, 14-3-86, 1986-03-14, 14 March 1986, March 14th, 1986
  [/\b(?:DOB|D\.O\.B\.?|date of birth|born(?: on)?)\s*:?\s*(?:\d{4}[\/.-]\d{1,2}[\/.-]\d{1,2}|\d{1,2}[\/.-]\d{1,2}[\/.-]\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]{3,9}\.?,?\s+\d{2,4}|[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4})/gi, '[DOB removed]'],
  // NHS number: 10 digits, often 3-3-4
  [/\b[1-9]\d{2}[\s-]?\d{3}[\s-]?\d{4}\b/g, '[NHS no. removed]'],
  // UK postcode
  [/\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b/gi, '[postcode removed]'],
  // UK phone numbers, mobile or landline, any spacing: 07700 900 123, 020 7946 0958, (020) 7946 0958, +44 7700 900123
  [/(?:\+44\s?\(?0?\)?\s?|\(?\b0)\d(?:[\s-]?\)?[\s-]?\d){8,9}\b/g, '[phone removed]'],
  // Email
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
json.dump(wf, open(os.path.join(sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__)), 'redact.json'),'w'), indent=1)
print('ok', len(nodes))
