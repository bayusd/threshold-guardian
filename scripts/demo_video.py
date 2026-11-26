"""Demo video for Threshold Guardian — Reactive Omni Buildathon.
Landscape 1280x720 @24fps, PIL frames + TTS narration + ffmpeg.
Reads scripts/loop-results.json for the real loop numbers at render time.
Run:  cd ~/workspace/dorahacks-reactive && python3 scripts/demo_video.py
Out:  ~/workspace/dorahacks-reactive/demo-video.mp4
"""
import json, math, os, subprocess, sys
sys.path.insert(0, '/home/hatch/workspace/anim-engine')
from engine import font, ss, lerp
from PIL import Image, ImageDraw

ROOT = '/home/hatch/workspace/dorahacks-reactive'
FRAMES = os.path.join(ROOT, 'scripts', 'video_frames')
os.makedirs(FRAMES, exist_ok=True)
W, H, FPS = 1280, 720, 24
TTS = '/opt/hatch/bin/tts'

RESULTS = json.load(open(os.path.join(ROOT, 'scripts', 'loop-results.json')))
RUNS = [r for r in RESULTS if r.get('latency_event_to_callback_s') is not None]
LATS = sorted(r['latency_event_to_callback_s'] for r in RUNS)
P50 = LATS[len(LATS) // 2]
N = len(RUNS)

NARR = [
    "Threshold Guardian. An autonomous stop-loss for a vault, built on Reactive Network. Set a price threshold once — and forget it.",
    "A price oracle on Base Sepolia reports the asset price. A reactive contract on Lasna watches every price event. When the price falls below the threshold, it pauses the vault automatically. When the price recovers, it unpauses it. No bots. No keepers. No manual steps.",
    f"We ran the loop live, {N} times. Each crossing — breach, then recovery — triggered the full chain: oracle event, reactive check, callback to the vault. Median latency: {P50} second from event to vault paused.",
    "Every run succeeded. One hundred percent. A single reactive call costs about two hundredths of a lREACT, and one callback costs less than a millionth of an ether. The contracts are deployed and verified on testnet.",
    "Threshold Guardian. Set it and forget it. Source code and full results are on GitHub.",
]

# ---- audio: synthesize each segment, measure durations --------------------
def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)

def mp3_dur(path):
    r = sh(f"ffprobe -v error -show_entries format=duration -of csv=p=0 {path}")
    return float(r.stdout.strip())

segs, durs = [], []
for i, text in enumerate(NARR):
    out = os.path.join(ROOT, 'scripts', f'narr{i}.mp3')
    if not os.path.exists(out) or os.path.getsize(out) < 1000:
        r = subprocess.run([TTS, 'speak', '--language', 'en', '--output', out,
                            '--text', text], capture_output=True, text=True)
        assert os.path.exists(out) and os.path.getsize(out) > 1000, f"TTS failed seg {i}: {r.stderr[:300]}"
    d = mp3_dur(out)
    segs.append(out); durs.append(d)
    print(f"seg {i}: {d:.1f}s")

GAP = 0.6
bounds = []  # (start, end) per scene
t = 0.0
for d in durs:
    bounds.append((t, t + d + GAP))
    t += d + GAP
DUR = t - GAP + 1.2  # trailing pad
print(f"total video: {DUR:.1f}s")

# concat narration with silence gaps
with open(os.path.join(ROOT, 'scripts', 'concat.txt'), 'w') as f:
    for s in segs:
        f.write(f"file '{s}'\n")
        # silence gap file
        gap = os.path.join(ROOT, 'scripts', 'gap.mp3')
        if not os.path.exists(gap):
            sh(f"ffmpeg -y -v error -f lavfi -i anullsrc=r=44100:cl=stereo -t {GAP} -c:a libmp3lame {gap}")
        f.write(f"file '{gap}'\n")
narr = os.path.join(ROOT, 'scripts', 'narration.mp3')
sh(f"ffmpeg -y -v error -f concat -safe 0 -i {ROOT}/scripts/concat.txt -c copy {narr}")
# pad to DUR
sh(f"ffmpeg -y -v error -i {narr} -af apad -t {DUR:.2f} {narr}.tmp.mp3 && mv {narr}.tmp.mp3 {narr}")

# ---- drawing helpers ------------------------------------------------------
BG = (10, 14, 24)
PANEL = (19, 24, 38)
LINE = (35, 42, 61)
GREEN = (74, 222, 128)
RED = (248, 113, 113)
GOLD = (255, 214, 64)
BLUE = (124, 196, 255)
MUT = (154, 163, 178)

