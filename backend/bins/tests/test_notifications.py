from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from bins.models import Alert, Bin, EmailNotification, NotificationSettings, SensorReading
from bins.services import notifications


class BrokenBackend:
    """Email backend that always fails, like an unreachable SMTP server."""

    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise ConnectionError("SMTP down")


@override_settings(NOTIFICATIONS_ASYNC=False, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   SITE_URL="http://dashboard.test")
class EmailAlertTests(APITestCase):
    def setUp(self):
        self.bin = Bin.objects.create(name="Library Bin", location="Library", organic_depth_cm=40, inorganic_depth_cm=40)
        self.key = {"HTTP_X_API_KEY": self.bin.api_key}
        self.admin = User.objects.create_user("boss", email="boss@example.com", password="pw123456", is_staff=True)

    def telemetry(self, organic_cm, inorganic_cm=38, gas=150):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post("/api/device/telemetry/", {"organic_distance_cm": organic_cm,
                                 "inorganic_distance_cm": inorganic_cm, "gas_ppm": gas}, format="json", **self.key)
        self.assertEqual(r.status_code, 201)

    def test_full_compartment_sends_one_email(self):
        self.telemetry(2)  # 95 % full
        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertEqual(m.to, ["boss@example.com"])
        self.assertIn("Organic compartment is FULL (95%)", m.subject)
        self.assertIn("Library", m.body)
        self.assertIn("http://dashboard.test", m.body)
        self.assertEqual(m.alternatives[0][1], "text/html")
        self.assertEqual(EmailNotification.objects.get().status, "sent")
        # still full on the next readings: the alert already exists, so no second email
        self.telemetry(2)
        self.telemetry(1.5)
        self.assertEqual(len(mail.outbox), 1)

    def test_almost_full_then_full_sends_both(self):
        self.telemetry(8)   # 80 % -> almost full (warning)
        self.telemetry(2)   # 95 % -> full (critical)
        subjects = [m.subject for m in mail.outbox]
        self.assertEqual(len(subjects), 2)
        self.assertIn("almost full", subjects[0])
        self.assertIn("FULL", subjects[1])

    def test_language_preference(self):
        NotificationSettings.objects.create(user=self.admin, language="rw")
        self.telemetry(2)
        self.assertIn("Igice cy'ibibora CYUZUYE", mail.outbox[0].subject)
        self.assertIn("Muraho boss", mail.outbox[0].body)

    def test_preferences_are_respected(self):
        viewer = User.objects.create_user("cleaner", email="cleaner@example.com", password="pw123456")
        NotificationSettings.objects.create(user=viewer, min_severity="critical", language="fr")
        off = User.objects.create_user("off", email="off@example.com", password="pw123456")
        NotificationSettings.objects.create(user=off, email_enabled=False)
        other_bin = Bin.objects.create(name="Other")
        only_other = User.objects.create_user("other", email="other@example.com", password="pw123456")
        s = NotificationSettings.objects.create(user=only_other)
        s.bins.set([other_bin])
        User.objects.create_user("noemail", password="pw123456")  # no address: never emailed

        self.telemetry(8)  # warning: boss only (cleaner wants critical only)
        self.assertEqual([m.to[0] for m in mail.outbox], ["boss@example.com"])
        self.telemetry(2)  # critical: boss + cleaner (in French)
        last_two = dict((m.to[0], m.subject) for m in mail.outbox[1:])
        self.assertEqual(sorted(last_two), ["boss@example.com", "cleaner@example.com"])
        self.assertIn("PLEIN", last_two["cleaner@example.com"])

    def test_no_flood_when_level_bounces_around_threshold(self):
        self.telemetry(2)    # full -> email
        self.telemetry(30)   # emptied -> alert resolved
        self.telemetry(2)    # full again within 30 min -> no new email
        self.assertEqual(len(mail.outbox), 1)
        Alert.objects.update(created_at=timezone.now() - timedelta(hours=1))
        self.telemetry(30)
        self.telemetry(2)    # an hour later -> new email
        self.assertEqual(len(mail.outbox), 2)

    def test_smtp_failure_is_retried_then_marked_failed(self):
        with override_settings(EMAIL_BACKEND="bins.tests.test_notifications.BrokenBackend"):
            self.telemetry(2)
            n = EmailNotification.objects.get()
            self.assertEqual((n.status, n.attempts), ("pending", 1))
            self.assertIn("SMTP down", n.error)
            notifications.process_outbox()
            notifications.process_outbox()
            n.refresh_from_db()
            self.assertEqual((n.status, n.attempts), ("failed", 3))
        # mail server back: the command sends it again
        call_command("send_notifications", "--retry-failed")
        n.refresh_from_db()
        self.assertEqual(n.status, "sent")

    def test_email_problem_never_blocks_telemetry(self):
        with override_settings(EMAIL_BACKEND="bins.tests.test_notifications.BrokenBackend"):
            self.telemetry(2)  # asserts 201 inside
        self.assertEqual(SensorReading.objects.count(), 1)

    # ---------------------------------------------------------------- API
    def test_settings_api_and_test_email(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get("/api/notifications/settings/")
        self.assertEqual(r.json()["email"], "boss@example.com")
        self.assertEqual(r.json()["delivery"], "memory")
        r = self.client.patch("/api/notifications/settings/", {"email": "not-an-email"}, format="json")
        self.assertEqual((r.status_code, r.json()["code"]), (400, "invalid_email"))
        r = self.client.patch("/api/notifications/settings/", {"email": "new@example.com", "language": "fr",
                              "min_severity": "critical", "bins": [self.bin.id]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["bins"], [self.bin.id])
        r = self.client.post("/api/notifications/test/")
        self.assertEqual(r.json()["status"], "sent")
        self.assertEqual(mail.outbox[-1].to, ["new@example.com"])
        self.assertIn("E-mail de test", mail.outbox[-1].subject)
        log = self.client.get("/api/notifications/log/").json()
        self.assertEqual(log[0]["alert_kind"], "test")

    def test_viewer_sees_only_own_emails(self):
        viewer = User.objects.create_user("v", email="v@example.com", password="pw123456")
        self.telemetry(2)  # emails boss and v
        self.client.force_authenticate(viewer)
        self.assertEqual({row["to"] for row in self.client.get("/api/notifications/log/").json()}, {"v@example.com"})
        self.client.force_authenticate(self.admin)
        self.assertEqual(len(self.client.get("/api/notifications/log/").json()), 2)

    def test_email_required_to_enable(self):
        u = User.objects.create_user("x", password="pw123456")
        self.client.force_authenticate(u)
        r = self.client.patch("/api/notifications/settings/", {"email_enabled": True}, format="json")
        self.assertEqual(r.json()["code"], "email_required")
        self.assertEqual(self.client.post("/api/notifications/test/").json()["code"], "email_required")
