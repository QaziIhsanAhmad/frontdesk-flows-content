"""Build a FrontDesk Flows Reel from a recorded take + a reel script.
Usage: python3 build.py reels/<id>.json   -> out/<id>.mp4, out/<id>_cover.jpg"""
import json, sys, os, re, subprocess, math, bisect
import numpy as np, soundfile as sf
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(sys.argv[1]))
TAKE = os.path.join(HERE, 'takes', R['take'])
M = json.load(open(os.path.join(TAKE, 'meta.json')))
_mk = M['marks']
_al = None
if M.get('mails') and len(M['mails']) > 1: _al = M['mails'][1]['rel'] - _mk['submit']
_tok = {'{ALERT}': ('%.1f' % _al) if _al is not None else '?', '{EMAIL}': '%.1f' % (M['mails'][0]['at'] - 0 - (0)) if False else None}
_ed = None
if M.get('mails'):
    _t0 = M['mails'][0]['at'] - M['mails'][0]['rel']
    _ed = M['mails'][0]['rel'] - _mk['submit']
_al = None
if M.get('mails') and len(M['mails']) > 1: _al = M['mails'][1]['rel'] - _mk['submit']
_tok = {'{ALERT}': ('%.1f' % _al) if _al is not None else '?', '{EMAIL}': ('%.1f' % _ed) if _ed is not None else '?', '{FORM}': '%.1f' % (_mk['form_reply'] - _mk['submit'])}
def _sub(o):
    if isinstance(o, str):
        for a, b in _tok.items(): o = o.replace(a, b)
        return o
    if isinstance(o, list): return [_sub(x) for x in o]
    if isinstance(o, dict): return {k: _sub(v) for k, v in o.items()}
    return o
R = _sub(R)
WORK = os.path.join(HERE, 'work', R['id']); os.makedirs(WORK, exist_ok=True)
OUTD = os.path.join(HERE, 'out'); os.makedirs(OUTD, exist_ok=True)
FPS = 30; SR = 44100
RATIO = 1920 / 1080 if R.get('layout') == 'bleed' else 980 / 1000

# ---------- voice ----------
from kokoro_onnx import Kokoro
_k = None
def tts(text, name):
    global _k
    f = os.path.join(WORK, name + '.wav')
    clean = re.sub(r'[*]', '', text)
    key = '%s|%s|%s' % (R.get('voice', 'af_heart'), R.get('speed', 1.12), clean)  # every synthesis input
    stale = not (os.path.exists(f) and os.path.exists(f + '.txt') and open(f + '.txt').read() == key)
    if stale:
        if _k is None: _k = Kokoro('/home/claude/tts/kokoro-v1.0.onnx', '/home/claude/tts/voices-v1.0.bin')
        s, sr = _k.create(clean, voice=R.get('voice', 'af_heart'), speed=R.get('speed', 1.12), lang='en-us')
        # trim silence
        idx = np.where(np.abs(s) > 0.01)[0]; s = s[max(0, idx[0] - 600): idx[-1] + 2400]
        sf.write(f, s, sr); open(f + '.txt', 'w').write(key)
    x, sr = sf.read(f)
    return f, len(x) / sr

# ---------- frames ----------
def frame_at(log, t, sub):
    i = max(0, bisect.bisect_right(log, t) - 1)
    return os.path.join(TAKE, sub, '%05d.jpg' % i)

nl, fl, mk, nt = M['nlog'], M['flog'], M['marks'], M['nodeTimes']
rects = M['rects']
def ctr(n): x, y, w, h = rects[n]; return x + w / 2, y + h / 2

scenes = []
T = 0.0
for i, sc in enumerate(R['scenes']):
    sc = dict(sc)
    vo = None
    if sc.get('say'):
        f, d = tts(sc['say'], f's{i}'); vo = (f, d)
    base = sc.get('min', 1.5)
    dur = max(base, (vo[1] + sc.get('pad', 0.35)) if vo else base)
    sc.update(start=T, end=T + dur, vo=vo)
    scenes.append(sc); T += dur
TOTAL = T

