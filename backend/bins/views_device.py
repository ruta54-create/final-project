"""API used by the hardware (ESP32 main controller + ESP32-CAM).

Every request carries the header  X-API-KEY: <bin api key>.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .auth import DeviceKeyAuthentication, IsDevice
from .models import INORGANIC, ORGANIC, Command, Detection, SensorReading
from .serializers import CommandAckIn, DetectionIn, TelemetryIn
from .services import alerts

MIN_DEPTH_CM = 10  # an empty compartment shallower than this = calibration done on a full bin
TELEMETRY_INTERVAL_S = 30
COMMAND_POLL_S = 2


def device_view(methods, parsers=(JSONParser,)):
    def wrap(fn):
        fn = parser_classes(list(parsers))(fn)
        fn = permission_classes([IsDevice])(fn)
        fn = authentication_classes([DeviceKeyAuthentication])(fn)
        return api_view(methods)(fn)
    return wrap


def config_payload(bin):
    return {
        "bin_id": bin.id,
        "name": bin.name,
        "mode": bin.mode,
        "min_confidence": bin.min_confidence,
        "organic_depth_cm": bin.organic_depth_cm,
        "inorganic_depth_cm": bin.inorganic_depth_cm,
        "telemetry_interval_s": TELEMETRY_INTERVAL_S,
        "command_poll_s": COMMAND_POLL_S,
        "server_time": timezone.now(),
    }


@device_view(["GET"])
def device_config(request):
    """Both boards call this at boot (and the CAM every few minutes as a heartbeat)."""
    bin = request.auth
    if request.query_params.get("role") == "cam":
        bin.cam_last_seen = timezone.now()
        bin.save(update_fields=["cam_last_seen"])
    else:
        bin.last_seen = timezone.now()
        bin.save(update_fields=["last_seen"])
    return Response(config_payload(bin))


@device_view(["POST"])
def telemetry(request):
    s = TelemetryIn(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    bin = request.auth
    now = timezone.now()

    reading = SensorReading.objects.create(
        bin=bin,
        organic_distance_cm=d.get("organic_distance_cm"),
        inorganic_distance_cm=d.get("inorganic_distance_cm"),
        organic_level=bin.distance_to_level(ORGANIC, d.get("organic_distance_cm")),
        inorganic_level=bin.distance_to_level(INORGANIC, d.get("inorganic_distance_cm")),
        gas_ppm=d.get("gas_ppm"),
        temperature=d.get("temperature"),
        humidity=d.get("humidity"),
    )

    bin.last_seen = now
    if "lid_open" in d:
        bin.lid_open = d["lid_open"]
    if "firmware" in d:
        bin.firmware_main = d["firmware"]
    if "wifi_rssi" in d:
        bin.wifi_rssi = d["wifi_rssi"]
    bin.ip_main = d.get("ip") or request.META.get("REMOTE_ADDR")
    if d.get("booted") or bin.booted_at is None:
        bin.booted_at = now
    # Save ONLY the fields the device reports. A full save() would write back the
    # mode/settings loaded at the start of this request and undo a change an admin
    # made from the dashboard at the same moment.
    bin.save(update_fields=["last_seen", "lid_open", "firmware_main", "wifi_rssi", "ip_main", "booted_at"])
    bin.refresh_from_db(fields=["mode", "min_confidence", "organic_depth_cm", "inorganic_depth_cm"])

    alerts.evaluate_reading(bin, reading)
    return Response(
        {
            "organic_level": reading.organic_level,
            "inorganic_level": reading.inorganic_level,
            **config_payload(bin),
        },
        status=status.HTTP_201_CREATED,
    )


@device_view(["POST"], parsers=(MultiPartParser, FormParser, JSONParser))
def detection(request):
    """ESP32-CAM reports one classified item (+ the JPEG photo)."""
    s = DetectionIn(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    bin = request.auth

    uncertain = d["confidence"] < bin.min_confidence
    # Safety rule: when the AI is not sure, the item goes to INORGANIC so it never contaminates compost.
    sorted_to = d.get("sorted_to") or (INORGANIC if uncertain else d["category"])

    det = Detection.objects.create(
        bin=bin,
        label=d["label"].lower(),
        category=d["category"],
        confidence=d["confidence"],
        sorted_to=sorted_to,
        uncertain=uncertain,
        image=d.get("image"),
        inference_ms=d.get("inference_ms"),
    )

    bin.cam_last_seen = timezone.now()
    if "firmware" in d:
        bin.firmware_cam = d["firmware"]
    if "model_version" in d:
        bin.model_version = d["model_version"]
    bin.ip_cam = d.get("ip") or request.META.get("REMOTE_ADDR")
    bin.save(update_fields=["cam_last_seen", "firmware_cam", "model_version", "ip_cam"])

    alerts.evaluate_detections(bin)
    return Response(
        {"id": det.id, "sorted_to": sorted_to, "uncertain": uncertain, "mode": bin.mode},
        status=status.HTTP_201_CREATED,
    )


@device_view(["GET"])
def pending_commands(request):
    """Main controller polls this every ~2 s. Commands are handed out once."""
    bin = request.auth
    now = timezone.now()
    bin.last_seen = now
    bin.save(update_fields=["last_seen"])

    with transaction.atomic():
        bin.commands.filter(status__in=["pending", "sent"], created_at__lt=now - Command.EXPIRE_AFTER).update(
            status="expired", completed_at=now, message="Device did not answer in time", message_code="expired"
        )
        cmds = list(bin.commands.filter(status="pending").order_by("created_at"))
        bin.commands.filter(id__in=[c.id for c in cmds]).update(status="sent", sent_at=now)

    return Response({
        "mode": bin.mode,
        "commands": [{"id": c.id, "action": c.action, "payload": c.payload} for c in cmds],
    })


@device_view(["POST"])
def ack_command(request, pk):
    bin = request.auth
    try:
        cmd = bin.commands.get(pk=pk)
    except Command.DoesNotExist:
        return Response({"detail": "Unknown command"}, status=404)

    s = CommandAckIn(data=request.data)
    s.is_valid(raise_exception=True)
    d = s.validated_data
    cmd.status = d["status"]
    cmd.message = d.get("message", "")
    cmd.result = d.get("result") or {}

    if cmd.action == "calibrate" and cmd.status == "done":
        # Protect against calibrating a bin that is not empty (it would break every fill level)
        for field in ("organic_depth_cm", "inorganic_depth_cm"):
            value = cmd.result.get(field)
            if not isinstance(value, (int, float)) or value < MIN_DEPTH_CM:
                cmd.status = "failed"
                cmd.message = (f"Rejected: {field.split('_')[0]} depth {value} cm is too small. "
                               "Empty BOTH compartments, then calibrate again.")
                cmd.message_code = "depth_too_small"
                cmd.message_params = {"compartment": field.split("_")[0], "value": value}
                break
    cmd.completed_at = timezone.now()
    cmd.save()

    if cmd.status == "done":
        changed = []  # save only what this command changed (see telemetry() for why)
        if cmd.action == "calibrate":
            for field in ("organic_depth_cm", "inorganic_depth_cm"):
                value = cmd.result.get(field)
                if isinstance(value, (int, float)) and value >= MIN_DEPTH_CM:
                    setattr(bin, field, round(float(value), 1))
                    changed.append(field)
        elif cmd.action in ("open_lid", "close_lid"):
            bin.lid_open = cmd.action == "open_lid"
            changed.append("lid_open")
        if changed:
            bin.save(update_fields=changed)
    return Response({"ok": True})
