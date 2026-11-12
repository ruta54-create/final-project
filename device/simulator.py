"""Smart-bin SIMULATOR: behaves exactly like the two real boards
(ESP32 main controller + ESP32-CAM) so you can test the whole web system
without hardware.

    backend\\venv\\Scripts\\python device\\simulator.py
    backend\\venv\\Scripts\\python device\\simulator.py --key <api key> --items-per-min 6

It: reports sensors, sends classified items with a generated photo,
polls the dashboard's remote commands and executes/acknowledges them.
"""

import argparse
import io
import json
import random
import sys
import time
import urllib.error
import urllib.request
import uuid

try:
    from PIL import Image, ImageDraw  # optional: makes fake camera photos
except ImportError:
    Image = None

FIRMWARE = "sim-2.0.0"
MODEL_VERSION = "waste4-mobilenetv2-128-v1"
# the 4 materials the AI recognises -> compartment (paper is biodegradable, so it goes to ORGANIC)
BIN_OF = {"organic": "organic", "paper": "organic", "plastic": "inorganic", "metal": "inorganic"}
SHARE = {"organic": 0.38, "paper": 0.22, "plastic": 0.28, "metal": 0.12}


class Device:
    def __init__(self, url, key):
        self.base = url.rstrip("/") + "/api/device"
        self.key = key

    def request(self, method, path, payload=None, files=None):
        headers = {"X-API-KEY": self.key}
        data = None
        if files:
            boundary = uuid.uuid4().hex
            parts = []
            for k, v in (payload or {}).items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
            for k, (name, content, ctype) in files.items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                             f"Content-Type: {ctype}\r\n\r\n".encode() + content + b"\r\n")
            parts.append(f"--{boundary}--\r\n".encode())
            data = b"".join(parts)
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif payload is not None:
            data = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read() or b"null")


