import json, uuid, copy, os, sys
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'clinic-enquiry-ai-triage.json')
d = json.load(open(SRC))
by = {n['name']: copy.deepcopy(n) for n in d['nodes']}
wh = by['Website Form']; wh['name'] = 'WhatsApp Message'; wh['webhookId'] = str(uuid.uuid4())
wh['parameters'] = {"httpMethod": "POST", "path": "whatsapp-inbound", "responseMode": "onReceived", "options": {"allowedOrigins": "*"}}
settings = by['Settings']
readmsg = {"id": "", "name": "Read Message", "type": "n8n-nodes-base.code", "typeVersion": 2, "parameters": {"jsCode": r"""// WhatsApp Cloud API style payload -> one clean lead
const b = $json.body || {};
const m = b.entry?.[0]?.changes?.[0]?.value?.messages?.[0];
// Delivery/read status callbacks arrive on the same webhook with no message: stop here.
if (!m || m.type !== 'text' || !m.text?.body) return [];
const c = b.entry?.[0]?.changes?.[0]?.value?.contacts?.[0] || {};
return [{ json: {
  name: c.profile?.name || 'there',
  phone: m.from || '',
  email: '',
  message: m.text?.body || '',
  receivedAt: new Date().toISOString(),
  channel: 'whatsapp'
} }];"""}}
ai = by['AI Triage & Draft']
ai['parameters']['jsonBody'] = ai['parameters']['jsonBody'].replace("a warm, short email reply, max 110 words", "a warm, short WhatsApp reply, max 60 words, no subject line")
read = by['Read AI Answer']; read['parameters']['jsCode'] = read['parameters']['jsCode'].replace("$('Is Valid?')", "$('Read Message')")
send = {"id": "", "name": "Send WhatsApp Reply", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "parameters": {
  "method": "POST", "url": "http://whatsapp.sandbox/v1/messages", "sendBody": True, "specifyBody": "json",
  "jsonBody": "={{ JSON.stringify({ messaging_product: 'whatsapp', to: $json.phone, type: 'text', text: { body: $json.reply } }) }}", "options": {}}}
notspam = by['Not Spam?']   # spam gets an empty reply, so never send it
nodes = [wh, settings, readmsg, ai, read, notspam, send]
names = ['WhatsApp Message','Settings','Read Message','AI Triage & Draft','Read AI Answer','Not Spam?','Send WhatsApp Reply']
for i, n in enumerate(nodes):
    n['id'] = str(uuid.uuid4()); n['position'] = [i*240, 300]
conns = {}
for a, b in zip(names, names[1:]):
    conns[a] = {"main": [[{"node": b, "type": "main", "index": 0}]]}
wf = {"name": "FrontDesk Flows – WhatsApp AI replies", "active": False, "nodes": nodes, "connections": conns, "settings": {"executionOrder": "v1"}}
json.dump(wf, open(os.path.join(sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__)), 'wa.json'),'w'), indent=1)