# ---------- per-scene derived data ----------
lead_frame = frame_at(nl, mk['done'] + 1.2, 'nframes')
for sc in scenes:
    dur = sc['end'] - sc['start']
    if sc['type'] == 'form':
        a, b = mk['form_start'] + 0.2, mk['form_reply'] + 0.6
        sc['src_map'] = (a, b)
        sc['tapAt'] = (mk['submit'] - a) / (b - a) * dur
        x, y, w, h = M['sendRect']; s = 676 / 1080
        sc['tapXY'] = [(x + w / 2) * s, (y + h / 2) * s]
    if sc['type'] == 'hook' and sc.get('canvas', True):
        runsc = next(x for x in R['scenes'] if x['type'] == 'run')
        path = runsc['path']; sim = set(runsc.get('sim', [])); n = len(path)
        first = 0.05; per = (dur - 0.5) / max(1, n - 1); arrive = {path[0]: first}; edges = []
        for k in range(1, n):
            b_ = path[k]; src = runsc.get('from', {}).get(b_, path[k - 1])
            t0 = arrive[src]; t1 = first + k * per
            ax, ay, aw, ah = rects[src]; bx, by, bw, bh = rects[b_]
            p0 = [ax + aw, ay + ah / 2]; p3 = [bx, by + bh / 2]; dx = max(60, (p3[0] - p0[0]) * 0.5)
            edges.append({'p': [p0, [p0[0] + dx, p0[1]], [p3[0] - dx, p3[1]], p3], 't0': t0, 't1': t1}); arrive[b_] = t1
        sc['edges'] = edges; sc['glow'] = [{'r': rects[nm], 't': arrive[nm], 'sim': nm in sim} for nm in path]
        xs = [rects[nm][0] for nm in path]; xe = [rects[nm][0] + rects[nm][2] for nm in path]
        ys = [rects[nm][1] for nm in path]; ye = [rects[nm][1] + rects[nm][3] for nm in path]
        cx, cy = (min(xs) + max(xe)) / 2, (min(ys) + max(ye)) / 2; w0 = max(xe) - min(xs) + 240
        HW = sc.get('camW', 980); keys = []
        for nm in path:
            x_, y_ = ctr(nm); keys.append([arrive[nm], x_, y_, HW])
        keys.insert(0, [0] + keys[0][1:])
        for kk in keys:
            w = kk[3]; h = w * RATIO
            kk[1] = min(max(kk[1], w / 2 + 60), 2560 - w / 2); kk[2] = min(max(kk[2], h / 2 + 60), 1600 - h / 2)
        sc['cam'] = keys
        sc['steps'] = []; sc['src_t'] = [(99, mk['done'] + 0.8)]
    if sc['type'] == 'run':
        path = sc['path']; sim = set(sc.get('sim', []))
        n = len(path); first = sc.get('lead', 0.5)
        per = (dur - first - sc.get('tail', 1.2)) / max(1, n - 1)
        arrive = {path[0]: first}
        edges = []
        for k in range(1, n):
            a_, b_ = path[k - 1], path[k]
            src = sc.get('from', {}).get(b_, a_)
            t0 = arrive[src] if src in arrive else first + (k - 1) * per
            t1 = first + k * per
            ax, ay, aw, ah = rects[src]; bx, by, bw, bh = rects[b_]
            p0 = [ax + aw, ay + ah / 2]; p3 = [bx, by + bh / 2]; dx = max(60, (p3[0] - p0[0]) * 0.5)
            edges.append({'p': [p0, [p0[0] + dx, p0[1]], [p3[0] - dx, p3[1]], p3], 't0': t0, 't1': t1})
            arrive[b_] = t1
        sc['edges'] = edges
        sc['glow'] = [{'r': rects[nm], 't': arrive[nm], 'sim': nm in sim} for nm in path]
        steps = []
        for j, st in enumerate(sc['steps']):
            steps.append({'i': j + 1, 't': arrive[st['node']], 'title': st['title'], 'sub': st.get('sub', ''), 'sim': st['node'] in sim})
        sc['stepsR'] = steps
        # camera keys
        W = sc.get('camW', 760); keys = [[0] + list(ctr(path[0])) + [W]]
        for nm in path:
            cx, cy = ctr(nm); keys.append([arrive[nm], cx, cy, W])
        xs = [rects[nm][0] for nm in rects]; xe = [rects[nm][0] + rects[nm][2] for nm in rects]
        ys = [rects[nm][1] for nm in rects]; ye = [rects[nm][1] + rects[nm][3] for nm in rects]
        ov = [(min(xs) + max(xe)) / 2, (min(ys) + max(ye)) / 2 + 20, max(xe) - min(xs) + 200]
        last = keys[-1]; keys.append([dur - 0.1, last[1] + 60, last[2], last[3] * 1.12])
        # clamp cam inside 2560x1600
        for kk in keys:
            w = kk[3]; h = w * RATIO
            kk[1] = min(max(kk[1], w / 2 + 60), 2560 - w / 2); kk[2] = min(max(kk[2], h / 2 + 60), 1600 - h / 2)
        sc['cam'] = keys
        # source frame timeline
        t_pre = mk['listening'] + 0.6
        t_mid = (nt[sc.get('midNode', 'Is Valid?') + ':success'] + 0.15) if (sc.get('midNode', 'Is Valid?') + ':success') in nt else mk['done'] + 0.8
        t_end = mk['done'] + 0.8
        aiN = sc.get('waitNode', 'AI Triage & Draft')
        sc['src_t'] = [(first - 0.01, t_pre), (arrive.get(aiN, 99) + 0.4, t_mid), (99, t_end)]
    if sc['type'] == 'split':
        a = mk['submit'] - sc.get('preRoll', 1.0); b2 = mk['done'] + sc.get('postRoll', 0.8)
        sc['src_map'] = (a, b2)
        nodes = sc.get('ncamNodes') or [nm for nm in rects]; xs = [rects[n][0] for n in nodes]; xe = [rects[n][0] + rects[n][2] for n in nodes]
        ys = [rects[n][1] for n in nodes]; ye = [rects[n][1] + rects[n][3] for n in nodes]
        w = max(xe) - min(xs) + 120; sc['ncam'] = [(min(xs) + max(xe)) / 2, (min(ys) + max(ye)) / 2, w]
    if sc['type'] == 'panel':
        im = Image.open(os.path.join(TAKE, sc['img']))
        x0, y0, x1, y1 = sc['crop']
        c = im.crop((x0, y0, x1, y1)); s = 1000 / c.width
        c = c.resize((1000, int(c.height * s)), Image.LANCZOS)
        p = os.path.join(WORK, 'panel_%s.png' % sc['img'][:-4]); c.save(p)
        sc['imgPath'] = p
        if sc.get('hlSrc'):
            hx0, hy0, hx1, hy1 = sc['hlSrc']; sc['hl'] = [(hx0 - x0) * s, (hy0 - y0) * s, (hx1 - hx0) * s, (hy1 - hy0) * s]
    if sc['type'] == 'result':
        mails = M['mails']; which = sc.get('mailIndex', 0)
        m = mails[which] if mails else {'subject': '(no email sent)', 'text': '', 'to': '', 'from': ''}
        delay = m['rel'] - mk['submit'] if mails else None
        sc['mail'] = {'subject': m['subject'], 'text': m['text'].strip(), 'to': m['to'], 'fromName': sc.get('fromName', 'Harbourline Physio'),
                      'when': sc.get('when', 'just now'), 'note': sc.get('note', "Sent by n8n's Email node · demo inbox")}
        sc['delay'] = delay
        if sc.get('listAll'):
            sc['list'] = [{'to': x['to'], 'subject': x['subject'], 'text': x['text']} for x in mails]

