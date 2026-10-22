"""Put the fish pond pack's design into a running Inspector Studio through its API (every part is checked by
Inspector when it is saved).   python pack/build.py [--url http://127.0.0.1:8766]

What it makes:
  states        pack/states.json - five states, all judged by screen rules (no training needed)
  output        "pond": the simulator's equipment (HTTP POST to its /api/command)
  variable      pumping: the pump was started by the script
  sub-scripts   one per piece of equipment (the panel's buttons and the schedules use them)
  main script   Pond keeper: fish at the surface -> aerator on; daylight again -> aerator off; heron -> scare it;
                water low -> pump on, back up -> pump off; each with a notification
  schedules     feeding at 08:00 and 17:00"""
import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = "http://127.0.0.1:8800/api/command"


def call(base, method, path, body):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-Lang": "en"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path}: {e.code} {e.read().decode('utf-8', 'replace')}")


def state(sid, op, value, secs=None):
    c = {"state": sid, "op": op, "value": value}
    if secs:
        c["for"] = secs
    return c


def out(command, label=None):
    st = {"type": "output", "output": "pond", "command": command}
    if label:
        st["label"] = label
    return st


def note(text):
    return {"type": "notify", "text": text}


SUBS = [
    ("aerator_on", "Start the aerator", "aerator_on", "Aerator started"),
    ("aerator_off", "Stop the aerator", "aerator_off", "Aerator stopped"),
    ("pump_on", "Start the pump", "pump_on", "Pump started"),
    ("pump_off", "Stop the pump", "pump_off", "Pump stopped"),
    ("feed", "Feed the fish", "feed", "Fed the fish"),
    ("scare_bird", "Scare the bird away", "scare", "Scared the bird away"),
]

MAIN = {
    "id": "pond_keeper", "name": "Pond keeper", "enabled": True, "devices": {"*": "off", "POND-CAM": "live"},
    "description": "Keeps the fish alive: oxygen at night, birds by day, the water level always.",
    "otherwise": {"type": "none", "text": "Nothing to do"}, "initial": "watching",
    "situations": [{"id": "watching", "name": "Watching the pond", "rules": [
        {"id": "surfacing", "name": "Fish at the surface: start the aerator", "enabled": True, "urgent": True, "cooldown": 20,
         "when": [[state("fish_surfacing", "is", "yes", 3), state("aerator_running", "is", "no")]],
         "do": [out("aerator_on"), note("Fish at the surface (low oxygen): the aerator is on")]},
        {"id": "heron", "name": "Heron at the pond: scare it", "enabled": True, "cooldown": 15,
         "when": [[state("heron", "is", "yes", 2)]],
         "do": [out("scare"), note("A heron was at the pond: scared it away")]},
        {"id": "water_low", "name": "Water low: start the pump", "enabled": True, "cooldown": 60,
         "when": [[state("water_level", "lt", 0.3, 5), {"kind": "var", "var": "pumping", "op": "is", "value": 0}]],
         "do": [out("pump_on"), {"type": "set_var", "var": "pumping", "mode": "set", "value": 1},
                note("Water level low: the pump is on")]},
        {"id": "water_back", "name": "Water back up: stop the pump", "enabled": True, "cooldown": 60,
         "when": [[state("water_level", "gt", 0.75, 5), {"kind": "var", "var": "pumping", "op": "is", "value": 1}]],
         "do": [out("pump_off"), {"type": "set_var", "var": "pumping", "mode": "set", "value": 0},
                note("Water level back up: the pump is off")]},
        {"id": "aerator_rest", "name": "Daylight and fish fine: stop the aerator", "enabled": True, "cooldown": 60,
         "when": [[state("daylight", "is", "day", 30), state("fish_surfacing", "is", "no", 60),
                   state("aerator_running", "is", "yes", 10)]],
         "do": [out("aerator_off"), note("Daylight and the fish are fine: the aerator is off")]},
    ]}],
}

SCHEDULES = [
    {"id": "feed_morning", "name": "Morning feeding", "enabled": True, "at": "08:00", "days": [], "window": 120,
     "devices": ["POND-CAM"], "sub": "feed", "args": {}, "pause_others": False, "max_minutes": 5},
    {"id": "feed_evening", "name": "Evening feeding", "enabled": True, "at": "17:00", "days": [], "window": 120,
     "devices": ["POND-CAM"], "sub": "feed", "args": {}, "pause_others": False, "max_minutes": 5},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8766")
    a = ap.parse_args()
    b = a.url.rstrip("/")
    st = json.load(open(os.path.join(HERE, "states.json"), encoding="utf-8"))["states"]
    call(b, "POST", "/api/states", {"states": st, "note": "Fish pond: five states judged by screen rules"})
    call(b, "PUT", "/api/outputs", {"outputs": [{"id": "pond", "name": "Pond equipment", "type": "http", "url": SIM,
                                                 "method": "POST", "headers": {}}]})
    call(b, "POST", "/api/variables", {"vars": [{"name": "pumping", "label": "Pump started by the script",
                                                "scope": "device", "reset": "never", "initial": 0}]})
    for sid, name, cmd, text in SUBS:
        call(b, "POST", "/api/subscripts", {"sub": {"id": sid, "name": name, "description": f"Sends \"{cmd}\" to the pond equipment.",
                                                    "timeout": 30, "params": [], "say": name,
                                                    "steps": [out(cmd), note(text)], "cleanup": []}, "note": "fish pond pack"})
    call(b, "POST", "/api/scripts", {"script": MAIN, "note": "fish pond pack"})
    call(b, "POST", "/api/schedules", {"items": SCHEDULES})
    print("done: states, output, variable, %d sub-scripts, main script, %d schedules" % (len(SUBS), len(SCHEDULES)))


if __name__ == "__main__":
    main()
