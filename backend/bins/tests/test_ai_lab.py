import io
import shutil
import tempfile
import urllib.error
from unittest import mock

from django.contrib.auth.models import User
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from bins.models import Bin, Detection

MEDIA = tempfile.mkdtemp()


def photo():
    buf = io.BytesIO()
    Image.new("RGB", (200, 150), "orange").save(buf, "JPEG")
    buf.seek(0)
    buf.name = "test.jpg"
    return buf


def ai_answer(label, conf):
    scores = {"organic": 0.0, "paper": 0.0, "plastic": 0.0, "metal": 0.0}
    scores[label] = conf
    return lambda path, data=None: {"label": label, "confidence": conf, "scores": scores, "inference_ms": 3.1}


@override_settings(MEDIA_ROOT=MEDIA)
class AiLabTests(APITestCase):
    """'Test the AI' page: photo -> AI service -> the bin's sorting rules (no hardware needed)."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.bin = Bin.objects.create(name="B", min_confidence=0.7)
        self.client.force_authenticate(User.objects.create_user("u", password="pw123456"))

    def classify(self, save=False):
        return self.client.post("/api/ai/classify/", {"image": photo(), "bin": self.bin.id, "save": "1" if save else ""},
                                format="multipart")

    def test_paper_goes_to_organic(self):
        with mock.patch("bins.views_ai.ai_service", ai_answer("paper", 0.91)):
            r = self.classify()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["category"], r.json()["sorted_to"], r.json()["uncertain"]), ("organic", "organic", False))
        self.assertIsNone(r.json()["saved"])
        self.assertFalse(Detection.objects.exists())  # only a test: nothing saved

    def test_unsure_goes_to_inorganic(self):
        with mock.patch("bins.views_ai.ai_service", ai_answer("organic", 0.55)):
            r = self.classify()
        self.assertEqual((r.json()["sorted_to"], r.json()["uncertain"]), ("inorganic", True))

    def test_save_as_detection_like_the_camera(self):
        with mock.patch("bins.views_ai.ai_service", ai_answer("metal", 0.88)):
            r = self.classify(save=True)
        det = Detection.objects.get()
        self.assertEqual((det.label, det.sorted_to, det.bin_id), ("metal", "inorganic", self.bin.id))
        self.assertTrue(det.image.name.endswith(".jpg"))
        self.assertEqual(r.json()["saved"]["id"], det.id)

    def test_service_offline(self):
        def down(path, data=None):
            raise urllib.error.URLError("refused")
        with mock.patch("bins.views_ai.ai_service", down):
            r = self.classify()
            self.assertEqual((r.status_code, r.json()["code"]), (503, "ai_offline"))
            self.assertFalse(self.client.get("/api/ai/status/").json()["online"])

    def test_no_image_and_login_required(self):
        self.assertEqual(self.client.post("/api/ai/classify/", {}, format="multipart").json()["code"], "no_image")
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post("/api/ai/classify/", {"image": photo()}, format="multipart").status_code, 403)
