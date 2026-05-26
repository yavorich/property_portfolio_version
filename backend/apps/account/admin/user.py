from django.contrib import admin
from django.utils import timezone

from apps.account.models import User
from apps.listings.models import Listing
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
        "generations_used",
        "generations_reset_at",
    )
    readonly_fields = (
        "telegram_id",
        "telegram_name",
        "avatar",
        "full_name",
        "created_at",
        "generations_used",
        "generations_reset_at",
    )
    search_fields = ("telegram_name", "telegram_id", "first_name", "last_name")
    list_filter = (("is_active", AllValuesFieldListDropdownFilter),)
    list_display = (
        "telegram_id",
        "telegram_name",
        "full_name",
        "is_active",
        "generations_used",
        "created_at",
    )
    list_display_links = (
        "telegram_id",
        "telegram_name",
        "full_name",
    )
    show_full_result_count = False
    actions = ["reset_generation_counter"]

    @admin.display(description="ФИО")
    def full_name(self, obj):
        return obj.full_name

    @admin.display(description="Использовано генераций")
    def generations_used(self, obj):
        qs = Listing.objects.filter(user=obj, status=Listing.Status.DONE)
        if obj.generations_reset_at:
            qs = qs.filter(created_at__gt=obj.generations_reset_at)
        return qs.count()

    @admin.action(description="Сбросить счётчик генераций")
    def reset_generation_counter(self, request, queryset):
        now = timezone.now()
        updated = queryset.update(generations_reset_at=now)
        self.message_user(
            request,
            f"Счётчик генераций сброшен у {updated} пользователей.",
        )

    def has_add_permission(self, request):
        return False
