"""A fish pond, simulated and drawn as a cartoon camera picture - a stand-in for a real farm camera, so Inspector can
be tried without one.

What happens in it (time runs faster than real time, one day in a few minutes):
  - day and night; the oxygen in the water rises by day (plants) and falls at night (fish breathe). When it is low
    the fish come up to the surface gasping for air; when it stays too low some fish die.
  - the aerator (paddle wheel) adds oxygen while it runs: foam and spray around it.
  - the water level drops slowly (evaporation) and rises with rain or the pump.
  - now and then a heron lands at the edge and takes a fish now and then, until it is scared away.
  - the feeder throws pellets; the fish gather there.

Nothing in the picture is read from this model by Inspector: it only sees the picture, like a real camera, and acts
through the commands (aerator, pump, feeder, scare) - the way it would drive real equipment."""
import math
import random
import threading
import time

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1280, 720
POND = (150, 175, 1130, 640)                    # the pond's bank (outer ellipse box)
LEVEL_TUBE = (1180, 250, 24, 200)               # the level gauge on the right bank: a clear tube, x y w h


def _font(size):
    for name in ("arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT = _font(22)
FONT_S = _font(16)


def _mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Pond:
    def __init__(self, seed=None, day_minutes=6.0):
        self.rng = random.Random(seed)
        self.lock = threading.Lock()
        self.day_minutes = day_minutes          # real minutes for one simulated day
        self.hour = 9.0                         # simulated time of day (0..24)
        self.day = 1
        self.oxygen = 7.5                       # mg/L
        self.level = 72.0                       # % of the staff
        self.aerator = False
        self.pump = False
        self.feeding_until = 0.0                # real time
        self.rain_hours = 0.0                   # simulated hours of rain left
        self.heron = None                       # {"x", "y", "since", "leaving"}
        self.fish_total = 14
        self.lost_heron = 0
        self.lost_oxygen = 0
        self._low_for = 0.0
        self._heron_meal = 0.0
        self.fish = [self._new_fish(i) for i in range(self.fish_total)]
        self.log = []                           # [(real time, text)]
        self._last = time.time()

    # ---------------- the model ----------------
    def _new_fish(self, i):
        r = self.rng
        return {"a": r.uniform(0, 2 * math.pi), "r": r.uniform(0.2, 0.7), "speed": r.uniform(0.05, 0.12) * r.choice([1, -1]),
                "size": r.uniform(0.8, 1.25), "phase": r.uniform(0, 6.28), "hue": r.choice([(245, 130, 40), (240, 90, 50), (250, 175, 60)])}

    def note(self, text):
        self.log.append((time.time(), text))
        self.log = self.log[-30:]

    def daylight(self):
        """0 at night, 1 at noon."""
        return max(0.0, math.sin((self.hour - 6) / 12 * math.pi)) if 6 <= self.hour <= 18 else 0.0

    def is_night(self):
        return self.hour < 6 or self.hour >= 18.5

    def step(self):
        now = time.time()
        dt_real = min(1.0, now - self._last)
        self._last = now
        hours = dt_real / (self.day_minutes * 60) * 24
        with self.lock:
            self.hour += hours
            if self.hour >= 24:
                self.hour -= 24
                self.day += 1
            sun = self.daylight()
            n = len(self.fish)
            # oxygen: plants by day, fish and mud all the time, the aerator, a little from the air
            d = 1.5 * sun - 0.6 - 0.02 * n + (1.5 if self.aerator else 0) + 0.08 * (7 - self.oxygen)
            self.oxygen = max(0.5, min(11.0, self.oxygen + d * hours))
            if self.oxygen < 1.6:
                self._low_for += hours
                if self._low_for > 2.5 and n > 4:
                    self.fish.pop()
                    self.lost_oxygen += 1
                    self._low_for = 0.0
                    self.note("a fish died: too little oxygen")
            else:
                self._low_for = 0.0
            # water level: evaporation, rain, the pump
            evap = 0.35 + 0.6 * sun
            self.level += (-evap + (7.0 if self.rain_hours > 0 else 0) + (5.0 if self.pump else 0)) * hours
            self.level = max(5.0, min(100.0, self.level))
            if self.rain_hours > 0:
                self.rain_hours = max(0.0, self.rain_hours - hours)
            elif self.rng.random() < 0.06 * hours:
                self.rain_hours = self.rng.uniform(1.0, 2.5)
                self.note("rain")
            # the heron
            if self.heron is None:
                if sun > 0.15 and self.rng.random() < 0.18 * hours:
                    self.land_heron()
            else:
                h = self.heron
                if h["leaving"] is not None:
                    if now - h["leaving"] > 3:
                        self.heron = None
                else:
                    h["stay"] -= hours
                    self._heron_meal += hours
                    if self._heron_meal > 0.6 and len(self.fish) > 4:
                        self.fish.pop()
                        self.lost_heron += 1
                        self._heron_meal = 0.0
                        self.note("the heron took a fish")
                    if h["stay"] <= 0:
                        h["leaving"] = now
                        self.note("the heron flew away")
            for f in self.fish:
                f["a"] += f["speed"] * dt_real * 6
                f["phase"] += dt_real * 4

    def land_heron(self):
        side = self.rng.choice([(870, 215), (560, 205), (330, 225)])     # on the far bank, where the camera sees it whole
        self.heron = {"x": side[0], "y": side[1], "stay": self.rng.uniform(1.5, 3.0), "leaving": None, "since": time.time()}
        self._heron_meal = 0.0
        self.note("a heron landed")

    def command(self, cmd, value=None):
        """What equipment and the demo buttons do: aerator_on / aerator_off / pump_on / pump_off / feed / scare;
        demo: night / day / heron / rain / level (value = %) / restock / speed (value = real minutes per day); test: does nothing."""
        cmd = (cmd or "").strip().lower()
        with self.lock:
            if cmd in ("aerator_on", "aerator_off"):
                self.aerator = cmd.endswith("on")
            elif cmd == "aerator":
                self.aerator = str(value).lower() in ("1", "true", "on", "yes")
            elif cmd in ("pump_on", "pump_off"):
                self.pump = cmd.endswith("on")
            elif cmd == "pump":
                self.pump = str(value).lower() in ("1", "true", "on", "yes")
            elif cmd == "feed":
                self.feeding_until = time.time() + 15
            elif cmd == "scare":
                if self.heron and self.heron["leaving"] is None:
                    self.heron["leaving"] = time.time()
                    self.note("the heron was scared away")
            elif cmd == "night":
                self.hour = 21.0
            elif cmd == "day":
                self.hour = 9.0
            elif cmd == "heron":
                if self.heron is None:
                    self.land_heron()
            elif cmd == "level":                 # demo: set the water level (value = %)
                self.level = max(5.0, min(100.0, float(value)))
            elif cmd == "rain":
                self.rain_hours = 2.0
            elif cmd == "restock":
                while len(self.fish) < self.fish_total:
                    self.fish.append(self._new_fish(len(self.fish)))
                self.lost_heron = self.lost_oxygen = 0
            elif cmd == "test":                 # Inspector's "Test" button on an output: just say it arrived
                pass
            elif cmd == "speed":
                self.day_minutes = max(0.5, min(240.0, float(value)))
            else:
                raise ValueError(f"unknown command: {cmd}")
            if cmd not in ("speed",):
                self.note(f"command: {cmd}" + ("" if value is None else f" {value}"))

    def state(self):
        with self.lock:
            return {"day": self.day, "hour": round(self.hour, 2), "night": self.is_night(), "oxygen": round(self.oxygen, 2),
                    "fish_surfacing": self.oxygen < 3.0, "level": round(self.level, 1), "aerator": self.aerator,
                    "pump": self.pump, "feeding": time.time() < self.feeding_until, "raining": self.rain_hours > 0,
                    "heron": self.heron is not None and self.heron["leaving"] is None, "fish": len(self.fish),
                    "lost_heron": self.lost_heron, "lost_oxygen": self.lost_oxygen, "day_minutes": self.day_minutes,
                    "log": [t for _, t in self.log[-8:]]}

    # ---------------- the picture ----------------
    def draw(self):
        with self.lock:
            return self._draw()

    def _water_box(self):
        x0, y0, x1, y1 = POND
        inset = 24 + (100 - self.level) * 0.55        # lower water: a wider band of mud shows inside the bank
        return (x0 + inset, y0 + inset * 0.7, x1 - inset, y1 - inset * 0.7)

    def _draw(self):
        t = time.time()
        sun = self.daylight()
        night = self.is_night()
        img = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(img, "RGBA")

        # sky, hills, grass
        sky = _mix((25, 30, 70), (130, 195, 245), sun if not night else 0)
        if 5 <= self.hour < 7 or 17.5 <= self.hour < 19:
            sky = _mix(sky, (240, 150, 90), 0.45)
        d.rectangle((0, 0, W, 130), fill=sky)
        if sun > 0:
            sx = 100 + (self.hour - 6) / 12 * (W - 200)
            d.ellipse((sx - 30, 60 - 40 * sun - 25, sx + 30, 60 - 40 * sun + 35), fill=(255, 225, 90))
        elif night:
            d.ellipse((1050, 25, 1095, 70), fill=(235, 235, 210))
            d.ellipse((1068, 20, 1110, 62), fill=sky)
        hill = _mix((40, 70, 50), (90, 160, 90), sun)
        d.polygon([(0, 130), (180, 85), (380, 120), (600, 75), (860, 118), (1080, 80), (1280, 115), (1280, 140), (0, 140)], fill=hill)
        grass = _mix((30, 55, 35), (110, 175, 80), max(sun, 0.15 if not night else 0.05))
        d.rectangle((0, 130, W, H), fill=grass)
        rng = random.Random(7)
        for _ in range(140):                    # tufts of grass (fixed places)
            gx, gy = rng.randint(0, W), rng.randint(140, H)
            if (gx - 640) ** 2 / 520 ** 2 + (gy - 408) ** 2 / 255 ** 2 < 1:
                continue
            d.line((gx, gy, gx - 3, gy - 9), fill=_mix(grass, (20, 60, 20), 0.5), width=2)
            d.line((gx, gy, gx + 3, gy - 8), fill=_mix(grass, (20, 60, 20), 0.5), width=2)

        # bank, mud, water
        bank = _mix((52, 48, 42), (138, 126, 108), max(sun, 0.2))       # grey-brown earth
        d.ellipse(POND, fill=bank)
        x0, y0, x1, y1 = POND
        d.ellipse((x0 + 14, y0 + 10, x1 - 14, y1 - 10), fill=_mix(bank, (92, 86, 76), 0.6))
        wb = self._water_box()
        o = self.oxygen
        water = _mix((95, 125, 70), (45, 140, 165), (o - 2) / 5)
        water = _mix(water, (15, 25, 45), 0.7 if night else 0.35 * (1 - sun))
        d.ellipse(wb, fill=water)
        cx, cy = (wb[0] + wb[2]) / 2, (wb[1] + wb[3]) / 2
        rx, ry = (wb[2] - wb[0]) / 2, (wb[3] - wb[1]) / 2
        for k in range(10):                     # little waves
            a = k * 0.63 + t * 0.15
            wx, wy = cx + math.cos(a) * rx * 0.6, cy + math.sin(a * 1.3) * ry * 0.55
            d.arc((wx - 30, wy - 6, wx + 30, wy + 6), 200, 340, fill=(255, 255, 255, 40), width=2)

        # fish (under water: dim; at the surface gasping when the oxygen is low)
        surfacing = o < 3.0
        feeding = t < self.feeding_until
        for i, f in enumerate(self.fish):
            r = f["r"]
            a = f["a"]
            fx, fy = cx + math.cos(a) * rx * r * 0.85, cy + math.sin(a) * ry * r * 0.8
            if feeding:
                tx, ty = 960, 545
                fx, fy = fx + (tx - fx) * 0.55, fy + (ty - fy) * 0.55
            if surfacing:                          # up for air in open water: not by the running machine, not by the far bank
                fx, fy = cx + math.cos(a * 0.3 + i) * rx * 0.55, cy + math.sin(i * 1.7) * ry * 0.45
                fy = max(fy, y0 + 115)
                if abs(fx - 360) < 120 and abs(fy - 430) < 80:
                    fx += 240
            s = 22 * f["size"]
            ang = a + (math.pi / 2 if f["speed"] > 0 else -math.pi / 2)
            col = f["hue"]
            if surfacing:
                pulse = 1 + 0.25 * math.sin(f["phase"] * 2)
                for ring in (1.0, 1.7):
                    rr = s * ring * pulse
                    d.ellipse((fx - rr, fy - rr * 0.6, fx + rr, fy + rr * 0.6), outline=(235, 245, 255, 170), width=2)
                d.ellipse((fx - s * 0.55, fy - s * 0.55, fx + s * 0.55, fy + s * 0.55), fill=col + (255,))
                d.ellipse((fx - s * 0.22, fy - s * 0.22, fx + s * 0.22, fy + s * 0.22), fill=(60, 20, 20, 255))
                continue
            alpha = 120 if not night else 70
            dx, dy = math.cos(ang), math.sin(ang)
            body = [(fx + dx * s, fy + dy * s * 0.7), (fx - dy * s * 0.4, fy + dx * s * 0.3), (fx - dx * s * 0.8, fy - dy * s * 0.55),
                    (fx + dy * s * 0.4, fy - dx * s * 0.3)]
            d.polygon(body, fill=col + (alpha,))
            tail = [(fx - dx * s * 0.75, fy - dy * s * 0.5), (fx - dx * s * 1.3 - dy * s * 0.4, fy - dy * s * 0.9 + dx * s * 0.3),
                    (fx - dx * s * 1.3 + dy * s * 0.4, fy - dy * s * 0.9 - dx * s * 0.3)]
            d.polygon(tail, fill=col + (alpha,))

        # the aerator (paddle wheel on floats)
        ax, ay = 360, 430
        if self.aerator:                        # a white wake on both sides of the wheel, and bubbles around it
            d.ellipse((ax - 85, ay - 40, ax + 85, ay + 40), fill=(240, 250, 255, 70))
            for side in (-1, 1):
                for k in range(9):
                    wx = ax + side * (62 + k * 7 + (int(t * 40) + k * 5) % 6)
                    wy = ay - 14 + (k * 7) % 28
                    d.ellipse((wx - 9, wy - 6, wx + 9, wy + 6), fill=(255, 255, 255, 235))
            for k in range(26):
                rr = 18 + (k * 37 + int(t * 60)) % 70
                aa = k * 0.9 + t * 2
                bx, by = ax + math.cos(aa) * rr, ay + math.sin(aa) * rr * 0.55
                d.ellipse((bx - 5, by - 4, bx + 5, by + 4), fill=(255, 255, 255, 190))
        d.rounded_rectangle((ax - 60, ay - 12, ax + 60, ay + 12), 6, fill=(235, 195, 40))
        spin = t * 9 if self.aerator else 0.4
        for k in range(4):
            aa = spin + k * math.pi / 2
            px, py = ax + math.cos(aa) * 34, ay + math.sin(aa) * 16
            d.line((ax, ay, px, py), fill=(70, 70, 80), width=6)
            d.rectangle((px - 7, py - 5, px + 7, py + 5), fill=(60, 120, 200))
        d.ellipse((ax - 9, ay - 9, ax + 9, ay + 9), fill=(80, 80, 90))
        d.line((ax - 60, ay, x0 + 30, ay - 40), fill=(40, 40, 40), width=3)       # its power cable to the bank

        # the pump's pipe (top left)
        px0, py0 = x0 + 70, y0 + 300
        d.rounded_rectangle((px0 - 70, py0 - 18, px0 + 10, py0 + 2), 6, fill=(120, 125, 135))
        if self.pump:
            for k in range(8):
                yy = py0 + (k * 13 + int(t * 120)) % 90
                d.line((px0 + 4, yy, px0 + 10, yy + 10), fill=(220, 240, 255, 220), width=4)
            d.ellipse((px0 - 20, py0 + 80, px0 + 40, py0 + 105), fill=(240, 250, 255, 120))

        # the feeder (bottom right, on the bank)
        fx0, fy0 = 1000, 585
        d.rectangle((fx0 - 4, fy0, fx0 + 4, fy0 + 45), fill=(90, 90, 90))
        d.polygon([(fx0 - 32, fy0 - 40), (fx0 + 32, fy0 - 40), (fx0 + 20, fy0), (fx0 - 20, fy0)], fill=(180, 185, 195))
        d.rectangle((fx0 - 35, fy0 - 50, fx0 + 35, fy0 - 40), fill=(150, 155, 165))
        if feeding:
            for k in range(30):
                u = ((k * 0.13 + t * 0.9) % 1.0)
                bx = fx0 - 20 - u * 90 + math.sin(k) * 15
                by = fy0 - 20 - math.sin(u * math.pi) * 60 + u * 25
                d.ellipse((bx - 3, by - 3, bx + 3, by + 3), fill=(85, 52, 24))

        # the level gauge: a clear tube on the bank, blue water up to the pond's level, marks every 10%
        tx, ty, tw, th = LEVEL_TUBE
        d.rounded_rectangle((tx - 6, ty - 8, tx + tw + 6, ty + th + 8), 6, fill=(90, 95, 105))
        d.rectangle((tx, ty, tx + tw, ty + th), fill=(215, 222, 228))
        top = ty + th - self.level / 100 * th
        d.rectangle((tx, top, tx + tw, ty + th), fill=(35, 105, 215))
        for k in range(11):
            yy = ty + th - k * th / 10
            d.line((tx - 14, yy, tx - 7, yy), fill=(240, 240, 240), width=3 if k % 5 == 0 else 1)
        d.text((tx - 16, ty + th + 12), "LEVEL", font=FONT_S, fill=(240, 240, 240))

        # the heron
        if self.heron:
            h = self.heron
            hx, hy = h["x"], h["y"]
            if h["leaving"] is not None:
                u = time.time() - h["leaving"]
                hx, hy = hx + u * 220, hy - u * 160
                wing = math.sin(u * 18) * 25
                d.polygon([(hx - 10, hy), (hx - 70, hy - 20 - wing), (hx - 20, hy + 8)], fill=(245, 245, 245))
                d.polygon([(hx + 10, hy), (hx + 70, hy - 20 - wing), (hx + 20, hy + 8)], fill=(235, 235, 235))
                d.ellipse((hx - 28, hy - 10, hx + 28, hy + 12), fill=(250, 250, 250))
            else:
                d.line((hx - 8, hy + 20, hx - 10, hy + 70), fill=(60, 60, 60), width=4)
                d.line((hx + 8, hy + 20, hx + 10, hy + 70), fill=(60, 60, 60), width=4)
                d.ellipse((hx - 34, hy - 18, hx + 30, hy + 28), fill=(250, 250, 250))
                d.line((hx + 20, hy - 6, hx + 30, hy - 60), fill=(250, 250, 250), width=10)
                d.ellipse((hx + 20, hy - 76, hx + 44, hy - 56), fill=(250, 250, 250))
                d.polygon([(hx + 42, hy - 70), (hx + 80, hy - 64), (hx + 42, hy - 62)], fill=(235, 180, 40))
                d.ellipse((hx + 33, hy - 70, hx + 37, hy - 66), fill=(20, 20, 20))

        # rain
        if self.rain_hours > 0:
            for k in range(160):
                rx_ = (k * 97 + int(t * 400)) % W
                ry_ = (k * 53 + int(t * 900)) % H
                d.line((rx_, ry_, rx_ - 6, ry_ + 18), fill=(200, 210, 230, 140), width=2)
            d.rectangle((0, 0, W, H), fill=(60, 70, 90, 40))

        # night: darker overall
        if night:
            d.rectangle((0, 0, W, H), fill=(5, 10, 30, 110))

        # camera overlay
        hh, mm = int(self.hour), int((self.hour % 1) * 60)
        d.rectangle((14, 12, 330, 46), fill=(0, 0, 0, 120))
        d.text((24, 16), f"CAM-01  POND A   {hh:02d}:{mm:02d}", font=FONT, fill=(255, 255, 255))
        if int(t * 2) % 2 == 0:
            d.ellipse((1222, 20, 1240, 38), fill=(230, 40, 40))
        d.text((1180, 18), "REC", font=FONT_S, fill=(255, 255, 255))
        return img.filter(ImageFilter.SMOOTH) if False else img
