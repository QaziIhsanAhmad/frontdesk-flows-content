"""Make a Story (1080x1920, 6-10s, music only) from a built cinematic reel.
Usage: python3 story.py <reel_id> <story_id> <kind:preview|tip|sample> "<line1|line2>" ["<sub>"] [scene_index]
Writes work2/<story_id>/render.json + mix_norm.wav, then render with: node cine_render.js <story_id>"""
import json, sys, os, subprocess, math
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__))
rid, sid, kind, lines = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split('|')
subl = sys.argv[5] if len(sys.argv) > 5 else ''
src = json.load(open(os.path.join(HERE, 'work2', rid, 'render.json')))
D, frames = src['D'], src['frames']
canv = [s for s in D['sched'] if s['type'] == 'canvas' and s.get('edges')]
sc = dict(canv[int(sys.argv[6]) if len(sys.argv) > 6 else 0])
dur0 = sc['end'] - sc['start']
# frames of that scene
fr = [f for f in frames if sc['start'] <= f['T'] < sc['end']]
STORY_DUR = min(max(dur0, 6.0), 9.0) if kind != 'sample' else 7.0
speed = dur0 / STORY_DUR
sc.update(start=0, end=STORY_DUR)
for e in sc['edges']: e['t0'] /= speed; e['t1'] /= speed
for g in sc['glow']: g['t'] /= speed
sc['cam'] = [[k[0] / speed] + k[1:] for k in sc['cam']]
sc['steps'] = [] if kind != 'preview' else [dict(s, t=s['t'] / speed) for s in sc.get('steps', [])]
sc['lines'] = lines; sc['ksize'] = 92; sc['ktop'] = 300 if kind != 'preview' else 1240
sc['stepTop'] = 280; sc['stepSize'] = 70
sc.pop('result', None); sc.pop('trigger', None)
nf = int(round(STORY_DUR * 30)); out = []
for i in range(nf):
    t = i / 30; f = fr[min(len(fr) - 1, int(t * speed * 30))]
    out.append({'T': t, 'nsrc': f['nsrc'], 'fsrc': None})
end = {'type': 'cta', 'start': STORY_DUR, 'end': STORY_DUR + 2.2, 'lines': (['Watch the', '[a]full run ↓[/a]'] if kind == 'preview' else ['Want this', '[a]workflow?[/a]']),
       'button': 'Tap ▸ new Reel on our profile' if kind == 'preview' else 'DM “FLOW” for a free sample', 'small': subl or '@frontdeskflows', 'noBadge': True, 'ktop': 560, 'by': 1000}
last = out[-1]['nsrc']
for i in range(int(2.2 * 30)): out.append({'T': STORY_DUR + i / 30, 'nsrc': last, 'fsrc': None})
end['cam'] = sc['cam'][-1:] + [[2.2] + sc['cam'][-1][1:]]; end['dim'] = 0.35; end['blur'] = 6; end['particles'] = 1
end['cam'] = [[0] + sc['cam'][-1][1:], [2.2] + sc['cam'][-1][1:]]
WD = os.path.join(HERE, 'work2', sid); os.makedirs(WD, exist_ok=True)
json.dump({'D': {'style': D['style'], 'sched': [sc, end], 'total': STORY_DUR + 2.2, 'subs': []}, 'frames': out}, open(os.path.join(WD, 'render.json'), 'w'))
# music only + ticks
SR = 44100; total = STORY_DUR + 2.2
mus, _ = sf.read(os.path.join(HERE, 'audio', 'music%d.wav' % (hash(sid) % 3)))
mix = mus[:int(total * SR)].copy() * 0.6
tick, _ = sf.read(os.path.join(HERE, 'audio/sfx/tick.wav'))
for g in sc['glow']:
    i = int(g['t'] * SR); j = min(len(mix), i + len(tick)); mix[i:j] += np.stack([tick, tick], 1)[:j - i]
fo = int(0.6 * SR); mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
sf.write(os.path.join(WD, 'mix.wav'), mix, SR)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(WD, 'mix.wav'), '-af', 'loudnorm=I=-16:TP=-1.5', '-ar', '44100', os.path.join(WD, 'mix_norm.wav')], check=True)
print(sid, round(total, 1))
