"""Record the demo GIF: the simulator's camera while Inspector (already running with the pack) looks after the pond.

    python tools/record_gif.py [--out docs/demo.gif]

Nothing here acts on the equipment: it only sets the scene (day, then night; a heron) the way the demo buttons do.
What Inspector does is read from the picture's own changes: the aerator going on, the heron going away."""
import argparse
import io
import json
import os
import time
import urllib.request

from PIL import Image, ImageDraw, ImageFont

SIM = "http://127.0.0.1:8800"


def get(path):
    with urllib.request.urlopen(SIM + path, timeout=10) as r:
        return r.read()


def cmd(command, value=None):
    body = json.dumps({"command": command, "value": value}).encode()
    urllib.request.urlopen(urllib.request.Request(SIM + "/api/command", data=body, method="POST",
                                                  headers={"Content-Type": "application/json"}), timeout=10).read()


def font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def caption(img, top, bottom):
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    d.rectangle((0, h - 70, w, h), fill=(0, 0, 0, 175))
    d.text((16, h - 64), top, font=font(22), fill=(255, 255, 255))
    if bottom:
        d.text((16, h - 34), bottom, font=font(20), fill=(255, 205, 70))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "docs", "demo.gif"))
    a = ap.parse_args()
    cmd("restock")
    cmd("aerator_off")
    cmd("day")
    cmd("speed", 3)                          # one day in 3 minutes: the night comes quickly
    shots = []                               # (tag, top, bottom, picture)
    t0 = time.time()
    phase, said = "day", ""
    last = json.loads(get("/api/state"))
    heron_set = None
    while time.time() - t0 < 300:
        st = json.loads(get("/api/state"))
        if phase == "day" and time.time() - t0 > 4:
            cmd("night")
            phase = "night"
        elif phase == "night" and st["aerator"] and not last["aerator"]:
            phase, said = "aerator", "Inspector: fish at the surface -> aerator ON"
        elif phase == "aerator" and heron_set is None and time.time() - aerator_since > 7:
            cmd("day")
            cmd("heron")
            heron_set = time.time()
            phase, said = "heron", ""
        elif phase == "heron" and last["heron"] and not st["heron"]:
            phase, said = "scared", "Inspector: heron at the pond -> scared away"
        if phase == "aerator" and not last["aerator"]:
            aerator_since = time.time()
        top = {"day": "A fish pond, watched by one camera",
               "night": "Night: the oxygen falls" + (" - fish come up gasping" if st["fish_surfacing"] else ""),
               "aerator": "Before dawn the oxygen is lowest - fish come up gasping",
               "heron": "Morning: a heron lands...", "scared": "Morning: a heron lands..."}[phase]
        img = Image.open(io.BytesIO(get("/snapshot.jpg"))).convert("RGB").resize((640, 360))
        quiet = phase == "night" and not st["fish_surfacing"]
        shots.append(("quiet" if quiet else phase, caption(img, top, said)))
        last = st
        if phase == "scared" and sum(1 for t, _ in shots if t == "scared") >= 8:
            break
        time.sleep(0.7)
    cmd("speed", 6)
    keep, q = [], 0
    for tag, im in shots:
        if tag == "quiet":                   # the long, quiet part of the night goes by fast
            q += 1
            if q % 6:
                continue
        keep.append(im)
    keep += [keep[-1]] * 6                   # hold the end a moment
    pal = [f.quantize(colors=96, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in keep]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    pal[0].save(a.out, save_all=True, append_images=pal[1:], duration=260, loop=0, optimize=True)
    print(f"{len(shots)} shots, {len(pal)} frames -> {a.out} ({os.path.getsize(a.out) // 1024} KB)")


if __name__ == "__main__":
    main()
