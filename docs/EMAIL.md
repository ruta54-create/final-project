# Email Alerts

The smart dustbin emails its users when something needs attention, in English, French or Kinyarwanda.

| Alert | Severity | Sent when |
|---|---|---|
| Organic / inorganic compartment **almost full** | warning | level reaches "Almost full" (default 75 %) |
| Organic / inorganic compartment **full** | critical | level reaches "Full" (default 90 %) |
| **Bad smell** | warning | gas ≥ threshold (default 400 ppm) |
| **Bin offline** | critical | no data from the controller for 90 s |
| **AI often uncertain** | info | ≥ 30 % of the last 20 items were uncertain |

Thresholds are set in **Settings → Bin settings**.

## 1. Turn it on for yourself (every user)

Dashboard → **Settings → Email notifications**:

1. Type your **email address** and tick **Send me email alerts**.
2. Choose the **email language** and **which alerts** you want:
   * *Almost full, full, bad smell, offline* (recommended): warning + critical
   * *Only full and offline*: critical only (good for supervisors)
   * *All alerts*: also "AI often uncertain"
3. With several bins, tick the bins you care about (none ticked = all bins).
4. Click **Save email settings**, then **Send test email**.

The **Recent emails** table shows every email with its status: *sent*, *waiting* (being retried) or *failed*.

## 2. Send real emails (Gmail example)

Until a mail server is configured, emails are **saved as `.eml` files** in `backend/sent_emails/`.
Double-click one to open it in Outlook or Windows Mail. To send real emails:

1. Use a Gmail account for the bin (for example `smartbin.ur@gmail.com`).
2. Google Account → **Security** → turn on **2-Step Verification**.
3. Google Account → **Security** → **App passwords** → create one named "Smart Dustbin" → copy the 16 letters.
4. Open `backend/.env` and remove the `#` in front of these lines, filling in your values:
   ```
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_USE_TLS=1
   EMAIL_HOST_USER=smartbin.ur@gmail.com
   EMAIL_HOST_PASSWORD=abcdefghijklmnop
   DEFAULT_FROM_EMAIL=Edge-AI Smart Dustbin <smartbin.ur@gmail.com>
   SITE_URL=http://192.168.1.10:8000
   ```
   `SITE_URL` is the link inside the email: use your PC's IP (from `ipconfig`) so the link works from a phone.
5. Restart the website (close the server window, double-click `RUN_DEMO.bat`).
6. Settings → **Send test email**. The note "No mail server is set up yet" disappears and the email arrives
   (check the spam folder the first time).

Other providers work the same way (Outlook: `smtp.office365.com`, port 587; a university SMTP server, and so on).

## 3. How it works (for the report)

```
bin sends telemetry ──▶ alert created (level ≥ threshold)
                          │
                          ├─ anti-flood: same alert in the last 30 min? → no email
                          ├─ who wants it? (address, on/off, severity, bins)
                          ▼
                 EmailNotification rows ("outbox", status = pending)
                          │  after the database commit
                          ▼
                 background thread sends them ──▶ sent / retried (3 attempts) / failed
```

* **The bin is never slowed down.** Telemetry is saved first; emails go out in a background thread.
* **Nothing is lost.** Every email is stored before sending. If the mail server is down, it is retried, and
  `python manage.py send_notifications --retry-failed` sends failed ones again later.
* **One email per event.** An alert stays active until the compartment is emptied, so a full bin produces
  one email, not one every 30 seconds. A level bouncing around the threshold also produces no extra emails
  within 30 minutes.
* **Code:** `backend/bins/services/notifications.py` (rules, outbox, sending),
  `services/email_content.py` (texts in 3 languages, HTML layout), `views_notifications.py` (API),
  `frontend/src/components/EmailSettings.jsx` (Settings card). Tests: `bins/tests/test_notifications.py`.

## 4. Offline alerts without the dashboard open

Fill-level, smell and AI alerts are raised by the bin's own data, so they are always emailed.
"Bin offline" is detected when someone views the dashboard. To be emailed even when nobody is looking,
schedule this command every 5 minutes (Windows **Task Scheduler** → *Create Basic Task* → program
`backend\venv\Scripts\python.exe`, arguments `manage.py send_notifications --check-offline`,
start in `...\My final project\backend`):

```
python manage.py send_notifications --check-offline
```
