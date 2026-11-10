# API Reference

Base URL: `http://<server>:8000/api`. All bodies are JSON unless noted.

## 1. Device API (ESP32 boards)

Header on every request: `X-API-KEY: <bin api key>`. A wrong key returns **401**.

### `GET /device/config/` (add `?role=cam` from the camera)
Heartbeat + settings.
```json
{"bin_id":1,"name":"Smart Bin #1","mode":"auto","min_confidence":0.7,
 "organic_depth_cm":40.0,"inorganic_depth_cm":40.0,"telemetry_interval_s":30,"command_poll_s":2,
 "server_time":"2026-11-05T15:10:00Z"}
```

### `POST /device/telemetry/` → 201
```json
{"organic_distance_cm":14.2,"inorganic_distance_cm":30.1,"gas_ppm":310,"temperature":26.4,
 "humidity":63,"lid_open":false,"firmware":"1.0.0","wifi_rssi":-61,"ip":"192.168.1.50","booted":false}
```
All fields optional. Response = computed levels + the config above:
`{"organic_level":64.5,"inorganic_level":24.8,"mode":"auto",...}`

### `POST /device/detection/` → 201 (multipart/form-data or JSON)
| field | type | |
|---|---|---|
| label | text | raw model class, e.g. `fruit_peel` |
| category | `organic` / `inorganic` | AI decision |
| confidence | 0–1 | |
| sorted_to | `organic` / `inorganic` | optional; default = category, or inorganic if confidence < min_confidence |
| image | JPEG file | optional |
| inference_ms, firmware, model_version, ip | | optional |

Response: `{"id":812,"sorted_to":"organic","uncertain":false,"mode":"auto"}`

### `GET /device/commands/`
Returns pending commands **once** (they become `sent`):
```json
{"mode":"auto","commands":[{"id":7,"action":"open_lid","payload":{}}]}
```
Actions: `open_lid, close_lid, sort_organic, sort_inorganic, capture, calibrate, set_mode, buzzer, reboot`.

### `POST /device/commands/<id>/ack/`
```json
{"status":"done","message":"Measured 40.2 / 39.8 cm","result":{"organic_depth_cm":40.2,"inorganic_depth_cm":39.8}}
```
A `calibrate` ack with `result` updates the bin depths.

## 2. Dashboard API (logged-in users)

Session cookie + header `X-CSRFToken` (from cookie `csrftoken`) on POST/PATCH/DELETE.
Not logged in → **403**. Viewer trying to change something → **403**.

| Method | URL | Who | Description |
|---|---|---|---|
| GET | `/auth/csrf/` | all | sets the CSRF cookie |
| POST | `/auth/login/` | all | `{"username","password"}` |
| POST | `/auth/logout/` | user | |
| GET | `/auth/me/` | all | `{"authenticated":true,"id","username","is_staff","name"}` or `{"authenticated":false}` |
| POST | `/auth/change-password/` | user | `{"old_password","new_password"}` |
| GET / POST | `/bins/` | user / admin | list / create bins |
| GET / PATCH / DELETE | `/bins/<id>/` | user / admin | bin settings (api_key only shown to admins) |
| GET | `/bins/<id>/overview/` | user | everything the dashboard needs: levels, predictions, today's counts, last photo, trend (24 h), alerts, recommendations |
| GET | `/bins/<id>/readings/?hours=24` | user | sensor history (≤ 300 averaged points) |
| GET | `/bins/<id>/analytics/?days=7` | user | totals, per day, per hour, confidence, top labels, collections |
| GET / POST | `/bins/<id>/commands/` | user / admin | command log / send `{"action","payload"}` |
| GET / POST | `/bins/<id>/collections/` | user | collection log / record `{"compartment","note"}` (resolves full + gas alerts) |
| POST | `/bins/<id>/regenerate-key/` | admin | new device API key |
| GET | `/bins/<id>/export/?type=detections\|readings\|collections&days=30` | user | CSV download |
| GET | `/detections/?bin=&category=&uncertain=1&days=&limit=&offset=` | user | paginated detections |
| GET | `/alerts/?bin=&active=1` | user | alerts |
| POST | `/alerts/<id>/resolve/` | user | close an alert |

## 3. Try it

```powershell
# device side
curl -X POST http://127.0.0.1:8000/api/device/telemetry/ -H "X-API-KEY: demo-key-bin-001" ^
     -H "Content-Type: application/json" -d "{\"organic_distance_cm\": 10, \"inorganic_distance_cm\": 30}"
```
The browsable API is also available: log in on the dashboard, then open http://localhost:8000/api/bins/.
