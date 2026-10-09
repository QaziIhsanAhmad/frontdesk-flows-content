"""Original royalty-free music + SFX for FrontDesk Flows Reels (synthesised from scratch, no samples).
Usage: python3 music.py <seconds> <variant 0-2> out.wav"""
import numpy as np, soundfile as sf, sys
SR = 44100


def env(n, a, d, s=0.0, r=0.0):
    e = np.ones(n) * s
    A, D = int(a * SR), int(d * SR)
    e[:A] = np.linspace(0, 1, A, endpoint=False) if A else 1
    e[A:A + D] = np.linspace(1, s, max(1, len(e[A:A + D])))
    if r:
        R = int(r * SR); e[-R:] *= np.linspace(1, 0, R)
    return e


def lp(x, cut):
    # one-pole low-pass
    a = np.exp(-2 * np.pi * cut / SR); y = np.zeros_like(x); p = 0.0
    for i in range(len(x)):
        p = (1 - a) * x[i] + a * p; y[i] = p
    return y


def hz(m): return 440 * 2 ** ((m - 69) / 12)


def track(seconds, variant=0):
    bpm = [104, 98, 110][variant]
    beat = 60 / bpm; n = int(seconds * SR)
    L = np.zeros(n); R = np.zeros(n)
    progs = [[57, 53, 48, 55], [50, 46, 53, 48], [52, 48, 55, 50]]  # Am F C G / Dm Bb F C / Em C G D
    prog = progs[variant]
    quality = [[0, 3, 7], [0, 4, 7], [0, 4, 7], [0, 4, 7]] if variant != 1 else [[0, 3, 7], [0, 4, 7], [0, 4, 7], [0, 4, 7]]
    bar = 4 * beat
    rng = np.random.default_rng(7 + variant)
    t_all = np.arange(n) / SR
    nb = int(seconds / beat) + 1
    for b in range(nb):
        t0 = b * beat; i0 = int(t0 * SR)
        if i0 >= n: break
        ci = int(t0 // bar) % 4
        root = prog[ci]
        # kick
        kn = int(0.35 * SR); tk = np.arange(kn) / SR
        k = np.sin(2 * np.pi * (45 + 90 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 9) * 0.32
        seg = min(kn, n - i0); L[i0:i0 + seg] += k[:seg]; R[i0:i0 + seg] += k[:seg]
        # snare/clap on 2 and 4
        if b % 2 == 1:
            sn = int(0.22 * SR); noise = rng.standard_normal(sn) * np.exp(-np.arange(sn) / SR * 22) * 0.16
            noise = noise - lp(noise, 900)
            seg = min(sn, n - i0); L[i0:i0 + seg] += noise[:seg] * 0.9; R[i0:i0 + seg] += noise[:seg]
        # hats on 8ths
        for h in range(2):
            j0 = int((t0 + h * beat / 2) * SR)
            if j0 >= n: continue
            hn = int(0.05 * SR); hh = rng.standard_normal(hn) * np.exp(-np.arange(hn) / SR * 70) * (0.07 if h else 0.045)
            hh = hh - lp(hh, 6000); seg = min(hn, n - j0)
            L[j0:j0 + seg] += hh[:seg] * 0.7; R[j0:j0 + seg] += hh[:seg]
        # bass 8ths
        for h in range(2):
            j0 = int((t0 + h * beat / 2) * SR)
            if j0 >= n: continue
            bn = int(beat / 2 * SR * 0.9); tb = np.arange(bn) / SR; f = hz(root - 12)
            bs = (np.sin(2 * np.pi * f * tb) + 0.3 * np.sign(np.sin(2 * np.pi * f * tb))) * env(bn, 0.005, 0.25, 0.4, 0.03) * 0.2
            seg = min(bn, n - j0); L[j0:j0 + seg] += bs[:seg]; R[j0:j0 + seg] += bs[:seg]
        # pluck arp 16ths
        for s in range(4):
            j0 = int((t0 + s * beat / 4) * SR)
            if j0 >= n: continue
            notes = [root + 12 + q for q in quality[ci]] + [root + 24]
            m = notes[(b * 4 + s) % 4]
            pn = int(0.3 * SR); tp = np.arange(pn) / SR; f = hz(m)
            tri = 2 * np.abs(2 * ((tp * f) % 1) - 1) - 1
            pl = tri * np.exp(-tp * 12) * 0.15
            pan = 0.35 + 0.3 * (s % 2); seg = min(pn, n - j0)
            L[j0:j0 + seg] += pl[:seg] * (1 - pan); R[j0:j0 + seg] += pl[:seg] * pan
    # pads per bar
    nbars = int(seconds / bar) + 1
    for c in range(nbars):
        i0 = int(c * bar * SR)
        if i0 >= n: break
        root = prog[c % 4]; qn = int(bar * SR); tp = np.arange(qn) / SR
        pad = np.zeros(qn)
        for q in quality[c % 4]:
            for det in (-0.12, 0.12):
                f = hz(root + q) * 2 ** (det / 12)
                pad += 2 * ((tp * f) % 1) - 1
        pad = lp(pad, 900) * env(qn, 0.4, 0.1, 1, 0.4) * 0.055
        seg = min(qn, n - i0); L[i0:i0 + seg] += pad[:seg]; R[i0:i0 + seg] += pad[:seg]
    st = np.stack([L, R], 1)
    st = np.tanh(st * 1.6) / 1.6
    # fade in/out
    fi = int(0.05 * SR); fo = int(1.2 * SR)
    st[:fi] *= np.linspace(0, 1, fi)[:, None]; st[-fo:] *= np.linspace(1, 0, fo)[:, None]
    return st / np.max(np.abs(st)) * 0.85


def sfx():
    out = {}
    t = np.arange(int(0.45 * SR)) / SR
    noise = np.random.default_rng(1).standard_normal(len(t))
    sweep = np.zeros_like(noise); p = 0
    for i in range(len(t)):
        cut = 300 + 5000 * (i / len(t)); a = np.exp(-2 * np.pi * cut / SR); p = (1 - a) * noise[i] + a * p; sweep[i] = p
    out['whoosh'] = sweep * np.sin(np.pi * t / t[-1]) * 0.5
    t = np.arange(int(0.12 * SR)) / SR
    out['pop'] = np.sin(2 * np.pi * (700 + 900 * np.exp(-t * 40)) * t) * np.exp(-t * 35) * 0.5
    t = np.arange(int(1.0 * SR)) / SR
    out['ding'] = (np.sin(2 * np.pi * 1318.5 * t) + 0.5 * np.sin(2 * np.pi * 1975.5 * t) + 0.25 * np.sin(2 * np.pi * 2637 * t)) * np.exp(-t * 5) * 0.28
    t = np.arange(int(0.03 * SR)) / SR
    out['tick'] = np.random.default_rng(2).standard_normal(len(t)) * np.exp(-t * 300) * 0.12
    t = np.arange(int(0.35 * SR)) / SR
    out['buzz'] = np.sign(np.sin(2 * np.pi * 110 * t)) * np.exp(-t * 6) * 0.08
    return out


if __name__ == '__main__':
    secs, var, out = float(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
    sf.write(out, track(secs, var), SR)
    if len(sys.argv) > 4:
        for k, v in sfx().items(): sf.write(f'{sys.argv[4]}/{k}.wav', v, SR)
