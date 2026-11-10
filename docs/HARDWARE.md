# Hardware Guide

## 1. Recommended design

```
            ┌──────────── LID (servo 2, opened by hand sensor) ────────────┐
            │   [HC-SR04 hand sensor, front]                               │
            │  ┌────────── INSPECTION BOX (closed, white inside) ───────┐  │
            │  │        ESP32-CAM + LED ring, looking down              │  │
            │  │   ┌───────────── TILTING TRAY (servo 1) ─────────────┐ │  │
            │  │   │        IR sensor detects the item                │ │  │
            │  │   └──────────────────────────────────────────────────┘ │  │
            │  └────────────────────────────────────────────────────────┘  │
            │  [HC-SR04 organic]                      [HC-SR04 inorganic]  │
            │  ┌────────────────────┐   ┌────────────────────┐             │
            │  │  ORGANIC           │   │  INORGANIC         │  MQ-135 +   │
            │  │  (tray tilts LEFT) │   │  (tray tilts RIGHT)│  DHT22 in   │
            │  │                    │   │                    │  organic    │
            │  └────────────────────┘   └────────────────────┘  side       │
            └──────────────────────────────────────────────────────────────┘
```

**Sorting cycle:** hand near → lid opens → item placed on tray → IR sees it → lid closes →
main ESP32 sends `CAPTURE` to the camera → camera AI answers `SORT organic 0.93` (~0.5–1 s) →
tray tilts left or right → item falls → tray returns to the centre → photo and result appear on the dashboard.

**Why two boards?** The ESP32-CAM has only ~4 free GPIO pins and its CPU is busy with the camera and the AI.
The ESP32 DevKit has 25+ pins for all sensors and servos. They talk over a 2-wire UART link.

## 2. Components list (Bill of Materials)

| # | Component | Qty | Purpose | Approx. price (USD) |
|---|---|---|---|---|
| 1 | ESP32-CAM AI-Thinker (OV2640, 4 MB PSRAM) | 1 | camera + AI | 8 |
| 2 | ESP32-CAM-MB USB programmer board | 1 | flashing the camera | 3 |
| 3 | ESP32 DevKit V1 (30 pins) | 1 | main controller | 6 |
| 4 | HC-SR04 ultrasonic sensor | 3 | organic level, inorganic level, hand (lid) | 3 × 1.5 |
| 5 | (optional) JSN-SR04T waterproof ultrasonic | 1 | organic side (humidity) | 6 |
| 6 | IR obstacle sensor FC-51 | 1 | item on tray | 1 |
| 7 | MQ-135 gas sensor module | 1 | smell / decomposition | 3 |
| 8 | DHT22 (AM2302) | 1 | temperature + humidity | 4 |
| 9 | MG996R servo (metal gear) | 2 | tray + lid | 2 × 5 |
| 10 | White LED ring 5 V or 2 × white LEDs + IRLZ44N MOSFET | 1 | uniform light for the camera | 2 |
| 11 | Active buzzer 5 V | 1 | sounds | 0.5 |
| 12 | LEDs green, red, blue + 220 Ω | 3 | status | 0.5 |
| 13 | Resistors 1 kΩ ×3, 2 kΩ ×3, 10 kΩ ×2, 20 kΩ ×1 | – | voltage dividers, DHT pull-up | 1 |
| 14 | 5 V 3 A power supply (or 12 V + LM2596 buck to 5 V) | 1 | everything | 6 |
| 15 | 1000 µF 16 V electrolytic capacitor | 1 | absorbs servo current spikes | 0.5 |
| 16 | Breadboard/perfboard, jumper wires, screw terminal | – | wiring | 4 |
| 17 | Bin body (2 compartments), plywood/acrylic for the box and tray, hinges | – | mechanics | 10–20 |

**Total ≈ 70–90 USD.**

## 3. Wiring: ESP32 DevKit (main controller)

| Device | Device pin | ESP32 pin | Note |
|---|---|---|---|
| HC-SR04 organic | VCC / GND | 5V / GND | |
| | TRIG | GPIO 5 | |
| | ECHO | GPIO 18 | **through divider** 1 kΩ (ECHO→pin) + 2 kΩ (pin→GND) |
| HC-SR04 inorganic | TRIG / ECHO | GPIO 19 / GPIO 21 | ECHO through divider |
| HC-SR04 hand (front) | TRIG / ECHO | GPIO 22 / GPIO 23 | ECHO through divider |
| IR sensor FC-51 | VCC / GND / OUT | 3V3 / GND / GPIO 34 | OUT = LOW when item present |
| MQ-135 | VCC / GND | 5V / GND | heater needs 5 V, warm up 24 h the first time |
| | AO | GPIO 35 | **through divider** 10 kΩ (AO→pin) + 20 kΩ (pin→GND) |
| DHT22 | VCC / DATA / GND | 3V3 / GPIO 4 / GND | 10 kΩ from DATA to 3V3 |
| Tray servo MG996R | signal | GPIO 27 | red/brown wires to the **5 V supply**, not to the ESP32 |
| Lid servo MG996R | signal | GPIO 14 | same |
| Buzzer | + / − | GPIO 25 / GND | |
| LED green / red / blue | anode via 220 Ω | GPIO 26 / 33 / 32 | cathodes to GND |
| ESP32-CAM | GPIO 13 (its RX) | GPIO 17 (TX2) | UART link, 115200 baud |
| | GPIO 14 (its TX) | GPIO 16 (RX2) | |
| | GND | GND | **common ground is required** |

