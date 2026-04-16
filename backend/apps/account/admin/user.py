from django.contrib import admin

from apps.account.models import User
from core.unfold_admin.admin import UnfoldModelAdmin
from core.unfold_admin.filters import AllValuesFieldListDropdownFilter


@admin.register(User)
class UserAdmin(UnfoldModelAdmin):
    fields = (
        "telegram_id",
        "telegram_name",
        "avatar",
        "full_name",
        "is_active",
        "created_at",
    )
    readonly_fields = (
        "telegram_id",
        "telegram_name",
        "avatar",
        "full_name",
        "created_at",
    )
    search_fields = ("telegram_name", "telegram_id", "first_name", "last_name")
    list_filter = (("is_active", AllValuesFieldListDropdownFilter),)
    list_display = (
        "telegram_id",
        "telegram_name",
        "full_name",
        "is_active",
        "created_at",
    )
    list_display_links = list_display
    show_full_result_count = False

    @admin.display(description="ФИО")
    def full_name(self, obj):
        return obj.full_name

    def has_add_permission(self, request):
        return False
