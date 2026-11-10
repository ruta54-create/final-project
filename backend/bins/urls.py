from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views_auth, views_dashboard, views_device, views_notifications

router = DefaultRouter()
router.register("bins", views_dashboard.BinViewSet, basename="bin")
router.register("detections", views_dashboard.DetectionViewSet, basename="detection")
router.register("alerts", views_dashboard.AlertViewSet, basename="alert")

urlpatterns = [
    # login / session
    path("auth/csrf/", views_auth.csrf),
    path("auth/login/", views_auth.login_view),
    path("auth/logout/", views_auth.logout_view),
    path("auth/me/", views_auth.me),
    path("auth/change-password/", views_auth.change_password),
    # email alerts
    path("notifications/settings/", views_notifications.notification_settings),
    path("notifications/test/", views_notifications.test_email),
    path("notifications/log/", views_notifications.email_log),
    # hardware (X-API-KEY)
    path("device/config/", views_device.device_config),
    path("device/telemetry/", views_device.telemetry),
    path("device/detection/", views_device.detection),
    path("device/commands/", views_device.pending_commands),
    path("device/commands/<int:pk>/ack/", views_device.ack_command),
] + router.urls
