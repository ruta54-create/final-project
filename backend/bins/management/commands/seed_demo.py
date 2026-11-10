"""python manage.py seed_demo

Creates demo users, one bin and 7 days of realistic data so the dashboard can be
shown before the hardware is finished. Safe to run again (it resets the demo bin).
"""

import math
import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bins.models import INORGANIC, ORGANIC, Bin, Collection, Detection, SensorReading
from bins.models import Command as BinCommand
from bins.services import alerts

DEMO_KEY = "demo-key-bin-001"
ORGANIC_LABELS = ["food_waste", "fruit_peel", "vegetable", "leaves", "bread", "eggshell"]
INORGANIC_LABELS = ["plastic_bottle", "plastic_bag", "can", "glass", "wrapper", "paper_cup"]


class Command(BaseCommand):
    help = "Create demo users, a demo bin and 7 days of sample data"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(42)
        now = timezone.now()
        start = now - timedelta(days=opts["days"])

        admin, created = User.objects.get_or_create(
            username="admin", defaults={"is_staff": True, "is_superuser": True, "first_name": "Admin"})
        if created:
            admin.set_password("admin12345")
            admin.save()
        cleaner, created = User.objects.get_or_create(username="cleaner", defaults={"first_name": "Cleaner"})
        if created:
            cleaner.set_password("cleaner12345")
            cleaner.save()

        Bin.objects.filter(api_key=DEMO_KEY).delete()
        bin = Bin.objects.create(
            name="Smart Bin #1", location="University of Rwanda - Main Campus", api_key=DEMO_KEY,
            firmware_main="1.0.0", firmware_cam="1.0.0", model_version="organic-inorganic-v1",
            ip_main="192.168.1.50", ip_cam="192.168.1.51", wifi_rssi=-58,
            booted_at=now - timedelta(hours=5, minutes=12), last_seen=now, cam_last_seen=now,
        )

        # --- sensor readings every 10 minutes, compartments emptied when nearly full
        readings, collections = [], []
        org, ino, org_since = 8.0, 12.0, start
        t = start
        while t <= now:
            hour = timezone.localtime(t).hour
            busy = 1.0 if 7 <= hour <= 20 else 0.15
            org += rnd.uniform(0.15, 0.5) * busy
            ino += rnd.uniform(0.08, 0.32) * busy
            if org >= 92:
                collections.append(Collection(bin=bin, compartment=ORGANIC, level_before=round(org, 1),
                                              created_by=cleaner, created_at=t))
                org, org_since = rnd.uniform(2, 6), t
            if ino >= 92:
                collections.append(Collection(bin=bin, compartment=INORGANIC, level_before=round(ino, 1),
                                              created_by=cleaner, created_at=t))
                ino = rnd.uniform(2, 6)
            hours_since = (t - org_since).total_seconds() / 3600
            temp = 24 + 4 * math.sin((hour - 9) / 24 * 2 * math.pi) + rnd.uniform(-0.5, 0.5)
            readings.append(SensorReading(
                bin=bin, created_at=t,
                organic_level=round(org, 1), inorganic_level=round(ino, 1),
                organic_distance_cm=round(40 * (1 - org / 100), 1),
                inorganic_distance_cm=round(40 * (1 - ino / 100), 1),
                gas_ppm=round(110 + org * 1.6 + hours_since * 2.5 + rnd.uniform(-10, 10)),
                temperature=round(temp, 1), humidity=round(rnd.uniform(55, 72), 1),
            ))
            t += timedelta(minutes=10)
        SensorReading.objects.bulk_create(readings)
        Collection.objects.bulk_create(collections)

        # --- detections: busier during the day, ~60% organic
        dets = []
        t = start
        while t <= now:
            hour = timezone.localtime(t).hour
            per_hour = 5 if 7 <= hour <= 20 else 1
            for _ in range(rnd.randint(per_hour - 1, per_hour + 1)):
                cat = ORGANIC if rnd.random() < 0.6 else INORGANIC
                conf = round(rnd.choice([rnd.uniform(0.8, 0.99)] * 9 + [rnd.uniform(0.5, 0.7)]), 3)
                uncertain = conf < bin.min_confidence
                dets.append(Detection(
                    bin=bin, created_at=t + timedelta(minutes=rnd.randint(0, 59)),
                    label=rnd.choice(ORGANIC_LABELS if cat == ORGANIC else INORGANIC_LABELS),
                    category=cat, confidence=conf, uncertain=uncertain,
                    sorted_to=INORGANIC if uncertain else cat, inference_ms=rnd.randint(380, 620),
                ))
            t += timedelta(hours=1)
        Detection.objects.bulk_create([d for d in dets if d.created_at <= now])

        BinCommand.objects.bulk_create([
            BinCommand(bin=bin, action="calibrate", status="done", created_by=admin,
                    created_at=now - timedelta(days=2), completed_at=now - timedelta(days=2),
                    result={"organic_depth_cm": 40.0, "inorganic_depth_cm": 40.0}),
            BinCommand(bin=bin, action="open_lid", status="done", created_by=admin,
                    created_at=now - timedelta(hours=3), completed_at=now - timedelta(hours=3)),
        ])

        alerts.evaluate_reading(bin, bin.readings.first())
        alerts.evaluate_detections(bin)

        self.stdout.write(self.style.SUCCESS(
            f"Demo ready: {len(readings)} readings, {bin.detections.count()} detections, "
            f"{len(collections)} collections.\n"
            f"  Login (admin):   admin / admin12345\n"
            f"  Login (viewer):  cleaner / cleaner12345\n"
            f"  Device API key:  {DEMO_KEY}"
        ))
