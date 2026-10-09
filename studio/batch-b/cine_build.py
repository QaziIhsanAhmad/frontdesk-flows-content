"""Cinematic Reel builder. Usage: python3 cine_build.py reels2/<id>.json  -> work2/<id>/render.json + mix_norm.wav"""
import json, sys, os, re, subprocess, math, bisect
import numpy as np, soundfile as sf
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TTS = os.environ.get('TTS_DIR', os.path.join(os.environ.get('STUDIO_DIR', '/home/claude/studio'), 'tts'))
R = json.load(open(sys.argv[1]))
TAKE = os.path.join(HERE, 'takes4k', R['take'])
M = json.load(open(os.path.join(TAKE, 'meta.json')))
WORK = os.path.join(HERE, 'work2', R['id']); os.makedirs(WORK, exist_ok=True)
FPS, SR = 30, 44100
mk, nt, rects = M['marks'], M['nodeTimes'], M['rects']
nl, fl = M['nlog'], M['flog']

ed = (M['mails'][0]['at'] - (M['mails'][0]['at'] - M['mails'][0]['rel']) - mk['submit']) if M.get('mails') else None
TOK = {'{EMAIL}': ('%.1f' % ed) if ed is not None else '?', '{FORM}': '%.1f' % (mk['form_reply'] - mk['submit'])}
def sub_(o):
    if isinstance(o, str):
        for a, b in TOK.items(): o = o.replace(a, b)
        return o
    if isinstance(o, list): return [sub_(x) for x in o]
    if isinstance(o, dict): return {k: sub_(v) for k, v in o.items()}
    return o
R = sub_(R)

from kokoro_onnx import Kokoro
_k = None
def tts(text, name):
    global _k
    f = os.path.join(WORK, name + '.wav'); clean = re.sub(r'[*]', '', text)
    key = clean + '|' + R.get('voice', 'af_heart') + '|' + str(R.get('speed', 1.15)) + '|' + R.get('lang', 'en-us')
    if not (os.path.exists(f) and os.path.exists(f + '.txt') and open(f + '.txt').read() == key):
        if _k is None: _k = Kokoro(os.path.join(TTS, 'kokoro-v1.0.onnx'), os.path.join(TTS, 'voices-v1.0.bin'))
        s, sr = _k.create(clean, voice=R.get('voice', 'af_heart'), speed=R.get('speed', 1.15), lang=R.get('lang', 'en-us'))
        idx = np.where(np.abs(s) > 0.01)[0]; s = s[max(0, idx[0] - 600): idx[-1] + 2400]
        sf.write(f, s, sr); open(f + '.txt', 'w').write(key)
    x, sr = sf.read(f); return f, len(x) / sr

def frame_at(log, t, sub):
    i = max(0, bisect.bisect_right(log, t) - 1); return 'file://' + os.path.join(TAKE, sub, '%05d.jpg' % i)
def ctr(n): x, y, w, h = rects[n]; return [x + w / 2, y + h / 2]

PATH = R.get('path', []); FROM = R.get('from', {})
scenes = []; T = 0.0
for i, sc in enumerate(R['scenes']):
    sc = dict(sc); vo = None
    if sc.get('say') and R.get('vo', True):
        vo = tts(sc['say'], f's{i}')
    dur = sc.get('dur') or max(sc.get('min', 1.5), (vo[1] + sc.get('pad', 0.3)) if vo else sc.get('min', 1.5))
    sc.update(start=T, end=T + dur, vo=vo); scenes.append(sc); T += dur
TOTAL = T

