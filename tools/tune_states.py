"""Check the pack's screen rules on pictures of every situation of the simulator (no Inspector server needed).

    python tools/tune_states.py            prints each state's answer and its measure for each situation"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sim"))
sys.path.insert(0, os.environ.get("INSPECTOR_DIR", r"D:\code\inspector_platform"))

import numpy as np  # noqa: E402

from pond import Pond  # noqa: E402
from labeler import generic  # noqa: E402

STATES = json.load(open(os.path.join(HERE, "..", "pack", "states.json"), encoding="utf-8"))["states"]


def situations():
    """(name, picture, what the simulator knows)"""
    out = []
    for night in (False, True):
        for case in ("calm", "aerator", "surfacing", "surfacing+aerator", "heron", "feeding", "rain", "low water", "high water"):
            p = Pond(seed=3)
            p.step()
            p.command("night" if night else "day")
            if "aerator" in case:
                p.command("aerator_on")
            if "surfacing" in case:
                p.oxygen = 2.2
            if case == "heron":
                p.command("heron")
            if case == "feeding":
                p.command("feed")
            if case == "rain":
                p.command("rain")
            if case == "low water":
                p.level = 22
            if case == "high water":
                p.level = 95
            out.append(((("night " if night else "day ") + case), np.asarray(p.draw()), p.state()))
    return out


def main():
    rows = situations()
    for s in STATES:
        print(f"== {s['id']} ({s['source']['rule']})")
        for name, img, truth in rows:
            r = generic.evaluate(s, img) if hasattr(generic, "evaluate") else None
            print(f"   {name:24s} -> {r}")


if __name__ == "__main__":
    main()
