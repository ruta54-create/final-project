from django.contrib import admin

from .models import Alert, Bin, Collection, Command, Detection, EmailNotification, NotificationSettings, SensorReading


@admin.register(Bin)
class BinAdmin(admin.ModelAdmin):
    list_display = ["name", "location", "mode", "last_seen", "cam_last_seen"]
    readonly_fields = ["api_key"]


@admin.register(Detection)
class DetectionAdmin(admin.ModelAdmin):
    list_display = ["created_at", "bin", "label", "category", "confidence", "sorted_to", "uncertain"]
    list_filter = ["bin", "category", "uncertain"]


@admin.register(SensorReading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ["created_at", "bin", "organic_level", "inorganic_level", "gas_ppm", "temperature"]
    list_filter = ["bin"]


@admin.register(Command)
class CommandAdmin(admin.ModelAdmin):
    list_display = ["created_at", "bin", "action", "status", "created_by"]
    list_filter = ["bin", "status", "action"]


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["created_at", "bin", "kind", "severity", "is_active"]
    list_filter = ["bin", "is_active", "severity"]


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["created_at", "bin", "compartment", "level_before", "created_by"]




@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ["user", "email_enabled", "language", "min_severity"]
    filter_horizontal = ["bins"]


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ["created_at", "to", "subject", "status", "attempts"]
    list_filter = ["status"]
    readonly_fields = ["alert", "user", "to", "subject", "body", "status", "attempts", "error", "created_at", "sent_at"]
    exclude = ["html"]
