"""Email notification preferences, test email and email log (for logged-in users)."""

from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Bin, EmailNotification, NotificationSettings
from .services.notifications import delivery_mode, send_test_email


def payload(user, prefs):
    return {
        "email": user.email,
        "email_enabled": prefs.email_enabled,
        "language": prefs.language,
        "min_severity": prefs.min_severity,
        "bins": list(prefs.bins.values_list("id", flat=True)),
        "delivery": delivery_mode(),  # "smtp" = real emails, "file" = saved in backend/sent_emails
    }


@api_view(["GET", "PATCH"])
def notification_settings(request):
    user = request.user
    prefs, _ = NotificationSettings.objects.get_or_create(user=user)
    if request.method == "PATCH":
        d = request.data
        errors = {}
        if "email" in d:
            email = (d.get("email") or "").strip()
            try:
                if email:
                    validate_email(email)
                user.email = email
            except ValidationError:
                errors["email"] = "invalid_email"
        if "email_enabled" in d:
            prefs.email_enabled = bool(d["email_enabled"])
        if "language" in d:
            if d["language"] in dict(NotificationSettings.LANGUAGES):
                prefs.language = d["language"]
            else:
                errors["language"] = "invalid_language"
        if "min_severity" in d:
            if d["min_severity"] in dict(NotificationSettings.LEVELS):
                prefs.min_severity = d["min_severity"]
            else:
                errors["min_severity"] = "invalid_severity"
        bins = None
        if "bins" in d:
            ids = [int(i) for i in (d.get("bins") or []) if str(i).isdigit()]
            bins = list(Bin.objects.filter(id__in=ids))
        if errors:
            code = next(iter(errors.values()))
            return Response({"detail": "Invalid notification settings.", "code": code, "fields": errors}, status=400)
        if prefs.email_enabled and not user.email:
            return Response({"detail": "Enter an email address to receive alerts.", "code": "email_required"}, status=400)
        user.save(update_fields=["email"])
        prefs.save()
        if bins is not None:
            prefs.bins.set(bins)
    return Response(payload(user, prefs))


@api_view(["POST"])
def test_email(request):
    if not request.user.email:
        return Response({"detail": "Enter and save your email address first.", "code": "email_required"}, status=400)
    n = send_test_email(request.user)
    return Response({"status": n.status, "error": n.error, "to": n.to, "delivery": delivery_mode()},
                    status=200 if n.status == "sent" else 502)


@api_view(["GET"])
def email_log(request):
    qs = EmailNotification.objects.select_related("alert", "alert__bin")
    if not request.user.is_staff:
        qs = qs.filter(user=request.user)
    rows = qs[: min(int(request.query_params.get("limit", 20) or 20), 100)]
    return Response([
        {
            "id": n.id, "to": n.to, "subject": n.subject, "status": n.status, "attempts": n.attempts,
            "error": n.error, "created_at": n.created_at, "sent_at": n.sent_at,
            "alert_kind": n.alert.kind if n.alert else "test",
            "bin": n.alert.bin.name if n.alert else None,
        }
        for n in rows
    ])
