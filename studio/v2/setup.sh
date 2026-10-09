#!/bin/bash
# Rebuild the FrontDesk Flows v2 recording studio on a fresh Linux box (cloud session).
set -e
V2="$(cd "$(dirname "$0")" && pwd)"
W=${STUDIO_DIR:-/home/claude/studio}; mkdir -p "$W" && cd "$W"
cp -r "$V2"/{rec2.js,build.py,stage2.html,render2.js,cover2.html,cover2.js,music.py,prep.py,story.html,storycard.js,scenarios,reels} .
# committed sources use /home/claude/{n8n,sandbox,tts}; point them at this studio folder
[ "$W" = /home/claude ] || sed -i "s#/home/claude/\(n8n\|sandbox\|tts\)#$W/\1#g" rec2.js build.py prep.py scenarios/*.json
# Playwright + fonts
[ -d node_modules/playwright ] || npm i --no-audit --no-fund playwright@1.56.1 @fontsource/poppins@5.1.0
# n8n (xlsx override: cdn.sheetjs.com is not reachable)
if [ ! -x n8n/node_modules/.bin/n8n ]; then
  mkdir -p n8n && (cd n8n && npm init -y >/dev/null && node -e 'const p=require("./package.json");p.overrides={xlsx:"0.18.5"};require("fs").writeFileSync("package.json",JSON.stringify(p))' && npm i --no-audit --no-fund n8n@1.95.3)
fi
pip install --break-system-packages -q kokoro-onnx soundfile aiosmtpd numpy pillow
mkdir -p tts && for f in kokoro-v1.0.onnx voices-v1.0.bin; do [ -f tts/$f ] || curl -sSL -o tts/$f https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f; done
# sandbox hosts + servers
for h in ai.sandbox harbourlinephysio.test whatsapp.sandbox; do grep -q " $h" /etc/hosts || echo "127.0.0.1 $h" >> /etc/hosts; done
mkdir -p sandbox/mail && cp -r "$V2"/sandbox/* sandbox/ && cp node_modules/@fontsource/poppins/files/poppins-latin-{500,600,700}-normal.woff2 sandbox/site/
[ "$W" = /home/claude ] || sed -i "s#/home/claude/sandbox#$W/sandbox#g" sandbox/server.py
(setsid nohup python3 sandbox/server.py > sandbox/server.log 2>&1 &)
# n8n
export N8N_USER_FOLDER=$W/n8n/data N8N_DIAGNOSTICS_ENABLED=false N8N_PERSONALIZATION_ENABLED=false N8N_VERSION_NOTIFICATIONS_ENABLED=false N8N_TEMPLATES_ENABLED=false N8N_SECURE_COOKIE=false N8N_RUNNERS_ENABLED=false
(cd n8n && setsid nohup npx n8n start > n8n.log 2>&1 &)
for i in $(seq 1 60); do curl -s -o /dev/null localhost:5678/healthz && break; sleep 2; done
echo "Studio ready in $W. Next: create the n8n owner + credentials + import workflows (see import.py)."
