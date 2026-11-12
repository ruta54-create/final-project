from rest_framework import serializers

from .models import COMPARTMENTS, Alert, Bin, Collection, Command, Detection, SensorReading

CATEGORY_CHOICES = [c[0] for c in COMPARTMENTS]


class BinSerializer(serializers.ModelSerializer):
    is_online = serializers.BooleanField(read_only=True)
    cam_online = serializers.BooleanField(read_only=True)

    class Meta:
        model = Bin
        fields = [
            "id", "name", "location", "mode", "api_key",
            "organic_depth_cm", "inorganic_depth_cm", "warning_level", "full_level",
            "gas_threshold_ppm", "min_confidence",
            "firmware_main", "firmware_cam", "model_version", "ip_main", "ip_cam", "wifi_rssi",
            "lid_open", "booted_at", "last_seen", "cam_last_seen", "is_online", "cam_online", "created_at",
        ]
        read_only_fields = [
            "api_key", "firmware_main", "firmware_cam", "model_version", "ip_main", "ip_cam",
            "wifi_rssi", "lid_open", "booted_at", "last_seen", "cam_last_seen", "created_at",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if not (request and request.user and request.user.is_staff):
            data["api_key"] = None  # only admins may see the device secret
        return data

    def validate(self, data):
        warn = data.get("warning_level", getattr(self.instance, "warning_level", 75))
        full = data.get("full_level", getattr(self.instance, "full_level", 90))
        if not 0 < warn < full <= 100:
            raise serializers.ValidationError("Need 0 < warning level < full level <= 100.")
        conf = data.get("min_confidence")
        if conf is not None and not 0 <= conf <= 1:
            raise serializers.ValidationError("min_confidence must be between 0 and 1.")
        for f in ("organic_depth_cm", "inorganic_depth_cm"):
            if f in data and data[f] < 10:
                raise serializers.ValidationError(f"{f} must be at least 10 cm (depth of the EMPTY compartment).")
        return data


class ReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorReading
        fields = ["id", "organic_level", "inorganic_level", "organic_distance_cm", "inorganic_distance_cm",
                  "gas_ppm", "temperature", "humidity", "created_at"]


class DetectionSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    bin_name = serializers.CharField(source="bin.name", read_only=True)

    class Meta:
        model = Detection
        fields = ["id", "bin", "bin_name", "label", "category", "confidence", "sorted_to", "uncertain",
                  "image_url", "inference_ms", "created_at",
                  "true_label", "reviewed_by", "reviewed_at", "is_correct", "right_compartment"]

    reviewed_by = serializers.CharField(source="reviewed_by.username", read_only=True, default=None)
    is_correct = serializers.BooleanField(read_only=True, allow_null=True)
    right_compartment = serializers.BooleanField(read_only=True, allow_null=True)

    def get_image_url(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class CommandSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True, default=None)
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = Command
        fields = ["id", "action", "action_label", "payload", "status", "result", "message",
                  "message_code", "message_params", "created_by", "created_at", "sent_at", "completed_at"]
        read_only_fields = ["status", "result", "message", "message_code", "message_params",
                            "created_at", "sent_at", "completed_at"]

    def validate(self, data):
        if data["action"] == "set_mode":
            mode = (data.get("payload") or {}).get("mode")
            if mode not in dict(Bin.MODES):
                raise serializers.ValidationError({"payload": "set_mode needs payload {\"mode\": auto|manual|maintenance}"})
        return data


class AlertSerializer(serializers.ModelSerializer):
    bin_name = serializers.CharField(source="bin.name", read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = Alert
        fields = ["id", "bin", "bin_name", "kind", "kind_label", "severity", "message", "params", "is_active",
                  "created_at", "resolved_at"]


class CollectionSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True, default=None)

    class Meta:
        model = Collection
        fields = ["id", "compartment", "level_before", "note", "created_by", "created_at"]
        read_only_fields = ["level_before", "created_at"]


# ------------------------------------------------------------ device payloads

class TelemetryIn(serializers.Serializer):
    organic_distance_cm = serializers.FloatField(required=False, allow_null=True, min_value=0)
    inorganic_distance_cm = serializers.FloatField(required=False, allow_null=True, min_value=0)
    gas_ppm = serializers.FloatField(required=False, allow_null=True, min_value=0)
    temperature = serializers.FloatField(required=False, allow_null=True)
    humidity = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=100)
    lid_open = serializers.BooleanField(required=False)
    firmware = serializers.CharField(required=False, max_length=20)
    wifi_rssi = serializers.IntegerField(required=False)
    ip = serializers.IPAddressField(required=False)
    booted = serializers.BooleanField(required=False, default=False)


class DetectionIn(serializers.Serializer):
    label = serializers.CharField(max_length=50)
    category = serializers.ChoiceField(choices=CATEGORY_CHOICES)
    confidence = serializers.FloatField(min_value=0, max_value=1)
    sorted_to = serializers.ChoiceField(choices=CATEGORY_CHOICES, required=False)
    image = serializers.ImageField(required=False)
    inference_ms = serializers.IntegerField(required=False, min_value=0)
    firmware = serializers.CharField(required=False, max_length=20)
    model_version = serializers.CharField(required=False, max_length=40)
    ip = serializers.IPAddressField(required=False)


class CommandAckIn(serializers.Serializer):
    status = serializers.ChoiceField(choices=["done", "failed"])
    message = serializers.CharField(required=False, allow_blank=True, max_length=200)
    result = serializers.JSONField(required=False)
