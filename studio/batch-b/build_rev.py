import json, uuid, copy, os, sys
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'clinic-enquiry-ai-triage.json')
d = json.load(open(SRC))
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
  "text": "=New {{ $json.stars }}-star Google review from {{ $json.reviewer }}:\n\"{{ $json.text }}\"\n\nSuggested reply:\n{{ $json.reply }}\n\nReview and decide here (opens a page, nothing is posted until you press Submit):\n{{ $execution.resumeFormUrl }}"})
# Resume on a form submit (POST), so link scanners that prefetch the email link can't approve or skip anything.
wait = N("Wait for Approval", "n8n-nodes-base.wait", 1.1, {"resume": "form", "formTitle": "Approve this review reply?",
  "formDescription": "={{ $('Read Draft').item.json.reply }}",
  "formFields": {"values": [{"fieldLabel": "Decision", "fieldType": "dropdown", "requiredField": True,
     "fieldOptions": {"values": [{"option": "Approve and post"}, {"option": "Skip"}]}}]}, "options": {}}, webhookId=str(uuid.uuid4()))
# If the AI draft failed or came back empty, don't ask for approval; tell the owner instead.
draftok = copy.deepcopy(by['Is Valid?']); draftok['id'] = str(uuid.uuid4()); draftok['name'] = 'Draft OK?'
dc = draftok['parameters']['conditions']['conditions'][0]
dc.update({"leftValue": "={{ ($json.reply || '').trim().length }}", "rightValue": 20, "operator": {"type": "number", "operation": "gt"}})
failmail = copy.deepcopy(by['Email Reply to Lead']); failmail['id'] = str(uuid.uuid4()); failmail['name'] = 'Tell Owner: Draft Failed'
failmail['parameters'].update({"toEmail": "={{ $('Settings').item.json.staffEmail }}", "subject": "=Please reply to {{ $json.reviewer }}'s review yourself",
  "text": "=The AI draft for {{ $json.reviewer }}'s {{ $json.stars }}-star review failed, so nothing was posted.\n\nReview:\n\"{{ $json.text }}\""})
ifn = copy.deepcopy(by['Is Valid?']); ifn['id'] = str(uuid.uuid4()); ifn['name'] = 'Approved?'
c = ifn['parameters']['conditions']['conditions'][0]
c.update({"leftValue": "={{ $json.Decision }}", "rightValue": "Approve and post", "operator": {"type": "string", "operation": "equals"}})
post = N("Post Reply to Google", "n8n-nodes-base.httpRequest", 4.2, {"method": "POST", "url": "http://reviews.sandbox/v4/reviews/reply",
  "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify({ reviewer: $('Read Draft').item.json.reviewer, comment: $('Read Draft').item.json.reply }) }}", "options": {}})
nodes = [trig, settings, ai, read, draftok, email, wait, ifn, post, failmail]
for i, n in enumerate(nodes[:9]): n['position'] = [i*230, 300]
failmail['position'] = [5*230, 520]
chain = ['New Google Review','Settings','AI Drafts Reply','Read Draft','Draft OK?','Ask Owner to Approve','Wait for Approval','Approved?','Post Reply to Google']
conns = {a: {"main": [[{"node": b, "type": "main", "index": 0}]]} for a, b in zip(chain, chain[1:])}
conns['Draft OK?']['main'].append([{"node": "Tell Owner: Draft Failed", "type": "main", "index": 0}])
pin = {"New Google Review": [{"json": {"reviewer": "Hannah Lee", "stars": 5, "text": "Tom fixed my shoulder in three sessions. Clear exercises and he actually explained what was going on. Thank you!"}}]}
wf = {"name": "FrontDesk Flows – Review replies with owner approval", "active": False, "nodes": nodes, "connections": conns, "settings": {"executionOrder": "v1"}, "pinData": pin}
json.dump(wf, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rev.json'),'w'), indent=1)
