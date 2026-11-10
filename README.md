# Edge-AI Smart Dustbin
### Real-time organic / inorganic waste sorting and predictive fill-level monitoring with Edge AI, ESP32 and Django

A smart dustbin that **recognises each item with a camera and AI running on the device**, drops it into the
**organic** or **inorganic** compartment, measures **how full each compartment is**, detects **bad smell**,
**predicts when it will be full**, and lets you **monitor and control everything from a web dashboard**.

```
 ┌───────────────────────── SMART BIN ─────────────────────────┐
 │  ESP32-CAM  (camera + Edge Impulse AI model)                │
 │      │ UART "CAPTURE" / "SORT organic 0.93"                 │        Wi-Fi / HTTP
 │  ESP32 main controller ── ultrasonic x3, IR, MQ-135, DHT22 │ ───────────────────────┐
 │      └── servos (lid + sorting tray), LEDs, buzzer          │                        │
 └─────────────────────────────────────────────────────────────┘                        ▼
                                                     ┌─────────────────────────────────────────┐
   Any browser (PC, phone)  ◀────── http://localhost:8000 ──────│  Django + REST API + SQLite/PostgreSQL  │
   React dashboard: monitor, analytics, control      │  prediction · alerts · recommendations  │
                                                     └─────────────────────────────────────────┘
```

## Quick start (Windows)

1. Install **Python 3.11+** and **Node.js 18+** (already on this PC).
2. Double-click **`RUN_WEBSITE.bat`** (or run `RUN_DEMO.bat` to also start a simulated bin).
3. The browser opens **http://localhost:8000**. Log in with:

| Account | Password | Can do |
|---|---|---|
| `admin` | `admin12345` | everything: settings, remote control, users |
| `cleaner` | `cleaner12345` | view everything, record "compartment emptied" |

> Change these passwords before showing the system to anyone else (Settings → My account).

Without hardware, run the **simulator**. It behaves exactly like the two ESP32 boards:
```
backend\venv\Scripts\python device\simulator.py
```

## Features

| Area | What it does |
|---|---|
| **Edge AI sorting** | ESP32-CAM runs an Edge Impulse CNN (organic vs inorganic) in ~0.5 s. Unsure items (< 70 % confidence) go to *inorganic* so compost is never contaminated. |
| **Fill levels** | Ultrasonic sensor above each compartment → % full, every 30 s. |
| **Prediction (ML)** | Linear-regression filling rate → "organic full in 6 h (tomorrow 04:30)". |
| **Smell & climate** | MQ-135 gas + DHT22 temperature/humidity → "organic waste decomposing, empty within 24 h". |
| **Recommendations** | Rule engine turns data into actions (empty now, schedule collection, clean lens/retrain model, …). |
| **Alerts** | Full / almost full / gas high / device offline / AI often uncertain, auto-resolved. |
| **Remote control** | Open/close lid, tilt tray, capture, calibrate, test buzzer, reboot, change mode (Auto / Manual / Maintenance). |
| **Touchless lid** | Hand sensor opens the lid, closes after 5 s. |
| **Dashboard** | Live camera photo, compartments, trends, detections gallery, analytics, CSV export. |
| **Users & security** | Login, admin vs viewer roles, one secret API key per bin, CSRF protection. |
| **Email alerts** | Each user gets an email (EN/FR/RW) when a compartment is almost full or full, smells bad or goes offline. Gmail/SMTP ready; see docs/EMAIL.md. |
| **3 languages** | English, Français, Kinyarwanda: switch with EN / FR / RW in the sidebar or on the login page; the choice is remembered. |
| **Many bins** | Add bins in Settings, switch between them at the top of every page. |

## Project structure

```
My final project/
├── RUN_WEBSITE.bat                 one-click start (build, migrate, run)
├── backend/                  Django 5 + Django REST Framework
│   ├── config/settings.py    DB_ENGINE=sqlite (dev) | postgresql (production)
│   └── bins/
│       ├── models.py         Bin, SensorReading, Detection, Command, Alert, Collection
│       ├── views_device.py   API for the ESP32 boards (X-API-KEY)
│       ├── views_dashboard.py API for the React dashboard (login)
│       ├── services/         prediction.py · alerts.py · recommendations.py
│       ├── management/commands/  seed_demo · create_bin
│       └── tests/            33 automated tests
├── frontend/                 React 18 + Vite + Recharts
│   └── src/pages/            Login, Dashboard, Detections, Analytics, Alerts, Control, Settings
├── device/
│   ├── esp32_main/           main controller firmware (Arduino)
│   ├── esp32_cam/            AI camera firmware (Arduino + Edge Impulse)
│   └── simulator.py          fake bin for testing without hardware
├── tools/system_check.py     end-to-end check of the running system (32 checks)
└── docs/                     full documentation (start with PROJECT_PLAN.md)
```

## Documentation

| Document | Contents |
|---|---|
| [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) | Problem, objectives, what was improved from the first idea, work plan & timeline |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the parts talk, data flow, database tables |
| [docs/HARDWARE.md](docs/HARDWARE.md) | Components list, wiring tables, power, mechanical build, calibration |
| [docs/AI_MODEL.md](docs/AI_MODEL.md) | Dataset, training in Edge Impulse, deployment, prediction & recommendation logic |
| [docs/API.md](docs/API.md) | Every API endpoint with examples |
| [docs/EMAIL.md](docs/EMAIL.md) | Email alerts: turning them on, Gmail setup, how sending works |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | How to use each dashboard page |
| [docs/TESTING.md](docs/TESTING.md) | How the system was tested and the results |

## Common commands

```powershell
cd backend
venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000     # start the server
python manage.py test bins                  # run the 33 automated tests
python manage.py seed_demo                  # reset demo data
python manage.py create_bin "Library bin" --location "Library"   # register a real bin
python manage.py createsuperuser            # create your own admin account

cd frontend
npm run dev        # live-reload development on http://localhost:5173
npm run build      # rebuild the dashboard that Django serves on :8000
```

## Moving to production (PostgreSQL)

In `backend/.env` set `DB_ENGINE=postgresql`, fill `DB_NAME / DB_USER / DB_PASSWORD`, set `DJANGO_DEBUG=0`
and a long random `DJANGO_SECRET_KEY`, then `python manage.py migrate`. See *Deployment* in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
