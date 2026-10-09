#!/bin/bash
# Batch B studio, run after studio/v2/setup.sh and studio/v2/import.py (same STUDIO_DIR).
# Adds the WhatsApp/review sandbox endpoints, the cinematic recorder and renderer, music and SFX,
# and imports the four Batch B workflows (writes csvid, redactid, waid, revid into $STUDIO_DIR/n8n).
set -e
B="$(cd "$(dirname "$0")" && pwd)"
W=${STUDIO_DIR:-/home/claude/studio}; N="$W/n8n"; cd "$W"

# recorder + renderer + scenarios + reel scripts + committed panel screenshots
cp "$B"/{rec3.js,prep.py,cine_build.py,cine_render.js,cine.html,finalize.sh,story.py,music.py} .
mkdir -p scenarios reels2 takes4k work2 out2 audio/sfx
cp "$B"/scenarios/*.json scenarios/ && cp "$B"/reels2/*.json reels2/ && cp -r "$B"/takes4k/* takes4k/
chmod +x finalize.sh

# original music and sound effects (generated, no licensing needed)
for v in 0 1 2; do [ -f audio/music$v.wav ] || python3 music.py 60 $v audio/music$v.wav; done
for k in whoosh pop ding buzz tick; do [ -f audio/sfx/$k.wav ] || { python3 music.py 1 0 /tmp/sfx-seed.wav audio/sfx; break; }; done

# sandbox: WhatsApp API + review API endpoints and the demo chat page
grep -q " reviews.sandbox" /etc/hosts || echo "127.0.0.1 reviews.sandbox" >> /etc/hosts
cp "$B/server.py" sandbox/server.py && cp "$B/chat.html" sandbox/site/chat.html
pkill -f "sandbox/server.py" || true; (setsid nohup python3 sandbox/server.py > sandbox/server.log 2>&1 &)

# CSV lead log folder: restart n8n so it is allowed to write there (same env as studio/v2/setup.sh)
mkdir -p clinic-files
pkill -f "n8n start" || true; sleep 3
export N8N_USER_FOLDER=$W/n8n/data N8N_DIAGNOSTICS_ENABLED=false N8N_PERSONALIZATION_ENABLED=false N8N_VERSION_NOTIFICATIONS_ENABLED=false N8N_TEMPLATES_ENABLED=false N8N_SECURE_COOKIE=false N8N_RUNNERS_ENABLED=false N8N_RESTRICT_FILE_ACCESS_TO=$W/clinic-files
(cd n8n && setsid nohup npx n8n start > n8n.log 2>&1 &)
for i in $(seq 1 60); do curl -s -o /dev/null localhost:5678/healthz && break; sleep 2; done
curl -s -c "$N/cj" -H 'content-type: application/json' -d '{"emailOrLdapLoginId":"demo@frontdeskflows.test","password":"DemoPass123!"}' localhost:5678/rest/login > /dev/null

# build + import the four workflows, pointing them at the sandbox credentials and folders
mkdir -p "$W/workflows"
for b in redact csv wa rev; do python3 "$B/build_$b.py" "$B/../clinic-enquiry-ai-triage.json" "$W/workflows"; done
python3 - "$B" "$W" <<'EOF'
import json, os, subprocess, sys
B, W = sys.argv[1], sys.argv[2]; N = f'{W}/n8n'
def curl(*a): return subprocess.run(['curl', '-s', '-b', f'{N}/cj', *a], capture_output=True, text=True).stdout
creds = {c['type']: {'id': c['id'], 'name': c['name']} for c in json.loads(curl('localhost:5678/rest/credentials'))['data']}
for f, idf in (('redact.json', 'redactid'), ('csv.json', 'csvid'), ('wa.json', 'waid'), ('rev.json', 'revid')):
    w = json.load(open(f'{W}/workflows/{f}')); w['active'] = False
    for n in w['nodes']:
        p = n.get('parameters', {})
        if n['type'] == 'n8n-nodes-base.httpRequest' and p.get('authentication') == 'genericCredentialType':
            n['credentials'] = {p.get('genericAuthType', 'httpHeaderAuth'): creds[p.get('genericAuthType', 'httpHeaderAuth')]}
        if n['type'] == 'n8n-nodes-base.emailSend':
            n['credentials'] = {'smtp': creds['smtp']}
        if n['name'] == 'Settings':
            for a in n['parameters']['assignments']['assignments']:
                if a['name'] == 'llmBaseUrl': a['value'] = 'http://ai.sandbox/v1'
                if a['name'] == 'leadsCsvPath': a['value'] = f'{W}/clinic-files/leads.csv'
    r = json.loads(curl('-X', 'POST', 'localhost:5678/rest/workflows', '-H', 'content-type: application/json', '-d', json.dumps(w)))
    open(f'{N}/{idf}', 'w').write(r['data']['id']); print(f, r['data']['id'])
EOF
echo "Batch B studio ready. Record:  cd $W && python3 prep.py scenarios/t20-redact.json && node rec3.js scenarios/t20-redact.json"
echo "Render:  cd $W && python3 cine_build.py reels2/c20-redact.json && node cine_render.js c20-redact && ./finalize.sh c20-redact"