## 4. Wiring: ESP32-CAM

| ESP32-CAM pin | Connect to |
|---|---|
| 5V, GND | 5 V supply (the camera needs ≥ 500 mA peaks) |
| GPIO 13 | main ESP32 GPIO 17 (TX2) |
| GPIO 14 | main ESP32 GPIO 16 (RX2) |
| GPIO 4 | on-board flash LED; for a LED ring use a MOSFET (gate = GPIO 4 via 220 Ω) |

Flashing: plug the ESP32-CAM on the **ESP32-CAM-MB** board and connect USB. If upload fails, hold
**IO0** while pressing **RST**.

## 5. Power

```
 5 V 3 A adapter ──┬── 1000 µF ──┬── servo tray (red)
                   │             └── servo lid  (red)
                   ├── ESP32 DevKit VIN (5V pin)
                   ├── ESP32-CAM 5V
                   ├── MQ-135 VCC, HC-SR04 VCC ×3, buzzer
 GND ──────────────┴── all GNDs together (servos, both ESP32, sensors)
```

* Never power servos from the ESP32 3V3/5V pin: their current spikes reset the board.
* Keep the USB cable connected only while programming (or use a USB power-only cable).

## 6. Mechanical tips

* **Inspection box:** closed, painted **matt white**, LED ring above, camera 20–25 cm above the tray.
  Constant light and background raise accuracy more than anything else.
* **Tray:** flat plate on a horizontal axle in the middle; servo horn tilts it ±60° (angles in
  `esp32_main.ino`: `TRAY_ORGANIC = 30`, `TRAY_INORGANIC = 150`, centre `90`).
* **Ultrasonic sensors:** mounted under the box ceiling of each compartment, pointing straight down, at least
  5 cm above the highest waste level (HC-SR04 cannot measure < 2 cm).
* **MQ-135:** inside the organic compartment, near the top, protected from liquid.
* **Lid:** light material; MG996R with a short arm; `LID_OPEN = 100`, `LID_CLOSED = 0`.

## 7. Arduino IDE setup

1. **Arduino IDE 2** → *File → Preferences → Additional boards URL*:
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json` → *Boards Manager* → install **esp32**.
   (If the Edge Impulse library fails to compile with the newest core, install core **2.0.17**.)
2. *Library Manager*: **ArduinoJson** (v7), **ESP32Servo**, **DHT sensor library** (Adafruit) + **Adafruit Unified Sensor**.
3. Edge Impulse library: *Sketch → Include Library → Add .ZIP Library* (see AI_MODEL.md).

| Sketch | Board | Settings |
|---|---|---|
| `device/esp32_main/esp32_main.ino` | ESP32 Dev Module | default |
| `device/esp32_cam/esp32_cam.ino` | AI Thinker ESP32-CAM | PSRAM: Enabled, Partition: Huge APP |

Before uploading, copy `secrets.example.h` to `secrets.h` in **each** sketch folder and enter:
Wi-Fi name/password, `SERVER_URL` = `http://<PC IP>:8000` (find the IP with `ipconfig`), and the bin's
**API key** (dashboard → Settings → Device API key). Start Django with `RUN_WEBSITE.bat` (it listens on all
network interfaces) and allow Python through the Windows Firewall when asked.

## 8. First power-on checklist

1. Open the *Serial Monitor* (115200) of the main ESP32: you should see `Wi-Fi OK`, `Config: bin ...`,
   `Telemetry: organic xx%`.
2. Dashboard header shows **Controller online** and **Camera online**.
3. Control Panel → **Test buzzer & LEDs**: it beeps 3 times.
4. Control Panel → **Open lid / Close lid / Tilt tray** buttons move the servos.
5. **Empty both compartments**, then Control Panel → **Calibrate**: depths are saved in Settings.
6. Put an item on the tray → it is classified, sorted, and its photo appears on the dashboard.

## 9. MQ-135 calibration (optional but recommended)

1. Let the sensor heat for 24 h the first time (and ~2 min at every start).
2. In clean outdoor air read the sensor resistance: temporarily print `rs` in `readGasPpm()`.
3. `R0 = rs / 3.6` (clean-air ratio from the datasheet) → put it in `MQ_R0_KOHM`.
4. Readings are *CO₂-equivalent ppm*: good for "smell is rising", not a laboratory measurement.
   Tune the alarm threshold in Settings (default 400 ppm).
