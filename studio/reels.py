"""Render vertical Reels (1080x1920) for FrontDesk Flows: Pillow scenes + Kokoro voice + ffmpeg."""
import json, os, subprocess, sys, textwrap
import numpy as np, soundfile as sf
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from kokoro_onnx import Kokoro

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "kokoro-v1.0.onnx")
VOICES = os.path.join(HERE, "voices-v1.0.bin")
FD = "/usr/share/fonts/truetype"
F = lambda n, s: ImageFont.truetype({"b": f"{FD}/google-fonts/Poppins-Bold.ttf", "m": f"{FD}/google-fonts/Poppins-Medium.ttf",
                                    "r": f"{FD}/google-fonts/Poppins-Regular.ttf", "mono": f"{FD}/dejavu/DejaVuSansMono.ttf"}[n], s)
W, H = 1080, 1920
INK, PAPER, TEAL, AMBER, RED, MUTED = (11, 18, 32), (248, 250, 252), (15, 118, 110), (245, 158, 11), (220, 38, 38), (100, 116, 139)
SHOTS = os.path.join(HERE, "shots")


def wrap(d, text, font, maxw):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split(" "):
            t = (cur + " " + w).strip()
            if d.textlength(t, font=font) <= maxw: cur = t
            else: lines.append(cur); cur = w
        lines.append(cur)
    return lines


def base(dark=True):
    im = Image.new("RGB", (W, H), INK if dark else PAPER)
    d = ImageDraw.Draw(im)
    # brand bug
    d.rounded_rectangle((60, 70, 60 + 46, 70 + 46), 12, fill=TEAL)
    d.text((83, 93), "F", font=F("b", 30), fill=PAPER, anchor="mm")
    d.text((122, 93), "FrontDesk Flows", font=F("m", 30), fill=PAPER if dark else INK, anchor="lm")
    return im, d


