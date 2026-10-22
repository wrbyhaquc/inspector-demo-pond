"""Put the fish pond pack's design into a running Inspector Studio through its API (every part is checked by
Inspector when it is saved), in English or Traditional Chinese.

    python pack/build.py --lang en    --url http://127.0.0.1:8766 --design <the pack's design folder>
    python pack/build.py --lang zh-TW --url http://127.0.0.1:8767 --design <...>

What it makes (the ids are the same in both languages; only the words differ):
  states        pack/states.json - five states, all judged by screen rules (no training needed)
  output        "pond": the simulator's equipment (HTTP POST to its /api/command)
  settings      pump_start / pump_stop: the water levels the pump starts and stops at (the farmer sets them)
  variable      pumping: the pump was started by the script
  sub-scripts   one per piece of equipment (the panel's buttons and the schedules use them)
  main script   Pond keeper: fish at the surface -> aerator on; daylight again -> aerator off; heron -> scare it;
                water low -> pump on, back up -> pump off; each with a notification. Runs on POND-CAM only.
  schedules     feeding at 08:00 and 17:00
  panel         the farmer's page: the camera and how it is, the equipment's buttons, feeding times, the pump's
                levels, notifications"""
import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = "http://127.0.0.1:8800/api/command"
CAM = "POND-CAM"