t_pre = mk['canvas'] + 0.4
t_end = mk['done'] + 0.8
for sc in scenes:
    dur = sc['end'] - sc['start']
    if sc['type'] in ('canvas', 'hook'):
        nodes = sc.get('nodes', PATH)
        lead, tail = sc.get('lead', 0.25), sc.get('tail', 0.9)
        per = (dur - lead - tail) / max(1, len(nodes) - 1) if len(nodes) > 1 else 0
        arrive = {nodes[0]: lead}; edges = []
        for k in range(1, len(nodes)):
            b = nodes[k]; a = FROM.get(b, nodes[k - 1])
            if a not in arrive: a = nodes[k - 1]
            ax, ay, aw, ah = rects[a]; bx, by, bw, bh = rects[b]
            p0 = [ax + aw, ay + ah / 2]; p3 = [bx, by + bh / 2]; dx = max(80, (p3[0] - p0[0]) * 0.5)
            t1 = lead + k * per
            edges.append({'p': [p0, [p0[0] + dx, p0[1]], [p3[0] - dx, p3[1]], p3], 't0': arrive[a] + (0.05 if a != nodes[k - 1] else 0), 't1': t1})
            arrive[b] = t1
        if sc.get('edgesFromStart'): pass
        sim = set(R.get('sim', []))
        sc['edges'] = edges if not sc.get('noFlow') else []
        sc['glow'] = [] if sc.get('noFlow') else [{'r': rects[n], 't': arrive[n], 'sim': n in sim} for n in nodes]
        sc['steps'] = [{'i': j + 1 + sc.get('stepOffset', 0), 't': arrive[s_['node']] + sc.get('stepDelay', 0.0), 'title': s_['title'], 'sub': s_.get('sub', '')} for j, s_ in enumerate(sc.get('stepsCfg', []))]
        W = sc.get('camW', 760); rot = sc.get('rot', 0)
        if sc.get('camMode') == 'overview':
            xs = [rects[n][0] for n in rects]; xe = [rects[n][0] + rects[n][2] for n in rects]
            ys = [rects[n][1] for n in rects]; ye = [rects[n][1] + rects[n][3] for n in rects]
            cx, cy = (min(xs) + max(xe)) / 2, (min(ys) + max(ye)) / 2
            w0 = sc.get('camW', (max(xe) - min(xs)) * 1.08)
            keys = [[0, cx, cy, w0, rot], [dur, cx, cy, w0 * sc.get('push', 0.9), -rot]]
        else:
            keys = [[0] + ctr(nodes[0]) + [W * 1.15, rot]]
            for n in nodes: keys.append([arrive[n]] + ctr(n) + [W, rot * (-1 if len(keys) % 2 else 1)])
            keys.append([dur] + ctr(nodes[-1]) + [W * sc.get('endZoom', 1.0), 0])
        for kk in keys:  # keep window within the 3840x2400 frame
            w = kk[3]; h = w * 1920 / 1080
            if h > 2400: kk[3] = w = 2400 * 1080 / 1920; h = 2400
            kk[1] = min(max(kk[1], w / 2 + 30), 3840 - w / 2); kk[2] = min(max(kk[2], h / 2), 2400 - h / 2)
        sc['cam'] = keys
        last = max(arrive.values()) if arrive else 0
        mode = sc.get('src', 'run')
        if mode == 'end': sc['srcT'] = [(99, t_end)]
        elif mode == 'pre': sc['srcT'] = [(99, t_pre)]
        else: sc['srcT'] = [(last + 0.05, t_pre), (99, t_end)]
        if sc.get('trigger'):
            tr = sc['trigger']; tr.setdefault('flyAt', max(0.4, lead - 0.5)); tr['to'] = ctr(nodes[0])
        if sc.get('result'):
            r = sc['result']; r.setdefault('at', last + 0.25); r['from'] = ctr(r.get('fromNode', nodes[-1]))
            if r.get('mail', True) and M.get('mails') and not r.get('body'):
                m = M['mails'][r.get('mailIndex', 0)]
                r.update(t1=r.get('t1') or m['subject'], t2=r.get('t2') or ('to ' + m['to']), body=m['text'].strip())
    if sc['type'] == 'form':
        a, b = mk['form_start'] + sc.get('skip', 0.2), mk['form_reply'] + sc.get('tailExtra', 0.7)
        sc['src_map'] = (a, b)
        sc['tapAt'] = (mk['submit'] - a) / (b - a) * dur
        x, y, w, h = M['sendRect']; pw = sc.get('pw', 780) - 28; s = pw / 1080
        sc['tapXY'] = [sc.get('px', 150) + 14 + (x + w / 2) * s, sc.get('py', 560) + 14 + (y + h / 2) * s]
    if sc['type'] == 'panel':
        im = Image.open(os.path.join(TAKE, sc['img'])); x0, y0, x1, y1 = sc['crop']
        c = im.crop((x0, y0, x1, y1)); p = os.path.join(WORK, 'panel_%d.png' % int(sc['start'] * 100)); c.save(p)
        z = 1080 / (x1 - x0); top = sc.get('top', 600)
        sc['img'] = 'file://' + p; sc['zoom'] = [[0, z * 1.0, 0, top], [dur, z * 1.06, -1080 * 0.03, top - 20]]
        if sc.get('hlSrc'):
            hx0, hy0, hx1, hy1 = sc['hlSrc']; sc['hl'] = [hx0 - x0, hy0 - y0, hx1 - hx0, hy1 - hy0]

