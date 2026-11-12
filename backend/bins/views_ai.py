"""'Test the AI' without hardware: the dashboard sends a photo (upload or webcam), the AI service
(ml/serve_model.py, same int8 model as the ESP32) classifies it, and the bin's rules decide the compartment.
Optionally the result is saved as a detection, exactly as if the bin's camera had taken the photo.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from .models import BIN_OF, INORGANIC, Bin, Detection
from .serializers import DetectionSerializer
from .services import alerts

TIMEOUT = 20


def ai_service(path, data=None):
    req = urllib.request.Request(settings.AI_SERVICE_URL.rstrip("/") + path, data=data,
                                 headers={"Content-Type": "application/octet-stream"} if data else {},
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


OFFLINE = {"detail": "The AI model service is not running. Start it with RUN_DEMO.bat "
                     "(or: ml\\.venv\\Scripts\\python ml\\serve_model.py).", "code": "ai_offline"}


@api_view(["GET"])
def ai_status(request):
    try:
        return Response({"online": True, **ai_service("/health")})
    except (urllib.error.URLError, OSError, ValueError):
        return Response({"online": False, **OFFLINE})


@api_view(["POST"])
@parser_classes([MultiPartParser])
def ai_classify(request):
    image = request.data.get("image")
    if not isinstance(image, UploadedFile):
        return Response({"detail": "Choose a photo first.", "code": "no_image"}, status=400)
    if image.size > 8 * 1024 * 1024:
        return Response({"detail": "The photo is larger than 8 MB.", "code": "too_big"}, status=400)
    bin = get_object_or_404(Bin, pk=request.data.get("bin")) if request.data.get("bin") else Bin.objects.first()
    if bin is None:
        return Response({"detail": "Register a bin first.", "code": "no_bin"}, status=400)

    data = image.read()
    try:
        result = ai_service("/classify", data)
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("detail", "")
        except ValueError:
            detail = ""
        return Response({"detail": detail or "The AI could not read this image.", "code": "bad_image"}, status=400)
    except (urllib.error.URLError, OSError):
        return Response(OFFLINE, status=503)

    # the bin's rules, identical to the ESP32-CAM firmware and the device API
    label, conf = result["label"], result["confidence"]
    category = BIN_OF.get(label, INORGANIC)
    uncertain = conf < bin.min_confidence
    sorted_to = INORGANIC if uncertain else category
    payload = {**result, "category": category, "sorted_to": sorted_to, "uncertain": uncertain,
               "min_confidence": bin.min_confidence, "bin": bin.id, "saved": None}

    if str(request.data.get("save", "")).lower() in ("1", "true"):
        image.seek(0)
        det = Detection.objects.create(
            bin=bin, label=label, category=category, confidence=conf, sorted_to=sorted_to,
            uncertain=uncertain, image=image, inference_ms=round(result["inference_ms"]))
        alerts.evaluate_detections(bin)
        payload["saved"] = DetectionSerializer(det, context={"request": request}).data
    return Response(payload)
