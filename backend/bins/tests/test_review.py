import io
import shutil
import tempfile
import zipfile

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import override_settings
from rest_framework.test import APITestCase

from bins.models import BIN_OF, Bin, Detection
from bins.services.model_quality import quality

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class TeachTheAiTests(APITestCase):
    """Human review of detections -> real-world accuracy -> training photos for the next model."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.bin = Bin.objects.create(name="B")
        self.admin = User.objects.create_user("admin", password="pw123456", is_staff=True)
        self.cleaner = User.objects.create_user("cleaner", password="pw123456")

    def det(self, label, true_label="", image=False):
        d = Detection(bin=self.bin, label=label, category=BIN_OF[label], confidence=0.9,
                      sorted_to=BIN_OF[label], true_label=true_label)
        if image:
            d.image.save(f"{label}.jpg", ContentFile(b"\xff\xd8fakejpeg"), save=False)
        d.save()
        return d

    def test_paper_goes_to_the_organic_compartment(self):
        self.assertEqual(BIN_OF["paper"], "organic")
        self.assertEqual(BIN_OF["organic"], "organic")
        self.assertEqual(BIN_OF["plastic"], "inorganic")
        self.assertEqual(BIN_OF["metal"], "inorganic")

    def test_cleaner_can_review_and_undo(self):
        d = self.det("plastic")
        self.client.force_authenticate(self.cleaner)
        r = self.client.post(f"/api/detections/{d.id}/review/", {"true_label": "metal"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["true_label"], r.json()["is_correct"], r.json()["reviewed_by"]), ("metal", False, "cleaner"))
        # plastic and metal share the inorganic compartment: wrong class, but the right compartment
        self.assertTrue(r.json()["right_compartment"])
        r = self.client.post(f"/api/detections/{d.id}/review/", {"true_label": ""}, format="json")
        self.assertIsNone(r.json()["is_correct"])

    def test_invalid_material_rejected(self):
        d = self.det("paper")
        self.client.force_authenticate(self.cleaner)
        r = self.client.post(f"/api/detections/{d.id}/review/", {"true_label": "banana"}, format="json")
        self.assertEqual((r.status_code, r.json()["code"]), (400, "invalid_material"))

    def test_quality_numbers(self):
        rows = [self.det("plastic", "plastic"), self.det("plastic", "metal"), self.det("paper", "plastic"),
                self.det("organic", "organic"), self.det("metal")]  # last one not reviewed
        q = quality(Detection.objects.exclude(true_label=""))
        self.assertEqual(q["reviewed"], 4)
        self.assertEqual(q["accuracy"], 0.5)                 # 2 of 4 exactly right
        self.assertEqual(q["compartment_accuracy"], 0.75)    # paper->organic bin but it was plastic: wrong bin
        i = q["labels"].index
        self.assertEqual(q["confusion"][i("metal")][i("plastic")], 1)
        self.assertEqual(len(rows), 5)

    def test_filters_and_analytics(self):
        self.det("plastic", "plastic")
        self.det("plastic", "metal")
        self.det("paper")
        self.client.force_authenticate(self.cleaner)
        self.assertEqual(self.client.get(f"/api/detections/?bin={self.bin.id}&reviewed=0").json()["count"], 1)
        self.assertEqual(self.client.get(f"/api/detections/?bin={self.bin.id}&wrong=1").json()["count"], 1)
        mq = self.client.get(f"/api/bins/{self.bin.id}/analytics/?days=7").json()["model_quality"]
        self.assertEqual((mq["reviewed"], mq["accuracy"]), (2, 0.5))

    def test_training_photo_export(self):
        self.det("plastic", "plastic", image=True)
        self.det("plastic", "metal", image=True)
        self.det("organic", "other", image=True)   # "other" is not a training class: left out
        self.det("paper", "", image=True)          # not reviewed: left out
        self.client.force_authenticate(self.cleaner)
        self.assertEqual(self.client.get(f"/api/bins/{self.bin.id}/training-photos/").status_code, 403)
        self.client.force_authenticate(self.admin)
        r = self.client.get(f"/api/bins/{self.bin.id}/training-photos/")
        self.assertEqual(r["Content-Type"], "application/zip")
        names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
        self.assertEqual(sorted(n.split("/")[0] for n in names if n.endswith(".jpg")), ["metal", "plastic"])
        self.assertIn("README.txt", names)
        self.assertEqual(r["X-Photo-Count"], "2")