def caption(d, text, y=1560):
    font = F("b", 50)
    lines = wrap(d, text, font, 920)
    h = len(lines) * 66 + 50
    y0 = min(y, H - 120 - h)
    d.rounded_rectangle((60, y0, W - 60, y0 + h), 28, fill=(0, 0, 0))
    for i, l in enumerate(lines):
        d.text((W // 2, y0 + 25 + 33 + i * 66), l, font=font, fill=PAPER, anchor="mm")


def s_hook(sc):
    im, d = base()
    font = F("b", 92)
    lines = wrap(d, sc["big"], font, 940)
    y = 700 - len(lines) * 55
    for i, l in enumerate(lines):
        d.text((W // 2, y + i * 112), l, font=font, fill=AMBER if i == sc.get("hl", -1) else PAPER, anchor="mm")
    if sc.get("sub"):
        for i, l in enumerate(wrap(d, sc["sub"], F("r", 44), 900)):
            d.text((W // 2, y + len(lines) * 112 + 60 + i * 60), l, font=F("r", 44), fill=(203, 213, 225), anchor="mm")
    return im


def s_shot(sc):
    im, d = base()
    shot = Image.open(os.path.join(SHOTS, sc["img"])).convert("RGB")
    if sc.get("crop"): shot = shot.crop(tuple(sc["crop"]))
    tw = 1000; th = int(shot.height * tw / shot.width)
    if th > 1100: th = 1100; tw = int(shot.width * th / shot.height)
    shot = shot.resize((tw, th), Image.LANCZOS)
    x, y = (W - tw) // 2, 330
    d.rounded_rectangle((x - 8, y - 8, x + tw + 8, y + th + 8), 26, fill=(51, 65, 85))
    mask = Image.new("L", (tw, th), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, tw, th), 20, fill=255)
    im.paste(shot, (x, y), mask)
    if sc.get("label"):
        d.text((W // 2, 270), sc["label"], font=F("m", 38), fill=(148, 163, 184), anchor="mm")
    return im


def card(d, x, y, w, title, lines, head_fill=TEAL, body_font=None, foot=None):
    body_font = body_font or F("r", 46)
    wrapped = []
    for ln in lines:
        wrapped += wrap(d, ln, body_font, w - 80) if ln else [""]
    h = 130 + len(wrapped) * 64 + (70 if foot else 30)
    d.rounded_rectangle((x, y, x + w, y + h), 30, fill=PAPER)
    d.rounded_rectangle((x, y, x + w, y + 104), 30, fill=head_fill)
    d.rectangle((x, y + 70, x + w, y + 104), fill=head_fill)
    d.text((x + 40, y + 52), title, font=F("b", 44), fill=PAPER, anchor="lm")
    for i, l in enumerate(wrapped):
        d.text((x + 40, y + 134 + i * 64), l, font=body_font, fill=INK)
    if foot: d.text((x + 40, y + h - 45), foot, font=F("m", 30), fill=MUTED, anchor="lm")
    return y + h


def s_card(sc):
    im, d = base()
    y = sc.get("y", 520)
    for c in sc["cards"]:
        y = card(d, 70, y, W - 140, c["title"], c["lines"], head_fill={"teal": TEAL, "red": RED, "amber": (180, 83, 9), "ink": (51, 65, 85)}[c.get("color", "teal")],
                 body_font=F("mono", 40) if c.get("mono") else None, foot=c.get("foot")) + 40
    return im


def s_cta(sc):
    im, d = base()
    d.text((W // 2, 560), sc["big"], font=F("b", 96), fill=AMBER, anchor="mm")
    for i, l in enumerate(wrap(d, sc["sub"], F("m", 52), 900)):
        d.text((W // 2, 720 + i * 72), l, font=F("m", 52), fill=PAPER, anchor="mm")
    d.rounded_rectangle((190, 1040, W - 190, 1170), 65, fill=TEAL)
    d.text((W // 2, 1105), sc["button"], font=F("b", 52), fill=PAPER, anchor="mm")
    if sc.get("small"):
        for i, l in enumerate(wrap(d, sc["small"], F("r", 36), 880)):
            d.text((W // 2, 1250 + i * 50), l, font=F("r", 36), fill=(148, 163, 184), anchor="mm")
    return im


def s_list(sc):
    im, d = base()
    d.text((W // 2, 300), sc["title"], font=F("b", 64), fill=AMBER, anchor="mm")
    y = 420
    for i, it in enumerate(sc["items"]):
        d.ellipse((80, y, 150, y + 70), fill=TEAL)
        d.text((115, y + 35), str(i + 1), font=F("b", 40), fill=PAPER, anchor="mm")
        lines = wrap(d, it, F("m", 46), 820)
        for j, l in enumerate(lines):
            d.text((180, y + 8 + j * 58), l, font=F("m", 46), fill=PAPER)
        y += max(1, len(lines)) * 58 + 50
    return im


def s_flow(sc):
    im, d = base()
    if sc.get("title"):
        d.text((W // 2, 280), sc["title"], font=F("b", 56), fill=AMBER, anchor="mm")
    steps = sc["steps"]; y = 380; bw = 820; x = (W - bw) // 2
    for i, st in enumerate(steps):
        lines = wrap(d, st, F("m", 42), bw - 60)
        h = 40 + len(lines) * 54
        hl = i in sc.get("hl", [])
        d.rounded_rectangle((x, y, x + bw, y + h), 24, fill=(15, 118, 110) if hl else (30, 41, 59), outline=(71, 85, 105), width=2)
        for j, l in enumerate(lines):
            d.text((W // 2, y + 20 + 27 + j * 54), l, font=F("m", 42), fill=PAPER, anchor="mm")
        y += h
        if i < len(steps) - 1:
            d.line((W // 2, y + 6, W // 2, y + 44), fill=(148, 163, 184), width=5)
            d.polygon([(W // 2 - 14, y + 38), (W // 2 + 14, y + 38), (W // 2, y + 56)], fill=(148, 163, 184))
            y += 62
    return im


def s_code(sc):
    im, d = base()
    if sc.get("title"):
        d.text((W // 2, 300), sc["title"], font=F("b", 56), fill=AMBER, anchor="mm")
    font = F("mono", sc.get("size", 34))
    lines = []
    for ln in sc["code"].split("\n"):
        lines += textwrap.wrap(ln, sc.get("wrap", 44)) or [""]
    h = 90 + len(lines) * (font.size + 14)
    y = 380
    d.rounded_rectangle((60, y, W - 60, y + h), 26, fill=(2, 6, 23), outline=(51, 65, 85), width=2)
    for k, c in enumerate([(239, 68, 68), (245, 158, 11), (34, 197, 94)]):
        d.ellipse((96 + k * 40, y + 26, 120 + k * 40, y + 50), fill=c)
    for i, l in enumerate(lines):
        d.text((100, y + 76 + i * (font.size + 14)), l, font=font, fill=(226, 232, 240))
    return im


R = {"hook": s_hook, "shot": s_shot, "card": s_card, "cta": s_cta, "list": s_list, "flow": s_flow, "code": s_code}


def main(path):
    ep = json.load(open(path)); slug = ep["slug"]
    out = os.path.join(HERE, "reels", slug); os.makedirs(out, exist_ok=True)
    k = Kokoro(MODEL, VOICES)
    clips = []
    for i, sc in enumerate(ep["scenes"]):
        samples, sr = k.create(sc["say"], voice=ep.get("voice", "af_heart"), speed=ep.get("speed", 1.05), lang="en-us")
        pad = np.zeros(int(sr * 0.25), dtype=np.float32)
        audio = np.concatenate([pad, samples, np.zeros(int(sr * 0.35), dtype=np.float32)])
        wav = f"{out}/a{i:02d}.wav"; sf.write(wav, audio, sr)
        dur = len(audio) / sr
        im = R[sc["type"]](sc)
        if sc.get("cap", True) and sc["type"] not in ("cta",):
            caption(ImageDraw.Draw(im), sc.get("caption", sc["say"]))
        png = f"{out}/s{i:02d}.png"; im.save(png)
        clip = f"{out}/c{i:02d}.mp4"
        frames = int(dur * 30) + 1
        vf = f"scale=1188:2112,zoompan=z='min(zoom+0.0006,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png, "-i", wav, "-vf", vf, "-t", f"{dur:.3f}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", clip], check=True)
        clips.append(clip)
    lst = f"{out}/list.txt"; open(lst, "w").write("".join(f"file '{c}'\n" for c in clips))
    raw = f"{out}/raw.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", raw], check=True)
    final = os.path.join(HERE, "reels", f"{slug}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", final], check=True)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", final]).decode())
    print(slug, f"{dur:.1f}s", final)


if __name__ == "__main__":
    for p in sys.argv[1:]: main(p)
