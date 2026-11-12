"""Database tables of the Edge-AI Smart Dustbin.

One Bin = one physical dustbin with two compartments (organic + inorganic),
an ESP32-CAM (AI camera) and an ESP32 main controller (sensors + motors).
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

ORGANIC, INORGANIC = "organic", "inorganic"
COMPARTMENTS = [(ORGANIC, "Organic"), (INORGANIC, "Inorganic")]

# The 4 materials the AI recognises and the compartment each one goes to
MATERIALS = [("organic", "Organic (food, peels, leaves)"), ("paper", "Paper / cardboard"),
             ("plastic", "Plastic"), ("metal", "Metal")]
BIN_OF = {"organic": ORGANIC, "paper": ORGANIC, "plastic": INORGANIC, "metal": INORGANIC}
# what a reviewer can answer: a material, or "other" (glass, textile... the AI was not trained for it)
REVIEW_CHOICES = MATERIALS + [("other", "Other / not a known material")]

ONLINE_TIMEOUT = timedelta(seconds=90)


def new_api_key():
    return secrets.token_hex(20)


class Bin(models.Model):
    MODES = [
        ("auto", "Automatic"),        # detect -> classify -> sort by itself
        ("manual", "Manual"),         # only does what the dashboard commands
        ("maintenance", "Maintenance"),  # lid open, sorting disabled (cleaning)
    ]

    name = models.CharField(max_length=100)
    location = models.CharField(max_length=150, blank=True)
    api_key = models.CharField(max_length=64, unique=True, default=new_api_key)
    mode = models.CharField(max_length=12, choices=MODES, default="auto")

    # Calibration: distance from the ultrasonic sensor to the bottom of each empty compartment
    organic_depth_cm = models.FloatField(default=40.0)
    inorganic_depth_cm = models.FloatField(default=40.0)

    # Thresholds
    warning_level = models.FloatField(default=75.0, help_text="% -> 'Almost full'")
    full_level = models.FloatField(default=90.0, help_text="% -> 'Full'")
    gas_threshold_ppm = models.FloatField(default=400.0, help_text="MQ-135 reading -> 'Bad smell'")
    min_confidence = models.FloatField(
        default=0.70, help_text="Below this the item goes to INORGANIC and is flagged 'uncertain'"
    )

    # Reported by the devices
    firmware_main = models.CharField(max_length=20, blank=True)
    firmware_cam = models.CharField(max_length=20, blank=True)
    model_version = models.CharField(max_length=40, blank=True)
    ip_main = models.GenericIPAddressField(null=True, blank=True)
    ip_cam = models.GenericIPAddressField(null=True, blank=True)
    wifi_rssi = models.IntegerField(null=True, blank=True)
    lid_open = models.BooleanField(default=False)
    booted_at = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)       # main controller
    cam_last_seen = models.DateTimeField(null=True, blank=True)   # ESP32-CAM

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name

    @property
    def is_online(self):
        return bool(self.last_seen and timezone.now() - self.last_seen < ONLINE_TIMEOUT)

    @property
    def cam_online(self):
        return bool(self.cam_last_seen and timezone.now() - self.cam_last_seen < timedelta(minutes=5))

    def depth(self, compartment):
        return self.organic_depth_cm if compartment == ORGANIC else self.inorganic_depth_cm

    def distance_to_level(self, compartment, distance_cm):
        """Ultrasonic distance (cm) -> fill level (%)."""
        if distance_cm is None:
            return None
        depth = self.depth(compartment)
        level = (depth - distance_cm) / depth * 100
        return round(max(0.0, min(100.0, level)), 1)


class SensorReading(models.Model):
    """Telemetry sent by the main controller every ~30 s."""

    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name="readings")
    organic_level = models.FloatField(null=True)
    inorganic_level = models.FloatField(null=True)
    organic_distance_cm = models.FloatField(null=True, blank=True)
    inorganic_distance_cm = models.FloatField(null=True, blank=True)
    gas_ppm = models.FloatField(null=True, blank=True)
    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class Detection(models.Model):
    """One item classified by the AI camera."""

    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name="detections")
    label = models.CharField(max_length=50, help_text="Raw class from the model")
    category = models.CharField(max_length=10, choices=COMPARTMENTS, help_text="What the AI thinks")
    confidence = models.FloatField()
    sorted_to = models.CharField(max_length=10, choices=COMPARTMENTS, help_text="Where it physically went")
    uncertain = models.BooleanField(default=False)
    image = models.ImageField(upload_to="detections/%Y/%m/%d/", null=True, blank=True)
    inference_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    # Human review ("teach the AI"): what the item really was. Used to measure real accuracy
    # in the bin and exported as new training photos.
    true_label = models.CharField(max_length=20, choices=REVIEW_CHOICES, blank=True, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="reviewed_detections")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_correct(self):
        """None = not reviewed yet."""
        return None if not self.true_label else self.true_label == self.label

    @property
    def right_compartment(self):
        """Did the item physically end up in the right compartment?"""
        if not self.true_label:
            return None
        return BIN_OF.get(self.true_label, INORGANIC) == self.sorted_to


class Command(models.Model):
    """Remote-control order from the dashboard to the bin (the device polls for these)."""

    ACTIONS = [
        ("open_lid", "Open lid"),
        ("close_lid", "Close lid"),
        ("sort_organic", "Tilt tray to organic"),
        ("sort_inorganic", "Tilt tray to inorganic"),
        ("capture", "Capture & classify"),
        ("calibrate", "Calibrate empty depth"),
        ("set_mode", "Set mode"),
        ("buzzer", "Test buzzer"),
        ("reboot", "Reboot"),
    ]
    STATUSES = [
        ("pending", "Pending"),
        ("sent", "Sent to device"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]
    EXPIRE_AFTER = timedelta(minutes=2)

    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name="commands")
    action = models.CharField(max_length=20, choices=ACTIONS)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default="pending")
    result = models.JSONField(default=dict, blank=True)
    message = models.CharField(max_length=200, blank=True)
    # set for messages written by the SERVER (translated by the dashboard); device messages keep only `message`
    message_code = models.CharField(max_length=40, blank=True)
    message_params = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Alert(models.Model):
    KINDS = [
        ("organic_full", "Organic compartment full"),
        ("organic_warning", "Organic compartment almost full"),
        ("inorganic_full", "Inorganic compartment full"),
        ("inorganic_warning", "Inorganic compartment almost full"),
        ("gas_high", "Bad smell / gas high"),
        ("device_offline", "Device offline"),
        ("low_confidence", "AI often uncertain"),
    ]
    SEVERITIES = [("info", "Info"), ("warning", "Warning"), ("critical", "Critical")]

    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name="alerts")
    kind = models.CharField(max_length=20, choices=KINDS)
    severity = models.CharField(max_length=10, choices=SEVERITIES)
    message = models.CharField(max_length=255, help_text="English fallback text")
    params = models.JSONField(default=dict, blank=True, help_text="Values the dashboard puts in the translated text")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Collection(models.Model):
    """A compartment was emptied by a worker."""

    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name="collections")
    compartment = models.CharField(max_length=10, choices=COMPARTMENTS)
    level_before = models.FloatField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]


# ------------------------------------------------------------------ email notifications

SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


class NotificationSettings(models.Model):
    """What each user wants to receive by email (their address is User.email)."""

    LEVELS = [
        ("info", "All alerts"),
        ("warning", "Warnings and critical (almost full, full, smell, offline)"),
        ("critical", "Critical only (full, offline)"),
    ]
    LANGUAGES = [("en", "English"), ("fr", "Français"), ("rw", "Kinyarwanda")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_settings")
    email_enabled = models.BooleanField(default=True)
    language = models.CharField(max_length=2, choices=LANGUAGES, default="en")
    min_severity = models.CharField(max_length=10, choices=LEVELS, default="warning")
    bins = models.ManyToManyField(Bin, blank=True, help_text="Leave empty to receive alerts for ALL bins")

    def __str__(self):
        return f"Notifications for {self.user}"

    def wants(self, alert):
        if not self.email_enabled or not self.user.email or not self.user.is_active:
            return False
        if SEVERITY_RANK[alert.severity] < SEVERITY_RANK[self.min_severity]:
            return False
        chosen = list(self.bins.values_list("id", flat=True)) if self.pk else []  # unsaved = defaults = all bins
        return not chosen or alert.bin_id in chosen


class EmailNotification(models.Model):
    """Outbox: every email is stored first, then sent by a background worker (with retries)."""

    STATUSES = [("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")]
    MAX_ATTEMPTS = 3

    alert = models.ForeignKey(Alert, null=True, blank=True, on_delete=models.SET_NULL, related_name="emails")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    to = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    html = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default="pending", db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.status}: {self.subject} -> {self.to}"
