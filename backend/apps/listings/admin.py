from django.contrib import admin
from django.utils.html import format_html
from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    SolarSchedule,
)

from apps.listings.models import BotSettings, Listing, ListingPhoto
from core.unfold_admin.admin import UnfoldModelAdmin, UnfoldTabularInline
from core.unfold_admin.filters import AllValuesFieldListDropdownFilter
from core.unfold_singleton.admin import UnfoldSingletonModelAdmin

# Скрываем раздел «Периодические задачи» celery-beat из админки.
for _model in (
    PeriodicTask,
    IntervalSchedule,
    CrontabSchedule,
    SolarSchedule,
    ClockedSchedule,
):
    try:
        admin.site.unregister(_model)
    except admin.sites.NotRegistered:
        pass


@admin.register(BotSettings)
class BotSettingsAdmin(UnfoldSingletonModelAdmin):
    fieldsets = (
        (None, {
            "fields": ("support_url", "support_button_label"),
        }),
    )


class ListingPhotoInline(UnfoldTabularInline):
    model = ListingPhoto
    extra = 0
    fields = ("index", "source_url", "original", "processed", "downloaded_at")
    readonly_fields = ("index", "source_url", "original", "processed", "downloaded_at")
    can_delete = False


@admin.register(Listing)
class ListingAdmin(UnfoldModelAdmin):
    list_display = (
        "id",
        "title",
        "source",
        "status",
        "user",
        "price",
        "currency",
        "presentation_link",
        "created_at",
    )
    list_display_links = ("id", "title")
    list_filter = (
        ("source", AllValuesFieldListDropdownFilter),
        ("status", AllValuesFieldListDropdownFilter),
    )
    search_fields = ("title", "address", "source_url", "broker_name", "broker_phone")
    readonly_fields = (
        "uuid",
        "user",
        "source",
        "source_url_link",
        "status",
        "error",
        "created_at",
        "updated_at",
        "presentation_link",
        "presentation_preview",
    )
    fieldsets = (
        (None, {
            "fields": (
                "uuid", "user", "source", "source_url_link", "status", "error",
                "created_at", "updated_at",
            ),
        }),
        ("Объект", {
            "fields": (
                "title", "address", "description",
                "price", "currency",
                "area_sqft", "area_sqm",
                "rooms", "bathrooms", "floor",
            ),
        }),
        ("Брокер", {
            "fields": ("broker_name", "broker_phone", "broker_email", "broker_agency"),
        }),
        ("Презентация", {
            "fields": ("presentation", "presentation_link", "presentation_preview"),
        }),
    )
    inlines = [ListingPhotoInline]
    show_full_result_count = False

    @admin.display(description="URL")
    def source_url_link(self, obj):
        if not obj.source_url:
            return "-"
        return format_html('<a href="{0}" target="_blank">{0}</a>', obj.source_url)

    @admin.display(description="PDF")
    def presentation_link(self, obj):
        if not obj.presentation:
            return "—"
        return format_html(
            '<a href="{0}" target="_blank" rel="noopener">📄 Открыть PDF</a>',
            obj.presentation.url,
        )

    @admin.display(description="Превью")
    def presentation_preview(self, obj):
        if not obj.presentation:
            return "—"
        return format_html(
            '<iframe src="{0}" '
            'style="width:100%;height:900px;border:1px solid #d3d6e0;'
            'border-radius:6px;background:#f3f4f8;"></iframe>',
            obj.presentation.url,
        )

    def has_add_permission(self, request):
        return False
