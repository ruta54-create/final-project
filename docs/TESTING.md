# Testing

## 1. Summary (software, 5 Nov 2026)

| Level | Tool | Result |
|---|---|---|
| Unit + API tests (backend) | `python manage.py test bins` | **47 / 47 passed** |
| End-to-end system check (server + simulated bin) | `python tools/system_check.py` | **32 / 32 passed** |
| Frontend build | `npm run build` | passes, no errors |
| Visual check | headless Chrome, 1536 px desktop and 400 px phone, all 7 pages | all pages render with live data |
| Email alerts (live, in Chrome) | save address, test email, real FULL alert emailed automatically | **8 / 8** |
| Translations | `node tools/check_i18n.mjs` | **344 keys** in EN / FR / RW, no missing key or placeholder |
| Language switch in browser | headless Chrome, all 6 pages × 3 languages | **27 / 27**, no English left in FR / RW |
| Hardware firmware | Arduino IDE | **not yet compiled or run on real boards**: do this in weeks 6–9 (section 4) |

## 2. Automated backend tests (`backend/bins/tests/`)

| Group | What is verified |
|---|---|
| Device security | missing/wrong API key rejected; a device cannot acknowledge another bin's command; regenerated key invalidates the old one |
| Telemetry | distance → % conversion, online status, firmware info, invalid values rejected, full/gas alerts raised **and auto-resolved** |
| Detections | confident item sorted by category; uncertain (< 70 %) item forced to inorganic; JPEG upload stored; low-confidence alert after many uncertain items |
| Remote control | command delivered once, acknowledged, calibration updates depths; old commands expire; `set_mode` changes mode; invalid mode rejected |
| Dashboard API | login required, login with CSRF, overview contents, analytics/readings/detections filters, CSV export, settings validation, collections resolve alerts, alert resolve |
| Roles | viewers cannot see API key, send commands or change settings; admins can |
| Prediction | linear rate & time-to-full, ignores data before emptying, collection resets the window, full = 0 h, no-data case, 7-day history fallback |
| Recommendations | full → "empty now" with action; bad smell; offline; "everything OK" |
| Web serving | React routes (/, /control, /analytics/) return the app; API URLs are never swallowed; message when the dashboard is not built |

## 3. End-to-end check (`tools/system_check.py`)

Run with Django and the simulator (or the real bin) running. It checks: pages load, anonymous access refused,
wrong password refused, admin login, overview/analytics/readings/detections/alerts, CSV export,
**controller online, new items arriving, camera photo served**, **7 remote commands executed by the bin**
(open/close lid, tilt, capture, buzzer, manual/auto mode), recording a collection, viewer restrictions, logout.

## 4. Hardware test procedures (fill in during integration)

### 4.1 Classification accuracy (100 items)
| | Predicted organic | Predicted inorganic |
|---|---|---|
| **Actually organic (50)** | | |
| **Actually inorganic (50)** | | |

Accuracy = correct / 100 = ____ %   (target ≥ 90 %).
Organic precision = ____  Organic recall = ____ .
Use *Analytics → Detections CSV* to get confidence and timestamps.

### 4.2 Fill-level accuracy
| Real level (ruler) | 0 % | 25 % | 50 % | 75 % | 100 % |
|---|---|---|---|---|---|
| Dashboard organic | | | | | |
| Dashboard inorganic | | | | | |

Target error ≤ 5 %.

### 4.3 Timing
| Measurement | Result | Target |
|---|---|---|
| Item placed → item falls into compartment | | < 3 s |
| AI inference time (shown on dashboard) | | < 1 s |
| Item sorted → visible on dashboard | | < 5 s |
| Dashboard button → servo moves | | < 3 s |

### 4.4 Other
| Test | Expected | OK? |
|---|---|---|
| Hand at 10 cm from front sensor | lid opens, closes after 5 s | |
| Unplug Wi-Fi router, place items | bin still sorts (edge AI); dashboard shows offline, then recovers | |
| Rotten fruit in organic compartment for 1 day | gas ppm rises, *Bad smell* alert | |
| Fill a compartment above 90 % | red LED, 3 beeps, *Full* alert and recommendation | |
| Maintenance mode | lid opens and stays open, blue LED blinks, no sorting | |
| 24-hour run | no reboot, readings every 30 s, prediction close to reality | |

## 5. How to re-run everything

```powershell
cd backend
venv\Scripts\python manage.py test bins           # 33 tests (~3 min on OneDrive)
cd ..
RUN_DEMO.bat                                    # server + simulator
backend\venv\Scripts\python tools\system_check.py # in a new terminal
```
