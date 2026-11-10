"""Email notifications for alerts.

Flow:  alert created  ->  queue_alert_emails()  ->  EmailNotification rows (outbox, status "pending")
       ->  after the database commit, a background thread runs process_outbox()  ->  "sent" / retried / "failed"

* Telemetry from the bin never waits for the mail server (sending happens in the background).
* Nothing is lost: every email is stored first; failed ones are retried (MAX_ATTEMPTS) and can be
  re-sent with  python manage.py send_notifications
* Anti-flood: if the same alert (bin + kind) fired in the last COOLDOWN, no new email is sent.
"""

import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections, transaction
from django.utils import timezone

from ..models import Alert, EmailNotification, NotificationSettings
from .email_content import render_alert, render_test

log = logging.getLogger(__name__)
COOLDOWN = timedelta(minutes=30)
EMAIL_KINDS = {"organic_full", "organic_warning", "inorganic_full", "inorganic_warning",
               "gas_high", "device_offline", "low_confidence"}
_worker_lock = threading.Lock()


def settings_for(user):
    """A user's preferences, read fresh from the database (defaults if never saved)."""
    return NotificationSettings.objects.filter(user=user).first() or NotificationSettings(user=user)


def recipients_for(alert):
    """(user, language) for every active user with an email address who wants this alert."""
    users = get_user_model().objects.filter(is_active=True).exclude(email="")
    prefs = {p.user_id: p for p in NotificationSettings.objects.filter(user__in=users).prefetch_related("bins")}
    result = []
    for user in users:
        p = prefs.get(user.id) or NotificationSettings(user=user)  # never saved = defaults
        if p.wants(alert):
            result.append((user, p.language))
    return result


def queue_alert_emails(alert):
    """Store one email per interested user. Called when a NEW alert is created."""
    if alert.kind not in EMAIL_KINDS:
        return []
    recently = Alert.objects.filter(
        bin=alert.bin, kind=alert.kind, created_at__gte=alert.created_at - COOLDOWN
    ).exclude(pk=alert.pk).exists()
    if recently:  # level going up and down around the threshold: don't flood people
        return []

    queued = []
    for user, lang in recipients_for(alert):
        subject, text, html = render_alert(alert, user, lang)
        queued.append(EmailNotification.objects.create(
            alert=alert, user=user, to=user.email, subject=subject, body=text, html=html))
    if queued:
        transaction.on_commit(start_worker)
    return queued


def send_one(n):
    """Try to send one stored email; update its status. Returns True if sent."""
    n.attempts += 1
    try:
        msg = EmailMultiAlternatives(n.subject, n.body, settings.DEFAULT_FROM_EMAIL, [n.to])
        if n.html:
            msg.attach_alternative(n.html, "text/html")
        msg.send(fail_silently=False)
        n.status, n.sent_at, n.error = "sent", timezone.now(), ""
    except Exception as exc:  # network / SMTP / login errors: keep for retry
        n.error = f"{type(exc).__name__}: {exc}"[:500]
        n.status = "failed" if n.attempts >= EmailNotification.MAX_ATTEMPTS else "pending"
        log.warning("Email to %s failed (attempt %s): %s", n.to, n.attempts, n.error)
    n.save(update_fields=["status", "attempts", "error", "sent_at"])
    return n.status == "sent"


def process_outbox(limit=50):
    """Send pending emails. Safe to call from a thread, a command or a test."""
    sent = 0
    for n in EmailNotification.objects.filter(status="pending").order_by("created_at")[:limit]:
        sent += send_one(n)
    return sent


def _worker():
    if not _worker_lock.acquire(blocking=False):
        return  # another worker is already sending
    try:
        close_old_connections()
        process_outbox()
    except Exception:
        log.exception("Email worker crashed")
    finally:
        close_old_connections()
        _worker_lock.release()


def start_worker():
    if getattr(settings, "NOTIFICATIONS_ASYNC", True):
        threading.Thread(target=_worker, name="email-outbox", daemon=True).start()
    else:
        process_outbox()


def send_test_email(user):
    """Send a test email right now (synchronously) so the user sees the result immediately."""
    prefs = settings_for(user)
    subject, text, html = render_test(user, prefs.language)
    n = EmailNotification.objects.create(user=user, to=user.email, subject=subject, body=text, html=html)
    send_one(n)
    return n


def delivery_mode():
    """'smtp' = real emails; 'file' = saved in backend/sent_emails (no mail server configured)."""
    backend = settings.EMAIL_BACKEND
    for key, mode in (("smtp", "smtp"), ("filebased", "file"), ("EmlFile", "file"), ("console", "console"), ("locmem", "memory")):
        if key in backend:
            return mode
    return backend
