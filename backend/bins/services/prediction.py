"""Fill-level analytics and time-to-full prediction (the 'predictive' ML part).

Method
------
1. Take this compartment's readings since it was last emptied (max 48 h).
2. Fit a least-squares line  level% = rate * hours + b   -> rate in %/hour.
3. If there is not enough recent data, fall back to the average filling rate
   learned from the last 7 days of history.
4. hours_to_full = (full_level - current_level) / rate
"""

from datetime import timedelta

from django.utils import timezone

from ..models import ORGANIC

DROP = 25.0          # a fall of more than this many % between readings = bin was emptied
MIN_RATE = 0.05      # %/hour; slower than this we say "not filling"


def level_field(compartment):
    return "organic_level" if compartment == ORGANIC else "inorganic_level"


def compartment_status(level, bin):
    # `code` is translated by the dashboard; `label` is the English fallback
    if level is None:
        return {"code": "no_data", "label": "No data", "tone": "muted"}
    if level >= bin.full_level:
        return {"code": "full", "label": "Full", "tone": "danger"}
    if level >= bin.warning_level:
        return {"code": "almost_full", "label": "Almost full", "tone": "warning"}
    return {"code": "normal", "label": "Normal", "tone": "success"}


def linear_rate(points):
    """points = [(datetime, level)] sorted by time -> slope in %/hour (or None)."""
    if len(points) < 3:
        return None
    t0 = points[0][0]
    xs = [(t - t0).total_seconds() / 3600 for t, _ in points]
    if xs[-1] < 0.5:  # need at least 30 minutes of data
        return None
    ys = [v for _, v in points]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def since_last_empty(points):
    start = 0
    for i in range(1, len(points)):
        if points[i][1] < points[i - 1][1] - DROP:
            start = i
    return points[start:]


def historical_rate(bin, compartment, now):
    """Average %/hour while filling over the last 7 days (ignores emptying drops)."""
    field = level_field(compartment)
    rows = list(
        bin.readings.filter(created_at__gte=now - timedelta(days=7), **{f"{field}__isnull": False})
        .order_by("created_at")
        .values_list("created_at", field)
    )
    rise, hours = 0.0, 0.0
    for (t1, v1), (t2, v2) in zip(rows, rows[1:]):
        if v2 >= v1 - DROP:  # skip emptying events
            rise += max(0.0, v2 - v1)
            hours += (t2 - t1).total_seconds() / 3600
    return rise / hours if hours >= 1 else None


def predict(bin, compartment, now=None):
    now = now or timezone.now()
    field = level_field(compartment)

    since = now - timedelta(hours=48)
    last_collection = bin.collections.filter(compartment=compartment).first()
    if last_collection and last_collection.created_at > since:
        since = last_collection.created_at

    points = list(
        bin.readings.filter(created_at__gte=since, **{f"{field}__isnull": False})
        .order_by("created_at")
        .values_list("created_at", field)
    )
    latest = bin.readings.filter(**{f"{field}__isnull": False}).first()
    level = getattr(latest, field) if latest else None

    rate, method = linear_rate(since_last_empty(points)), "trend"
    if rate is None:
        rate, method = historical_rate(bin, compartment, now), "history"

    result = {
        "level": level,
        "status": compartment_status(level, bin),
        "rate_per_hour": round(rate, 2) if rate is not None else None,
        "hours_to_full": None,
        "full_at": None,
        "method": method if rate is not None else None,
    }
    if level is None:
        return result
    if level >= bin.full_level:
        result["hours_to_full"], result["full_at"] = 0, now
    elif rate is not None and rate > MIN_RATE:
        hours = (bin.full_level - level) / rate
        result["hours_to_full"] = round(hours, 1)
        result["full_at"] = now + timedelta(hours=hours)
    return result