T = {
    "en": {
        "project": ("Fish pond", "A fish pond watched by one camera: aerator, pump, feeder and bird scarer driven through an HTTP output.",
                    {"device": "camera", "item": "item"}),
        "states": {"fish_surfacing": ("Fish at the surface", "Fish come up gasping when the water is short of oxygen: bright orange fish with rings around them. Fish under water look dim.", {"yes": "Yes", "no": "No"}, "The pond"),
                   "aerator_running": ("Aerator running", "White foam and spray around the yellow paddle wheel.", {"yes": "Running", "no": "Stopped"}, "Around the paddle wheel"),
                   "water_level": ("Water level", "How high the blue water stands in the level tube on the right bank: 0 = empty, 1 = full.", {}, "Level tube"),
                   "heron": ("Heron", "A white heron standing on the far bank; it takes fish.", {"yes": "There", "no": "None"}, "The far bank"),
                   "daylight": ("Day or night", "How bright the sky is.", {"day": "Day", "night": "Night"}, "The sky")},
        "output": "Pond equipment",
        "camera": "Pond camera",
        "settings": {"pump_start": ("Pump on below", "The pump starts when the water level stays below this."),
                     "pump_stop": ("Pump off above", "The pump stops when the water level is back above this.")},
        "var": "Pump started by the script",
        "subs": {"aerator_on": ("Start the aerator", "Aerator started"), "aerator_off": ("Stop the aerator", "Aerator stopped"),
                 "pump_on": ("Start the pump", "Pump started"), "pump_off": ("Stop the pump", "Pump stopped"),
                 "feed": ("Feed the fish", "Fed the fish"), "scare_bird": ("Scare the bird away", "Scared the bird away")},
        "sub_desc": 'Sends "{cmd}" to the pond equipment.',
        "main": ("Pond keeper", "Keeps the fish alive: oxygen at night, birds by day, the water level always.", "Watching the pond", "Nothing to do"),
        "rules": {"surfacing": ("Fish at the surface: start the aerator", "Fish at the surface (low oxygen): the aerator is on"),
                  "heron": ("Heron at the pond: scare it", "A heron was at the pond: scared it away"),
                  "water_low": ("Water low: start the pump", "Water level low: the pump is on"),
                  "water_back": ("Water back up: stop the pump", "Water level back up: the pump is off"),
                  "aerator_rest": ("Daylight and fish fine: stop the aerator", "Daylight and the fish are fine: the aerator is off")},
        "schedules": {"feed_morning": "Morning feeding", "feed_evening": "Evening feeding"},
        "panel": {"title": "Fish pond", "pages": {"main": "Now", "settings": "Settings", "notify": "Notifications"},
                  "sources_help": "Start the simulator first (python sim/server.py), then add its camera: http://127.0.0.1:8800/video.mjpg",
                  "blocks": {"w_devices": ("How the pond is", ""), "equipment": ("Equipment", "Turn the equipment on or off by hand. The pond keeper also does it on its own when needed."),
                             "now": ("Stop / resume", "Stop: the pond keeper does nothing on its own until you press Resume."),
                             "w_schedules": ("Today's feeding", "Whether this morning's and this evening's feeding ran."),
                             "w_log": ("What happened lately", ""),
                             "feeding": ("Feeding times", "The feeder runs at these times every day."),
                             "pump": ("Water level", "The pump keeps the water between these two levels."),
                             "w_chat": ("Notifications and commands", "Get the pond's news on your phone, and give commands from the chat.")},
                  "controls": {"aerator_on": "Aerator on", "aerator_off": "Aerator off", "pump_on": "Pump on", "pump_off": "Pump off",
                               "feed_now": "Feed now", "scare_now": "Scare the bird", "stop_now": "Stop",
                               "morning_on": "Morning feeding", "morning_at": "Morning time", "evening_on": "Evening feeding", "evening_at": "Evening time",
                               "pump_start": "Pump on below", "pump_stop": "Pump off above"}},
    },
    "zh-TW": {
        "project": ("魚塭", "一台攝影機看著的魚塭:打氣機、抽水馬達、餵料機、驅鳥器透過 HTTP 輸出控制。", {"device": "攝影機", "item": "項目"}),
        "states": {"fish_surfacing": ("魚浮頭", "水裡溶氧不夠時魚會浮到水面喘氣:亮橘色的魚、周圍一圈圈漣漪。在水裡的魚看起來比較暗。", {"yes": "有", "no": "沒有"}, "魚塭"),
                   "aerator_running": ("打氣機運轉", "黃色水車周圍的白色泡沫和水花。", {"yes": "運轉中", "no": "停止"}, "水車周圍"),
                   "water_level": ("水位", "右岸液位管裡藍色水柱的高度:0 = 乾了,1 = 滿了。", {}, "液位管"),
                   "heron": ("白鷺鷥", "停在遠岸的白鷺鷥,會叼走魚。", {"yes": "有", "no": "沒有"}, "遠岸"),
                   "daylight": ("白天晚上", "天空有多亮。", {"day": "白天", "night": "晚上"}, "天空")},
        "output": "魚塭設備",
        "camera": "魚塭攝影機",
        "settings": {"pump_start": ("低於這個水位就抽水", "水位持續低於這個,就開抽水馬達。"),
                     "pump_stop": ("高於這個水位就停止", "水位回到這個以上,就關抽水馬達。")},
        "var": "抽水馬達是腳本開的",
        "subs": {"aerator_on": ("開打氣機", "打氣機已開"), "aerator_off": ("關打氣機", "打氣機已關"),
                 "pump_on": ("開抽水馬達", "抽水馬達已開"), "pump_off": ("關抽水馬達", "抽水馬達已關"),
                 "feed": ("餵魚", "已經餵魚"), "scare_bird": ("趕走鳥", "已經趕走鳥")},
        "sub_desc": "送「{cmd}」給魚塭設備。",
        "main": ("魚塭管家", "讓魚活得好好的:晚上顧溶氧、白天顧鳥、隨時顧水位。", "看著魚塭", "不用做什麼"),
        "rules": {"surfacing": ("魚浮頭:開打氣機", "魚浮頭了(溶氧不足):已開打氣機"),
                  "heron": ("白鷺鷥來了:趕走", "白鷺鷥來了:已經趕走"),
                  "water_low": ("水位低:開抽水馬達", "水位太低:已開抽水馬達"),
                  "water_back": ("水位回來:關抽水馬達", "水位回來了:已關抽水馬達"),
                  "aerator_rest": ("白天魚也正常:關打氣機", "天亮了,魚也正常:已關打氣機")},
        "schedules": {"feed_morning": "早上餵魚", "feed_evening": "傍晚餵魚"},
        "panel": {"title": "魚塭", "pages": {"main": "現況", "settings": "設定", "notify": "通知"},
                  "sources_help": "先啟動模擬器(python sim/server.py),再加入它的攝影機:http://127.0.0.1:8800/video.mjpg",
                  "blocks": {"w_devices": ("魚塭現況", ""), "equipment": ("設備", "手動開關設備。需要時魚塭管家也會自己處理。"),
                             "now": ("停下來 / 繼續", "停下來:魚塭管家不再自己做任何事,直到你按「繼續」。"),
                             "w_schedules": ("今天的餵食", "早上和傍晚的餵食有沒有跑。"),
                             "w_log": ("最近發生的事", ""),
                             "feeding": ("餵食時間", "每天這些時間餵料機會自動餵。"),
                             "pump": ("水位", "抽水馬達會把水位維持在這兩個之間。"),
                             "w_chat": ("通知與指令", "魚塭的消息傳到手機,也可以從聊天下指令。")},
                  "controls": {"aerator_on": "開打氣機", "aerator_off": "關打氣機", "pump_on": "開抽水", "pump_off": "關抽水",
                               "feed_now": "現在餵魚", "scare_now": "趕走鳥", "stop_now": "停下來",
                               "morning_on": "早上餵魚", "morning_at": "早上時間", "evening_on": "傍晚餵魚", "evening_at": "傍晚時間",
                               "pump_start": "低於這個水位就抽水", "pump_stop": "高於這個水位就停止"}},
    },
}