M['delays'] = {'email_after_submit': (M['mails'][0]['rel'] - mk['submit']) if M['mails'] else None, 'form_reply': mk['form_reply'] - mk['submit']}

# ---------- subtitles ----------
subs = []
for sc in scenes:
    if not sc.get('vo'): continue
    text = sc['say']; d = sc['vo'][1]
    words = text.split(); chunks = []; cur = []
    for w in words:
        cur.append(w)
        if len(' '.join(cur)) > 26 or re.search(r'[.?!,:]$', w) and len(' '.join(cur)) > 12:
            chunks.append(' '.join(cur)); cur = []
    if cur: chunks.append(' '.join(cur))
    total = sum(len(c) for c in chunks); t = sc['start'] + 0.1
    for c in chunks:
        dd = d * len(c) / total
        html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', c.replace('&', '&amp;'))
        if c.count('*') % 2: html = html.replace('*', '')
        subs.append({'s': t, 'e': t + dd, 'html': html}); t += dd

# ---------- per frame sources ----------
frames = []
N = int(round(TOTAL * FPS))
for i in range(N):
    t = i / FPS; sc = next((s for s in scenes if s['start'] <= t < s['end']), scenes[-1]); lt = t - sc['start']
    fs = ns = None
    if sc['type'] == 'form':
        a, b = sc['src_map']; ft = a + (b - a) * lt / (sc['end'] - sc['start']); fs = frame_at(fl, ft, 'fframes')
    rt = None
    if sc['type'] in ('run', 'hook'):
        st = next(v for (lim, v) in sc['src_t'] if lt < lim); ns = frame_at(nl, st, 'nframes')
    if sc['type'] == 'split':
        a, b2 = sc['src_map']; real = a + (b2 - a) * lt / (sc['end'] - sc['start'])
        fs = frame_at(fl, real, 'fframes'); ns = frame_at(nl, real, 'nframes'); rt = real - mk['submit']
    frames.append({'T': t, 'fsrc': fs and 'file://' + fs, 'nsrc': ns and 'file://' + ns, 'realT': rt})

