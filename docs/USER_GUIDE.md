# User Guide

Open **http://localhost:8000** on the server PC, or **http://<server-IP>:8000** from a phone or another
PC on the same Wi-Fi. Log in with your account.

| Role | Who | Can |
|---|---|---|
| **Administrator** | project owner, supervisor | everything: settings, remote control, API keys, users (Django admin) |
| **Viewer** | cleaners, staff | see every page, record "compartment emptied", resolve alerts |

Add accounts at **http://localhost:8000/admin** → *Users* → *Add*. Tick **Staff status** for an administrator.

## Language (English, Français, Kinyarwanda)
Click **EN**, **FR** or **RW** at the bottom of the sidebar (or at the top-right of the login page).
Every page, chart, date, alert and recommendation changes at once, and the browser remembers your choice.
Each person can use a different language on their own phone or PC.

## Header (every page)
* **Controller online / offline:** the main ESP32 has reported in the last 90 s.
* **Camera online / offline:** the ESP32-CAM has reported in the last 5 min.
* If you have several bins, a selector appears here.

## Dashboard
| Part | Meaning |
|---|---|
| Organic / Inorganic cards | % full, status (Normal / Almost full / Full) and predicted time until full |
| Items sorted today | total, organic, inorganic, uncertain |
| Air quality | gas ppm (smell), temperature, humidity |
| Live Camera & AI Prediction | last photo, label, confidence, where the tray sent it, AI time |
| Compartments | the two compartments drawn with their level, warning (orange) and full (red) lines |
| Recommendations | what to do now, with a one-click button (e.g. *Mark organic as emptied*) |
| Fill Level Trend | both compartments over the last 24 h |
| Recent Activity | last 6 items; ⚠ *uncertain* = AI was unsure, item went to inorganic |
| System Info | mode, lid, AI model version, IPs, firmware, Wi-Fi signal, uptime |

The page refreshes every 3 seconds.

## Detections
Every item with its photo. Filter **Organic / Inorganic / Uncertain only**. Use *Uncertain only* to collect
photos for retraining the AI model.

## Analytics
Choose 24 h / 7 days / 30 days. Items per day, busiest hours (plan collection times), organic share,
AI confidence, most common items, collection frequency, and fill & gas history.
**CSV buttons** download data for Excel and your report.

## Alerts
* **Recommendations:** the same as on the dashboard.
* **Alerts:** full, almost full, gas high, device offline, AI often uncertain. They resolve automatically when
  the problem is gone (e.g. after emptying). You can also click **Resolve**.

## Control Panel
* **Operating mode**
  * *Automatic*: the bin detects, classifies and sorts by itself (normal use).
  * *Manual*: items are only sorted when you press **Capture & classify** or a **Tilt tray** button.
  * *Maintenance*: the lid stays open and sorting is off, for cleaning.
* **Remote commands:** Open/Close lid, Tilt tray → Organic/Inorganic, Capture & classify, Test buzzer & LEDs,
  **Calibrate** (only when both compartments are EMPTY), Reboot controller.
  The bin runs the command within ~2 s. The **Command Log** shows *pending → sent → done*.
  If the bin is offline the command expires after 2 minutes.
* **Record a Collection:** after emptying a compartment, press *Organic emptied* or *Inorganic emptied*.
  This logs who emptied it and the level before, resolves alerts, and restarts the prediction.

## Settings (administrators)
* **Bin settings:** name, location, empty depths (set automatically by *Calibrate*), almost-full and full levels,
  gas threshold, minimum AI confidence.
* **Device API key:** copy into `secrets.h` of both ESP32 boards. *New key* invalidates the old one.
* **Add a bin:** register another physical bin; it gets its own API key.
* **Email notifications** (everyone): your address, language and which alerts to receive, plus a test button. See docs/EMAIL.md.
* **My account:** change your password (everyone).

## Daily routine for cleaners
1. Open the dashboard on the phone.
2. Empty any compartment marked **Full** or recommended.
3. Press **Organic emptied / Inorganic emptied** in the Control Panel (or the button in the recommendation).
4. If there is a **Bad smell** alert, empty and wash the organic compartment even if it is not full.
