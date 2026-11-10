import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from bins.models import Alert, Bin, Collection, Detection, SensorReading


class DashboardApiTests(APITestCase):
    def setUp(self):
        self.bin = Bin.objects.create(name="Main bin")
        self.admin = User.objects.create_user("admin", password="admin12345", is_staff=True)
        self.viewer = User.objects.create_user("viewer", password="viewer12345")
        SensorReading.objects.create(bin=self.bin, organic_level=80, inorganic_level=30, gas_ppm=200)
        Detection.objects.create(bin=self.bin, label="leaves", category="organic", confidence=0.9,
                                 sorted_to="organic")

    def test_login_required(self):
        self.assertEqual(self.client.get("/api/bins/").status_code, 403)
        self.assertEqual(self.client.get("/api/auth/me/").json(), {"authenticated": False})

    def test_login_flow_with_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        r = client.post("/api/auth/login/", {"username": "admin", "password": "admin12345"}, format="json")
        self.assertEqual(r.status_code, 403)  # no CSRF token yet
        client.get("/api/auth/csrf/")
        token = client.cookies["csrftoken"].value
        r = client.post("/api/auth/login/", {"username": "admin", "password": "wrong"}, format="json",
                        HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "bad_credentials")
        r = client.post("/api/auth/login/", {"username": "admin", "password": "admin12345"}, format="json",
                        HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["is_staff"])
        self.assertEqual(client.get("/api/auth/me/").json()["username"], "admin")

    def test_overview(self):
        self.client.force_authenticate(self.viewer)
        r = self.client.get(f"/api/bins/{self.bin.id}/overview/")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["compartments"]["organic"]["level"], 80)
        self.assertEqual(d["compartments"]["organic"]["status"]["label"], "Almost full")
        self.assertEqual(d["today"]["organic"], 1)
        self.assertIsNone(d["bin"]["api_key"])  # viewers never see the device secret
        self.assertTrue(d["recommendations"])

    def test_staff_sees_api_key(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f"/api/bins/{self.bin.id}/").json()["api_key"], self.bin.api_key)

    def test_viewer_cannot_control_or_change_settings(self):
        self.client.force_authenticate(self.viewer)
        r = self.client.post(f"/api/bins/{self.bin.id}/commands/", {"action": "open_lid"}, format="json")
        self.assertEqual(r.status_code, 403)
        r = self.client.patch(f"/api/bins/{self.bin.id}/", {"name": "x"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_set_mode_command_changes_mode(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f"/api/bins/{self.bin.id}/commands/",
                             {"action": "set_mode", "payload": {"mode": "maintenance"}}, format="json")
        self.assertEqual(r.status_code, 201)
        self.bin.refresh_from_db()
        self.assertEqual(self.bin.mode, "maintenance")
        r = self.client.post(f"/api/bins/{self.bin.id}/commands/",
                             {"action": "set_mode", "payload": {"mode": "party"}}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_settings_validation(self):
        self.client.force_authenticate(self.admin)
        r = self.client.patch(f"/api/bins/{self.bin.id}/", {"warning_level": 95, "full_level": 90}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(f"/api/bins/{self.bin.id}/", {"organic_depth_cm": 55, "location": "Gate"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["organic_depth_cm"], 55)

    def test_collection_resolves_alerts(self):
        Alert.objects.create(bin=self.bin, kind="organic_full", severity="critical", message="full")
        self.client.force_authenticate(self.viewer)  # cleaners may record collections
        r = self.client.post(f"/api/bins/{self.bin.id}/collections/", {"compartment": "organic"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["level_before"], 80)
        self.assertFalse(Alert.objects.filter(is_active=True).exists())
        self.assertEqual(Collection.objects.get().created_by, self.viewer)

    def test_alert_list_and_resolve(self):
        a = Alert.objects.create(bin=self.bin, kind="gas_high", severity="warning", message="smell")
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get("/api/alerts/?active=1").json()["count"], 1)
        self.client.post(f"/api/alerts/{a.id}/resolve/")
        self.assertEqual(self.client.get("/api/alerts/?active=1").json()["count"], 0)

    def test_analytics_readings_detections_export(self):
        self.client.force_authenticate(self.viewer)
        a = self.client.get(f"/api/bins/{self.bin.id}/analytics/?days=7").json()
        self.assertEqual((a["total"], a["organic"], a["inorganic"]), (1, 1, 0))
        self.assertEqual(len(a["per_hour"]), 24)
        self.assertEqual(self.client.get(f"/api/bins/{self.bin.id}/readings/?hours=24").json()["count"], 1)
        self.assertEqual(self.client.get("/api/detections/?category=organic").json()["count"], 1)
        self.assertEqual(self.client.get("/api/detections/?category=inorganic").json()["count"], 0)
        csv = self.client.get(f"/api/bins/{self.bin.id}/export/?type=detections")
        self.assertEqual(csv["Content-Type"], "text/csv")
        self.assertIn("leaves,organic", csv.content.decode())

    def test_regenerate_key(self):
        self.client.force_authenticate(self.admin)
        old = self.bin.api_key
        new = self.client.post(f"/api/bins/{self.bin.id}/regenerate-key/").json()["api_key"]
        self.assertNotEqual(old, new)
        self.client.force_authenticate(None)
        r = self.client.get("/api/device/config/", HTTP_X_API_KEY=old)
        self.assertEqual(r.status_code, 401)


class FrontendServingTests(APITestCase):
    def test_spa_routes_return_index(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            Path(d, "index.html").write_text("<html>dashboard</html>")
            Path(d, "logo.png").write_bytes(b"png")
            with override_settings(FRONTEND_DIST=Path(d)):
                for url in ("/", "/control", "/analytics/"):
                    r = self.client.get(url)
                    self.assertEqual(r.status_code, 200)
                    self.assertIn(b"dashboard", b"".join(r.streaming_content))
                    r.close()
                r = self.client.get("/logo.png")
                self.assertEqual(r.status_code, 200)
                r.close()
                # API urls are never swallowed by the SPA
                self.assertEqual(self.client.get("/api/bins/").status_code, 403)
                self.assertEqual(self.client.get("/api/nothing-here/").status_code, 404)

    def test_message_when_not_built(self):
        with tempfile.TemporaryDirectory() as d, override_settings(FRONTEND_DIST=Path(d)):
            self.assertEqual(self.client.get("/").status_code, 503)
