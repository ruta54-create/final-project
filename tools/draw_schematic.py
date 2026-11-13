"""Draws the Proteus-style schematic of the Edge-AI Smart Dustbin hardware.

    python tools/draw_schematic.py      ->  docs/schematic/smart_dustbin_schematic.svg

Pin numbers follow device/esp32_main/esp32_main.ino and device/esp32_cam/camera_pins.h.
Connections use NET LABELS (as in Proteus ISIS): two pins with the same label are connected.
"""

from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "docs" / "schematic"
W, H = 2480, 1754                       # A-size landscape sheet ratio (1.414)

# Proteus ISIS look
BG, GRID = "#fffff4", "#e9e9d6"
BODY, EDGE = "#ffffc4", "#8b1a1a"       # component body / outline
WIRE = "#00327a"                        # wires
PINTXT, REFTXT = "#14148c", "#00008b"
PWR, GNDC = "#c00000", "#222222"

svg = []


def add(s):
    svg.append(s)


def text(x, y, s, size=13, color="#000", anchor="start", weight="normal", italic=False):
    st = ' font-style="italic"' if italic else ""
    add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" '
        f'font-weight="{weight}"{st}>{escape(str(s))}</text>')


def line(x1, y1, x2, y2, color=WIRE, w=2):
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}" stroke-linecap="round"/>')


