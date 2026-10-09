import json, time, os, http.server
from aiosmtpd.controller import Controller
from email import message_from_bytes
from email.policy import default

D = '/home/claude/sandbox'


def mode():
    try:
        return json.load(open(D + '/ai_mode.json'))
    except Exception:
        return {'mode': 'normal'}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ct='application/json'):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('content-type', ct)
        self.send_header('access-control-allow-origin', '*')
        self.send_header('content-length', len(b))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        host = self.headers.get('host', '')
        if 'harbourline' in host and self.path.startswith('/api/bookings'):
            return self._send(200, json.dumps({'date': 'tomorrow', 'bookings': [
                {'name': 'Olivia Brown', 'email': 'olivia.brown@example.com', 'time': '09:30', 'service': 'Sports massage (60 min)'},
                {'name': 'Daniel Hughes', 'email': 'daniel.hughes@example.com', 'time': '14:30', 'service': 'Physio follow-up (30 min)'},
                {'name': 'Grace Wilson', 'email': 'grace.wilson@example.com', 'time': '16:00', 'service': 'First assessment (45 min)'}]}))
        if 'harbourline' in host and self.path.startswith('/api/wa_last'):
            try: return self._send(200, open(D + '/wa_last.json').read())
            except Exception: return self._send(200, '{}')
        if 'harbourline' in host:
            p = self.path.split('?')[0]
            p = '/index.html' if p == '/' else p
            f = D + '/site' + p
            if os.path.exists(f):
                ct = 'text/html' if f.endswith('.html') else ('font/woff2' if f.endswith('woff2') else 'application/octet-stream')
                return self._send(200, open(f, 'rb').read(), ct)
        self._send(404, '{}')

    def do_POST(self):
        n = int(self.headers.get('content-length', 0))
        body = self.rfile.read(n)
        host = self.headers.get('host', '')
        if 'ai.sandbox' in host:
            m = mode()
            time.sleep(m.get('delay', 1.2))
            open(D + '/ai_last.json', 'wb').write(body)
            if m['mode'] == 'outage':
                return self._send(503, '{"error":{"message":"Service temporarily unavailable"}}')
            content = m.get('raw') if m['mode'] == 'badjson' else json.dumps(m.get('answer', {}))
            return self._send(200, json.dumps({"id": "chatcmpl-demo", "object": "chat.completion", "model": "demo-sandbox",
                                               "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]}))
        if 'whatsapp.sandbox' in host:
            rec = json.loads(body or b'{}'); rec['at'] = time.time()
            json.dump(rec, open(D + '/wa_last.json', 'w'))
            return self._send(200, json.dumps({"messaging_product": "whatsapp", "messages": [{"id": "wamid.DEMO%d" % int(time.time())}]}))
        self._send(200, '{"status":"ok"}')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('access-control-allow-origin', '*')
        self.send_header('access-control-allow-headers', '*')
        self.send_header('access-control-allow-methods', 'POST,GET,OPTIONS')
        self.end_headers()


class Sink:
    async def handle_DATA(self, server, session, env):
        msg = message_from_bytes(env.content, policy=default)
        body = msg.get_body(preferencelist=('plain', 'html'))
        rec = {'from': str(msg['from']), 'to': str(msg['to']), 'subject': str(msg['subject']), 'date': str(msg['date']),
               'text': body.get_content() if body else '', 'at': time.time()}
        json.dump(rec, open(f"{D}/mail/{int(time.time() * 1000)}.json", 'w'))
        return '250 OK'


c = Controller(Sink(), hostname='127.0.0.1', port=1025)
c.start()
http.server.ThreadingHTTPServer(('0.0.0.0', 80), H).serve_forever()