def fake_photo(label):
    """Draw a simple 'object on a tray' picture like the ESP32-CAM would send."""
    if Image is None:
        return None
    img = Image.new("RGB", (320, 240), (225, 228, 232))
    d = ImageDraw.Draw(img)
    d.rectangle([20, 200, 300, 230], fill=(190, 194, 200))  # tray edge
    j = random.randint(-25, 25)
    if label == "plastic":            # bottle with a cap
        d.rounded_rectangle([130 + j, 60, 190 + j, 200], 14, fill=(80, 160, 230), outline=(40, 90, 160), width=3)
        d.rectangle([148 + j, 40, 172 + j, 62], fill=(30, 80, 200))
    elif label == "metal":            # drink can
        d.rounded_rectangle([120 + j, 80, 200 + j, 200], 10, fill=(170, 170, 180), outline=(90, 90, 100), width=3)
        d.rectangle([120 + j, 120, 200 + j, 150], fill=(200, 30, 40))
    elif label == "paper":            # crumpled sheet with printed lines
        d.polygon([(90 + j, 70), (230 + j, 60), (240 + j, 190), (85 + j, 200)], fill=(248, 246, 238), outline=(150, 150, 150))
        for y in range(85, 185, 14):
            d.line([(105 + j, y), (220 + j, y - 3)], fill=(120, 120, 140), width=2)
    elif random.random() < 0.5:       # organic: banana peel
        d.chord([70 + j, 60, 250 + j, 220], 200, 340, fill=(240, 200, 40), outline=(150, 120, 20), width=3)
    else:                             # organic: leaves
        for i in range(4):
            x = 90 + i * 35 + j
            d.ellipse([x, 90 + i * 12, x + 70, 150 + i * 12], fill=(60, 150, 50), outline=(30, 90, 30), width=2)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser(description="Simulate the smart bin hardware")
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--key", default="demo-key-bin-001", help="bin API key (Settings page)")
    ap.add_argument("--items-per-min", type=float, default=4)
    ap.add_argument("--telemetry-s", type=float, default=5, help="real device: 30 s")
    args = ap.parse_args()

    dev = Device(args.url, args.key)
    while True:  # the server can take ~30 s to start: wait for it
        try:
            cfg = dev.request("GET", "/config/")
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                sys.exit("Wrong API key. Copy it from Settings > Device API key and use --key.")
            print(f"Server error {e.code}, retrying in 3 s...")
        except OSError:
            print(f"Waiting for the server at {args.url} ...")
        time.sleep(3)
    dev.request("GET", "/config/?role=cam")
    # real physical depth of the simulated compartments (does not change, like a real bin)
    depth = {c: cfg[f"{c}_depth_cm"] if cfg[f"{c}_depth_cm"] >= 10 else 40.0 for c in ("organic", "inorganic")}
    dist = {"organic": depth["organic"] * 0.8, "inorganic": depth["inorganic"] * 0.85}
    state = {"mode": cfg["mode"], "lid": False, "booted": True}
    print(f"Connected to '{cfg['name']}' (mode={cfg['mode']}). Ctrl+C to stop.\n")

    def level(c):
        return round((1 - dist[c] / depth[c]) * 100)

    def classify(forced=None):
        label = random.choices(list(SHARE), weights=list(SHARE.values()))[0]
        cat = BIN_OF[label]
        conf = round(random.uniform(0.55, 0.7) if random.random() < 0.12 else random.uniform(0.8, 0.99), 3)
        payload = {"label": label, "category": cat, "confidence": conf, "inference_ms": random.randint(380, 620),
                   "firmware": FIRMWARE, "model_version": MODEL_VERSION}
        photo = fake_photo(label)
        res = dev.request("POST", "/detection/", payload,
                          files={"image": ("capture.jpg", photo, "image/jpeg")} if photo else None)
        to = res["sorted_to"]
        dist[to] = max(1.0, dist[to] - random.uniform(0.3, 1.1))  # item lands in that compartment
        print(f"  item  {label:15s} {cat:9s} {conf:.0%}  -> {to}{'  (uncertain)' if res['uncertain'] else ''}")

    def telemetry():
        for c in dist:  # a cleaner empties a compartment when it is very full
            if level(c) >= 96:
                dist[c] = depth[c] - random.uniform(0.5, 2)
                print(f"  ** {c} compartment emptied")
        org = level("organic")
        res = dev.request("POST", "/telemetry/", {
            "organic_distance_cm": round(dist["organic"], 1),
            "inorganic_distance_cm": round(dist["inorganic"], 1),
            "gas_ppm": round(120 + org * 3.2 + random.uniform(-15, 15)),
            "temperature": round(random.uniform(24, 29), 1),
            "humidity": round(random.uniform(55, 70), 1),
            "lid_open": state["lid"], "firmware": FIRMWARE, "wifi_rssi": random.randint(-70, -50),
            "booted": state["booted"],
        })
        state["booted"] = False
        state["mode"] = res["mode"]
        print(f"  telemetry  organic {res['organic_level']}%  inorganic {res['inorganic_level']}%  mode={res['mode']}")

    def run_commands():
        res = dev.request("GET", "/commands/")
        state["mode"] = res["mode"]
        for cmd in res["commands"]:
            action, result, msg = cmd["action"], {}, ""
            if action in ("open_lid", "close_lid"):
                state["lid"] = action == "open_lid"
            elif action in ("sort_organic", "sort_inorganic"):
                msg = "Tray tilted and returned to centre"
            elif action == "capture":
                classify()
            elif action == "calibrate":
                # the operator empties both compartments before calibrating (as the dashboard asks)
                for c in dist:
                    dist[c] = depth[c] - random.uniform(0.0, 0.4)
                result = {"organic_depth_cm": round(dist["organic"], 1), "inorganic_depth_cm": round(dist["inorganic"], 1)}
                msg = f"Measured {result['organic_depth_cm']} / {result['inorganic_depth_cm']} cm"
                print("  ** both compartments emptied for calibration")
            elif action == "set_mode":
                state["mode"] = cmd["payload"].get("mode", state["mode"])
            elif action == "reboot":
                state["booted"] = True
            dev.request("POST", f"/commands/{cmd['id']}/ack/", {"status": "done", "message": msg, "result": result})
            print(f"  command {action} -> done")

    next_tel = next_cmd = next_cam = 0.0
    next_item = time.time() + 60 / args.items_per_min
    while True:
        now = time.time()
        try:
            if now >= next_cmd:
                run_commands()
                next_cmd = now + 2
            if now >= next_tel:
                telemetry()
                next_tel = now + args.telemetry_s
            if now >= next_cam:
                dev.request("GET", "/config/?role=cam")  # camera heartbeat
                next_cam = now + 60
            if now >= next_item:
                if state["mode"] == "auto":
                    classify()
                next_item = now + random.expovariate(args.items_per_min / 60)
        except urllib.error.HTTPError as e:
            print(f"  server error {e.code}: {e.read()[:200]!r}")
            if e.code in (401, 403):
                print("  -> wrong API key? Copy it from Settings > Device API key.")
                return
        except OSError as e:
            print(f"  network error: {e}. Is Django running?")
            time.sleep(3)
        time.sleep(0.2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
