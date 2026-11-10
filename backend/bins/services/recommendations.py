"""Rule-based recommendation engine: turns sensor data + predictions into actions.

Each recommendation:
    {code, params, priority (1 = most urgent), tone, title, detail, action}

`code` + `params` are language-neutral: the dashboard translates them into English,
French or Kinyarwanda. `title` / `detail` are an English fallback for other API users.
`action` is None, {"type": "collect", "compartment": ...} or {"type": "command", ...}.
"""

from datetime import timedelta

from django.utils import timezone

from ..models import INORGANIC, ORGANIC


def _fmt_time(dt):
    local = timezone.localtime(dt)
    today = timezone.localtime().date()
    day = "today" if local.date() == today else "tomorrow" if local.date() == today + timedelta(days=1) else local.strftime("%a %d %b")
    return f"{day} at {local:%H:%M}"


def _rec(code, priority, tone, title, detail, action=None, **params):
    return {"code": code, "params": params, "priority": priority, "tone": tone,
            "title": title, "detail": detail, "action": action}


def build(bin, predictions, latest, now=None):
    now = now or timezone.now()
    recs = []

    if bin.last_seen and not bin.is_online:
        recs.append(_rec("offline", 1, "danger", "Bin is offline",
                         "No data from the main controller. Check the power supply and Wi-Fi."))

    for comp in (ORGANIC, INORGANIC):
        p = predictions[comp]
        name = comp.capitalize()
        if p["level"] is None:
            continue
        collect = {"type": "collect", "compartment": comp}
        if p["status"]["tone"] == "danger":
            recs.append(_rec(
                "empty_now", 1, "danger", f"Empty the {comp} compartment now",
                f"It is {p['level']:.0f}% full. New {comp} waste may overflow or be mis-sorted.",
                collect, compartment=comp, level=round(p["level"])))
        elif p["hours_to_full"] is not None and p["hours_to_full"] <= 12:
            recs.append(_rec(
                "schedule", 2, "warning", f"Schedule {comp} collection",
                f"{name} will be full {_fmt_time(p['full_at'])} (filling {p['rate_per_hour']}%/h). Collect before then.",
                collect, compartment=comp, full_at=p["full_at"].isoformat(), rate=p["rate_per_hour"]))

    gas = latest.gas_ppm if latest else None
    if gas is not None and gas >= bin.gas_threshold_ppm:
        recs.append(_rec(
            "bad_smell", 2, "warning", "Bad smell detected",
            f"Gas is {gas:.0f} ppm. Organic waste is decomposing: empty the organic compartment "
            "within 24 h even if not full, and wash it.",
            {"type": "collect", "compartment": ORGANIC}, gas=round(gas)))
    if latest and latest.temperature is not None and latest.temperature >= 32:
        recs.append(_rec(
            "hot", 3, "warning", "High temperature",
            f"{latest.temperature:.0f} °C speeds up decomposition. Empty organic waste more often "
            "or move the bin to the shade.", temp=round(latest.temperature)))

    recent = list(bin.detections.values_list("uncertain", flat=True)[:20])
    if len(recent) >= 10 and sum(recent) / len(recent) >= 0.3:
        recs.append(_rec(
            "improve_ai", 3, "info", "Improve AI accuracy",
            "The camera is often unsure. Clean the lens, check the LED lighting, and add photos "
            "of the uncertain items to the Edge Impulse dataset, then retrain."))

    week = bin.detections.filter(created_at__gte=now - timedelta(days=7))
    total = week.count()
    if total >= 20:
        organic = week.filter(category=ORGANIC).count() / total
        if organic >= 0.6:
            recs.append(_rec(
                "mostly_organic", 4, "info", "Mostly organic waste",
                f"{organic:.0%} of this week's waste is organic: it can be composted. "
                "Consider a bigger organic compartment or more frequent collection.", share=round(organic, 2)))
        elif organic <= 0.3:
            recs.append(_rec(
                "mostly_inorganic", 4, "info", "Mostly inorganic waste",
                f"{1 - organic:.0%} of this week's waste is inorganic. Partner with a recycler "
                "for plastics and metals.", share=round(1 - organic, 2)))

    if bin.mode == "maintenance":
        recs.append(_rec(
            "maintenance_on", 3, "info", "Maintenance mode is on",
            "Sorting is disabled. Switch back to Automatic when cleaning is finished.",
            {"type": "command", "action": "set_mode", "payload": {"mode": "auto"}}))

    if not recs:
        recs.append(_rec("all_ok", 5, "success", "Everything is OK",
                         "Both compartments have space and the sensors are normal. No action needed."))
    return sorted(recs, key=lambda r: r["priority"])
