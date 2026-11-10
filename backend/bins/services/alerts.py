"""Creates and auto-resolves alerts. There is at most ONE active alert per (bin, kind).

`message` is an English fallback; `kind` + `params` are what the dashboard translates
(English / French / Kinyarwanda), so the server stays language-neutral.
"""

import logging

from django.utils import timezone

from ..models import INORGANIC, ORGANIC, Alert


def set_alert(bin, kind, active, severity="warning", message="", params=None):
    params = params or {}
    current = bin.alerts.filter(kind=kind, is_active=True).first()
    if active and not current:
        alert = Alert.objects.create(bin=bin, kind=kind, severity=severity, message=message, params=params)
        try:
            from .notifications import queue_alert_emails
            queue_alert_emails(alert)  # emails users who asked for this kind of alert
        except Exception:  # an email problem must never stop the bin's data from being saved
            logging.getLogger(__name__).exception("Could not queue alert emails")
        return alert
    if active and current and (current.message != message or current.severity != severity or current.params != params):
        current.message, current.severity, current.params = message, severity, params
        current.save(update_fields=["message", "severity", "params"])
    if not active and current:
        current.is_active = False
        current.resolved_at = timezone.now()
        current.save(update_fields=["is_active", "resolved_at"])
    return current


def evaluate_reading(bin, reading):
    for comp in (ORGANIC, INORGANIC):
        level = getattr(reading, f"{comp}_level")
        if level is None:
            continue
        name = comp.capitalize()
        full = level >= bin.full_level
        warn = not full and level >= bin.warning_level
        params = {"compartment": comp, "level": round(level)}
        set_alert(bin, f"{comp}_full", full, "critical",
                  f"{name} compartment is full ({level:.0f}%). Empty it now.", params)
        set_alert(bin, f"{comp}_warning", warn, "warning",
                  f"{name} compartment is almost full ({level:.0f}%).", params)

    if reading.gas_ppm is not None:
        set_alert(
            bin, "gas_high", reading.gas_ppm >= bin.gas_threshold_ppm, "warning",
            f"Gas level high ({reading.gas_ppm:.0f} ppm): organic waste is decomposing.",
            {"gas": round(reading.gas_ppm)},
        )


def evaluate_detections(bin):
    last = list(bin.detections.values_list("uncertain", flat=True)[:20])
    if len(last) < 10:
        return
    ratio = sum(last) / len(last)
    set_alert(
        bin, "low_confidence", ratio >= 0.3, "info",
        f"The AI was uncertain on {ratio:.0%} of the last {len(last)} items.",
        {"ratio": round(ratio, 2), "count": len(last)},
    )


def evaluate_offline(bin):
    if bin.last_seen is None:
        return
    set_alert(bin, "device_offline", not bin.is_online, "critical",
              f"Main controller has not reported since {timezone.localtime(bin.last_seen):%d %b %H:%M}.",
              {"since": bin.last_seen.isoformat()})
