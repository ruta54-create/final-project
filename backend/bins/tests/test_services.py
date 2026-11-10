from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from bins.models import Bin, Collection, SensorReading
from bins.services import prediction, recommendations


class PredictionTests(TestCase):
    def setUp(self):
        self.bin = Bin.objects.create(name="b", full_level=90, warning_level=75)
        self.now = timezone.now()

    def add(self, hours_ago, organic, inorganic=10):
        SensorReading.objects.create(bin=self.bin, organic_level=organic, inorganic_level=inorganic,
                                     created_at=self.now - timedelta(hours=hours_ago))

    def test_linear_trend(self):
        for h in range(10, -1, -1):          # 10 h ago -> now, +2 %/h, now at 50 %
            self.add(h, 30 + (10 - h) * 2)
        p = prediction.predict(self.bin, "organic", self.now)
        self.assertEqual(p["rate_per_hour"], 2.0)
        self.assertEqual(p["hours_to_full"], 20.0)   # (90-50)/2
        self.assertEqual(p["method"], "trend")

    def test_ignores_data_before_emptying(self):
        for h, lvl in [(6, 80), (5, 85), (4, 88), (3, 5), (2, 8), (1, 11), (0, 14)]:
            self.add(h, lvl)
        p = prediction.predict(self.bin, "organic", self.now)
        self.assertEqual(p["rate_per_hour"], 3.0)

    def test_collection_resets_window(self):
        for h in range(10, 2, -1):
            self.add(h, 60)
        Collection.objects.create(bin=self.bin, compartment="organic", created_at=self.now - timedelta(hours=2, minutes=30))
        for h, lvl in [(2, 10), (1, 14), (0, 18)]:
            self.add(h, lvl)
        self.assertEqual(prediction.predict(self.bin, "organic", self.now)["rate_per_hour"], 4.0)

    def test_full_and_no_data(self):
        self.add(0, 95)
        p = prediction.predict(self.bin, "organic", self.now)
        self.assertEqual((p["hours_to_full"], p["status"]["label"]), (0, "Full"))
        empty = Bin.objects.create(name="empty")
        p = prediction.predict(empty, "organic", self.now)
        self.assertIsNone(p["level"])
        self.assertEqual(p["status"]["label"], "No data")

    def test_history_fallback_when_few_recent_points(self):
        for h in range(96, 80, -1):  # filling 1 %/h 3-4 days ago, nothing recent
            self.add(h, 10 + (96 - h))
        p = prediction.predict(self.bin, "organic", self.now)
        self.assertEqual(p["method"], "history")
        self.assertGreater(p["rate_per_hour"], 0)


class RecommendationTests(TestCase):
    def test_full_compartment_recommends_collection(self):
        bin = Bin.objects.create(name="b", last_seen=timezone.now())
        r = SensorReading.objects.create(bin=bin, organic_level=95, inorganic_level=20, gas_ppm=500)
        preds = {c: prediction.predict(bin, c) for c in ("organic", "inorganic")}
        recs = recommendations.build(bin, preds, r)
        self.assertEqual(recs[0]["action"], {"type": "collect", "compartment": "organic"})
        self.assertIn("Bad smell detected", [x["title"] for x in recs])

    def test_all_good(self):
        bin = Bin.objects.create(name="b", last_seen=timezone.now())
        r = SensorReading.objects.create(bin=bin, organic_level=20, inorganic_level=20, gas_ppm=150)
        preds = {c: prediction.predict(bin, c) for c in ("organic", "inorganic")}
        self.assertEqual(recommendations.build(bin, preds, r)[0]["title"], "Everything is OK")

    def test_offline(self):
        bin = Bin.objects.create(name="b", last_seen=timezone.now() - timedelta(minutes=10))
        recs = recommendations.build(bin, {c: prediction.predict(bin, c) for c in ("organic", "inorganic")}, None)
        self.assertEqual(recs[0]["title"], "Bin is offline")


class LanguageNeutralCodesTests(TestCase):
    """The dashboard translates these codes into English / French / Kinyarwanda."""

    def test_status_and_recommendations_have_codes(self):
        bin = Bin.objects.create(name="b", last_seen=timezone.now())
        r = SensorReading.objects.create(bin=bin, organic_level=95, inorganic_level=80, gas_ppm=500)
        preds = {c: prediction.predict(bin, c) for c in ("organic", "inorganic")}
        self.assertEqual(preds["organic"]["status"]["code"], "full")
        self.assertEqual(preds["inorganic"]["status"]["code"], "almost_full")
        recs = recommendations.build(bin, preds, r)
        codes = {x["code"] for x in recs}
        self.assertIn("empty_now", codes)
        self.assertIn("bad_smell", codes)
        empty = next(x for x in recs if x["code"] == "empty_now")
        self.assertEqual(empty["params"], {"compartment": "organic", "level": 95})

    def test_alert_params(self):
        from bins.services import alerts
        bin = Bin.objects.create(name="b")
        r = SensorReading.objects.create(bin=bin, organic_level=93, inorganic_level=10, gas_ppm=450)
        alerts.evaluate_reading(bin, r)
        full = bin.alerts.get(kind="organic_full")
        self.assertEqual(full.params, {"compartment": "organic", "level": 93})
        self.assertEqual(bin.alerts.get(kind="gas_high").params, {"gas": 450})