def call(base, method, path, body, lang):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "X-Lang": lang})
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


def out(command):
    return {"type": "output", "output": "pond", "command": command}


def note(text):
    return {"type": "notify", "text": text}


SUBS = [("aerator_on", "aerator_on"), ("aerator_off", "aerator_off"), ("pump_on", "pump_on"), ("pump_off", "pump_off"),
        ("feed", "feed"), ("scare_bird", "scare")]


def states(t):
    out_ = json.load(open(os.path.join(HERE, "states.json"), encoding="utf-8"))["states"]
    for s in out_:
        name, desc, classes, roi = t["states"][s["id"]]
        s["name"], s["description"] = name, desc
        for c in s.get("classes") or []:
            c["name"] = classes[c["value"]]
        s["rois"][0]["name"] = roi
    return out_


def main_script(t):
    r = t["rules"]
    name, desc, sit, nothing = t["main"]
    return {
        "id": "pond_keeper", "name": name, "enabled": True, "devices": {"*": "off", CAM: "live"}, "description": desc,
        "otherwise": {"type": "none", "text": nothing}, "initial": "watching",
        "situations": [{"id": "watching", "name": sit, "rules": [
            {"id": "surfacing", "name": r["surfacing"][0], "enabled": True, "urgent": True, "cooldown": 20,
             "when": [[state("fish_surfacing", "is", "yes", 3), state("aerator_running", "is", "no")]],
             "do": [out("aerator_on"), note(r["surfacing"][1])]},
            {"id": "heron", "name": r["heron"][0], "enabled": True, "cooldown": 15,
             "when": [[state("heron", "is", "yes", 2)]],
             "do": [out("scare"), note(r["heron"][1])]},
            {"id": "water_low", "name": r["water_low"][0], "enabled": True, "cooldown": 60,
             "when": [[state("water_level", "lt", {"setting": "pump_start"}, 5), {"kind": "var", "var": "pumping", "op": "is", "value": 0}]],
             "do": [out("pump_on"), {"type": "set_var", "var": "pumping", "mode": "set", "value": 1}, note(r["water_low"][1])]},
            {"id": "water_back", "name": r["water_back"][0], "enabled": True, "cooldown": 60,
             "when": [[state("water_level", "gt", {"setting": "pump_stop"}, 5), {"kind": "var", "var": "pumping", "op": "is", "value": 1}]],
             "do": [out("pump_off"), {"type": "set_var", "var": "pumping", "mode": "set", "value": 0}, note(r["water_back"][1])]},
            {"id": "aerator_rest", "name": r["aerator_rest"][0], "enabled": True, "cooldown": 60,
             "when": [[state("daylight", "is", "day", 30), state("fish_surfacing", "is", "no", 60), state("aerator_running", "is", "yes", 10)]],
             "do": [out("aerator_off"), note(r["aerator_rest"][1])]},
        ]}]}


