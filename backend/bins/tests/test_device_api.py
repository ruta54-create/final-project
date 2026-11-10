import io
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from bins.models import Alert, Bin, Command, Detection

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class DeviceApiTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.bin = Bin.objects.create(name="Test bin", organic_depth_cm=40, inorganic_depth_cm=50)
        self.key = {"HTTP_X_API_KEY": self.bin.api_key}

    # ------------------------------------------------------------ auth
    def test_missing_key_is_rejected(self):
        r = self.client.post("/api/device/telemetry/", {}, format="json")
        self.assertIn(r.status_code, (401, 403))

    def test_wrong_key_is_rejected(self):
        r = self.client.post("/api/device/telemetry/", {}, format="json", HTTP_X_API_KEY="nope")
        self.assertEqual(r.status_code, 401)

    def test_config_marks_cam_online(self):
        r = self.client.get("/api/device/config/?role=cam", **self.key)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["min_confidence"], 0.7)
        self.bin.refresh_from_db()
        self.assertTrue(self.bin.cam_online)

    # ------------------------------------------------------------ telemetry
    def test_telemetry_converts_distance_to_level_and_raises_alerts(self):
        r = self.client.post("/api/device/telemetry/", {
            "organic_distance_cm": 2,      # 95 % of 40 cm  -> full
            "inorganic_distance_cm": 25,   # 50 % of 50 cm  -> normal
            "gas_ppm": 600, "temperature": 27.5, "humidity": 60,
            "firmware": "1.2.0", "wifi_rssi": -60, "booted": True,
        }, format="json", **self.key)
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertEqual(body["organic_level"], 95.0)
        self.assertEqual(body["inorganic_level"], 50.0)
        self.assertEqual(body["mode"], "auto")

        self.bin.refresh_from_db()
        self.assertTrue(self.bin.is_online)
        self.assertEqual(self.bin.firmware_main, "1.2.0")
        kinds = set(Alert.objects.filter(is_active=True).values_list("kind", flat=True))
        self.assertEqual(kinds, {"organic_full", "gas_high"})

        # bin emptied -> alerts resolve automatically
        self.client.post("/api/device/telemetry/", {"organic_distance_cm": 38, "inorganic_distance_cm": 45,
                                                    "gas_ppm": 150}, format="json", **self.key)
        self.assertFalse(Alert.objects.filter(is_active=True).exists())

    def test_telemetry_does_not_undo_a_mode_change(self):
        """Race: the device request loaded the bin, then an admin changed the mode."""
        from unittest import mock
        from django.contrib.auth.models import AnonymousUser
        from bins.auth import DeviceKeyAuthentication

        stale = Bin.objects.get(pk=self.bin.pk)            # mode = auto, loaded by the device request
        Bin.objects.filter(pk=self.bin.pk).update(mode="maintenance")  # admin clicks Maintenance
        with mock.patch.object(DeviceKeyAuthentication, "authenticate", return_value=(AnonymousUser(), stale)):
            r = self.client.post("/api/device/telemetry/", {"organic_distance_cm": 20}, format="json")
        self.assertEqual(r.json()["mode"], "maintenance")   # device is told the NEW mode
        self.bin.refresh_from_db()
        self.assertEqual(self.bin.mode, "maintenance")      # and the change was not overwritten

    def test_invalid_telemetry(self):
        r = self.client.post("/api/device/telemetry/", {"humidity": 300}, format="json", **self.key)
        self.assertEqual(r.status_code, 400)

    # ------------------------------------------------------------ detection
    def test_confident_detection_is_sorted_by_category(self):
        r = self.client.post("/api/device/detection/", {
            "label": "Fruit_Peel", "category": "organic", "confidence": 0.93, "inference_ms": 420,
            "model_version": "v2"}, format="json", **self.key)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["sorted_to"], "organic")
        det = Detection.objects.get()
        self.assertEqual(det.label, "fruit_peel")
        self.assertFalse(det.uncertain)

    def test_uncertain_detection_goes_to_inorganic(self):
        r = self.client.post("/api/device/detection/", {
            "label": "food_waste", "category": "organic", "confidence": 0.55}, format="json", **self.key)
        self.assertEqual(r.json()["sorted_to"], "inorganic")  # never contaminate the compost
        self.assertTrue(r.json()["uncertain"])

    def test_detection_with_photo_upload(self):
        buf = io.BytesIO()
        Image.new("RGB", (320, 240), "green").save(buf, "JPEG")
        buf.seek(0)
        buf.name = "capture.jpg"
        r = self.client.post("/api/device/detection/", {
            "label": "plastic_bottle", "category": "inorganic", "confidence": "0.88", "image": buf,
        }, format="multipart", **self.key)
        self.assertEqual(r.status_code, 201, r.content)
        det = Detection.objects.get()
        self.assertTrue(det.image.name.endswith(".jpg"))
        self.bin.refresh_from_db()
        self.assertTrue(self.bin.cam_online)

    def test_low_confidence_alert_after_many_uncertain_items(self):
        for i in range(12):
            self.client.post("/api/device/detection/", {
                "label": "x", "category": "organic", "confidence": 0.5 if i % 2 else 0.9},
                format="json", **self.key)
        self.assertTrue(Alert.objects.filter(kind="low_confidence", is_active=True).exists())

    # ------------------------------------------------------------ commands
    def test_command_round_trip(self):
        admin = User.objects.create_user("boss", password="pw123456", is_staff=True)
        self.client.force_authenticate(admin)
        r = self.client.post(f"/api/bins/{self.bin.id}/commands/",
                             {"action": "calibrate", "payload": {}}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        cmd_id = r.json()["id"]
        self.client.force_authenticate(None)

        polled = self.client.get("/api/device/commands/", **self.key).json()
        self.assertEqual([c["id"] for c in polled["commands"]], [cmd_id])
        self.assertEqual(Command.objects.get().status, "sent")
        # handed out only once
        self.assertEqual(self.client.get("/api/device/commands/", **self.key).json()["commands"], [])

        r = self.client.post(f"/api/device/commands/{cmd_id}/ack/", {
            "status": "done", "result": {"organic_depth_cm": 42.3, "inorganic_depth_cm": 51}},
            format="json", **self.key)
        self.assertEqual(r.status_code, 200)
        self.bin.refresh_from_db()
        self.assertEqual((self.bin.organic_depth_cm, self.bin.inorganic_depth_cm), (42.3, 51.0))
        self.assertEqual(Command.objects.get().status, "done")

    def test_calibration_of_a_full_bin_is_rejected(self):
        cmd = Command.objects.create(bin=self.bin, action="calibrate", status="sent")
        r = self.client.post(f"/api/device/commands/{cmd.id}/ack/", {
            "status": "done", "result": {"organic_depth_cm": 4.8, "inorganic_depth_cm": 34.6}},
            format="json", **self.key)
        self.assertEqual(r.status_code, 200)
        cmd.refresh_from_db()
        self.bin.refresh_from_db()
        self.assertEqual(cmd.status, "failed")
        self.assertIn("too small", cmd.message)
        self.assertEqual(cmd.message_code, "depth_too_small")
        self.assertEqual(cmd.message_params, {"compartment": "organic", "value": 4.8})
        self.assertEqual((self.bin.organic_depth_cm, self.bin.inorganic_depth_cm), (40, 50))  # unchanged

    def test_old_commands_expire(self):
        Command.objects.create(bin=self.bin, action="buzzer", created_at=timezone.now() - timedelta(minutes=5))
        self.assertEqual(self.client.get("/api/device/commands/", **self.key).json()["commands"], [])
        self.assertEqual(Command.objects.get().status, "expired")
        self.assertEqual(Command.objects.get().message_code, "expired")

    def test_device_cannot_ack_other_bins_command(self):
        other = Bin.objects.create(name="Other")
        cmd = Command.objects.create(bin=other, action="buzzer")
        r = self.client.post(f"/api/device/commands/{cmd.id}/ack/", {"status": "done"}, format="json", **self.key)
        self.assertEqual(r.status_code, 404)
