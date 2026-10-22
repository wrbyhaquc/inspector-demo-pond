"""Every combination of day/night, aerator, surfacing fish, heron, feeding, rain and water levels, several moments
each: does every state of the pack answer what the simulator knows?   python tools/check_states.py"""
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
sys.path.insert(0, os.environ.get("INSPECTOR_DIR", r"D:\code\inspector_platform"))
import numpy as np  # noqa: E402

import pond as P  # noqa: E402
from labeler import generic  # noqa: E402

st = {s["id"]: s for s in json.load(open(os.path.join(HERE, "..", "pack", "states.json"), encoding="utf-8"))["states"]}
clock = [1000.0]
P.time.time = lambda: clock[0]
total = bad = 0
for night, aer, surf, heron, feed, rain in itertools.product((False, True), repeat=6):
    for k, level in enumerate((15, 30, 50, 72, 90, 98)):
        p = P.Pond(seed=k * 7 + 1)
        clock[0] = 1000 + k * 0.53
        p._last = clock[0]
        p.command("night" if night else "day")
        p.aerator = aer
        p.level = level
        if surf:
            p.oxygen = 2.2
        if heron:
            p.command("heron")
        if feed:
            p.command("feed")
        if rain:
            p.command("rain")
        img = np.asarray(p.draw())
        want = {"fish_surfacing": "yes" if surf else "no", "aerator_running": "yes" if aer else "no",
                "heron": "yes" if heron else "no", "daylight": "night" if night else "day"}
        for sid, w in want.items():
            v, info = generic.evaluate(st[sid], img)
            total += 1
            if v != w:
                bad += 1
                print("WRONG", sid, "want", w, "got", v, info, dict(night=night, aerator=aer, surf=surf, heron=heron, feed=feed, rain=rain))
        v, info = generic.evaluate(st["water_level"], img)
        total += 1
        if v is None or abs(v - level / 100) > 0.04:
            bad += 1
            print("WRONG water_level want", level / 100, "got", v, info)
print(f"checked {total}, wrong {bad}")
