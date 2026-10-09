import json, uuid, copy
d = json.load(open('/home/claude/n8n/prod.json'))
by = {n['name']: copy.deepcopy(n) for n in d['nodes']}
def N(name, type_, ver, params, **kw):
    x = {"id": str(uuid.uuid4()), "name": name, "type": type_, "typeVersion": ver, "parameters": params}; x.update(kw); return x
trig = N("New Google Review", "n8n-nodes-base.manualTrigger", 1, {})
settings = by['Settings']; settings['id'] = str(uuid.uuid4())
ai = by['AI Triage & Draft']; ai['id'] = str(uuid.uuid4()); ai['name'] = 'AI Drafts Reply'
ai['parameters']['jsonBody'] = "={{ JSON.stringify({ model: $('Settings').item.json.llmModel, temperature: 0.3, response_format: { type: 'json_object' }, messages: [ { role: 'system', content: 'You reply to Google reviews for ' + $('Settings').item.json.businessName + '. Return JSON {reply}. Thank the reviewer by first name, mention one specific thing they said, max 60 words, no medical advice, never mention their condition or treatment details publicly, sign as ' + $('Settings').item.json.signature + '.' }, { role: 'user', content: 'Reviewer: ' + $('New Google Review').item.json.reviewer + '\\nStars: ' + $('New Google Review').item.json.stars + '\\nReview: ' + $('New Google Review').item.json.text } ] }) }}"
read = N("Read Draft", "n8n-nodes-base.code", 2, {"jsCode": r"""const r = $('New Google Review').first().json;
let reply = '';
try { reply = JSON.parse($json.choices[0].message.content).reply || ''; } catch (e) {}
return [{ json: { ...r, reply } }];"""})
email = copy.deepcopy(by['Email Reply to Lead']); email['id'] = str(uuid.uuid4()); email['name'] = 'Ask Owner to Approve'
email['parameters'].update({"toEmail": "={{ $('Settings').item.json.staffEmail }}",
  "subject": "=Approve reply to {{ $json.reviewer }}'s {{ $json.stars }}-star review?",
  "text": "=New {{ $json.stars }}-star Google review from {{ $json.reviewer }}:\n\"{{ $json.text }}\"\n\nSuggested reply:\n{{ $json.reply }}\n\nApprove and post: {{ $execution.resumeUrl }}?approve=yes\nSkip: {{ $execution.resumeUrl }}?approve=no"})
wait = N("Wait for Approval", "n8n-nodes-base.wait", 1.1, {"resume": "webhook", "httpMethod": "GET", "options": {}}, webhookId=str(uuid.uuid4()))
ifn = copy.deepcopy(by['Is Valid?']); ifn['id'] = str(uuid.uuid4()); ifn['name'] = 'Approved?'
c = ifn['parameters']['conditions']['conditions'][0]
c.update({"leftValue": "={{ $json.query.approve }}", "rightValue": "yes", "operator": {"type": "string", "operation": "equals"}})
post = N("Post Reply to Google", "n8n-nodes-base.httpRequest", 4.2, {"method": "POST", "url": "http://reviews.sandbox/v4/reviews/reply",
  "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify({ reviewer: $('Read Draft').item.json.reviewer, comment: $('Read Draft').item.json.reply }) }}", "options": {}})
nodes = [trig, settings, ai, read, email, wait, ifn, post]
for i, n in enumerate(nodes): n['position'] = [i*230, 300]
names = [n['name'] for n in nodes]
conns = {a: {"main": [[{"node": b, "type": "main", "index": 0}]]} for a, b in zip(names, names[1:])}
pin = {"New Google Review": [{"json": {"reviewer": "Hannah Lee", "stars": 5, "text": "Tom fixed my shoulder in three sessions. Clear exercises and he actually explained what was going on. Thank you!"}}]}
wf = {"name": "FrontDesk Flows – Review replies with owner approval", "active": False, "nodes": nodes, "connections": conns, "settings": {"executionOrder": "v1"}, "pinData": pin}
json.dump(wf, open('rev.json','w'), indent=1)
