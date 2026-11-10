"""API used by the React dashboard (logged-in users, session cookie)."""

import csv
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Avg
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import COMPARTMENTS, INORGANIC, ORGANIC, Alert, Bin, Collection, Command, Detection
from .serializers import (
    AlertSerializer,
    BinSerializer,
    CollectionSerializer,
    CommandSerializer,
    DetectionSerializer,
    ReadingSerializer,
)
from .services import alerts, prediction, recommendations


class IsStaffOrReadOnly(permissions.BasePermission):
    """Everyone logged in can look; only staff (admins/operators) can change or control."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.method in permissions.SAFE_METHODS or request.user.is_staff


def int_param(request, name, default, lo, hi):
    try:
        return max(lo, min(hi, int(request.query_params.get(name, default))))
    except ValueError:
        return default


def downsample(rows, max_points):
    """Average consecutive readings into at most `max_points` buckets."""
    if len(rows) <= max_points:
        return rows
    size = -(-len(rows) // max_points)
    out = []
    for i in range(0, len(rows), size):
        chunk = rows[i:i + size]
        point = {"created_at": chunk[-1]["created_at"]}
        for key in ("organic_level", "inorganic_level", "gas_ppm", "temperature", "humidity"):
            vals = [r[key] for r in chunk if r[key] is not None]
            point[key] = round(sum(vals) / len(vals), 1) if vals else None
        out.append(point)
    return out


class BinViewSet(viewsets.ModelViewSet):
    queryset = Bin.objects.all()
    serializer_class = BinSerializer
    permission_classes = [IsStaffOrReadOnly]
    pagination_class = None

    # ------------------------------------------------------------ dashboard
    @action(detail=True)
    def overview(self, request, pk=None):
        bin = self.get_object()
        alerts.evaluate_offline(bin)
        now = timezone.now()
        latest = bin.readings.first()
        preds = {c: prediction.predict(bin, c, now) for c in (ORGANIC, INORGANIC)}

        start_of_day = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
        today = bin.detections.filter(created_at__gte=start_of_day)
        ctx = {"request": request}
        last = bin.detections.first()

        trend = list(
            bin.readings.filter(created_at__gte=now - timedelta(hours=24))
            .order_by("created_at")
            .values("created_at", "organic_level", "inorganic_level", "gas_ppm", "temperature", "humidity")
        )

        return Response({
            "bin": BinSerializer(bin, context=ctx).data,
            "latest": ReadingSerializer(latest).data if latest else None,
            "compartments": preds,
            "today": {
                "total": today.count(),
                "organic": today.filter(category=ORGANIC).count(),
                "inorganic": today.filter(category=INORGANIC).count(),
                "uncertain": today.filter(uncertain=True).count(),
                "avg_confidence": round(today.aggregate(a=Avg("confidence"))["a"] or 0, 3),
            },
            "last_detection": DetectionSerializer(last, context=ctx).data if last else None,
            "recent_detections": DetectionSerializer(bin.detections.all()[:6], many=True, context=ctx).data,
            "trend": downsample(trend, 96),
            "alerts": AlertSerializer(bin.alerts.filter(is_active=True), many=True).data,
            "recommendations": recommendations.build(bin, preds, latest, now),
            "uptime_seconds": int((now - bin.booted_at).total_seconds()) if bin.booted_at and bin.is_online else None,
            "server_time": now,
        })

    @action(detail=True)
    def readings(self, request, pk=None):
        bin = self.get_object()
        hours = int_param(request, "hours", 24, 1, 24 * 31)
        rows = list(
            bin.readings.filter(created_at__gte=timezone.now() - timedelta(hours=hours))
            .order_by("created_at")
            .values("created_at", "organic_level", "inorganic_level", "gas_ppm", "temperature", "humidity")
        )
        return Response({"hours": hours, "count": len(rows), "points": downsample(rows, 300)})

    @action(detail=True)
    def analytics(self, request, pk=None):
        bin = self.get_object()
        days = int_param(request, "days", 7, 1, 365)
        since = timezone.now() - timedelta(days=days)
        dets = list(bin.detections.filter(created_at__gte=since).values(
            "created_at", "category", "label", "confidence", "uncertain"))

        per_day = defaultdict(lambda: {ORGANIC: 0, INORGANIC: 0})
        per_hour = [{"hour": h, ORGANIC: 0, INORGANIC: 0} for h in range(24)]
        conf = defaultdict(list)
        for d in dets:
            local = timezone.localtime(d["created_at"])
            per_day[local.date().isoformat()][d["category"]] += 1
            per_hour[local.hour][d["category"]] += 1
            conf[d["category"]].append(d["confidence"])

        cols = list(bin.collections.filter(created_at__gte=since).order_by("created_at"))
        intervals = defaultdict(list)
        prev = {}
        for c in cols:
            if c.compartment in prev:
                intervals[c.compartment].append((c.created_at - prev[c.compartment]).total_seconds() / 3600)
            prev[c.compartment] = c.created_at

        total = len(dets)
        organic = sum(1 for d in dets if d["category"] == ORGANIC)
        return Response({
            "days": days,
            "total": total,
            "organic": organic,
            "inorganic": total - organic,
            "uncertain": sum(1 for d in dets if d["uncertain"]),
            "avg_confidence": round(sum(d["confidence"] for d in dets) / total, 3) if total else None,
            "confidence_by_category": {k: round(sum(v) / len(v), 3) for k, v in conf.items()},
            "per_day": [{"day": k, **v} for k, v in sorted(per_day.items())],
            "per_hour": per_hour,
            "top_labels": [{"label": k, "count": n} for k, n in Counter(d["label"] for d in dets).most_common(8)],
            "collections": {
                comp: {
                    "count": sum(1 for c in cols if c.compartment == comp),
                    "avg_hours_between": round(sum(intervals[comp]) / len(intervals[comp]), 1) if intervals[comp] else None,
                }
                for comp, _ in COMPARTMENTS
            },
        })

    # ------------------------------------------------------------ control
    @action(detail=True, methods=["get", "post"])
    def commands(self, request, pk=None):
        bin = self.get_object()
        if request.method == "GET":
            return Response(CommandSerializer(bin.commands.all()[:30], many=True).data)
        s = CommandSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        cmd = s.save(bin=bin, created_by=request.user)
        if cmd.action == "set_mode":  # the server is the source of truth for the mode
            bin.mode = cmd.payload["mode"]
            bin.save(update_fields=["mode"])
        return Response(CommandSerializer(cmd).data, status=201)

    @action(detail=True, methods=["get", "post"], permission_classes=[permissions.IsAuthenticated])
    def collections(self, request, pk=None):
        """Any logged-in user (e.g. a cleaner) can record that a compartment was emptied."""
        bin = self.get_object()
        if request.method == "GET":
            return Response(CollectionSerializer(bin.collections.all()[:50], many=True).data)
        s = CollectionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        comp = s.validated_data["compartment"]
        latest = bin.readings.exclude(**{f"{comp}_level": None}).first()
        col = s.save(bin=bin, created_by=request.user,
                     level_before=getattr(latest, f"{comp}_level") if latest else None)
        bin.alerts.filter(kind__in=[f"{comp}_full", f"{comp}_warning"], is_active=True).update(
            is_active=False, resolved_at=timezone.now())
        if comp == ORGANIC:
            bin.alerts.filter(kind="gas_high", is_active=True).update(is_active=False, resolved_at=timezone.now())
        return Response(CollectionSerializer(col).data, status=201)

    @action(detail=True, methods=["post"], url_path="regenerate-key")
    def regenerate_key(self, request, pk=None):
        from .models import new_api_key
        bin = self.get_object()
        bin.api_key = new_api_key()
        bin.save(update_fields=["api_key"])
        return Response({"api_key": bin.api_key})

    @action(detail=True, url_path="export")
    def export(self, request, pk=None):
        bin = self.get_object()
        kind = request.query_params.get("type", "detections")
        days = int_param(request, "days", 30, 1, 365)
        since = timezone.now() - timedelta(days=days)
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="bin{bin.id}_{kind}_{days}d.csv"'
        w = csv.writer(resp)
        if kind == "readings":
            w.writerow(["time", "organic_level", "inorganic_level", "gas_ppm", "temperature", "humidity"])
            for r in bin.readings.filter(created_at__gte=since).order_by("created_at"):
                w.writerow([timezone.localtime(r.created_at).isoformat(), r.organic_level, r.inorganic_level,
                            r.gas_ppm, r.temperature, r.humidity])
        elif kind == "collections":
            w.writerow(["time", "compartment", "level_before", "by", "note"])
            for c in bin.collections.filter(created_at__gte=since).order_by("created_at"):
                w.writerow([timezone.localtime(c.created_at).isoformat(), c.compartment, c.level_before,
                            c.created_by.username if c.created_by else "", c.note])
        else:
            w.writerow(["time", "label", "category", "confidence", "sorted_to", "uncertain"])
            for d in bin.detections.filter(created_at__gte=since).order_by("created_at"):
                w.writerow([timezone.localtime(d.created_at).isoformat(), d.label, d.category,
                            d.confidence, d.sorted_to, d.uncertain])
        return resp


class DetectionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DetectionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Detection.objects.select_related("bin")
        p = self.request.query_params
        if p.get("bin"):
            qs = qs.filter(bin_id=p["bin"])
        if p.get("category") in (ORGANIC, INORGANIC):
            qs = qs.filter(category=p["category"])
        if p.get("uncertain") in ("1", "true"):
            qs = qs.filter(uncertain=True)
        if p.get("days"):
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=int_param(self.request, "days", 7, 1, 365)))
        return qs


class AlertViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Alert.objects.select_related("bin")
        p = self.request.query_params
        if p.get("bin"):
            qs = qs.filter(bin_id=p["bin"])
        if p.get("active") in ("1", "true"):
            qs = qs.filter(is_active=True)
        elif p.get("active") in ("0", "false"):
            qs = qs.filter(is_active=False)
        return qs

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        alert = self.get_object()
        alert.is_active = False
        alert.resolved_at = timezone.now()
        alert.save(update_fields=["is_active", "resolved_at"])
        return Response(AlertSerializer(alert).data)
