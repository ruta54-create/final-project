"""python manage.py send_notifications [--check-offline] [--retry-failed]

Sends emails still waiting in the outbox (e.g. after the mail server was down).
--check-offline  also raises "device offline" alerts (and their emails) for bins that stopped reporting.
--retry-failed   gives failed emails another set of attempts.
Schedule it every few minutes with Windows Task Scheduler or cron for fully unattended alerts.
"""

from django.core.management.base import BaseCommand

from bins.models import Bin, EmailNotification
from bins.services import alerts
from bins.services.notifications import process_outbox


class Command(BaseCommand):
    help = "Send pending alert emails (and optionally check for offline bins)"

    def add_arguments(self, parser):
        parser.add_argument("--check-offline", action="store_true")
        parser.add_argument("--retry-failed", action="store_true")

    def handle(self, *args, **opts):
        if opts["check_offline"]:
            for bin in Bin.objects.all():
                alerts.evaluate_offline(bin)
        if opts["retry_failed"]:
            n = EmailNotification.objects.filter(status="failed").update(status="pending", attempts=0)
            self.stdout.write(f"{n} failed email(s) queued again")
        sent = process_outbox(limit=500)
        left = EmailNotification.objects.filter(status="pending").count()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} email(s); {left} still pending"))