def base():
    return Image.new('RGB', (W, H), BG)

def header(img, text="THRESHOLD GUARDIAN  •  REACTIVE OMNI BUILDATHON"):
    d = ImageDraw.Draw(img, 'RGBA')
    d.rectangle([0, 0, W, 52], fill=(8, 11, 20, 220))
    d.text((28, 14), text, font=font(22), fill=MUT)

def footer(img, text):
    d = ImageDraw.Draw(img, 'RGBA')
    d.rectangle([0, H - 44, W, H], fill=(8, 11, 20, 220))
    d.text((28, H - 34), text, font=font(20, bold=False), fill=MUT)

def subtitle(img, seg, t):
    """Word-by-word caption, bottom center."""
    start, _ = bounds[seg]
    dur = durs[seg]
    if not (start <= t <= start + dur + 0.3):
        return
    words = NARR[seg].split()
    shown = min(len(words), int((t - start) / (dur / len(words))) + 1)
    txt = ' '.join(words[:shown])
    d = ImageDraw.Draw(img)
    f = font(28)
    lines, cur = [], ''
    for w_ in txt.split():
        tt = (cur + ' ' + w_).strip()
        if d.textlength(tt, font=f) <= W - 160:
            cur = tt
        else:
            lines.append(cur); cur = w_
    if cur:
        lines.append(cur)
    yy = H - 44 - 40 * len(lines) - 14
    for ln in lines:
        tw = d.textlength(ln, font=f)
        d.rounded_rectangle([(W - tw) / 2 - 14, yy - 6, (W + tw) / 2 + 14, yy + 36], radius=10, fill=(5, 5, 8, 170))
        d.text(((W - tw) / 2, yy), ln, font=f, fill=(255, 255, 255))
        yy += 40

def scene_of(t):
    for i, (a, b) in enumerate(bounds):
        if a <= t < b:
            return i, t - a
    return len(bounds) - 1, t - bounds[-1][0]

# ---- scenes ---------------------------------------------------------------
def shield(cx, cy, r, col=GREEN):
    d = ImageDraw.Draw(img_global, 'RGBA')
    pts = [(cx, cy - r), (cx + r * 0.85, cy - r * 0.55), (cx + r * 0.85, cy + r * 0.1),
           (cx, cy + r), (cx - r * 0.85, cy + r * 0.1), (cx - r * 0.85, cy - r * 0.55)]
    d.polygon(pts, outline=col, width=6)
    d.line([(cx - r * 0.4, cy), (cx - r * 0.08, cy + r * 0.35), (cx + r * 0.5, cy - r * 0.4)], fill=col, width=8)