# subtitles
subs = []
for sc in scenes:
    if not sc.get('vo'): continue
    words = sc['say'].split(); chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(' '.join(cur)) > 24 or (re.search(r'[.?!,:]$', w) and len(' '.join(cur)) > 10): chunks.append(' '.join(cur)); cur = []
    if cur: chunks.append(' '.join(cur))
    tot = sum(len(c) for c in chunks); t = sc['start'] + 0.08
    for c in chunks:
        d = sc['vo'][1] * len(c) / tot
        html = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', c.replace('&', '&amp;').replace('<', '&lt;')).replace('*', '')
        subs.append({'s': t, 'e': t + d, 'html': html}); t += d

frames = []
for i in range(int(round(TOTAL * FPS))):
    t = i / FPS; sc = next((s for s in scenes if s['start'] <= t < s['end']), scenes[-1]); lt = t - sc['start']
    nsrc = fsrc = None
    if sc['type'] in ('canvas', 'hook'):
        st = next(v for (lim, v) in sc['srcT'] if lt < lim); nsrc = frame_at(nl, st, 'nframes')
    if sc['type'] == 'form':
        a, b = sc['src_map']; fsrc = frame_at(fl, a + (b - a) * lt / (sc['end'] - sc['start']), 'fframes')
    frames.append({'T': t, 'nsrc': nsrc, 'fsrc': fsrc})

