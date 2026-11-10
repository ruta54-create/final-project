# Project Plan: Edge-AI Smart Dustbin

## 1. Problem

In schools, markets and offices, organic waste (food, peels, leaves) and inorganic waste (plastic,
metal, glass) are thrown into the same bin. This causes:

* recyclable and compostable material is lost, because mixed waste is dirty and too hard to separate later;
* bins overflow before anyone notices, giving bad smell, insects and disease;
* collection is done on a fixed schedule: trucks or cleaners come when bins are half-empty, or too late.

## 2. Objectives

1. **Automatically separate** each item into *organic* or *inorganic* using a camera and an AI model
   that runs **on the device** (edge AI, so it works even when the internet is slow).
2. **Measure the fill level** of each compartment and **detect bad smell** (decomposition).
3. **Predict** when each compartment will be full and **recommend** what to do.
4. Provide a **web dashboard** to monitor, analyse and **remotely control** one or many bins.

## 3. What was improved from the first idea

| First idea | Problem | Redesign |
|---|---|---|
| Classes plastic / paper / metal / unknown | Needs 4+ compartments and a hard model; did not match the goal "organic vs inorganic" | **2 classes: organic / inorganic**, 2 compartments, one tilting tray |
| One ESP32-CAM doing everything | The ESP32-CAM has only ~4 free pins and little power: not enough for 3 ultrasonic sensors, 2 servos, gas, temperature, LEDs | **Two boards**: ESP32-CAM = camera + AI only; ESP32 DevKit = sensors + motors. They talk over UART |
| One fill sensor | Two compartments fill at different speeds | **One ultrasonic sensor per compartment** |
| No smell monitoring | Organic waste rots before the bin is full | **MQ-135 gas + DHT22** → "empty organic within 24 h" |
| Uncertain items went to "unknown" | No physical "unknown" compartment | **Safety rule:** confidence < 70 % → inorganic (never contaminate compost), flagged for review |
| Lid always open / manual | Hygiene | **Touchless lid** (hand sensor) + lid closes during classification (steady light) |
| Dashboard only displayed data | No way to act | **Control panel** (lid, tray, capture, calibrate, mode, reboot), **collections log**, **alerts**, **recommendations** |
| No login, one global key | Anyone could read or control the bin | **Login with roles** (admin / viewer), **one secret API key per bin** |
| One bin only | Real deployments have many bins | **Multi-bin**: add bins in Settings, switch at the top of every page |
| PostgreSQL required | Hard to set up on a student PC | **SQLite for development**, PostgreSQL for production (one setting) |
| Fill prediction from all data | Wrong after the bin is emptied | Prediction **restarts after each emptying**, with a 7-day history fallback |

## 4. Scope

**In scope:** one physical prototype bin, web system for many bins, organic/inorganic sorting, fill
level, gas/temperature/humidity, prediction, alerts, recommendations, remote control, CSV reports.

**Out of scope (future work):** SMS/WhatsApp alerts, GPS route planning for trucks, weight sensor
(HX711 load cell), solar power, finer classes (plastic/metal/glass) with a 3rd compartment.

## 5. Work plan (12 weeks)

| Week | Phase | Tasks | Deliverable |
|---|---|---|---|
| 1 | Planning | Requirements, buy components (see HARDWARE.md), set up PC (Python, Node, Arduino IDE) | Component list, this plan |
| 2 | Software base | Run this project with the simulator, understand the API and dashboard | Dashboard working with simulated bin |
| 3–4 | Dataset | Build the inspection box (tray + LED + white background). Take ~300 photos per class **with the ESP32-CAM inside the box**. Add public images (see AI_MODEL.md) | Labelled dataset in Edge Impulse |
| 5 | AI model | Train in Edge Impulse, test accuracy (target ≥ 90 %), export Arduino library | Model + confusion matrix |
| 6 | Camera firmware | Flash `esp32_cam.ino`, test "CAPTURE" with serial monitor, photo appears on dashboard | Camera classifying + uploading |
| 7 | Sensors | Wire ultrasonic ×3, IR, MQ-135, DHT22 on a breadboard; flash `esp32_main.ino`; check telemetry on dashboard | Live levels/gas on dashboard |
| 8 | Mechanics | Build the 2-compartment bin, tilting tray, lid; mount servos and sensors | Physical prototype |
| 9 | Integration | Connect both boards (UART), full sorting cycle, calibrate depths from the Control Panel | End-to-end sorting |
| 10 | Testing | Run TESTING.md procedures: 100 items accuracy test, fill accuracy, response times, 24 h run | Test results tables |
| 11 | Improvement | Retrain with misclassified photos (Detections → Uncertain only), tune thresholds | Final model version |
| 12 | Report | Screenshots, results, demo video, presentation | Final report + defense |

## 6. Risks and mitigation

| Risk | Mitigation |
|---|---|
| Low AI accuracy in real light | Closed inspection box + LED, photos taken with the same camera, retrain with mistakes |
| Ultrasonic wrong on soft/angled waste | Median of 5 readings, sensor centred above compartment, calibrate empty depth |
| Servos reset the ESP32 (current spikes) | Separate 5 V 3 A supply for servos, 1000 µF capacitor, common ground |
| Wi-Fi drops | Boards reconnect automatically; sorting keeps working offline (AI is on the device) |
| ESP32-CAM out of memory | QVGA frames, PSRAM enabled, small model (96×96, int8) |
| Moisture from organic waste | Waterproof JSN-SR04T sensor for the organic side (optional), liner bag |

## 7. Success criteria

* ≥ 90 % correct sorting on 100 test items, < 3 s from item placed to item sorted.
* Fill level error ≤ 5 % compared to a ruler.
* Dashboard updates within 3 s; remote command executed within 3 s.
* All 33 automated tests and 32 system checks pass (see TESTING.md).
