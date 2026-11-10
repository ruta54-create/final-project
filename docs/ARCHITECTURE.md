# System Architecture

## 1. Components

```
┌────────────── Smart bin (edge) ──────────────┐        ┌──────────── Server (PC / cloud) ────────────┐
│ ESP32-CAM                                    │  HTTP  │ Django 5 + Django REST Framework            │
│  • OV2640 camera, LED                        │───────▶│  • Device API  /api/device/*  (X-API-KEY)   │
│  • Edge Impulse CNN  → organic / inorganic   │ photo+ │  • Dashboard API /api/* (login session)     │
│        ▲ UART  "CAPTURE" / "SORT organic"    │ result │  • services: prediction, alerts, recommend. │
│ ESP32 DevKit (main controller)               │        │  • SQLite (dev) / PostgreSQL (production)   │
│  • 3× ultrasonic, IR, MQ-135, DHT22          │───────▶│  • serves the built React app + photos      │
│  • 2× servo (tray, lid), LEDs, buzzer        │telemetry└────────────────────▲────────────────────────┘
│  • polls commands every 2 s                  │◀─────── commands               │ JSON every 2–10 s
└──────────────────────────────────────────────┘                          ┌─────┴──────────────────────┐
                                                                          │ React 18 dashboard          │
                                                                          │ any browser, PC or phone    │
                                                                          └────────────────────────────┘
```

**Why polling instead of WebSockets?** ESP32 HTTP polling every 2 s is simple, works through any router,
and is fast enough for a bin (commands are executed within ~2 s). The dashboard also polls (3 s).

## 2. Sequence: one item

```
Person      Main ESP32           ESP32-CAM                  Django                    Dashboard
  │ hand ──▶ lid opens                │                        │                          │
  │ item ──▶ IR detects, lid closes   │                        │                          │
  │          ── "CAPTURE\n" ─────────▶│ photo + AI (0.5 s)     │                          │
  │          ◀─ "SORT organic 0.93\n" │                        │                          │
  │          tray tilts left          │ ── POST /device/detection/ (JPEG + result) ─▶     │
  │          tray returns             │                        │ save, alerts             │
  │                                   │                        │ ◀── GET overview (3 s) ──│ shows photo
```

## 3. Sequence: remote command

```
Admin clicks "Open lid" ─▶ POST /api/bins/1/commands/  (status = pending)
Main ESP32 (every 2 s)  ─▶ GET  /api/device/commands/  (status → sent)
Main ESP32 opens lid    ─▶ POST /api/device/commands/7/ack/ {"status":"done"}
Dashboard Command Log shows "done". Commands not picked up within 2 minutes → "expired".
```

## 4. Database tables

| Table | Main fields | Notes |
|---|---|---|
| **Bin** | name, location, api_key, mode (auto/manual/maintenance), organic_depth_cm, inorganic_depth_cm, warning_level, full_level, gas_threshold_ppm, min_confidence, firmware, IPs, last_seen, cam_last_seen | one row per physical bin |
| **SensorReading** | bin, organic_level, inorganic_level, distances, gas_ppm, temperature, humidity, created_at | every 30 s |
| **Detection** | bin, label, category, confidence, sorted_to, uncertain, image, inference_ms, created_at | one per item |
| **Command** | bin, action, payload, status (pending/sent/done/failed/expired), result, message, created_by | remote control |
| **Alert** | bin, kind, severity, message, is_active, resolved_at | max one active per (bin, kind) |
| **Collection** | bin, compartment, level_before, note, created_by, created_at | "compartment emptied" log |
| **User** (Django) | username, password, is_staff | staff = admin, others = viewer |

```
User 1───* Command *───1 Bin 1───* SensorReading
User 1───* Collection *─┘   ├───* Detection
                            └───* Alert
```

## 5. Security

* Dashboard: Django session login, CSRF token on every change, HTTP-only session cookie.
* Roles: **admin** (`is_staff`): settings, commands, API keys. **Viewer**: read everything and record collections.
* Devices: a random 40-character **API key per bin** in the `X-API-KEY` header. It can be regenerated
  from Settings, and viewers never see it.
* Uploaded photos are validated as real images (Pillow); upload size is limited to 5 MB.

## 6. Code map

| File | Responsibility |
|---|---|
| `backend/bins/models.py` | tables, distance → level conversion, online status |
| `backend/bins/views_device.py` | config, telemetry, detection, commands, ack |
| `backend/bins/views_dashboard.py` | bins CRUD, overview, readings, analytics, commands, collections, export, alerts |
| `backend/bins/views_auth.py` | login, logout, me, change password, CSRF |
| `backend/bins/services/prediction.py` | regression & time-to-full |
| `backend/bins/services/alerts.py` | create / auto-resolve alerts |
| `backend/bins/services/recommendations.py` | rule engine |
| `backend/config/urls.py` | `/api`, `/admin`, `/media`, and the React app for every other URL |
| `frontend/src/api.js` | fetch wrapper (CSRF, session), polling hook, formatters |
| `frontend/src/context.jsx` | logged-in user, selected bin |
| `frontend/src/pages/*` | the 7 pages |

## 7. Deployment (production)

1. Server (e.g. Ubuntu VPS or campus PC). Install PostgreSQL, create database `smart_dustbin`.
2. `backend/.env`: `DB_ENGINE=postgresql`, DB credentials, `DJANGO_DEBUG=0`, long random `DJANGO_SECRET_KEY`,
   `DJANGO_ALLOWED_HOSTS=your-domain.com`.
3. `pip install -r requirements.txt gunicorn`, `python manage.py migrate`, `python manage.py createsuperuser`,
   `python manage.py collectstatic`.
4. `cd frontend && npm ci && npm run build`.
5. Run `gunicorn config.wsgi -b 127.0.0.1:8000` behind **Nginx**. Nginx serves `/static/` and `/media/`
   and proxies everything else. Enable HTTPS (Let's Encrypt).
6. In both `secrets.h` set `SERVER_URL` to `https://your-domain.com` (for HTTPS on ESP32 use
   `WiFiClientSecure` with the certificate, or keep the bins on the local network over HTTP).

## 8. Languages (i18n)

* The **server is language-neutral**: it sends codes and numbers (`status.code = "almost_full"`,
  recommendation `{"code": "schedule", "params": {"compartment": "organic", "full_at": ...}}`,
  alert `kind` + `params`, command `message_code`, error `code`). English text is still included as a fallback.
* The **dashboard translates** them: `frontend/src/i18n/index.jsx` (provider, `t()`, date/time formatting,
  Kinyarwanda month and day names) and one dictionary per language in `frontend/src/i18n/locales/`.
* **Add a language:** copy `locales/en.js` to e.g. `sw.js`, translate the values, add it to `LANGUAGES`
  in `i18n/index.jsx`, then run `node tools/check_i18n.mjs`. It fails if any key or `{placeholder}` is missing.