# cover scene: whole path lit up, overview camera, headline
cover = None
if PATH:
    xs = [rects[n][0] for n in PATH]; xe = [rects[n][0] + rects[n][2] for n in PATH]
    ys = [rects[n][1] for n in PATH]; ye = [rects[n][1] + rects[n][3] for n in PATH]
    cx, cy = (min(xs) + max(xe)) / 2, (min(ys) + max(ye)) / 2
    w0 = R.get('coverW') or min((max(xe) - min(xs)) * R.get('coverZoom', 0.5), 1150)
    sim = set(R.get('sim', []))
    cedges = []
    for k in range(1, len(PATH)):
        b = PATH[k]; a = FROM.get(b, PATH[k - 1])
        ax, ay, aw, ah = rects[a]; bx, by, bw, bh = rects[b]
        p0 = [ax + aw, ay + ah / 2]; p3 = [bx, by + bh / 2]; dx = max(80, (p3[0] - p0[0]) * 0.5)
        cedges.append({'p': [p0, [p0[0] + dx, p0[1]], [p3[0] - dx, p3[1]], p3], 't0': -2, 't1': -1})
    fx = R.get('coverFocus', PATH[len(PATH) // 2]); fcx, fcy = ctr(fx)
    cover = {'type': 'canvas', 'start': 0, 'end': 10, 'edges': cedges, 'glow': [{'r': rects[n], 't': -1, 'sim': n in sim} for n in PATH],
             'cam': [[0, fcx, fcy - 230, w0, 0], [10, fcx, fcy - 230, w0, 0]], 'lines': R.get('cover', 'FrontDesk Flows').split('|'),
             'ksize': R.get('coverSize', 124), 'ktop': 300, 'steps': [], 'noBadge': False, 'particles': 1}
    cover['cam'][0][1] = cover['cam'][1][1] = min(max(fcx, w0 / 2 + 30), 3840 - w0 / 2)
    hh = w0 * 1920 / 1080
    for kk in cover['cam']: kk[2] = min(max(kk[2], hh / 2 + 70), 2200 - hh / 2)
D = {'cover': cover, 'coverSrc': frame_at(nl, t_end, 'nframes'), 'style': R.get('style', {}), 'sched': [{k: v for k, v in s.items() if k not in ('vo', 'srcT', 'src_map')} for s in scenes], 'total': TOTAL, 'subs': subs, 'noSubs': R.get('noSubs', False)}
json.dump({'D': D, 'frames': frames}, open(os.path.join(WORK, 'render.json'), 'w'))

# audio
mix = np.zeros((int((TOTAL + 0.3) * SR), 2))
def place(x, sr, t, g=1.0):
    if sr != SR: x = np.interp(np.linspace(0, len(x) - 1, int(len(x) * SR / sr)), np.arange(len(x)), x)
    if x.ndim == 1: x = np.stack([x, x], 1)
    i = int(t * SR); j = min(len(mix), i + len(x))
    if j > i: mix[i:j] += x[:j - i] * g
vo_mask = np.zeros(len(mix))
for sc in scenes:
    if sc.get('vo'):
        x, sr = sf.read(sc['vo'][0]); place(x, sr, sc['start'] + 0.06, 1.0)
        i = int((sc['start'] + 0.06) * SR); vo_mask[i:i + int(len(x) * SR / sr)] = 1
SFX = {k: sf.read(os.path.join(HERE, 'audio/sfx', k + '.wav'))[0] for k in ('whoosh', 'pop', 'ding', 'buzz', 'tick')}
for n, sc in enumerate(scenes):
    if n: place(SFX['whoosh'], SR, max(0, sc['start'] - 0.12), 0.45)
    for g_ in sc.get('glow', []): place(SFX['tick'], SR, sc['start'] + g_['t'], 0.9)
    for s_ in sc.get('steps', []): place(SFX['pop'], SR, sc['start'] + s_['t'], 0.3)
    if sc.get('result'): place(SFX['ding'], SR, sc['start'] + sc['result']['at'], 0.6)
    if sc['type'] == 'form' and sc.get('tapAt') is not None: place(SFX['pop'], SR, sc['start'] + sc['tapAt'], 0.5)
    if sc['type'] == 'ba': place(SFX['buzz'], SR, sc['start'] + 0.1, 0.5); place(SFX['ding'], SR, sc['start'] + sc.get('afterAt', 0.9), 0.4)
mus, _ = sf.read(os.path.join(HERE, 'audio', 'music%d.wav' % R.get('music', 0)))
mus = np.concatenate([mus] * int(math.ceil(len(mix) / len(mus))))[:len(mix)]
k = int(0.15 * SR); sm = np.convolve(vo_mask, np.ones(k) / k, mode='same')
base = R.get('musicLevel', 0.32 if R.get('vo', True) else 0.55)
gain = base - (base * 0.6) * sm; fo = int(0.8 * SR); gain[-fo:] *= np.linspace(1, 0, fo)
mix += mus * gain[:, None]; mix = np.tanh(mix * 1.1) / 1.1
wav = os.path.join(WORK, 'mix.wav'); sf.write(wav, mix, SR)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', wav, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '44100', os.path.join(WORK, 'mix_norm.wav')], check=True)
print(json.dumps({'id': R['id'], 'total': round(TOTAL, 2), 'scenes': [(s['type'], round(s['start'], 1), round(s['end'], 1)) for s in scenes], 'email': TOK['{EMAIL}']}))