def dot(x, y):
    add(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{WIRE}"/>')


# ------------------------------------------------------------------ net labels & power symbols
def net(x, y, name, side="right"):
    """Proteus-style net label at the end of a wire (side = where the label sits)."""
    if name in ("+5V", "+3V3"):
        return power(x, y, name, side)
    if name == "GND":
        return ground(x, y, side)
    w = 9 * len(name) + 18
    if side == "right":
        pts = f"{x},{y} {x + 10},{y - 11} {x + w},{y - 11} {x + w},{y + 11} {x + 10},{y + 11}"
        tx = x + 12
    else:
        pts = f"{x},{y} {x - 10},{y - 11} {x - w},{y - 11} {x - w},{y + 11} {x - 10},{y + 11}"
        tx = x - w + 4
    add(f'<polygon points="{pts}" fill="#eef4ff" stroke="{WIRE}" stroke-width="1.3"/>')
    text(tx, y + 5, name, 12.5, WIRE, weight="bold")


def power(x, y, name, side="right"):
    dx = 22 if side == "right" else -22
    line(x, y, x + dx, y, PWR)
    line(x + dx, y - 11, x + dx, y + 11, PWR, 3)
    text(x + dx + (6 if side == "right" else -6), y + 5, name, 13, PWR, "start" if side == "right" else "end", "bold")


def ground(x, y, side="right"):
    dx = 18 if side == "right" else -18
    line(x, y, x + dx, y, GNDC)
    gx = x + dx
    for i, half in enumerate((12, 8, 4)):
        line(gx + i * (5 if side == "right" else -5), y - half, gx + i * (5 if side == "right" else -5), y + half, GNDC, 2)


def ground_down(x, y):
    line(x, y, x, y + 14, GNDC)
    for i, half in enumerate((12, 8, 4)):
        line(x - half, y + 14 + i * 5, x + half, y + 14 + i * 5, GNDC, 2)


def power_up(x, y, name):
    line(x, y, x, y - 18, PWR)
    line(x - 11, y - 18, x + 11, y - 18, PWR, 3)
    text(x, y - 24, name, 13, PWR, "middle", "bold")


# ------------------------------------------------------------------ parts
def chip(x, y, w, ref, value, left=(), right=(), sub="", pitch=32, stub=36):
    """Rectangle part with pins. Each pin = (pin_no, pin_name, net or None).
    Returns {pin_name: (x, y)} of the pin ends."""
    n = max(len(left), len(right), 1)
    h = n * pitch + 26
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{BODY}" stroke="{EDGE}" stroke-width="2.4"/>')
    text(x + w / 2, y - 26, ref, 15, REFTXT, "middle", "bold")
    text(x + w / 2, y - 9, value, 13, "#333", "middle", italic=True)
    if sub:
        text(x + w / 2, y + h + 18, sub, 11.5, "#555", "middle", italic=True)
    ends = {}
    for i, (no, name, netname) in enumerate(left):
        py = y + 28 + i * pitch
        line(x - stub, py, x, py, EDGE, 2)
        text(x + 8, py + 4.5, name, 12.5, PINTXT)
        text(x - stub + 4, py - 5, no, 10, "#7a2020")
        ends[name] = (x - stub, py)
        if netname:
            net(x - stub, py, netname, "left")
    for i, (no, name, netname) in enumerate(right):
        py = y + 28 + i * pitch
        line(x + w, py, x + w + stub, py, EDGE, 2)
        text(x + w - 8, py + 4.5, name, 12.5, PINTXT, "end")
        text(x + w + stub - 4, py - 5, no, 10, "#7a2020", "end")
        ends[name] = (x + w + stub, py)
        if netname:
            net(x + w + stub, py, netname, "right")
    return ends, h


def resistor_h(x, y, ref, val):  # from (x,y) to (x+70,y)
    line(x, y, x + 15, y)
    add(f'<rect x="{x + 15}" y="{y - 8}" width="40" height="16" fill="{BODY}" stroke="{EDGE}" stroke-width="2"/>')
    line(x + 55, y, x + 70, y)
    text(x + 35, y + 24, f"{ref}  {val}", 11.5, REFTXT, "middle", "bold")
    return x + 70


def resistor_v(x, y, ref, val):  # from (x,y) down to (x,y+70)
    line(x, y, x, y + 15)
    add(f'<rect x="{x - 8}" y="{y + 15}" width="16" height="40" fill="{BODY}" stroke="{EDGE}" stroke-width="2"/>')
    line(x, y + 55, x, y + 70)
    text(x + 14, y + 40, f"{ref} {val}", 11.5, REFTXT, weight="bold")
    return y + 70


def led_down(x, y, ref, color, label):  # LED from (x,y) down to (x,y+60)
    line(x, y, x, y + 16)
    add(f'<polygon points="{x - 12},{y + 16} {x + 12},{y + 16} {x},{y + 38}" fill="{color}" stroke="{EDGE}" stroke-width="2"/>')
    line(x - 12, y + 38, x + 12, y + 38, EDGE, 2.5)
    line(x, y + 38, x, y + 60)
    for k in (0, 9):
        line(x + 15, y + 20 + k, x + 26, y + 12 + k, color, 2)
    text(x + 18, y + 54, f"{ref} {label}", 11.5, REFTXT, weight="bold")
    return y + 60


def cap_polar(x, y, ref, val):  # vertical, from (x,y) down to (x,y+60)
    line(x, y, x, y + 24)
    line(x - 16, y + 24, x + 16, y + 24, EDGE, 3)
    add(f'<path d="M {x - 16} {y + 38} Q {x} {y + 30} {x + 16} {y + 38}" fill="none" stroke="{EDGE}" stroke-width="3"/>')
    line(x, y + 34, x, y + 60)
    text(x - 22, y + 22, "+", 14, PWR, "end", "bold")
    text(x - 24, y + 54, f"{ref} {val}", 11.5, REFTXT, "end", "bold")
    return y + 60


def frame(x, y, w, h, title, color="#8b1a1a"):
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{color}" stroke-width="1.4" stroke-dasharray="8 6" rx="6"/>')
    add(f'<rect x="{x + 10}" y="{y - 12}" width="{9 * len(title) + 16}" height="22" fill="{BG}"/>')
    text(x + 18, y + 4, title, 14, color, weight="bold")


def ultrasonic(x, y, ref, title, trig, echo, r_top, r_bot):
    ends, h = chip(x, y, 150, ref, "HC-SR04", right=[("1", "VCC", "+5V"), ("2", "TRIG", trig), ("3", "ECHO", None), ("4", "GND", "GND")],
                   sub=title, pitch=44)
    ex, ey = ends["ECHO"]
    rx = resistor_h(ex, ey, r_top, "1k")
    dot(rx + 20, ey)
    line(rx, ey, rx + 40, ey)
    net(rx + 40, ey, echo, "right")
    yb = resistor_v(rx + 20, ey, r_bot, "2k")
    ground_down(rx + 20, yb)


# ================================================================== sheet
add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Arial, Helvetica, sans-serif">')
add(f'<defs><pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="{GRID}"/></pattern></defs>')
add(f'<rect width="{W}" height="{H}" fill="{BG}"/><rect width="{W}" height="{H}" fill="url(#g)"/>')
add(f'<rect x="14" y="14" width="{W - 28}" height="{H - 28}" fill="none" stroke="#555" stroke-width="2"/>')
text(40, 58, "EDGE-AI SMART DUSTBIN  -  HARDWARE SCHEMATIC", 30, "#1a1a1a", weight="bold")
text(40, 86, "Organic / inorganic waste sorting with MobileNetV2 on ESP32-S3-CAM, fill-level, gas & climate sensing, ESP32 main controller", 15, "#444")

# ---------------- power supply (top centre)
frame(860, 120, 640, 220, "POWER SUPPLY 5 V / 3 A")
ends, _ = chip(900, 175, 130, "J1", "DC JACK 5V 3A", right=[("1", "+5V", None), ("2", "GND", None)], sub="adapter (servos need their own 5 V)")
px, py = ends["+5V"]
line(px, py, px + 160, py)
dot(px + 110, py)
power_up(px + 160, py, "+5V")
gx, gy = ends["GND"]
line(gx, gy, gx + 230, gy)
dot(gx + 110, gy)
ground_down(gx + 230, gy)
cy2 = cap_polar(px + 110, py, "C1", "1000uF/16V")
line(px + 110, cy2, px + 110, gy)
text(1150, 324, "C1 absorbs the servo current spikes", 11.5, "#555", italic=True)
text(1290, 205, "Common GND for ALL boards,", 12, "#7a2020", weight="bold")
text(1290, 221, "sensors and servos", 12, "#7a2020", weight="bold")

# ---------------- ESP32 main controller (centre)
frame(860, 390, 640, 600, "MAIN CONTROLLER")
chip(1020, 450, 320, "U1", "ESP32 DevKit V1 (ESP32-WROOM-32)",
     left=[("VIN", "VIN (5V)", "+5V"), ("GND", "GND", "GND"), ("3V3", "3V3 out", "+3V3"),
           ("5", "GPIO5", "TRIG_ORG"), ("18", "GPIO18", "ECHO_ORG"), ("19", "GPIO19", "TRIG_INO"),
           ("21", "GPIO21", "ECHO_INO"), ("22", "GPIO22", "TRIG_HAND"), ("23", "GPIO23", "ECHO_HAND"),
           ("34", "GPIO34 (in)", "IR_OUT"), ("35", "GPIO35 ADC1", "MQ_AO"), ("4", "GPIO4", "DHT_DATA")],
     right=[("17", "GPIO17 TX2", "CAM_RX"), ("16", "GPIO16 RX2", "CAM_TX"), ("27", "GPIO27", "SERVO_TRAY"),
            ("14", "GPIO14", "SERVO_LID"), ("25", "GPIO25", "BUZZER"), ("26", "GPIO26", "LED_G"),
            ("33", "GPIO33", "LED_R"), ("32", "GPIO32", "LED_B"), ("GND", "GND", "GND")],
     sub="Wi-Fi -> Django dashboard (telemetry, commands)", stub=40)

# ---------------- AI camera (right top)
frame(1530, 120, 910, 470, "AI CAMERA (EDGE AI)")
cam, _ = chip(1650, 280, 280, "U2", "ESP32-S3-CAM (OV2640, 8MB PSRAM)",
              left=[("14", "GPIO14 RX", "CAM_RX"), ("21", "GPIO21 TX", "CAM_TX"), ("5V", "5V", "+5V"), ("GND", "GND", "GND")],
              right=[("47", "GPIO47", None)],
              sub="MobileNetV2 int8 128x128: organic / paper / plastic / metal")
add('<rect x="1790" y="352" width="110" height="34" rx="5" fill="#dfe7f3" stroke="#556" stroke-width="1.5"/>')
add('<circle cx="1845" cy="369" r="12" fill="#223" stroke="#999" stroke-width="2"/><circle cx="1845" cy="369" r="5" fill="#68a"/>')
text(1845, 404, "OV2640 camera", 10.5, "#555", "middle", italic=True)
gx, gy = cam["GPIO47"]
rx = resistor_h(gx, gy, "R14", "220")
line(rx, gy, rx + 40, gy)
dot(rx + 20, gy)
yb = resistor_v(rx + 20, gy, "R15", "10k")
ground_down(rx + 20, yb)
ends, _ = chip(rx + 76, gy - 28, 120, "Q1", "IRLZ44N", left=[("G", "G", None)], right=[("D", "D", None), ("S", "S", "GND")], stub=36, pitch=28)
line(rx + 40, gy, ends["G"][0], ends["G"][1])
dx, dyy = ends["D"]
lx = dx + 40
line(dx, dyy, lx, dyy)
line(lx, dyy, lx, dyy - 40)                       # drain -> LED ring cathode
add(f'<rect x="{lx - 26}" y="{dyy - 80}" width="52" height="40" rx="18" fill="#fff9c8" stroke="{EDGE}" stroke-width="2"/>')
text(lx, dyy - 55, "LED", 11, "#7a2020", "middle", "bold")
line(lx, dyy - 80, lx, dyy - 96)
power_up(lx, dyy - 96, "+5V")
text(lx - 36, dyy - 104, "LS1 white LED ring", 11.5, REFTXT, "end", "bold")
text(lx - 36, dyy - 89, "5 V, uniform light", 11, "#555", "end", italic=True)

# ---------------- level sensors (left)
frame(40, 120, 760, 870, "FILL LEVEL & LID SENSORS")
ultrasonic(110, 180, "U3", "organic compartment (in the lid)", "TRIG_ORG", "ECHO_ORG", "R1", "R2")
ultrasonic(110, 445, "U4", "inorganic compartment (in the lid)", "TRIG_INO", "ECHO_INO", "R3", "R4")
ultrasonic(110, 710, "U5", "hand sensor (touchless lid, front)", "TRIG_HAND", "ECHO_HAND", "R5", "R6")
text(110, 972, "ECHO is 5 V: the 1k / 2k divider gives 3.3 V for the ESP32", 12, "#7a2020", italic=True)

# ---------------- item, gas and climate sensors (bottom left)
frame(40, 1030, 1220, 560, "ITEM, GAS & CLIMATE SENSORS")
chip(110, 1100, 150, "U6", "IR FC-51", right=[("1", "VCC", "+3V3"), ("2", "GND", "GND"), ("3", "OUT", "IR_OUT")], sub="item on the tray (LOW = present)")
ends, _ = chip(510, 1100, 150, "U7", "MQ-135", right=[("1", "VCC", "+5V"), ("2", "GND", "GND"), ("3", "AO", None)], sub="gas / bad smell (organic side)")
ax, ay = ends["AO"]
rx = resistor_h(ax, ay, "R7", "10k")
dot(rx + 20, ay)
line(rx, ay, rx + 40, ay)
net(rx + 40, ay, "MQ_AO")
yb = resistor_v(rx + 20, ay, "R8", "20k")
ground_down(rx + 20, yb)
ends, _ = chip(110, 1340, 150, "U8", "DHT22", right=[("1", "VCC", "+3V3"), ("2", "DATA", None), ("4", "GND", "GND")], sub="temperature & humidity")
dx2, dy2 = ends["DATA"]
line(dx2, dy2, dx2 + 190, dy2)
dot(dx2 + 120, dy2)
net(dx2 + 190, dy2, "DHT_DATA")
line(dx2 + 120, dy2, dx2 + 120, dy2 - 40)
resistor_v(dx2 + 120, dy2 - 110, "R9", "10k")
power_up(dx2 + 120, dy2 - 110, "+3V3")
text(510, 1305, "AO up to 5 V: 10k / 20k divider -> max 3.3 V on GPIO35", 12, "#7a2020", italic=True)

# ---------------- actuators and indicators (bottom right)
frame(1300, 1030, 1140, 560, "ACTUATORS & INDICATORS")
chip(1360, 1100, 160, "M1", "MG996R SERVO", right=[("1", "SIG", "SERVO_TRAY"), ("2", "+5V", "+5V"), ("3", "GND", "GND")], sub="sorting tray: 30 / 90 / 150 deg")
chip(1360, 1300, 160, "M2", "MG996R SERVO", right=[("1", "SIG", "SERVO_LID"), ("2", "+5V", "+5V"), ("3", "GND", "GND")], sub="lid: 0 / 100 deg")
chip(1760, 1100, 130, "BZ1", "BUZZER 5V", right=[("+", "+", "BUZZER"), ("-", "-", "GND")], sub="active buzzer")
for i, (netname, color, ref, rref, label) in enumerate([("LED_G", "#2fbf4f", "D1", "R10", "green: OK"),
                                                         ("LED_R", "#e53935", "D2", "R11", "red: full"),
                                                         ("LED_B", "#2f6fe0", "D3", "R12", "blue: maint.")]):
    x0 = 1840 + i * 190
    net(x0, 1300, netname, "left")
    line(x0, 1300, x0 + 30, 1300)
    line(x0 + 30, 1300, x0 + 30, 1310)
    yb = resistor_v(x0 + 30, 1310, rref, "220")
    yb = led_down(x0 + 30, yb, ref, color, "")
    text(x0 + 30, yb + 52, label, 11.5, "#333", "middle", italic=True)
    ground_down(x0 + 30, yb)

# ---------------- title block
tx, ty = W - 640, H - 150
add(f'<rect x="{tx}" y="{ty}" width="610" height="126" fill="#fffde6" stroke="#555" stroke-width="2"/>')
for yy in (ty + 42, ty + 84):
    line(tx, yy, tx + 610, yy, "#555", 1.2)
line(tx + 380, ty + 42, tx + 380, ty + 126, "#555", 1.2)
text(tx + 12, ty + 28, "TITLE: Edge-AI Smart Dustbin - Main Schematic", 16, "#000", weight="bold")
text(tx + 12, ty + 68, "PROJECT: final-project (ruta54-create)", 13)
text(tx + 392, ty + 68, f"DATE: {date.today():%d/%m/%Y}", 13)
text(tx + 12, ty + 110, "SHEET 1 / 1      REV 2.0      ESP32 + ESP32-S3-CAM", 13)
text(tx + 392, ty + 110, "Proteus-style, net-label wiring", 12, "#555", italic=True)

# ---------------- legend
lx, ly = 40, H - 140
add(f'<rect x="{lx}" y="{ly}" width="1080" height="112" fill="#ffffff" stroke="#bbb" rx="6"/>')
text(lx + 16, ly + 26, "HOW TO READ", 14, "#000", weight="bold")
net(lx + 30, ly + 56, "TRIG_ORG")
text(lx + 160, ly + 61, "net label: all pins with the same name are connected (as in Proteus ISIS)", 12.5)
power(lx + 18, ly + 92, "+5V")
text(lx + 110, ly + 97, "5 V rail", 12.5)
power(lx + 210, ly + 92, "+3V3")
text(lx + 310, ly + 97, "3.3 V from U1", 12.5)
ground(lx + 440, ly + 92)
text(lx + 490, ly + 97, "common ground", 12.5)
text(lx + 640, ly + 97, "UART 115200: U1 TX2 -> U2 RX, U2 TX -> U1 RX2", 12.5, WIRE, weight="bold")

add("</svg>")
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "smart_dustbin_schematic.svg").write_text("\n".join(svg), encoding="utf8")
print("written", OUT / "smart_dustbin_schematic.svg")
