"""End-to-end check of the running system (Django + simulator or real bin).

1. Start Django:      RUN_WEBSITE.bat   (or: python backend\\manage.py runserver)
2. Start the bin:     python device\\simulator.py   (or power on the real hardware)
3. Run this:          python tools\\system_check.py

Uses only the Python standard library.
"""

import argparse
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  -> ' + str(detail) if detail and not ok else ''}")
    return ok


class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def csrf(self):
        return next((c.value for c in self.jar if c.name == "csrftoken"), "")

    def call(self, method, path, body=None, raw=False):
        headers = {"X-CSRFToken": self.csrf(), "Referer": self.base + "/"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=15) as r:
                content = r.read()
                return r.status, (content if raw else json.loads(content or b"null")), r.headers
        except urllib.error.HTTPError as e:
            content = e.read()
            try:
                return e.code, json.loads(content), e.headers
            except ValueError:
                return e.code, content, e.headers

    def login(self, user, pw):
        self.call("GET", "/api/auth/csrf/")
        return self.call("POST", "/api/auth/login/", {"username": user, "password": pw})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="admin12345")
    ap.add_argument("--viewer", default="cleaner")
    ap.add_argument("--viewer-password", default="cleaner12345")
    ap.add_argument("--no-device", action="store_true", help="skip checks that need a running bin")
    a = ap.parse_args()

    print("\n1. Web pages")
    c = Client(a.url)
    for page in ("/", "/control", "/analytics", "/logo.png"):
        s, body, h = c.call("GET", page, raw=True)
        check(f"GET {page}", s == 200, s)
    s, *_ = c.call("GET", "/api/bins/")
    check("API refuses anonymous users", s == 403, s)

    print("\n2. Login")
    s, me, _ = c.login(a.user, "wrong-password")
    check("wrong password rejected", s == 400, s)
    s, me, _ = c.login(a.user, a.password)
    if not check(f"login as {a.user}", s == 200 and me.get("is_staff"), me):
        sys.exit("Cannot log in: run  python backend\\manage.py seed_demo  first.")

    print("\n3. Dashboard data")
    s, bins, _ = c.call("GET", "/api/bins/")
    check("bins listed", s == 200 and len(bins) > 0, bins)
    bin = bins[0]
    s, o, _ = c.call("GET", f"/api/bins/{bin['id']}/overview/")
    check("overview", s == 200 and {"compartments", "recommendations", "trend"} <= set(o), s)
    check("both compartments have a level", all(o["compartments"][k]["level"] is not None for k in ("organic", "inorganic")))
    check("recommendations generated", len(o["recommendations"]) > 0)
    for path in (f"/api/bins/{bin['id']}/analytics/?days=7", f"/api/bins/{bin['id']}/readings/?hours=24",
                 f"/api/detections/?bin={bin['id']}", f"/api/alerts/?bin={bin['id']}"):
        s, *_ = c.call("GET", path)
        check(f"GET {path.split('?')[0]}", s == 200, s)
    s, csv, h = c.call("GET", f"/api/bins/{bin['id']}/export/?type=detections&days=1", raw=True)
    check("CSV export", s == 200 and csv.startswith(b"time,label"), s)

    if not a.no_device:
        print("\n4. Live device (simulator or real bin)")
        check("controller online", o["bin"]["is_online"], "start device\\simulator.py")
        before = o["today"]["total"]
        time.sleep(12)
        s, o2, _ = c.call("GET", f"/api/bins/{bin['id']}/overview/")
        check("new items arriving", o2["today"]["total"] > before, f"{before} -> {o2['today']['total']}")
        last = o2["last_detection"]
        if last and last.get("image_url"):
            s, img, _ = c.call("GET", "/media/" + last["image_url"].split("/media/", 1)[1], raw=True)
            check("camera photo served", s == 200 and img[:2] == b"\xff\xd8", s)

        print("\n5. Remote control round-trip")
        for action, payload in [("open_lid", {}), ("close_lid", {}), ("sort_organic", {}), ("capture", {}),
                                ("buzzer", {}), ("set_mode", {"mode": "manual"}), ("set_mode", {"mode": "auto"})]:
            s, cmd, _ = c.call("POST", f"/api/bins/{bin['id']}/commands/", {"action": action, "payload": payload})
            ok = s == 201
            for _ in range(20):
                time.sleep(0.5)
                _, cmds, _ = c.call("GET", f"/api/bins/{bin['id']}/commands/")
                status = next(x["status"] for x in cmds if x["id"] == cmd["id"])
                if status in ("done", "failed"):
                    break
            check(f"{action} {payload or ''} executed by bin", ok and status == "done", status)

    print("\n6. Collections & alerts")
    s, col, _ = c.call("POST", f"/api/bins/{bin['id']}/collections/", {"compartment": "organic", "note": "system check"})
    check("record collection", s == 201, col)

    print("\n7. Permissions (viewer account)")
    v = Client(a.url)
    s, me, _ = v.login(a.viewer, a.viewer_password)
    if check(f"login as {a.viewer}", s == 200 and not me.get("is_staff"), me):
        s, b, _ = v.call("GET", f"/api/bins/{bin['id']}/")
        check("viewer cannot see API key", b.get("api_key") is None)
        s, *_ = v.call("POST", f"/api/bins/{bin['id']}/commands/", {"action": "open_lid"})
        check("viewer cannot send commands", s == 403, s)
        s, *_ = v.call("PATCH", f"/api/bins/{bin['id']}/", {"name": "hacked"})
        check("viewer cannot change settings", s == 403, s)

    s, *_ = c.call("POST", "/api/auth/logout/")
    s2, *_ = c.call("GET", "/api/bins/")
    check("logout ends the session", s == 200 and s2 == 403, (s, s2))

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed.")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