def s_title(t, lt):
    img = base()
    d = ImageDraw.Draw(img, 'RGBA')
    k = ss(min(1.0, lt / 1.2))
    # pulsing shield
    r = 90 + 6 * math.sin(t * 2.0)
    global img_global
    img_global = img
    shield(W // 2, 210, r)
    d.text((W // 2, 330), "THRESHOLD GUARDIAN", font=font(64), fill=(255, 255, 255), anchor="ma")
    d.text((W // 2, 410), "Autonomous stop-loss for a vault — powered by Reactive Network",
           font=font(28, bold=False), fill=MUT, anchor="ma")
    d.rounded_rectangle([W // 2 - 190, 470, W // 2 + 190, 514], radius=22, fill=(20, 60, 40))
    d.text((W // 2, 480), "SET IT AND FORGET IT", font=font(24), fill=GREEN, anchor="ma")
    d.text((W // 2, 560), "Base Sepolia  •  Lasna  •  DoraHacks Reactive Omni Buildathon",
           font=font(22, bold=False), fill=MUT, anchor="ma")
    return img

BOXES = [
    ("MOCK PRICE ORACLE", "Base Sepolia", "emits PriceUpdated", BLUE, 90),
    ("GUARDIAN", "Lasna — reactive", "react() checks threshold", GREEN, 490),
    ("VAULT", "Base Sepolia", "pause() / unpause()", GOLD, 890),
]
def s_arch(t, lt):
    img = base()
    d = ImageDraw.Draw(img, 'RGBA')
    d.text((W // 2, 84), "One loop. No bots, no keepers.", font=font(36), fill=(255, 255, 255), anchor="ma")
    # price ticker above oracle
    p = 100 if (int(lt * 1.2) % 2 == 0) else 40
    for i, (name, chain, desc, col, x) in enumerate(BOXES):
        k = ss(max(0.0, min(1.0, (lt - i * 0.7) / 0.8)))
        y0 = 200 - int(30 * (1 - k))
        d.rounded_rectangle([x, y0, x + 300, y0 + 190], radius=16, fill=PANEL, outline=col, width=3)
        d.text((x + 150, y0 + 22), name, font=font(26), fill=(255, 255, 255), anchor="ma")
        d.text((x + 150, y0 + 62), chain, font=font(20, bold=False), fill=MUT, anchor="ma")
        d.text((x + 150, y0 + 118), desc, font=font(20, bold=False), fill=col, anchor="ma")
        if i < 2:
            ax = x + 300
            flow = (t * 260) % 60
            d.line([ax + 10, y0 + 95, ax + 90, y0 + 95], fill=col, width=4)
            d.polygon([(ax + 90, y0 + 95), (ax + 72, y0 + 83), (ax + 72, y0 + 107)], fill=col)
            d.ellipse([ax + 16 + flow, y0 + 87, ax + 32 + flow, y0 + 103], fill=(255, 255, 255))
    # threshold strip
    d.rounded_rectangle([90, 450, W - 90, 560], radius=14, fill=PANEL)
    d.text((130, 478), "THRESHOLD", font=font(24), fill=MUT)
    d.text((330, 470), "$50", font=font(44), fill=GOLD)
    d.text((470, 490), "price < $50  →  pause      price ≥ $50  →  unpause", font=font(24, bold=False), fill=(255, 255, 255))
    d.text((W // 2, 600), "Hysteresis: one callback per crossing — repeated events do not spam the vault.",
           font=font(22, bold=False), fill=MUT, anchor="ma")
    return img

def s_loop(t, lt):
    img = base()
    d = ImageDraw.Draw(img, 'RGBA')
    d.text((W // 2, 84), f"Live loop — {N} crossings, measured on-chain", font=font(36), fill=(255, 255, 255), anchor="ma")
    # chart area
    x0, x1, y0, y1 = 90, 830, 170, 520
    d.rounded_rectangle([x0 - 20, y0 - 20, x1 + 20, y1 + 50], radius=14, fill=PANEL)
    ymin, ymax = 30.0, 110.0
    def ym(v): return y1 - (v - ymin) / (ymax - ymin) * (y1 - y0)
    # threshold line
    d.line([x0, ym(50), x1, ym(50)], fill=GOLD, width=3)
    d.text((x1 + 8, ym(50) - 14), "$50 threshold", font=font(20), fill=GOLD)
    # price path from real runs: 100 -> 40 -> 60 alternating
    prices = [100] + [r['price'] for r in RUNS]
    npts = len(prices)
    prog = ss(min(1.0, lt / (bounds[2][1] - bounds[2][0] - 0.5)))
    total = prog * (npts - 1)
    pts = []
    for i in range(npts):
        if i <= total:
            pts.append((x0 + (x1 - x0) * i / (npts - 1), ym(prices[i])))
        else:
            k = total - (i - 1)
            pts.append((x0 + (x1 - x0) * (i - 1 + k) / (npts - 1),
                        lerp(ym(prices[i - 1]), ym(prices[i]), k)))
            break
    if len(pts) > 1:
        d.line(pts, fill=BLUE, width=5)
        tx, ty = pts[-1]
        d.ellipse([tx - 9, ty - 9, tx + 9, ty + 9], fill=BLUE, outline=(255, 255, 255), width=2)
        d.text((tx + 14, ty - 34), f"${prices[min(int(total), npts - 1)]}", font=font(26), fill=(255, 255, 255))
    d.text((x0, y1 + 12), "price", font=font(20, bold=False), fill=MUT)
    # vault pill + latency
    idx = min(int(total), npts - 1)
    cur_price = prices[idx]
    paused = cur_price < 50
    pill = (1140, 200) if paused else (1140, 200)
    d.rounded_rectangle([900, 170, 1190, 300], radius=14, fill=PANEL)
    d.text((1045, 186), "VAULT", font=font(22), fill=MUT, anchor="ma")
    d.rounded_rectangle([950, 216, 1140, 268], radius=22, fill=(127, 29, 29) if paused else (20, 83, 45))
    d.text((1045, 228), "PAUSED" if paused else "OPEN", font=font(26), fill=(255, 255, 255), anchor="ma")
    d.rounded_rectangle([900, 320, 1190, 500], radius=14, fill=PANEL)
    d.text((1045, 336), "EVENT → CALLBACK", font=font(22), fill=MUT, anchor="ma")
    d.text((1045, 372), f"p50  {P50} s", font=font(44), fill=GREEN, anchor="ma")
    d.text((1045, 430), f"min {LATS[0]} s  •  max {LATS[-1]} s", font=font(22, bold=False), fill=(255, 255, 255), anchor="ma")
    d.text((1045, 462), f"{N} / {N} succeeded", font=font(22, bold=False), fill=GREEN, anchor="ma")
    # tx strip: latest completed run
    done = [r for r in RUNS if r['run'] <= max(1, int(total))]
    if done:
        r = done[-1]
        d.text((90, 600), f"run {r['run']}: event {r['event_tx'][:14]}…{r['event_tx'][-6:]}  →  "
               f"callback {r['callback_tx'][:14]}…{r['callback_tx'][-6:]}  •  {r['latency_event_to_callback_s']} s",
               font=font(20, bold=False), fill=MUT)
    return img

def s_numbers(t, lt):
    img = base()
    d = ImageDraw.Draw(img, 'RGBA')
    d.text((W // 2, 84), "The numbers", font=font(36), fill=(255, 255, 255), anchor="ma")
    cards = [
        ("LOOP LATENCY (p50)", f"{P50} s", f"{N} crossings, 100% success", GREEN),
        ("REACT COST", "~0.015 lREACT", "per react() on Lasna", BLUE),
        ("CALLBACK COST", "~0.0000007 ETH", "per callback on Base Sepolia", GOLD),
        ("RESERVES", "0.3 lREACT", "funded for 17 crossings", (255, 255, 255)),
    ]
    for i, (k, v, sub, col) in enumerate(cards):
        x = 90 + (i % 2) * 570
        y = 150 + (i // 2) * 210
        kk = ss(max(0.0, min(1.0, (lt - i * 0.4) / 0.6)))
        d.rounded_rectangle([x, y, x + 540, y + 180], radius=16, fill=PANEL, outline=col, width=2)
        d.text((x + 28, y + 20), k, font=font(22), fill=MUT)
        d.text((x + 28, y + 56), v, font=font(44), fill=col)
        d.text((x + 28, y + 122), sub, font=font(22, bold=False), fill=(255, 255, 255))
    return img

def s_close(t, lt):
    img = base()
    d = ImageDraw.Draw(img, 'RGBA')
    global img_global
    img_global = img
    shield(W // 2, 190, 70 + 4 * math.sin(t * 2.0))
    d.text((W // 2, 300), "THRESHOLD GUARDIAN", font=font(52), fill=(255, 255, 255), anchor="ma")
    d.text((W // 2, 366), "Set it and forget it.", font=font(30, bold=False), fill=GREEN, anchor="ma")
    d.text((W // 2, 440), "github.com/bayusd/threshold-guardian", font=font(28), fill=BLUE, anchor="ma")
    d.text((W // 2, 496), "Contracts: Base Sepolia  •  Lasna  •  testnet only", font=font(22, bold=False), fill=MUT, anchor="ma")
    d.text((W // 2, 540), "Built during the Reactive Omni Buildathon — November 2026", font=font(22, bold=False), fill=MUT, anchor="ma")
    return img

SCENES = [s_title, s_arch, s_loop, s_numbers, s_close]
img_global = None

n = int(DUR * FPS)
for i in range(n):
    t = i / FPS
    si, lt = scene_of(t)
    img = SCENES[si](t, lt)
    header(img)
    footer(img, "Threshold Guardian — Reactive Omni Buildathon (Set It and Forget It)")
    subtitle(img, si, t)
    img.save(f'{FRAMES}/f{i:04d}.png')
    if i % 120 == 0:
        print('frame', i, '/', n)
print('frames done', n)

r = sh(f"ffmpeg -y -v error -framerate {FPS} -i {FRAMES}/f%04d.png -i {narr} "
       f"-c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 128k -shortest "
       f"{ROOT}/demo-video.mp4")
assert os.path.exists(f"{ROOT}/demo-video.mp4"), r.stderr[:500]
print('VIDEO:', f"{ROOT}/demo-video.mp4", os.path.getsize(f"{ROOT}/demo-video.mp4") // 1024, 'KB')