def jsafe(sc):
    d = {k: v for k, v in sc.items() if k not in ('vo',)}
    if sc['type'] == 'run':
        d.update(edges=sc['edges'], glow=sc['glow'], steps=sc['stepsR'], cam=sc['cam'])
    if sc['type'] == 'hook':
        d.update(edges=sc['edges'], glow=sc['glow'], steps=[], cam=sc['cam'])
    if sc['type'] == 'panel': d['img'] = 'file://' + sc['imgPath']
    return d

# mini image for CTA = final canvas crop
im = Image.open(lead_frame); xs = [r[0] for r in rects.values()]; xe = [r[0] + r[2] for r in rects.values()]
ys = [r[1] for r in rects.values()]; ye = [r[1] + r[3] for r in rects.values()]
mini = im.crop((int(min(xs) - 60), int(min(ys) - 60), int(max(xe) + 140), int(max(ye) + 90))); mini_p = os.path.join(WORK, 'mini.jpg'); mini.save(mini_p, quality=92); mini.save(os.path.join(WORK, 'coverbg.jpg'), quality=92)  # cover2.js background
D = {'cfg': R, 'sched': [jsafe(s) for s in scenes], 'total': TOTAL, 'subs': subs, 'bg': 'file://' + lead_frame, 'mini': 'file://' + mini_p}
json.dump({'D': D, 'frames': frames}, open(os.path.join(WORK, 'render.json'), 'w'))

# ---------- audio mix ----------
mix = np.zeros((int((TOTAL + 0.5) * SR), 2))
def place(x, sr, t, g=1.0):
    if sr != SR:
        x = np.interp(np.linspace(0, len(x) - 1, int(len(x) * SR / sr)), np.arange(len(x)), x)
    if x.ndim == 1: x = np.stack([x, x], 1)
    i = int(t * SR); j = min(len(mix), i + len(x)); mix[i:j] += x[:j - i] * g
vo_mask = np.zeros(len(mix))
for sc in scenes:
    if sc.get('vo'):
        x, sr = sf.read(sc['vo'][0]); place(x, sr, sc['start'] + 0.08, 1.0)
        i = int((sc['start'] + 0.08) * SR); vo_mask[i:i + int(len(x) * SR / sr)] = 1
SFX = {k: sf.read(os.path.join(HERE, 'audio/sfx', k + '.wav'))[0] for k in ('whoosh', 'pop', 'ding', 'buzz', 'tick')}
for k, sc in enumerate(scenes):
    if k: place(SFX['whoosh'], SR, max(0, sc['start'] - 0.12), 0.5)
    if sc['type'] == 'run':
        for st in sc['stepsR']: place(SFX['pop'], SR, sc['start'] + st['t'], 0.35)
    if sc['type'] == 'result': place(SFX['ding'], SR, sc['start'] + 0.15, 0.6)
    if sc['type'] == 'form' and sc.get('tapAt') is not None: place(SFX['tick'], SR, sc['start'] + sc['tapAt'], 1.0)
    if sc['type'] == 'ba': place(SFX['buzz'], SR, sc['start'] + 0.15, 0.6); place(SFX['pop'], SR, sc['start'] + sc.get('afterAt', 1.2), 0.5)
    if sc['type'] == 'hook': place(SFX['pop'], SR, sc['start'] + 0.08, 0.5)
mus, msr = sf.read(os.path.join(HERE, 'audio', 'music%d.wav' % R.get('music', 0)))
reps = int(math.ceil(len(mix) / len(mus))); mus = np.concatenate([mus] * reps)[:len(mix)]
# duck under voice (smoothed)
k = int(0.15 * SR); sm = np.convolve(vo_mask, np.ones(k) / k, mode='same')
gain = 0.30 - 0.18 * sm
fo = int(1.0 * SR); gain[-fo:] *= np.linspace(1, 0, fo)
mix += mus * gain[:, None]
mix = np.tanh(mix * 1.1) / 1.1
wav = os.path.join(WORK, 'mix.wav'); sf.write(wav, mix, SR)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', wav, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '44100', os.path.join(WORK, 'mix_norm.wav')], check=True)
print(json.dumps({'id': R['id'], 'total': round(TOTAL, 2), 'scenes': [(s['type'], round(s['start'], 2), round(s['end'], 2)) for s in scenes], 'delays': M['delays']}))