def panel(t):
    p = t["panel"]
    b, c = p["blocks"], p["controls"]

    def block(bid, page, items=(), widget=None, toggle=None):
        out_ = {"id": bid, "title": b[bid][0], "help": b[bid][1], "items": list(items), "page": page}
        if widget:
            out_["widget"] = widget
        if toggle:
            out_["toggle"] = toggle
        return out_

    def act(cid, sub):
        return {"id": cid, "label": c[cid], "type": "action", "scope": "device", "bind": {"kind": "act_sub", "sub": sub}}

    return {
        "title": p["title"], "devices": [CAM],
        "pages": [{"id": k, "title": v} for k, v in p["pages"].items()],
        "sources": {"kinds": ["stream/http"], "help": p["sources_help"], "new_mode": "live"},
        "blocks": [
            block("w_devices", "main", widget={"kind": "devices", "show_step": True, "show_alerts": True, "show_image": True}),
            block("equipment", "main", ["aerator_on", "aerator_off", "pump_on", "pump_off", "feed_now", "scare_now"]),
            block("now", "main", ["stop_now"]),
            block("w_schedules", "main", widget={"kind": "schedules", "schedules": []}),
            block("w_log", "main", widget={"kind": "log", "limit": 20, "panel_changes": True}),
            block("feeding", "settings", ["morning_on", "morning_at", "evening_on", "evening_at"]),
            block("pump", "settings", ["pump_start", "pump_stop"]),
            block("w_chat", "notify", widget={"kind": "chat", "setup": True, "pair": True}),
        ],
        "controls": [
            act("aerator_on", "aerator_on"), act("aerator_off", "aerator_off"), act("pump_on", "pump_on"),
            act("pump_off", "pump_off"), act("feed_now", "feed"), act("scare_now", "scare_bird"),
            {"id": "stop_now", "label": c["stop_now"], "type": "action", "scope": "device", "bind": {"kind": "act_stop"}},
            {"id": "morning_on", "label": c["morning_on"], "type": "toggle", "scope": "global", "bind": {"kind": "schedule", "schedule": "feed_morning", "field": "enabled"}},
            {"id": "morning_at", "label": c["morning_at"], "type": "time", "scope": "global", "bind": {"kind": "schedule", "schedule": "feed_morning", "field": "at"}},
            {"id": "evening_on", "label": c["evening_on"], "type": "toggle", "scope": "global", "bind": {"kind": "schedule", "schedule": "feed_evening", "field": "enabled"}},
            {"id": "evening_at", "label": c["evening_at"], "type": "time", "scope": "global", "bind": {"kind": "schedule", "schedule": "feed_evening", "field": "at"}},
            {"id": "pump_start", "label": c["pump_start"], "type": "number", "unit": "%", "scale": 0.01, "min": 10, "max": 60, "scope": "device", "bind": {"kind": "setting", "setting": "pump_start"}},
            {"id": "pump_stop", "label": c["pump_stop"], "type": "number", "unit": "%", "scale": 0.01, "min": 50, "max": 95, "scope": "device", "bind": {"kind": "setting", "setting": "pump_stop"}},
        ],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=sorted(T), default="en")
    ap.add_argument("--url", default="http://127.0.0.1:8766")
    ap.add_argument("--design", help="the pack's design folder, to set the project's name and words (project.json)")
    a = ap.parse_args()
    t, lang, b = T[a.lang], a.lang, a.url.rstrip("/")
    if a.design:
        p = os.path.join(a.design, "project.json")
        pj = json.load(open(p, encoding="utf-8"))
        pj.update({"name": t["project"][0], "description": t["project"][1], "words": t["project"][2],
                   "screen": {"width": 1280, "height": 720}, "plugins": [],
                   # the camera this pack watches, made so on a new computer (Inspector: project.json "sources")
                   "sources": {CAM: {"kind": "stream/http", "name": t["camera"],
                                     "params": {"url": "http://127.0.0.1:8800/video.mjpg", "http_mode": "mjpeg", "fit": "contain"}}}})
        with open(p, "w", encoding="utf-8") as f:
            json.dump(pj, f, ensure_ascii=False, indent=1)
        pk = os.path.join(os.path.dirname(os.path.abspath(a.design)), "pack.json")      # the pack's own name too
        if os.path.exists(pk):
            info = json.load(open(pk, encoding="utf-8"))
            info.update({"name": t["project"][0], "description": t["project"][1], "license": "Apache-2.0",
                         "homepage": "https://github.com/wrbyhaquc/inspector"})
            with open(pk, "w", encoding="utf-8") as f:
                json.dump(info, f, ensure_ascii=False, indent=1)
    call(b, "POST", "/api/states", {"states": states(t), "note": "fish pond"}, lang)
    call(b, "PUT", "/api/outputs", {"outputs": [{"id": "pond", "name": t["output"], "type": "http", "url": SIM, "method": "POST", "headers": {}}]}, lang)
    s = t["settings"]
    call(b, "POST", "/api/settings", {"settings": [
        {"id": "pump_start", "label": s["pump_start"][0], "description": s["pump_start"][1], "type": "number", "scope": "device", "default": 0.3, "min": 0.1, "max": 0.6},
        {"id": "pump_stop", "label": s["pump_stop"][0], "description": s["pump_stop"][1], "type": "number", "scope": "device", "default": 0.75, "min": 0.5, "max": 0.95}]}, lang)
    call(b, "POST", "/api/variables", {"vars": [{"name": "pumping", "label": t["var"], "scope": "device", "reset": "never", "initial": 0}]}, lang)
    for sid, cmd in SUBS:
        name, text = t["subs"][sid]
        call(b, "POST", "/api/subscripts", {"sub": {"id": sid, "name": name, "description": t["sub_desc"].format(cmd=cmd), "timeout": 30,
                                                    "params": [], "say": name, "steps": [out(cmd), note(text)], "cleanup": []},
                                            "note": "fish pond"}, lang)
    call(b, "POST", "/api/scripts", {"script": main_script(t), "note": "fish pond"}, lang)
    call(b, "POST", "/api/schedules", {"items": [
        {"id": sid, "name": name, "enabled": True, "at": at, "days": [], "window": 120, "devices": [CAM], "sub": "feed",
         "args": {}, "pause_others": False, "max_minutes": 5}
        for (sid, name), at in zip(t["schedules"].items(), ("08:00", "17:00"))]}, lang)
    call(b, "POST", "/api/panel/definition", {"panel": panel(t)}, lang)
    print(f"done ({lang}): states, output, 2 settings, variable, {len(SUBS)} sub-scripts, main script, 2 schedules, panel")


if __name__ == "__main__":
    main()
