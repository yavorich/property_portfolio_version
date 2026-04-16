from django.contrib import admin
from django.utils.html import format_html

from apps.listings.models import Listing, ListingPhoto
from core.unfold_admin.admin import UnfoldModelAdmin, UnfoldTabularInline
from core.unfold_admin.filters import AllValuesFieldListDropdownFilter


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
    )
    inlines = [ListingPhotoInline]
    show_full_result_count = False

    @admin.display(description="URL")
    def source_url_link(self, obj):
        if not obj.source_url:
            return "-"
        return format_html('<a href="{0}" target="_blank">{0}</a>', obj.source_url)

    def has_add_permission(self, request):
        return False
